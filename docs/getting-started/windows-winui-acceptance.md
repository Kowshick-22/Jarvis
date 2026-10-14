---
title: WinUI ARM64 acceptance
description: Feature checklist, performance results, and how to measure them
---

# WinUI ARM64 acceptance

The target device is Surface Laptop Ultra (NVIDIA RTX Spark N1X, Windows 11 26H1, ARM64). The results below come from a stand-in machine without a GPU or NPU (see [test environment](#test-environment)). Anything that needs GPU or NPU evidence is listed as pending on the Surface. To install a build and rerun these checks, see [Testing the WinUI app](windows-winui-testing.md).

## Status key

| Status | Meaning |
|--------|---------|
| Pass | Works as specified |
| Partial | Works, with a gap noted |
| Fail | Doesn't meet the requirement |
| Not implemented | Not in the WinUI app |
| Not verified | Implemented in code, not exercised end to end |
| Pending (Surface) | Needs the target device |

The **Verified on** column says where each result comes from:

- **Installed build:** the ARM64 Burn bundle, installed and run on the test machine.
- **Source build:** the WinUI app run from a source checkout.
- **Code:** implemented, but not exercised end to end.

## Performance

Model: **Phi-4-mini-instruct-generic-cpu:5**, resolved by Setup from the default `Phi-4-mini-instruct` after the GPU variant failed to load. Execution provider: `CPUExecutionProvider` (CPU fallback).

| Metric | Result | How measured |
|--------|--------|--------------|
| First launch to ready | 71 s | Fresh install with no runtime in `%LOCALAPPDATA%`; model cached in Foundry but not loaded. App start until `GET /health` returns 200 |
| Relaunch to ready | 13 s | Runtime already copied, model already loaded in Foundry |
| Time to first token | 2.6–3.8 s | First SSE content delta; `measure-performance.ps1` and three streamed runs |
| Decode speed | ~13–15 tokens/s | SSE content deltas per second after the first token (about one delta per token); the backend doesn't report token usage for Foundry |
| Working set: `OpenJarvis.exe` | 233 MB | On the Chat page with the backend running |
| Working set: backend | ~160 MB | `python.exe` (2 processes, 153 MB) plus the `jarvis.exe` launcher (7 MB) |
| Working set: Foundry daemon | 4.5 GB | `foundrylocald` with the model loaded |
| Backend crash recovery | 13 s | `jarvis.exe` killed until `/health` returns 200 under a new process |
| Installer size | 117 MB | `OpenJarvis-1.0.0-arm64.exe` (Burn bundle) |
| Runtime on disk | ~230 MB | `%LOCALAPPDATA%\OpenJarvis` `python`, `venv` and `src`, copied on first launch |

GPU and NPU results (`NvTensorRTRTXExecutionProvider`, `CUDAExecutionProvider`, `WebGPUExecutionProvider`) are pending (Surface).

### Measuring

With OpenJarvis running and the API healthy:

```powershell
.\windows\scripts\measure-performance.ps1
```

The script uses the model the backend reports (override with `-Model`) and writes `docs/getting-started/windows-winui-perf-last.json` (git-ignored). It records:
- time to first token;
- tokens per second, estimated from SSE content deltas, because Foundry streams carry no usage counts;
- execution provider;
- working sets.

Its "cold start" figure is only the wait for `/health` on an already running server. Time first launch and relaunch from app start instead. [Testing the WinUI app](windows-winui-testing.md) has the full procedure.

## Feature checklist

### Build, install and lifecycle

| Item | Status | Verified on | Notes |
|------|--------|-------------|-------|
| ARM64 build | Pass | Installed build | `publish-arm64.ps1` builds the app, backend payload, MSI and Burn bundle with 0 errors. The build reports 3 XAML warnings (`WMC1506` in `Views/ApprovalsPage.xaml`). |
| Installer runs without Visual Studio or a terminal | Pass | Installed build | The Burn bundle installs to `Program Files\OpenJarvis` and registers in Apps & Features. It needs elevation and is unsigned (SmartScreen warns). |
| First launch reaches Chat with no developer tools | Pass | Installed build | The backend runs from the bundled ARM64 Python in `%LOCALAPPDATA%\OpenJarvis`. No uv, Python install or source checkout is involved. |
| Local-AI consent before setup | Pass | Installed build | On a new profile, nothing starts and no files are written until **Use Foundry Local and continue** is selected. Setup then runs and the consent is saved for later launches. |
| Setup progress and named errors | Pass | Installed build | The Inference Engine, AI Model and API Server steps report progress. A failure shows "Setup could not finish" with the cause (for example the Foundry load error) and a retry. |
| Default model resolves and falls back to CPU | Pass | Installed build | `Phi-4-mini-instruct` resolves to `Phi-4-mini-instruct-generic-gpu:5`. When that fails to load (WebGPU `EP_FAIL`), Setup loads `…-generic-cpu:5` and saves it. |
| Foundry Local installed by Setup when missing | Not verified | Code | Downloads the 0.11.0 ARM64 MSIX and runs `Add-AppxPackage`. Not exercised on a machine without Foundry. |
| Uninstall removes the app; data remains | Pass | Installed build | Uninstall removes `Program Files\OpenJarvis` and the Apps & Features entry. `%USERPROFILE%\.openjarvis` and `%LOCALAPPDATA%\OpenJarvis` remain; `uninstall-cleanup.ps1 -RemoveData` removes them. |
| Updates | Fail | Installed build | Installing a newer build doesn't refresh the copied backend runtime (see [known issues](windows-winui-known-issues.md)). The in-app update check skips silently until an update manifest is published. |

### Chat and backend

| Item | Status | Verified on | Notes |
|------|--------|-------------|-------|
| Chat streams tokens (SSE `/v1/chat/completions`) | Pass | Installed build | A prompt sent from the Chat page streams a reply and saves it to history. |
| Stop cancels the in-flight request | Pass | Installed build | Stop ends the reply with "(stopped)" and re-enables Send. The UI and server stay responsive. |
| Conversation history survives restart | Pass | Installed build | After a restart the conversation is listed and its messages are shown; `winui-conversations.json` is unchanged. |
| Chat renders Markdown and syntax-highlighted code | Pass | Source build | Assistant messages render through a Markdown control with syntax highlighting; user messages stay plain text, as in the React client. |
| Model list comes from the Foundry catalog | Pass | Source build | `/v1/models` returns the Foundry catalog. |
| Model picker restarts the backend with the new model | Pass | Source build | `RestartWithModelAsync` loads the model in Foundry and restarts `jarvis serve`. |
| Chat agent selection (`simple` / `orchestrator` / `react`) | Not implemented | Code | Chat always runs `jarvis serve --agent simple`, as the Tauri desktop does. Tool-using and managed agents are created from the Agents page. |
| Tool activity cards (`tool_call_start` / `tool_call_end`) | Pass | Source build | A real `native_react` calculator call over the streaming path renders tool cards. |
| Deep Research mode | Pass | Source build | `/api/research` drives a research timeline (searches, synthesis, completion) in Chat. With a connected notes folder, both `Phi-4-mini-instruct-generic-cpu:5` and `qwen3.5-4b-generic-cpu:3` search the notes and answer from them; both models write their tool calls as text, which the Foundry engine converts (see [known issues](windows-winui-known-issues.md)). Checked through the API, not through the Chat page. |
| Memory store and search | Pass | Installed build | `/v1/memory/store` and `/v1/memory/search` work through the bundled `openjarvis_rust` extension. |
| Status shows engine, model, execution provider | Pass | Installed build | `/v1/info` reports ARM64, the resolved model, `CPUExecutionProvider` and CPU fallback; Chat shows the active model. |
| Backend crash: UI stays responsive and recovers | Pass | Installed build | Killing `jarvis.exe` restarts the backend under a new process in about 13 s; the window stays responsive. |
| Attaches to an already-running server | Pass | Installed build | With a healthy server on `127.0.0.1:8000`, the app polls it and doesn't start a second backend. |
| Offline chat after setup | Partial | Source build | Works once the model and execution-provider assets are cached; a full offline pass from a fresh setup is pending. |

### Pages and settings

| Item | Status | Verified on | Notes |
|------|--------|-------------|-------|
| Approvals poll `/v1/approvals/pending` and approve/deny | Pass | Source build | Dedicated Approvals page. There is no approval badge elsewhere in the shell. |
| Dashboard shows telemetry, energy, savings and traces | Pass | Source build | Backed by `/v1/telemetry/*` and the trace endpoints. |
| Data Sources (Connectors and Memory) | Pass | Source build | Connector list, connect and sync, with live polling. |
| Agents page, including managed-agent messaging | Pass | Source build | `/v1/managed-agents` and the Slack/SendBlue channel endpoints. |
| Logs page | Pass | Source build | In-process log collection with copy and clear. |
| Ctrl+K command palette | Pass | Source build | One filterable list of pages, conversations, models and managed agents, with keyboard navigation. |
| Native speech dictation and read-aloud | Pass | Source build | Windows `SpeechRecognizer` / `SpeechSynthesizer`, wired into the chat input and message actions. |
| Theme follows light / dark / system | Pass | Source build | Applied at startup and saved across restarts. |
| Cloud provider keys in Settings | Pass | Source build | Saves and clears keys for the supported providers. Keys are stored in a plain file (see [known issues](windows-winui-known-issues.md)). |
| Cloud off: prompts stay local even with API keys | Pass | Installed build | `allow_cloud = false` by default, and `/v1/info` reports it; saved keys alone don't enable cloud inference. |
| Cloud on: explicit Settings save, then restart | Not verified | Code | `TomlSettings.SetAllowCloud` is wired to Settings → Save. |
| Windows AI API probe in Settings (not used for chat) | Pass | Source build | `ApiInformation.IsTypePresent` checks for `Microsoft.Windows.AI.Generative.LanguageModel` and WinML types; chat always goes through Foundry Local. |

### Accessibility and input

| Item | Status | Verified on | Notes |
|------|--------|-------------|-------|
| Keyboard: tab order, Enter to send, access keys | Partial | Code | Enter sends; default XAML tab order. Interactive controls across the 18 views carry `AutomationProperties.Name`, and primary page actions have an `AccessKey`. Status banners keep a dynamic name so changes are announced. A Narrator pass is pending. |
| Touch targets at 100% / 150% / 200% scale | Partial | Code | Primary buttons use a 40 px minimum height. A scaling pass on a touch device is pending. |

## Test environment

- Windows 11 build 26300, ARM64 virtual machine: 4 cores, 10 GB RAM, no GPU or NPU (software display adapter)
- Foundry Local 0.11.0
- Installed from `OpenJarvis-1.0.0-arm64.exe`, with an isolated profile (`OPENJARVIS_HOME`)
- Consent, Chat, Stop and restart checks drive the app through Windows UI Automation

## Surface Laptop Ultra (pending)

- SoC: NVIDIA RTX Spark N1X (Grace CPU, Blackwell GPU, NVIDIA NPU, unified memory)
- Qualcomm QNN is the wrong accelerator for this SKU
- The smallest RAM configuration is 24 GB; `Phi-4-mini-instruct` is the default model for it
- Needed on the device: execution provider evidence, GPU/NPU performance, the NVIDIA driver version, a Narrator pass, display-scaling and touch passes, and offline use after a fresh setup
