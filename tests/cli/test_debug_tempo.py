"""Unit tests for JARVIS_DEBUG_TEMPO timing logs in voice chat."""

from __future__ import annotations

import io
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from rich.console import Console

from openjarvis.cli._voice_chat import VoiceSession, record_voice, speak
from openjarvis.core.config import JarvisConfig


class TestDebugTempo(unittest.TestCase):
    """Test timing logs per stage controlled by JARVIS_DEBUG_TEMPO env var."""

    def setUp(self):
        self.output = io.StringIO()
        self.console = Console(file=self.output, force_terminal=False)

    def test_record_voice_timing_logs_when_enabled(self):
        backend = MagicMock()
        backend.transcribe.return_value = SimpleNamespace(text="olá jarvis")
        session = VoiceSession(JarvisConfig())

        with (
            patch.dict(os.environ, {"JARVIS_DEBUG_TEMPO": "1"}),
            patch("openjarvis.speech._discovery.get_speech_backend", return_value=backend),
            patch("openjarvis.speech.voice_io.record_until_silence", return_value=b"fake_wav"),
        ):
            result = record_voice(self.console, session)

        rendered = self.output.getvalue()
        self.assertEqual(result, "olá jarvis")
        self.assertIn("[TEMPO] Gravação até o silêncio:", rendered)
        self.assertIn("[TEMPO] Transcrição:", rendered)

    def test_record_voice_timing_logs_hidden_by_default(self):
        backend = MagicMock()
        backend.transcribe.return_value = SimpleNamespace(text="olá jarvis")
        session = VoiceSession(JarvisConfig())

        # Ensure env var is absent
        env = dict(os.environ)
        env.pop("JARVIS_DEBUG_TEMPO", None)
        with (
            patch.dict(os.environ, env, clear=True),
            patch("openjarvis.speech._discovery.get_speech_backend", return_value=backend),
            patch("openjarvis.speech.voice_io.record_until_silence", return_value=b"fake_wav"),
        ):
            result = record_voice(self.console, session)

        rendered = self.output.getvalue()
        self.assertEqual(result, "olá jarvis")
        self.assertNotIn("[TEMPO]", rendered)

    def test_speak_timing_log_when_enabled(self):
        backend = MagicMock()
        backend.synthesize.return_value = SimpleNamespace(audio=b"", sample_rate=24000)
        session = VoiceSession(JarvisConfig())

        with (
            patch.dict(os.environ, {"JARVIS_DEBUG_TEMPO": "1"}),
            patch.object(session, "get_tts_backend", side_effect=[backend, None]),
            patch.object(session, "voice_for_backend", return_value=("default", 1.0)),
        ):
            speak("Tudo bem com você?", self.console, session)

        rendered = self.output.getvalue()
        self.assertIn("[TEMPO] Síntese de voz:", rendered)

    def test_speak_timing_log_hidden_by_default(self):
        backend = MagicMock()
        backend.synthesize.return_value = SimpleNamespace(audio=b"", sample_rate=24000)
        session = VoiceSession(JarvisConfig())

        env = dict(os.environ)
        env.pop("JARVIS_DEBUG_TEMPO", None)
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(session, "get_tts_backend", side_effect=[backend, None]),
            patch.object(session, "voice_for_backend", return_value=("default", 1.0)),
        ):
            speak("Tudo bem com você?", self.console, session)

        rendered = self.output.getvalue()
        self.assertNotIn("[TEMPO]", rendered)

    def test_agent_response_timing_when_enabled(self):
        from click.testing import CliRunner
        from openjarvis.cli.chat_cmd import chat

        engine = MagicMock()
        engine.engine_id = "mock"
        engine.generate.return_value = {"content": "Olá, tudo bem!"}
        config = JarvisConfig()
        config.intelligence.default_model = "test-model"

        with (
            patch.dict(os.environ, {"JARVIS_DEBUG_TEMPO": "1"}),
            patch("openjarvis.cli.chat_cmd.load_config", return_value=config),
            patch("openjarvis.engine.get_engine", return_value=("mock", engine)),
            patch("openjarvis.intelligence.register_builtin_models"),
        ):
            result = CliRunner().invoke(
                chat,
                ["--model", "test-model"],
                input="Olá\n/quit\n",
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("[TEMPO] Resposta do agente:", result.output)

    def test_agent_response_timing_hidden_by_default(self):
        from click.testing import CliRunner
        from openjarvis.cli.chat_cmd import chat

        engine = MagicMock()
        engine.engine_id = "mock"
        engine.generate.return_value = {"content": "Olá, tudo bem!"}
        config = JarvisConfig()
        config.intelligence.default_model = "test-model"

        env = dict(os.environ)
        env.pop("JARVIS_DEBUG_TEMPO", None)
        with (
            patch.dict(os.environ, env, clear=True),
            patch("openjarvis.cli.chat_cmd.load_config", return_value=config),
            patch("openjarvis.engine.get_engine", return_value=("mock", engine)),
            patch("openjarvis.intelligence.register_builtin_models"),
        ):
            result = CliRunner().invoke(
                chat,
                ["--model", "test-model"],
                input="Olá\n/quit\n",
            )

        self.assertEqual(result.exit_code, 0)
        self.assertNotIn("[TEMPO]", result.output)


class TestSilenceThreshold(unittest.TestCase):
    """Test JARVIS_SILENCE_THRESHOLD environment variable handling."""

    def test_threshold_parsing(self):
        from openjarvis.speech.voice_io import _get_silence_threshold

        with patch.dict(os.environ, {"JARVIS_SILENCE_THRESHOLD": "1000"}):
            self.assertEqual(_get_silence_threshold(), 1000)

        with patch.dict(os.environ, {"JARVIS_SILENCE_THRESHOLD": "0"}):
            self.assertEqual(_get_silence_threshold(), 500)

        with patch.dict(os.environ, {"JARVIS_SILENCE_THRESHOLD": "-100"}):
            self.assertEqual(_get_silence_threshold(), 500)

        with patch.dict(os.environ, {"JARVIS_SILENCE_THRESHOLD": "abc"}):
            self.assertEqual(_get_silence_threshold(), 500)

        env = dict(os.environ)
        env.pop("JARVIS_SILENCE_THRESHOLD", None)
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(_get_silence_threshold(), 500)


if __name__ == "__main__":
    unittest.main()

