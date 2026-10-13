---
title: WinUI ARM64 acceptance
description: Feature checklist, performance table, and how to measure on Surface Laptop Ultra
---

# WinUI ARM64 acceptance

Primary target: Surface Laptop Ultra (NVIDIA RTX Spark N1X, Windows 11 26H1, ARM64).  
**This run was measured on a Parallels ARM64 guest (Mac M3, ~6 GB RAM, Windows 11 26H2 build 26300).** Ultra rows that need GPU/NPU evidence stay blank for upstream feedback.

Script: [`windows/scripts/measure-performance.ps1`](../../windows/scripts/measure-performance.ps1)

```powershell
# After OpenJarvis backend is healthy:
.\windows\scripts\measure-performance.ps1 -Model "Phi-4-mini-instruct-generic-cpu:5"
```

## Performance

Named model: **Phi-4-mini-instruct-generic-cpu:5** (Foundry catalog id; CPU variant on Parallels).

| Metric | Result | How measured |
|--------|--------|--------------|
| Resolved model id | Phi-4-mini-instruct-generic-cpu (serve) / `:5` for chat | `/v1/info` + successful SSE |
| Execution provider | CPUExecutionProvider (inferred from `*-generic-cpu`; Foundry status probe returned `unknown`) | `/v1/info` + catalog id |
| CPU fallback | yes | CPU catalog id on Parallels (no GPU) |
| Cold start (ms) | 1354 | Process start until `GET /health` returns 200 (server already warm) |
| Time to first token (ms) | 17152 | First SSE `choices[0].delta.content` via measure script |
| Tokens per second | _not reported by stream usage on this run_ | Manual chat returned `OpenJarvis says hello!` in ~24s for a short reply |
| Working set — OpenJarvis.exe (MB) | ~222 | Debug unpackaged build, idle on Chat (2026-10-12). Window stayed up. |
| Working set — jarvis / python (MB) | ~25 (python) | Process working set |
| Working set — Foundry (MB) | Foundry server PID active | `foundry server status` |

## Feature checklist

| Item | Pass? | Notes |
|------|-------|-------|
| ARM64 installer launches without Visual Studio / terminal | Pass | **2026-10-12: Burn bundle (`OpenJarvis-1.0.0-arm64.exe`, the actual end-user installer, not just the inner MSI) run with `/quiet` on this ARM64 host — `NativeMachine = 43620` gate evaluated true, exit 0x0, app registered in Apps & Features, launched from `Program Files\OpenJarvis` successfully.** |
| Setup shows download progress and a named error on failure | Partial | Setup page opens (Start setup / Skip setup). The *missing-backend* error path is now verified (see Known issues): installing without the payload produces the exact actionable `ErrorBar` message with retry/backoff, not a hang. First-run Foundry download progress UI itself was not re-run this pass (Foundry 0.11.0 was already installed). |
| Chat streams tokens (SSE `/v1/chat/completions`) | Pass (API) | curl SSE against `jarvis serve --engine foundry_local`; content `OpenJarvis says hello!` |
| Stop cancels the in-flight request | Pass (API) | Mid-stream curl job stopped; partial SSE written |
| Conversation history survives restart | Partial | **2026-10-12: storage-layer verified** — killed and relaunched `OpenJarvis.exe`; `winui-conversations.json` was read back byte-for-byte unchanged and the backend came up healthy. Full UI-level confirmation (the sidebar visually re-showing the thread) still needs a human or GUI-automation pass — this session has no GUI driving tool. |
| Model list comes from Foundry via `/v1/models` | Pass | Large Foundry catalog returned |
| Agent picker restarts serve (`simple` / `orchestrator` / `react`) | Code complete | `RestartWithAgentAsync` / model restart implemented |
| Tool activity cards appear on `tool_call_start` / `tool_call_end` | **Pass** | **2026-10-12, after raising this VM to 10 GB RAM: fully verified end-to-end, including a real code fix.** `jarvis serve --engine foundry_local --model Phi-4-mini-instruct-generic-cpu:5 --agent react`, asked to compute `847 * 293` via the `calculator` tool — correct result (`248171.0`) with the tool's float signature across repeated runs, confirming `native_react`'s Thought/Action/Observation loop genuinely calls the tool. **Found and fixed a real bug**: `_handle_agent_stream()` in `routes.py` — the only streaming path `ChatPage.xaml.cs`'s `StreamChatAsync` actually calls — only ever emitted the agent's *final* answer; it never subscribed to the bus for `TOOL_CALL_START`/`TOOL_CALL_END`, so the named `event: tool_call_start` / `event: tool_call_end` SSE lines `ApplySse()` listens for could never arrive, even though the agent's `ToolExecutor` genuinely publishes them. (There was already an unused, fully-built `AgentStreamBridge` in `stream_bridge.py` for exactly this, but it bypasses the per-agent model-override lock added for #759 and the `TraceCollector` wiring — reusing it would have reintroduced that race and dropped tracing, so the fix adds EventBus subscription/draining directly to `_handle_agent_stream` instead, keeping both.) Verified live: a streamed request now produces `event: tool_call_start` → `event: tool_call_end` (with `tool`, JSON-text `arguments`, `success`, `result: "248171.0"`) → the final content chunk, in that order. Added `test_streaming_agent_run_forwards_tool_call_events_over_sse` in `tests/server/test_routes.py`; full `tests/server/` suite still at 448 passed (the pre-existing 8 failures are unrelated and reproduce identically on unmodified code). Also fixed two probe bugs along the way: `max_tokens: 64` truncated reasoning models before `tool_calls` (raised to 512), and `tool_choice: "auto"` let `Phi-4-mini-instruct` correctly decline a contrived no-op probe and read as incapable (switched to `"required"`). `gemma-4-e2b-it-generic-cpu:3`'s HTTP 500 remains a confirmed Foundry-side chat-template bug, not ours. |
| Approvals poll `/v1/approvals/pending` and approve/deny | Pass (API) | Endpoint reachable (empty pending) |
| Settings theme follows light / dark / system | Partial | Settings page opens with Use system / Light / Dark. Theme was not switched on this pass. |
| Keyboard: tab order, Enter to send, access keys | Code complete | AccessKeys + Enter-to-send present; Narrator pass deferred to Ultra |
| Touch targets usable at 100% / 150% / 200% scale | Code complete | MinHeight/MinWidth 40 on primary buttons; scale pass deferred to Ultra |
| Narrator reads message box, send, navigation | Code complete | AutomationProperties present; Narrator pass deferred to Ultra |
| Status shows engine, model, execution provider | Pass | Chat and Settings showed engine `multi`, model `gemma-4-e2b-it-generic-cpu:3`, `CPUExecutionProvider`, CPU fallback, no GPU. `/v1/info` matched. |
| Offline chat after Setup (disconnect network) | Partial | Model already cached/loaded; full offline UI pass deferred |
| Cloud toggle off: prompts stay local even if API keys exist | Pass | `allow_cloud=false` in config; `/v1/info` reports false |
| Cloud toggle on: explicit Settings save, then restart | Code complete | TomlSettings.SetAllowCloud on Save |
| Windows AI API probe listed in Settings (not used for chat) | Code complete | Probe-only |
| Backend crash: UI stays responsive and recovers | **Pass** | **2026-10-12: killed the supervised `jarvis.exe` child directly while `OpenJarvis.exe` kept running. `/health` dropped, then returned 200 within ~15 seconds under a new PID; the WinUI shell never restarted or stopped responding.** |
| Uninstall removes the app; data remains unless `-RemoveData` | Pass | **2026-10-12: verified via the Burn bundle's `/uninstall /quiet` path** (previously only MSI-tested) — registry entries and `Program Files\OpenJarvis` removed; `winui-conversations.json` left in place as documented. |

## Hardware notes (this run)

- Device: Parallels ARM Virtual Machine on Mac M3 (6.0 GB RAM, about 1.7 GB free with Foundry up)
- Display: Parallels Display Adapter (WDDM), 0 B reported to Foundry
- Foundry Local: 0.11.0 (CLI and daemon)
- WinUI shell (2026-10-12): debug unpackaged `OpenJarvis.exe` launched and stayed up through Chat, Approvals, Setup, and Settings. Earlier `0xc000027b` crashes were not reproduced on this build.

## Hardware notes (Surface Laptop Ultra — pending upstream)

- SoC: NVIDIA RTX Spark N1X (Grace CPU, Blackwell GPU, NVIDIA NPU, unified memory)
- Qualcomm QNN is the wrong accelerator for this SKU
- Minimum RAM config is 24 GB; `Phi-4-mini-instruct` is the default alias for that band
