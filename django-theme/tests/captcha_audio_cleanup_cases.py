"""Explicit per-request file ownership, including interrupts and streaming."""
from concurrent.futures import ThreadPoolExecutor
import gc
import io
import os
from pathlib import Path
from threading import Barrier
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
import wave

from captcha.conf import settings as cap
from django.db import close_old_connections
from django.test import TransactionTestCase

from nova_admin import captcha_audio as generator
from nova_admin.captcha import captcha_audio
from .captcha_audio_generation_cases import SyntheticAudioTools


class CaptchaAudioCleanupTests(SyntheticAudioTools, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.audio_root = self.root / "audio"
        self.audio_root.mkdir()
        self.sentinel = self.audio_root / "other-request-sentinel"
        self.sentinel.write_text("keep")
        self.files = []
        self.directories = []

        def directory(**kwargs):
            path = tempfile.mkdtemp(dir=self.audio_root, **kwargs)
            self.directories.append(Path(path))
            return path

        def file():
            opened = tempfile.TemporaryFile(dir=self.audio_root)
            self.files.append(opened)
            return opened

        self.resources = SimpleNamespace(mkdtemp=directory, TemporaryFile=file)
        self.resource_patch = patch.object(generator, "tempfile", self.resources)
        self.resource_patch.start()
        self.addCleanup(self.resource_patch.stop)

    def assert_clean(self):
        self.assertTrue(all(not path.exists() for path in self.directories))
        self.assertTrue(all(file.closed for file in self.files))
        self.assertEqual(self.sentinel.read_text(), "keep")

    def test_retained_responses_close_unread_partial_range_and_repeatedly_without_gc(self):
        enabled = gc.isenabled()
        gc.disable()
        retained = []
        iterators = []
        try:
            for mode in ("unread", "partial", "range", "exhausted") * 2:
                if mode == "range":
                    self.request.META["HTTP_RANGE"] = "bytes=0-31"
                else:
                    self.request.META.pop("HTTP_RANGE", None)
                response = self.audio(self.executable())
                retained.append(response)
                self.assertEqual(response.status_code, 206 if mode == "range" else 200)
                if mode in ("partial", "range"):
                    iterator = iter(response.streaming_content)
                    iterators.append(iterator)
                    next(iterator)
                elif mode == "exhausted":
                    b"".join(response.streaming_content)
                    self.assertTrue(response._audio_file.closed)
                response.close()
                response.close()
                self.assert_clean()
            self.assertEqual(len(retained), 8)
        finally:
            for response in retained:
                response.close()
            for iterator in iterators:
                iterator.close()
            if enabled:
                gc.enable()

    def test_partial_iterator_close_releases_underlying_file(self):
        response = self.audio(self.executable())
        iterator = iter(response.streaming_content)
        next(iterator)
        iterator.close()
        self.assertTrue(response._audio_file.closed)
        response.close()
        self.assert_clean()

    def test_stream_read_exception_or_interrupt_closes_file(self):
        for error in (OSError("read failed"), KeyboardInterrupt(), SystemExit()):
            with self.subTest(error=type(error).__name__):
                response = self.audio(self.executable())
                file = response._audio_file
                class BrokenReader:
                    def seek(self, *args):
                        return file.seek(*args)
                    def read(self, *args):
                        raise error
                response.ranged_file.f = BrokenReader()
                with self.assertRaises(type(error)):
                    next(iter(response.streaming_content))
                response.close()
                self.assert_clean()

    def test_generation_each_stage_interrupt_cleans_only_own_directory(self):
        run = generator._run
        for target in range(4):
            count = 0
            def interrupted(*args, **kwargs):
                nonlocal count
                index = count
                count += 1
                if index == target:
                    raise KeyboardInterrupt()
                return run(*args, **kwargs)
            with self.subTest(stage=target), patch.object(generator, "_run", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
                self.audio(self.executable())
            self.assert_clean()

    def test_directory_and_response_file_creation_failures(self):
        for name in ("mkdtemp", "TemporaryFile"):
            for error in (OSError("create failed"), KeyboardInterrupt(), SystemExit()):
                with self.subTest(resource=name, error=type(error).__name__), patch.object(self.resources, name, side_effect=error):
                    if isinstance(error, OSError):
                        self.assert_unavailable(self.audio(self.executable()))
                    else:
                        with self.assertRaises(type(error)):
                            self.audio(self.executable())
                self.assert_clean()

    def test_process_interruption_reaps_child_and_closes_pipe(self):
        spawn = generator.subprocess.Popen
        for error in (KeyboardInterrupt(), SystemExit()):
            processes = []
            def started(*args, **kwargs):
                process = spawn(*args, **kwargs)
                processes.append(process)
                return process
            with self.subTest(error=type(error).__name__), patch.object(generator.subprocess, "Popen", side_effect=started), patch.object(generator, "_wait_process", side_effect=error), self.assertRaises(type(error)):
                generator._run([self.executable(slow="flite"), "-o", str(self.root / "interrupted.wav")], time.monotonic() + 5, output=True)
            self.assertEqual(len(processes), 1)
            process = processes[0]
            self.assertTrue(process.stdout.closed)
            with self.assertRaises(ProcessLookupError):
                os.kill(process.pid, 0)
            with self.assertRaises(ChildProcessError):
                os.waitpid(process.pid, os.WNOHANG)

    def test_read_copy_and_response_construction_failures_and_interrupts(self):
        for name in ("_wav_bytes", "_copy_audio", "CaptchaAudioResponse"):
            for error in (OSError("IO failed"), KeyboardInterrupt(), SystemExit()):
                with self.subTest(stage=name, error=type(error).__name__), patch.object(generator, name, side_effect=error):
                    if isinstance(error, OSError):
                        self.assert_unavailable(self.audio(self.executable()))
                    else:
                        with self.assertRaises(type(error)):
                            self.audio(self.executable())
                self.assert_clean()

    def test_short_copy_is_503_and_closes_file(self):
        create = self.resources.TemporaryFile
        def short_file():
            file = create()
            return SimpleNamespace(write=lambda block: 0, close=file.close)
        with patch.object(self.resources, "TemporaryFile", side_effect=short_file):
            self.assert_unavailable(self.audio(self.executable()))
        self.assert_clean()

    def test_cleanup_failure_after_response_created_closes_file_and_retries_own_directory(self):
        remove = generator.shutil.rmtree
        for error in (OSError("remove failed"), KeyboardInterrupt(), SystemExit()):
            count = 0
            def failed_once(path):
                nonlocal count
                count += 1
                if count == 1:
                    raise error
                return remove(path)
            with self.subTest(error=type(error).__name__), patch.object(generator.shutil, "rmtree", side_effect=failed_once):
                if isinstance(error, OSError):
                    self.assert_unavailable(self.audio(self.executable()))
                else:
                    with self.assertRaises(type(error)):
                        self.audio(self.executable())
            self.assertEqual(count, 2)
            self.assert_clean()

    def test_postcheck_failure_or_interrupt_closes_generated_file(self):
        for error in (RuntimeError("database unavailable"), KeyboardInterrupt(), SystemExit()):
            with self.subTest(error=type(error).__name__), patch("nova_admin.captcha._audio_available", side_effect=[True, error]), self.assertRaises(type(error)):
                self.audio(self.executable())
            self.assert_clean()

    def test_persistent_os_cleanup_denial_is_503_and_closes_file(self):
        remove = generator.shutil.rmtree
        with patch.object(generator.shutil, "rmtree", side_effect=PermissionError("persistent denial")):
            self.assert_unavailable(self.audio(self.executable()))
        directory = self.directories[-1]
        try:
            self.assertTrue(directory.exists())
            self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(file.closed for file in self.files))
            self.assertEqual(self.sentinel.read_text(), "keep")
        finally:
            # The OS-denial boundary is explicit, never represented as no residue.
            remove(directory)
        self.assert_clean()

    def test_invalid_empty_truncated_and_oversize_wavs_are_503(self):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as audio:
            audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0\1" * 160)
        valid = buffer.getvalue()
        for data in (b"", b"not wav", valid[:-1], b"x" * (generator.MAX_WAV_BYTES + 1)):
            def output(argv, *args, **kwargs):
                Path(argv[-1]).write_bytes(data)
            with self.subTest(bytes=len(data)), patch.object(generator, "_run", side_effect=output), patch.object(cap, "CAPTCHA_FLITE_PATH", "synthetic"), patch.object(cap, "CAPTCHA_SOX_PATH", None):
                self.assert_unavailable(captcha_audio(self.request, self.row.hashkey))
            self.assert_clean()

    def test_tool_output_overflow_is_503(self):
        executable = self.executable()
        path = Path(executable)
        path.write_text(path.read_text().replace("print('8000')", "print('x' * 1000000)"))
        self.assert_unavailable(self.audio(executable))
        self.assert_clean()

    def test_same_key_concurrent_requests_have_separate_directories(self):
        barrier = Barrier(2)
        run = generator._run
        def overlap(argv, *args, **kwargs):
            if "-o" in argv:
                barrier.wait(timeout=10)
            return run(argv, *args, **kwargs)
        def generate():
            close_old_connections()
            try:
                return captcha_audio(self.request, self.row.hashkey)
            finally:
                close_old_connections()
        executable = self.executable()
        with patch.object(cap, "CAPTCHA_FLITE_PATH", executable), patch.object(cap, "CAPTCHA_SOX_PATH", executable), patch.object(generator, "_run", side_effect=overlap), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(generate) for _ in range(2)]
            responses = [future.result(timeout=20) for future in futures]
        try:
            self.assertEqual([response.status_code for response in responses], [200, 200])
            self.assertEqual(len(set(self.directories)), 2)
        finally:
            for response in responses:
                response.close()
        self.assert_clean()

    def test_math_and_flite_only_preserve_text_and_valid_audio(self):
        type(self.row).objects.filter(pk=self.row.pk).update(challenge="3+4")
        run = generator._run
        spoken = []
        def record(argv, *args, **kwargs):
            if "-t" in argv:
                spoken.append(argv[argv.index("-t") + 1])
            return run(argv, *args, **kwargs)
        with patch.object(cap, "CAPTCHA_CHALLENGE_FUNCT", "captcha.helpers.math_challenge"), patch.object(cap, "CAPTCHA_FLITE_PATH", self.executable()), patch.object(cap, "CAPTCHA_SOX_PATH", None), patch.object(generator, "_run", side_effect=record):
            response = captcha_audio(self.request, self.row.hashkey)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(spoken, ["3plus4"])
        response.close()
        self.assert_clean()
