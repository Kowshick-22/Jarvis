"""Tests for the Foundry Local engine backend."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from openjarvis.core.registry import EngineRegistry
from openjarvis.core.types import Message, Role
from openjarvis.engine._base import EngineConnectionError
from openjarvis.engine.foundry_local import (
    FOUNDRY_LOCAL_FALLBACK_HOST,
    FoundryLocalEngine,
    check_tool_calling,
    classify_execution_provider,
    discover_foundry_host,
    parse_text_tool_calls,
    probe_execution_provider,
)

_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "time_range": {"type": "object"},
                "sources": {"type": "array"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
}


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {},
        },
    )


@pytest.fixture()
def engine() -> FoundryLocalEngine:
    EngineRegistry.register_value("foundry_local", FoundryLocalEngine)
    return FoundryLocalEngine(host="http://testhost:5273")


class TestFoundryLocalEngineBasics:
    def test_engine_id(self) -> None:
        assert FoundryLocalEngine.engine_id == "foundry_local"

    def test_api_prefix(self) -> None:
        assert FoundryLocalEngine._api_prefix == "/v1"

    def test_fallback_host(self) -> None:
        assert FOUNDRY_LOCAL_FALLBACK_HOST == "http://localhost:5273"

    def test_registry_registration(self) -> None:
        EngineRegistry.register_value("foundry_local", FoundryLocalEngine)
        assert EngineRegistry.get("foundry_local") is FoundryLocalEngine

    def test_env_var_overrides_default_host(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("FOUNDRY_LOCAL_HOST", "http://env-foundry:59959/v1")
        monkeypatch.delenv("FOUNDRY_LOCAL_ENDPOINT", raising=False)
        host = discover_foundry_host()
        assert host == "http://env-foundry:59959"

    def test_fallback_when_cli_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("FOUNDRY_LOCAL_HOST", raising=False)
        monkeypatch.delenv("FOUNDRY_LOCAL_ENDPOINT", raising=False)
        monkeypatch.setattr(
            "openjarvis.engine.foundry_local.shutil.which", lambda _: None
        )
        assert discover_foundry_host() == FOUNDRY_LOCAL_FALLBACK_HOST


class TestDiscoverFoundryHost:
    def test_parses_status_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FOUNDRY_LOCAL_HOST", raising=False)
        monkeypatch.delenv("FOUNDRY_LOCAL_ENDPOINT", raising=False)

        class _Result:
            stdout = "Service is running on http://127.0.0.1:59959/openai/status\n"
            stderr = ""

        monkeypatch.setattr(
            "openjarvis.engine.foundry_local.shutil.which", lambda _: "/usr/bin/foundry"
        )
        monkeypatch.setattr(
            "openjarvis.engine.foundry_local.subprocess.run",
            lambda *args, **kwargs: _Result(),
        )
        assert discover_foundry_host() == "http://127.0.0.1:59959"

    def test_parses_json_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FOUNDRY_LOCAL_HOST", raising=False)
        monkeypatch.delenv("FOUNDRY_LOCAL_ENDPOINT", raising=False)

        class _Result:
            stdout = '{"endpoint": "http://127.0.0.1:61234/v1"}'
            stderr = ""

        monkeypatch.setattr(
            "openjarvis.engine.foundry_local.shutil.which", lambda _: "/usr/bin/foundry"
        )
        monkeypatch.setattr(
            "openjarvis.engine.foundry_local.subprocess.run",
            lambda *args, **kwargs: _Result(),
        )
        assert discover_foundry_host() == "http://127.0.0.1:61234"

    def test_prefers_server_status_over_service(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FOUNDRY_LOCAL_HOST", raising=False)
        monkeypatch.delenv("FOUNDRY_LOCAL_ENDPOINT", raising=False)
        calls: list[list[str]] = []

        class _Result:
            def __init__(self, stdout: str = "") -> None:
                self.stdout = stdout
                self.stderr = ""

        def _run(args: list[str], **kwargs: object) -> _Result:
            calls.append(list(args))
            if args[1:3] == ["server", "status"]:
                return _Result("http://127.0.0.1:59959/v1")
            return _Result()

        monkeypatch.setattr(
            "openjarvis.engine.foundry_local.shutil.which", lambda _: "/usr/bin/foundry"
        )
        monkeypatch.setattr("openjarvis.engine.foundry_local.subprocess.run", _run)
        assert discover_foundry_host() == "http://127.0.0.1:59959"
        assert calls[0][1:3] == ["server", "status"]
        assert not any(call[1:3] == ["service", "status"] for call in calls)


class TestExecutionProvider:
    def test_cuda_is_not_fallback(self) -> None:
        name, fallback = classify_execution_provider("CUDAExecutionProvider")
        assert "CUDA" in name
        assert fallback is False

    def test_tensorrt_is_not_fallback(self) -> None:
        _, fallback = classify_execution_provider("NvTensorRTRTXExecutionProvider")
        assert fallback is False

    def test_cpu_is_fallback(self) -> None:
        name, fallback = classify_execution_provider("CPUExecutionProvider")
        assert "CPU" in name
        assert fallback is True

    def test_probe_reads_status_json(self) -> None:
        with respx.mock:
            respx.get("http://testhost:5273/openai/status").mock(
                return_value=httpx.Response(
                    200,
                    json={"executionProvider": "CUDAExecutionProvider"},
                )
            )
            info = probe_execution_provider("http://testhost:5273")
        assert info["execution_provider"] == "CUDAExecutionProvider"
        assert info["cpu_fallback"] is False


class TestFoundryGenerate:
    def test_generate_uses_v1_prefix(self, engine: FoundryLocalEngine) -> None:
        with respx.mock:
            respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {"content": "Hello!"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 5,
                            "completion_tokens": 2,
                            "total_tokens": 7,
                        },
                        "model": "Phi-4-mini-instruct",
                    },
                )
            )
            result = engine.generate(
                [Message(role=Role.USER, content="Hi")],
                model="Phi-4-mini-instruct",
            )
        assert result["content"] == "Hello!"

    def test_tools_400_does_not_retry(self, engine: FoundryLocalEngine) -> None:
        with respx.mock:
            respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=httpx.Response(400, text="tools not supported")
            )
            with pytest.raises(EngineConnectionError, match="rejected tool calling"):
                engine.generate(
                    [Message(role=Role.USER, content="Hi")],
                    model="Phi-4-mini-instruct",
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "ping",
                                "parameters": {"type": "object", "properties": {}},
                            },
                        }
                    ],
                )


class TestTextToolCalls:
    """Models whose tool-call markup Foundry doesn't parse return it as text;
    the engine recovers it so agents see a structured call."""

    def test_qwen_xml_format(self) -> None:
        content = (
            "<function=search>\n<parameter=query>\nProject Heron paused\n</parameter>\n"
            "<parameter=limit>\n20\n</parameter>\n</function>"
        )
        calls, remaining = parse_text_tool_calls(content, [_SEARCH_TOOL])
        assert len(calls) == 1
        assert calls[0]["name"] == "search"
        assert json.loads(calls[0]["arguments"]) == {
            "query": "Project Heron paused",
            "limit": 20,
        }
        assert remaining == ""

    def test_qwen_xml_inside_tool_call_wrapper(self) -> None:
        content = (
            "Let me search.\n<tool_call>\n<function=search>"
            "<parameter=query>Heron</parameter></function>\n</tool_call>"
        )
        calls, remaining = parse_text_tool_calls(content, [_SEARCH_TOOL])
        assert json.loads(calls[0]["arguments"]) == {"query": "Heron"}
        assert remaining == "Let me search."

    def test_hermes_json_format(self) -> None:
        content = (
            '<tool_call>{"name": "search", "arguments": '
            '{"query": "Heron", "sources": ["obsidian"]}}</tool_call>'
        )
        calls, _ = parse_text_tool_calls(content, [_SEARCH_TOOL])
        assert json.loads(calls[0]["arguments"]) == {
            "query": "Heron",
            "sources": ["obsidian"],
        }

    def test_python_call_format(self) -> None:
        content = (
            'search("Project Heron pause reason", '
            'time_range={"start": "2026-10-14", "end": "2026-10-14"}, '
            "sources=None, limit=1)"
        )
        calls, remaining = parse_text_tool_calls(content, [_SEARCH_TOOL])
        assert json.loads(calls[0]["arguments"]) == {
            "query": "Project Heron pause reason",
            "time_range": {"start": "2026-10-14", "end": "2026-10-14"},
            "limit": 1,
        }
        assert remaining == ""

    @pytest.mark.parametrize(
        "content",
        [
            "Project Heron is paused because the vendor missed deadlines.",
            "I will call search('Heron') to find out.",
            "search",
            'lookup("Heron")',
            "<function=lookup><parameter=q>x</parameter></function>",
            "",
        ],
    )
    def test_prose_and_unknown_tools_are_left_alone(self, content: str) -> None:
        calls, remaining = parse_text_tool_calls(content, [_SEARCH_TOOL])
        assert calls == []
        assert remaining == content

    def test_no_tools_offered_means_no_parsing(self) -> None:
        calls, _ = parse_text_tool_calls('search("Heron")', [])
        assert calls == []

    def test_generate_returns_recovered_calls(self, engine: FoundryLocalEngine) -> None:
        with respx.mock:
            respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=_chat_response(
                    "<function=search><parameter=query>Heron</parameter></function>"
                )
            )
            result = engine.generate(
                [Message(role=Role.USER, content="Why is Heron paused?")],
                model="qwen3.5-4b-generic-cpu:3",
                tools=[_SEARCH_TOOL],
            )
        assert result["tool_calls"][0]["name"] == "search"
        assert json.loads(result["tool_calls"][0]["arguments"]) == {"query": "Heron"}
        assert result["content"] == ""
        assert result["finish_reason"] == "tool_calls"

    def test_generate_keeps_plain_answers(self, engine: FoundryLocalEngine) -> None:
        with respx.mock:
            respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=_chat_response("Heron restarts after Falcon launches.")
            )
            result = engine.generate(
                [Message(role=Role.USER, content="Why is Heron paused?")],
                model="Phi-4-mini-instruct-generic-cpu:5",
                tools=[_SEARCH_TOOL],
            )
        assert "tool_calls" not in result
        assert result["content"] == "Heron restarts after Falcon launches."


class TestToolCallingProbe:
    def test_supported_when_tool_call_is_written_as_text(
        self, engine: FoundryLocalEngine
    ) -> None:
        with respx.mock:
            respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=_chat_response("<function=ping></function>")
            )
            result = check_tool_calling(engine, "qwen3.5-4b-generic-cpu:3")
        assert result["supported"] is True

    def test_supported_when_tool_calls_returned(
        self, engine: FoundryLocalEngine
    ) -> None:
        with respx.mock:
            respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "function": {
                                                "name": "ping",
                                                "arguments": "{}",
                                            },
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                )
            )
            result = check_tool_calling(engine, "Phi-4-mini-instruct")
        assert result["supported"] is True

    def test_probe_forces_tool_choice_required_not_auto(
        self, engine: FoundryLocalEngine
    ) -> None:
        """ "auto" lets a model decline a contrived no-op probe tool and
        read as incapable, even when it can emit tool_calls just fine (seen
        live with Phi-4-mini-instruct, which answered a real tool-shaped
        question wrong rather than calling a real calculator tool under
        "auto"). "required" tests capability, not default judgment."""
        with respx.mock:
            route = respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200, json={"choices": [{"message": {"tool_calls": []}}]}
                )
            )
            check_tool_calling(engine, "Phi-4-mini-instruct")
        sent = json.loads(route.calls.last.request.content)
        assert sent["tool_choice"] == "required"

    def test_unsupported_on_http_400(self, engine: FoundryLocalEngine) -> None:
        with respx.mock:
            respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=httpx.Response(400, text="no tools")
            )
            result = check_tool_calling(engine, "Phi-4-mini-instruct")
        assert result["supported"] is False
        assert "HTTP 400" in result["reason"]

    def test_probe_requests_enough_budget_for_reasoning_models(
        self, engine: FoundryLocalEngine
    ) -> None:
        """Reasoning models (Qwen3, DeepSeek-R1) spend tokens on
        reasoning_content before emitting tool_calls. A too-small max_tokens
        truncates them first and misreports tool calling as unsupported."""
        with respx.mock:
            route = respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200, json={"choices": [{"message": {"tool_calls": []}}]}
                )
            )
            check_tool_calling(engine, "qwen3-0.6b-generic-cpu")
        assert route.calls.last.request.read()
        sent = json.loads(route.calls.last.request.content)
        assert sent["max_tokens"] >= 512

    def test_unsupported_reason_distinguishes_truncation(
        self, engine: FoundryLocalEngine
    ) -> None:
        with respx.mock:
            respx.post("http://testhost:5273/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "finish_reason": "length",
                                "message": {"content": "", "reasoning_content": "…"},
                            }
                        ]
                    },
                )
            )
            result = check_tool_calling(engine, "qwen3-0.6b-generic-cpu")
        assert result["supported"] is False
        assert "truncated" in result["reason"]


class TestFoundryHealth:
    def test_health_true(self, engine: FoundryLocalEngine) -> None:
        with respx.mock:
            respx.get("http://testhost:5273/v1/models").mock(
                return_value=httpx.Response(200, json={"data": []})
            )
            assert engine.health() is True

    def test_list_models(self, engine: FoundryLocalEngine) -> None:
        with respx.mock:
            respx.get("http://testhost:5273/v1/models").mock(
                return_value=httpx.Response(
                    200,
                    json={"data": [{"id": "Phi-4-mini-instruct"}]},
                )
            )
            assert engine.list_models() == ["Phi-4-mini-instruct"]
