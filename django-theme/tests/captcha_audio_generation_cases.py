"""Bounded real executable probes, independent of optional speech binaries."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
import wave
from unittest.mock import Mock, patch

from captcha.conf import settings as captcha_settings
from captcha.models import CaptchaStore
from django.test import RequestFactory, TransactionTestCase, override_settings
from django.core.cache import cache

from nova_admin.captcha import captcha_audio, _discard_audio
from nova_admin.captcha_audio import AudioGenerationError, _run


class SyntheticAudioTools:
    def setUp(self):
        super().setUp()
        cache.clear()
        self.enterContext(override_settings(NOVA_ADMIN_CAPTCHA_AUDIO_KEY_LIMIT=1000, NOVA_ADMIN_CAPTCHA_AUDIO_IP_LIMIT=1000))
        self.directory = TemporaryDirectory(prefix="nova-audio-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.log = self.root / "pids.jsonl"
        self.request = RequestFactory().get("/audio/")
        self.row = CaptchaStore.objects.create(challenge="QWERT", response="qwert")

    def executable(self, *, fail=None, slow=None, delay=0):
        file = self.root / "speech-tool"
        file.write_text(f"#!{sys.executable}\n" + textwrap.dedent(f'''
            import json, os, sys, time, wave
            args = sys.argv[1:]
            stage = 'rate' if '--i' in args else 'noise' if '-n' in args else 'merge' if '-m' in args else 'flite'
            with open({str(self.log)!r}, 'a') as log:
                log.write(json.dumps({{'stage': stage, 'pid': os.getpid()}}) + '\\n')
            if stage == {fail!r}:
                print('PRIVATE_TOOL_OUTPUT', file=sys.stderr)
                print('PRIVATE_TOOL_OUTPUT')
                sys.exit(7)
            time.sleep(15 if stage == {slow!r} else {delay!r})
            if stage == 'rate':
                print('8000')
            else:
                destination = args[args.index('-o') + 1] if stage == 'flite' else args[args.index('-n') + 1] if stage == 'noise' else args[-1]
                with wave.open(destination, 'wb') as audio:
                    audio.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
                    audio.writeframes(b'\\0\\1' * 160)
        '''))
        file.chmod(0o700)
        return str(file)

    def audio(self, executable):
        with patch.object(captcha_settings, "CAPTCHA_FLITE_PATH", executable), patch.object(captcha_settings, "CAPTCHA_SOX_PATH", executable):
            return captcha_audio(self.request, self.row.hashkey)

    def assert_unavailable(self, response):
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, b"")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Expires", response)
        self.assertTrue(CaptchaStore.objects.filter(pk=self.row.pk).exists())


class CaptchaAudioGenerationTests(SyntheticAudioTools, TransactionTestCase):
    def test_all_four_stages_and_range_work_with_valid_output(self):
        response = self.audio(self.executable())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/wav")
        self.assertTrue(b"".join(response.streaming_content).startswith(b"RIFF"))
        _discard_audio(response)
        self.assertEqual([json.loads(line)["stage"] for line in self.log.read_text().splitlines()], ["flite", "rate", "noise", "merge"])

    def test_invalid_budgets_never_launch_a_process(self):
        for value in (0, -1, True, None, "invalid", float("inf"), float("nan")):
            with self.subTest(value=value), override_settings(NOVA_ADMIN_CAPTCHA_AUDIO_TIMEOUT=value), patch("nova_admin.captcha_audio.subprocess.Popen") as run:
                self.assert_unavailable(self.audio("/missing/tool"))
                run.assert_not_called()

    def test_missing_executable_returns_stable_uncached_503(self):
        self.assert_unavailable(self.audio(str(self.root / "missing")))

    def test_each_nonzero_stage_returns_503_without_tool_details(self):
        for stage in ("flite", "rate", "noise", "merge"):
            with self.subTest(stage=stage), self.assertNoLogs("nova_admin"):
                self.assert_unavailable(self.audio(self.executable(fail=stage)))

    @override_settings(NOVA_ADMIN_CAPTCHA_AUDIO_TIMEOUT=5)
    def test_real_slow_stage_is_killed_and_reaped(self):
        for stage in ("flite", "rate", "noise", "merge"):
            self.log.unlink(missing_ok=True)
            with self.subTest(stage=stage):
                self.assert_unavailable(self.audio(self.executable(slow=stage)))
                processes = [json.loads(line) for line in self.log.read_text().splitlines()]
                self.assertEqual(processes[-1]["stage"], stage)
                for process in processes:
                    with self.assertRaises(ProcessLookupError):
                        os.kill(process["pid"], 0)
                    with self.assertRaises(ChildProcessError):
                        os.waitpid(process["pid"], os.WNOHANG)

    def test_remaining_budget_decreases_between_commands(self):
        process = Mock(returncode=0, stdout=None)
        process.poll.return_value = 0
        with patch("nova_admin.captcha_audio.time.monotonic", side_effect=[0, 0.1, 0.25, 0.5, 0.6, 0.75]), patch("nova_admin.captcha_audio.subprocess.Popen", return_value=process) as spawn:
            _run(["synthetic"], 1)
            _run(["synthetic"], 1)
        waits = [call.kwargs["timeout"] for call in process.wait.call_args_list if "timeout" in call.kwargs]
        self.assertEqual(waits, [0.9, 0.2, 0.4, 0.2])
        for call in spawn.call_args_list:
            self.assertFalse(call.kwargs["shell"])

    def test_elapsed_budget_does_not_launch_next_command(self):
        with patch("nova_admin.captcha_audio.time.monotonic", return_value=2), patch("nova_admin.captcha_audio.subprocess.Popen") as run:
            with self.assertRaises(AudioGenerationError):
                _run(["synthetic"], 1)
            run.assert_not_called()

    def test_unreapable_killed_child_cannot_block_cleanup_forever(self):
        process = Mock(stdout=Mock())
        process.poll.return_value = None
        process.wait.side_effect = subprocess.TimeoutExpired('synthetic', 0.2)
        with patch('nova_admin.captcha_audio.subprocess.Popen', return_value=process), patch('nova_admin.captcha_audio._wait_process', side_effect=AudioGenerationError):
            with self.assertRaises(AudioGenerationError):
                _run(['synthetic'], float('inf'))
        process.kill.assert_called_once()
        process.wait.assert_called_once_with(timeout=0.2)
        process.stdout.close.assert_called_once()

    @override_settings(NOVA_ADMIN_CAPTCHA_AUDIO_TIMEOUT=1)
    def test_pipeline_shares_deadline_instead_of_restarting_each_stage(self):
        def spawn(argv, **kwargs):
            if "--i" not in argv:
                destination = argv[argv.index("-o") + 1] if "-o" in argv else argv[argv.index("-n") + 1] if "-n" in argv else argv[-1]
                with wave.open(destination, "wb") as audio:
                    audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                    audio.writeframes(b"\0\1" * 160)
            process = Mock(returncode=0, stdout=None)
            process.poll.return_value = 0
            process.argv = argv
            return process

        def completed(process, deadline, **kwargs):
            return b"8000\n" if "--i" in process.argv else b""

        with patch("nova_admin.captcha_audio.time.monotonic", side_effect=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 1.1]), patch("nova_admin.captcha_audio.subprocess.Popen", side_effect=spawn) as run, patch("nova_admin.captcha_audio._wait_process", side_effect=completed) as wait:
            self.assert_unavailable(self.audio("synthetic-tool"))
        self.assertEqual(run.call_count, 4)
        self.assertEqual([call.args[1] for call in wait.call_args_list], [1, 1, 1, 1])

    def test_zero_exit_with_invalid_wav_returns_503_then_normal_recovers(self):
        file = self.root / "bad-output"
        file.write_text(f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\nPath(sys.argv[-1]).write_bytes(b'not audio')\n")
        file.chmod(0o700)
        with patch.object(captcha_settings, "CAPTCHA_FLITE_PATH", str(file)), patch.object(captcha_settings, "CAPTCHA_SOX_PATH", None):
            self.assert_unavailable(captcha_audio(self.request, self.row.hashkey))
        response = self.audio(self.executable())
        self.assertEqual(response.status_code, 200)
        _discard_audio(response)
