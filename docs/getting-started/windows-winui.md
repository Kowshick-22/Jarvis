---
title: WinUI 3 desktop (ARM64)
description: Build and run the unpackaged WinUI 3 OpenJarvis app on Windows ARM64
---

# WinUI 3 desktop (ARM64)

OpenJarvis on Windows ARM64 is an unpackaged WinUI 3 app. It starts Foundry Local (Windows ML), then `jarvis serve --engine foundry_local`, and talks to the same FastAPI contracts as the Tauri desktop (chat SSE, models, approvals).

End users install from the ARM64 bundle. They do not need a terminal, Visual Studio, or the .NET SDK.

## What you get

- Native WinUI 3 chat, conversation history, model and agent pickers, settings, tool activity, and approvals
- Automatic Foundry Local + `jarvis serve` process supervision (job object, backoff restart)
- Local inference by default; cloud engines stay off until Settings opts in
- Offline chat after the first model and execution-provider download

Speech, the React dashboard, managed-agent studio, and deep research are not in this XAML shell. Those FastAPI routes still exist if you point a browser at `http://127.0.0.1:8000`.

## End-user install

1. Run `OpenJarvis-1.0.0-arm64.exe` (Burn bundle) or the MSI from the GitHub Actions `winui-arm64` workflow.
2. The installer refuses x64 Windows. It requires ARM64.
3. First launch opens Setup: Foundry Local starts, then `Phi-4-mini-instruct` downloads. After that, disconnect the network and chat still works.
4. Uninstall from Apps & Features. Conversations under `%USERPROFILE%\.openjarvis` and Foundry models stay unless you run [`windows/scripts/uninstall-cleanup.ps1`](../../windows/scripts/uninstall-cleanup.ps1) `-RemoveData`.

## Build from source (developers)

### Prerequisites

See [version pins](windows-winui-versions.md). You need:

- Windows 11 24H2 (build 26100) or later on ARM64. Surface Laptop Ultra ships Windows 11 26H1 and does not take 26H2.
- Visual Studio 2022 with the **WinUI application development** workload
- .NET 9 SDK
- Rust `aarch64-pc-windows-msvc` (for `openjarvis_rust`)
- WiX Toolset 5
- `uv`

```powershell
cd OpenJarvis
.\windows\scripts\publish-arm64.ps1
```

That publishes a self-contained `win-arm64` app to `windows/OpenJarvis.WinUI/bin/publish/win-arm64`, syncs the Python backend (`--extra server --group desktop-native`), and builds the MSI when WiX is on PATH.

Manual publish:

```powershell
dotnet publish windows\OpenJarvis.WinUI\OpenJarvis.WinUI.csproj `
  -c Release -r win-arm64 --self-contained true `
  /p:Platform=ARM64 /p:WindowsAppSDKSelfContained=true
```

## Runtime layout

| Path | Role |
|------|------|
| `Program Files\OpenJarvis\OpenJarvis.exe` | WinUI 3 shell |
| `%LOCALAPPDATA%\OpenJarvis\venv` | CPython 3.12 + OpenJarvis |
| `%LOCALAPPDATA%\OpenJarvis\src` | Backend tree used by `uv run` fallbacks |
| `%USERPROFILE%\.openjarvis\config.toml` | Engine host, `allow_cloud` |
| `%USERPROFILE%\.openjarvis\winui-conversations.json` | Chat history (same fields as the web `openjarvis-conversations` store) |

The supervisor attaches to an existing healthy `http://127.0.0.1:8000` if one is already running.

## Changing the chat agent

The agent combo restarts `jarvis serve --agent <name>`. Supported names: `simple`, `orchestrator`, `react`. `openhands` only works if that extra imported on this machine.

## Cloud opt-in

`[engine] allow_cloud = false` by default. Settings → **Allow cloud inference** writes that flag. `jarvis serve` then attaches `CloudEngine` on the next start. Until then, API keys on the machine do not send prompts off-device.

## Windows AI APIs

Settings probes `Microsoft.Windows.AI.Generative.LanguageModel` and WinML types with `ApiInformation.IsTypePresent`. Those APIs are **not** the chat engine. Chat always goes through Foundry Local → `foundry_local` → agents and tools.
