"""Timing behavior for microphone silence detection."""

from __future__ import annotations

import struct
import sys
from types import SimpleNamespace

from openjarvis.speech.voice_io import record_until_silence


class _FakeStream:
    def __init__(self, frames: list[bytes]) -> None:
        self.frames = iter(frames)
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

    def read(self, chunk: int):
        self.reads += 1
        return next(self.frames), False


def _install_audio(monkeypatch, stream: _FakeStream) -> None:
    fake_sd = SimpleNamespace(RawInputStream=lambda **kwargs: stream)
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)


def test_initial_silence_stops_at_startup_timeout(monkeypatch) -> None:
    silence = bytes(1024 * 2)
    stream = _FakeStream([silence] * 30)
    _install_audio(monkeypatch, stream)

    record_until_silence(
        sample_rate=1024,
        startup_silence_seconds=2,
        max_seconds=30,
    )

    assert stream.reads == 2


def test_post_speech_uses_normal_silence_window(monkeypatch) -> None:
    speech = struct.pack("1024h", *([1000] * 1024))
    silence = bytes(1024 * 2)
    stream = _FakeStream([speech, silence, silence, silence])
    _install_audio(monkeypatch, stream)

    record_until_silence(
        sample_rate=1024,
        silence_seconds=2,
        startup_silence_seconds=1,
        max_seconds=30,
    )

    assert stream.reads == 3


def test_post_speech_uses_env_var_silence_window(monkeypatch) -> None:
    speech = struct.pack("1024h", *([1000] * 1024))
    silence = bytes(1024 * 2)
    stream = _FakeStream([speech, silence, silence, silence])
    _install_audio(monkeypatch, stream)

    monkeypatch.setenv("JARVIS_SILENCE_SECONDS", "1")
    record_until_silence(
        sample_rate=1024,
        startup_silence_seconds=1,
        max_seconds=30,
    )

    # 1 speech chunk + 1 silence chunk = 2 reads
    assert stream.reads == 2


def test_silence_threshold_env_var_parsing(monkeypatch) -> None:
    from openjarvis.speech.voice_io import _get_silence_threshold

    monkeypatch.setenv("JARVIS_SILENCE_THRESHOLD", "1000")
    assert _get_silence_threshold() == 1000

    # Zero falls back to default 500
    monkeypatch.setenv("JARVIS_SILENCE_THRESHOLD", "0")
    assert _get_silence_threshold() == 500

    # Negative falls back to default 500
    monkeypatch.setenv("JARVIS_SILENCE_THRESHOLD", "-100")
    assert _get_silence_threshold() == 500

    # Invalid string falls back to default 500
    monkeypatch.setenv("JARVIS_SILENCE_THRESHOLD", "invalid")
    assert _get_silence_threshold() == 500

    # Unset falls back to default 500
    monkeypatch.delenv("JARVIS_SILENCE_THRESHOLD", raising=False)
    assert _get_silence_threshold() == 500


def test_silence_threshold_env_var_recording(monkeypatch) -> None:
    # Noise at 800 RMS (higher than 500 default, but lower than threshold 1000)
    noise = struct.pack("1024h", *([800] * 1024))
    speech = struct.pack("1024h", *([2000] * 1024))
    stream = _FakeStream([speech, noise, noise, noise])
    _install_audio(monkeypatch, stream)

    # Set threshold to 1000: noise (800) should now be counted as silence
    monkeypatch.setenv("JARVIS_SILENCE_THRESHOLD", "1000")
    monkeypatch.setenv("JARVIS_SILENCE_SECONDS", "1")
    record_until_silence(
        sample_rate=1024,
        startup_silence_seconds=1,
        max_seconds=30,
    )

    # 1 speech chunk + 1 silence chunk = 2 reads
    assert stream.reads == 2


