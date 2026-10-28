"""Optional live-challenge guard tests; no speech binaries required."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from inspect import unwrap
from io import BytesIO
from unittest.mock import patch

from captcha.conf import settings as captcha_settings
from captcha.models import CaptchaStore
from captcha.views import captcha_audio as upstream_audio
from django.http import HttpResponse
from django.core.cache import cache
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import URLResolver, get_resolver, resolve, reverse
from django.utils import timezone
from ranged_response import RangedFileResponse

from nova_admin.captcha import captcha_audio, _audio_rate_allowed


class CaptchaAudioTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.request = RequestFactory().get("/audio/")
        self.row = CaptchaStore.objects.create(challenge="SYNTHETIC", response="synthetic")
        self.flite = patch.object(captcha_settings, "CAPTCHA_FLITE_PATH", "/synthetic/flite")
        self.flite.start()
        self.addCleanup(self.flite.stop)

    @override_settings(NOVA_ADMIN_CAPTCHA_AUDIO_KEY_LIMIT=2)
    def test_key_limit_blocks_forks_across_different_connection_ips(self):
        with patch('nova_admin.captcha._generate_audio', side_effect=lambda *args: HttpResponse()) as generate:
            codes = [captcha_audio(RequestFactory().get('/audio/', REMOTE_ADDR=f'192.0.2.{i}'), self.row.hashkey).status_code for i in range(4)]
        self.assertEqual(codes, [200, 200, 429, 429])
        self.assertEqual(generate.call_count, 2)

    @override_settings(NOVA_ADMIN_CAPTCHA_AUDIO_IP_LIMIT=2)
    def test_ip_limit_spans_keys_and_ignores_forwarded_headers(self):
        with patch('nova_admin.captcha._generate_audio', side_effect=lambda *args: HttpResponse()) as generate:
            for index in range(3):
                row = CaptchaStore.objects.create(challenge='SYNTHETIC', response='synthetic')
                request = RequestFactory().get('/audio/', HTTP_X_FORWARDED_FOR=f'192.0.2.{index}')
                response = captcha_audio(request, row.hashkey)
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response['Retry-After'], '60')
            self.assert_no_cache(response)
            self.assertEqual(generate.call_count, 2)

    @override_settings(NOVA_ADMIN_CAPTCHA_AUDIO_KEY_LIMIT=3, NOVA_ADMIN_CAPTCHA_AUDIO_IP_LIMIT=100)
    def test_atomic_counter_admits_only_limit_under_concurrency_and_resets_on_expiry(self):
        def attempt(_):
            return _audio_rate_allowed(self.request, self.row.hashkey)[0]
        with ThreadPoolExecutor(max_workers=16) as pool:
            self.assertEqual(sum(pool.map(attempt, range(40))), 3)
        cache.clear()  # Simulate both windows expiring.
        self.assertTrue(attempt(None))

    def test_failed_cache_or_repeated_expiry_never_start_generator(self):
        for failure in (RuntimeError('offline'), ValueError('expired')):
            with self.subTest(failure=type(failure).__name__), patch('nova_admin.captcha.caches') as caches, patch('nova_admin.captcha._generate_audio') as generate:
                backend = caches.__getitem__.return_value
                backend.add.return_value = False
                backend.incr.side_effect = failure
                self.assertEqual(captcha_audio(self.request, self.row.hashkey).status_code, 503)
                generate.assert_not_called()

    def assert_no_cache(self, response):
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("max-age=0", response["Cache-Control"])
        self.assertIn("Expires", response)

    def test_live_response_is_unchanged_and_does_not_consume(self):
        generated = HttpResponse(b"synthetic audio", content_type="audio/wav")
        with patch("nova_admin.captcha._generate_audio", return_value=generated) as generate:
            response = captcha_audio(self.request, self.row.hashkey)
        generate.assert_called_once_with(self.request, self.row.hashkey, "default")
        self.assertIs(response, generated)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/wav")
        self.assertTrue(CaptchaStore.objects.filter(pk=self.row.pk).exists())
        self.assert_no_cache(response)

    def test_range_response_and_bytes_are_preserved(self):
        request = RequestFactory().get("/audio/", HTTP_RANGE="bytes=2-5")
        file = BytesIO(b"0123456789")
        generated = RangedFileResponse(request, file, content_type="audio/wav")
        with patch("nova_admin.captcha._generate_audio", return_value=generated):
            response = captcha_audio(request, self.row.hashkey)
        self.assertIs(response, generated)
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Content-Range"], "bytes 2-5/10")
        self.assertEqual(b"".join(response.streaming_content), b"2345")
        self.assert_no_cache(response)
        response.close()
        file.close()

    def test_expired_exact_deadline_missing_and_invalid_never_generate(self):
        now = timezone.now()
        for key, expiration in (
            (self.row.hashkey, now - timedelta(seconds=1)),
            (self.row.hashkey, now),
            ("0" * 40, now + timedelta(minutes=1)),
            ("invalid", now + timedelta(minutes=1)),
        ):
            with self.subTest(key=key, expiration=expiration):
                CaptchaStore.objects.filter(pk=self.row.pk).update(expiration=expiration)
                with patch("nova_admin.captcha.timezone") as clock, patch("nova_admin.captcha._generate_audio") as generate:
                    clock.now.return_value = now
                    response = captcha_audio(self.request, key)
                self.assertEqual(response.status_code, 410)
                generate.assert_not_called()
                self.assertTrue(CaptchaStore.objects.filter(pk=self.row.pk).exists())
                self.assert_no_cache(response)

    def test_disabled_audio_does_not_generate(self):
        with patch.object(captcha_settings, "CAPTCHA_FLITE_PATH", None), patch("nova_admin.captcha._generate_audio") as generate:
            response = captcha_audio(self.request, self.row.hashkey)
        self.assertEqual(response.status_code, 404)
        generate.assert_not_called()

    def test_both_checks_use_write_database(self):
        with patch("nova_admin.captcha.router.db_for_write", return_value="default") as write, patch("nova_admin.captcha.router.db_for_read", side_effect=AssertionError("read replica")), patch("nova_admin.captcha._generate_audio", return_value=HttpResponse()) as generate:
            response = captcha_audio(self.request, self.row.hashkey)
        self.assertEqual(response.status_code, 200)
        write.assert_called_once_with(CaptchaStore)
        generate.assert_called_once()

    def test_expiry_or_consumption_during_generation_closes_real_ranged_file(self):
        for consume in (False, True):
            with self.subTest(consume=consume):
                row = CaptchaStore.objects.create(challenge="SYNTHETIC", response="synthetic")
                file = BytesIO(b"synthetic wav")
                generated = RangedFileResponse(self.request, file, content_type="audio/wav")

                def generate(request, key, alias):
                    rows = CaptchaStore.objects.filter(pk=row.pk)
                    if consume:
                        rows.delete()
                    else:
                        rows.update(expiration=timezone.now() - timedelta(seconds=1))
                    return generated

                with patch("nova_admin.captcha._generate_audio", side_effect=generate):
                    response = captcha_audio(self.request, row.hashkey)
                self.assertEqual(response.status_code, 410)
                self.assertTrue(generated.closed)
                self.assertTrue(file.closed)
                self.assertEqual(CaptchaStore.objects.filter(pk=row.pk).exists(), not consume)
                self.assert_no_cache(response)

    def test_failed_recheck_closes_file_and_propagates_database_error(self):
        file = BytesIO(b"synthetic wav")
        generated = RangedFileResponse(self.request, file, content_type="audio/wav")
        with patch("nova_admin.captcha._audio_available", side_effect=[True, RuntimeError("database unavailable")]), patch("nova_admin.captcha._generate_audio", return_value=generated):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                captcha_audio(self.request, self.row.hashkey)
        self.assertTrue(generated.closed)
        self.assertTrue(file.closed)


class CaptchaAudioURLTests(TestCase):
    def test_demo_mounts_have_one_guarded_audio_route_and_preserve_refresh(self):
        # Axes' own settings suite verifies its wrapper separately.
        for urlconf, prefix in (("config.captcha_urls", "/admin/_captcha/"), ("config.compose_urls", "/_captcha/")):
            with self.subTest(urlconf=urlconf), override_settings(ROOT_URLCONF=urlconf, NOVA_EXAMPLE_CAPTCHA=True):
                url = reverse("captcha-audio", kwargs={"key": "a" * 40})
                self.assertTrue(url.startswith(prefix))
                self.assertIs(unwrap(resolve(url).func), unwrap(captcha_audio))
                self.assertTrue(reverse("captcha-refresh").startswith(prefix))
                callbacks = []

                def visit(patterns):
                    for pattern in patterns:
                        if isinstance(pattern, URLResolver):
                            visit(pattern.url_patterns)
                        elif pattern.name == "captcha-audio" or unwrap(pattern.callback) is upstream_audio:
                            callbacks.append(unwrap(pattern.callback))

                visit(get_resolver().url_patterns)
                self.assertEqual(callbacks, [unwrap(captcha_audio)])

    @override_settings(ROOT_URLCONF="config.captcha_urls")
    def test_expired_route_returns_uncached_410_without_generation(self):
        row = CaptchaStore.objects.create(challenge="SYNTHETIC", response="synthetic", expiration=timezone.now() - timedelta(seconds=1))
        with patch.object(captcha_settings, "CAPTCHA_FLITE_PATH", "/synthetic/flite"), patch("nova_admin.captcha._generate_audio") as generate:
            response = self.client.get(reverse("captcha-audio", kwargs={"key": row.hashkey}))
        self.assertEqual(response.status_code, 410)
        self.assertIn("no-store", response["Cache-Control"])
        generate.assert_not_called()
