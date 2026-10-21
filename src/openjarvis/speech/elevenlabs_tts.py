"""ElevenLabs text-to-speech backend.

Uses the ElevenLabs REST API, including voices from the ElevenLabs Voice
Library (add the voice to "My Voices" first, then use its voice ID).
Requires ELEVENLABS_API_KEY environment variable or config.
"""

from __future__ import annotations

import io
import os
import wave
from typing import List

import httpx

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

_ELEVENLABS_API_BASE = "https://api.elevenlabs.io"
_DEFAULT_MODEL = "eleven_multilingual_v2"
_PCM_SAMPLE_RATE = 24000
# ElevenLabs accepts voice_settings.speed only within this range.
_MIN_SPEED = 0.7
_MAX_SPEED = 1.2


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def _elevenlabs_synthesize(
    api_key: str,
    text: str,
    voice_id: str,
    model: str = _DEFAULT_MODEL,
    output_format: str = "mp3",
    speed: float = 1.0,
    language: str = "",
) -> bytes:
    """Call the ElevenLabs TTS API and return audio bytes (mp3 or wav)."""
    api_format = (
        f"pcm_{_PCM_SAMPLE_RATE}" if output_format == "wav" else "mp3_44100_128"
    )
    body: dict = {"text": text, "model_id": model}
    if speed != 1.0:
        body["voice_settings"] = {
            "speed": min(max(speed, _MIN_SPEED), _MAX_SPEED),
        }
    if language:
        body["language_code"] = language
    resp = httpx.post(
        f"{_ELEVENLABS_API_BASE}/v1/text-to-speech/{voice_id}",
        params={"output_format": api_format},
        headers={"xi-api-key": api_key},
        json=body,
        timeout=120.0,
    )
    resp.raise_for_status()
    if output_format == "wav":
        return _pcm_to_wav(resp.content, _PCM_SAMPLE_RATE)
    return resp.content


@TTSRegistry.register("elevenlabs")
class ElevenLabsTTSBackend(TTSBackend):
    """ElevenLabs TTS backend — natural multilingual voices."""

    backend_id = "elevenlabs"

    def __init__(
        self, *, api_key: str = "", model: str = "", language: str = ""
    ) -> None:
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self._model = model or os.environ.get("ELEVENLABS_MODEL", _DEFAULT_MODEL)
        self._language = language or os.environ.get("ELEVENLABS_LANGUAGE", "")

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "mp3",
        language: str = "",
    ) -> TTSResult:
        if not self._api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not set")
        if not voice_id:
            voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")
        if not voice_id:
            raise RuntimeError(
                "No ElevenLabs voice_id set (speech.voice_id or ELEVENLABS_VOICE_ID)"
            )
        if output_format not in ("mp3", "wav"):
            output_format = "mp3"

        audio = _elevenlabs_synthesize(
            self._api_key,
            text,
            voice_id=voice_id,
            model=self._model,
            output_format=output_format,
            speed=speed,
            language=language or self._language,
        )

        return TTSResult(
            audio=audio,
            format=output_format,
            voice_id=voice_id,
            sample_rate=_PCM_SAMPLE_RATE if output_format == "wav" else 44100,
            metadata={"backend": "elevenlabs", "model": self._model},
        )

    def available_voices(self) -> List[str]:
        if not self._api_key:
            return []
        resp = httpx.get(
            f"{_ELEVENLABS_API_BASE}/v1/voices",
            headers={"xi-api-key": self._api_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        return [v["voice_id"] for v in resp.json().get("voices", [])]

    def health(self) -> bool:
        return bool(self._api_key)
