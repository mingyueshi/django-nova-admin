"""Optional local audio generation with bounded IO and explicit ownership."""
import io
import math
import os
from pathlib import Path
import selectors
import shutil
import stat
import subprocess
import tempfile
import time
import wave

from captcha.conf import settings as captcha_settings
from captcha.models import CaptchaStore
from django.conf import settings
from django.utils import timezone
from ranged_response import RangedFileResponse


MAX_WAV_BYTES = 2 * 1024 * 1024
MAX_TOOL_OUTPUT_BYTES = 128
COPY_BLOCK_BYTES = 64 * 1024


class AudioGenerationError(Exception):
    """An unavailable generator; no command, answer or tool output attached."""


class AudioChallengeUnavailable(Exception):
    pass


class CaptchaAudioResponse(RangedFileResponse):
    def __init__(self, request, file, **kwargs):
        self._audio_file = file
        super().__init__(request, file, **kwargs)

    @property
    def streaming_content(self):
        content = super().streaming_content
        file = self._audio_file
        if self.is_async:
            async def stream():
                try:
                    async for chunk in content:
                        yield chunk
                finally:
                    file.close()
        else:
            def stream():
                try:
                    yield from content
                finally:
                    file.close()
        return stream()

    @streaming_content.setter
    def streaming_content(self, value):
        self._set_streaming_content(value)

    def close(self):
        try:
            super().close()
        finally:
            # ranged-response's iterator does not forward close to its file.
            self._audio_file.close()


def _deadline():
    value = getattr(settings, "NOVA_ADMIN_CAPTCHA_AUDIO_TIMEOUT", 10)
    try:
        seconds = float(value)
    except (TypeError, ValueError, OverflowError):
        raise AudioGenerationError from None
    if isinstance(value, bool) or not math.isfinite(seconds) or seconds <= 0:
        raise AudioGenerationError
    return time.monotonic() + seconds


def _remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise AudioGenerationError
    return seconds


def _wait_process(process, deadline, *, output):
    data = bytearray()
    if output:
        # One small pipe, no background reader or unbounded communicate buffer.
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                events = selector.select(_remaining(deadline))
                if not events:
                    raise AudioGenerationError
                block = os.read(process.stdout.fileno(), MAX_TOOL_OUTPUT_BYTES + 1 - len(data))
                if not block:
                    break
                data.extend(block)
                if len(data) > MAX_TOOL_OUTPUT_BYTES:
                    raise AudioGenerationError
    process.wait(timeout=_remaining(deadline))
    if process.returncode != 0:
        raise AudioGenerationError
    return bytes(data)


def _run(argv, deadline, *, output=False):
    _remaining(deadline)
    process = None
    try:
        process = subprocess.Popen(
            argv, shell=False, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE if output else subprocess.DEVNULL,
        )
        result = _wait_process(process, deadline, output=output)
        _remaining(deadline)
        return result
    except (OSError, ValueError, OverflowError, subprocess.SubprocessError):
        raise AudioGenerationError from None
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    process.kill()
            finally:
                try:
                    # Also reap on BaseException or output overflow. This owns
                    # the direct child only, not an arbitrary process tree.
                    process.wait()
                finally:
                    if process.stdout is not None:
                        process.stdout.close()


def _file_size(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_WAV_BYTES:
        raise AudioGenerationError


def _wav_bytes(path):
    _file_size(path)
    with path.open("rb") as source:
        data = source.read(MAX_WAV_BYTES + 1)
    if len(data) > MAX_WAV_BYTES or len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AudioGenerationError
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise AudioGenerationError
    with wave.open(io.BytesIO(data), "rb") as audio:
        expected = audio.getnframes() * audio.getnchannels() * audio.getsampwidth()
        if audio.getcomptype() != "NONE" or not 0 < expected <= MAX_WAV_BYTES:
            raise AudioGenerationError
        if len(audio.readframes(audio.getnframes())) != expected:
            raise AudioGenerationError
    return data


def _copy_audio(data, file):
    for offset in range(0, len(data), COPY_BLOCK_BYTES):
        block = data[offset:offset + COPY_BLOCK_BYTES]
        if file.write(block) != len(block):
            raise AudioGenerationError
    file.seek(0)


def _remove_directory(directory):
    try:
        shutil.rmtree(directory)
    except BaseException:
        # One bounded recovery attempt, only for the exact directory we made.
        # A permanent OS denial cannot be promised away or solved by GC.
        try:
            shutil.rmtree(directory)
        except OSError:
            pass
        raise


def generate_audio(request, key, alias):
    deadline = _deadline()
    challenge = CaptchaStore.objects.using(alias).filter(
        hashkey=key, expiration__gt=timezone.now(),
    ).values_list("challenge", flat=True).first()
    if challenge is None:
        raise AudioChallengeUnavailable
    if captcha_settings.CAPTCHA_CHALLENGE_FUNCT == "captcha.helpers.math_challenge":
        text = challenge.replace("*", "times").replace("-", "minus").replace("+", "plus")
    else:
        text = ", ".join(challenge)
    file = response = None
    try:
        directory = Path(tempfile.mkdtemp(prefix="nova-captcha-audio-"))
        try:
            source = directory / "source.wav"
            _run([captcha_settings.CAPTCHA_FLITE_PATH, "-t", text, "-o", str(source)], deadline)
            _file_size(source)
            if captcha_settings.CAPTCHA_SOX_PATH:
                sox = captcha_settings.CAPTCHA_SOX_PATH
                rate = _run([sox, "--i", "-r", str(source)], deadline, output=True).decode("ascii").strip()
                if not rate or not math.isfinite(float(rate)) or float(rate) <= 0:
                    raise AudioGenerationError
                noise = directory / "noise.wav"
                merged = directory / "merged.wav"
                _run([sox, "-r", rate, "-n", str(noise), "synth", "2", "brownnoise", "gain", "-15"], deadline)
                _file_size(noise)
                _run([sox, "-m", str(noise), str(source), "-t", "wavpcm", "-b", "16", str(merged)], deadline)
                source = merged
            data = _wav_bytes(source)
            file = tempfile.TemporaryFile()
            _copy_audio(data, file)
            response = CaptchaAudioResponse(request, file, content_type="audio/wav")
            response["Content-Disposition"] = f'attachment; filename="{key}.wav"'
        finally:
            _remove_directory(directory)
        return response
    except BaseException as error:
        try:
            if response is not None:
                response.close()
        finally:
            if file is not None:
                file.close()
        if isinstance(error, (OSError, ValueError, UnicodeError, wave.Error, EOFError)):
            raise AudioGenerationError from None
        raise
