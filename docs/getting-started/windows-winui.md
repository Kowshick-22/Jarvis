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
- **Setup installs Foundry Local** (ARM64 MSIX via `Add-AppxPackage`) when it is missing — no terminal
- Local inference by default; cloud engines stay off until Settings opts in
- Offline chat after the first model and execution-provider download

Speech, the React dashboard, managed-agent studio, memory/connectors UI, and deep research are not in this XAML shell. See [known issues](windows-winui-known-issues.md). FastAPI routes still exist if you point a browser at `http://127.0.0.1:8000`.

## End-user install

1. Run `OpenJarvis-1.0.0-arm64.exe` (Burn bundle) or the MSI from the GitHub Actions `winui-arm64` workflow (artifacts are unsigned unless signing is configured).
2. The installer refuses x64 Windows. It requires ARM64.
3. First launch opens **Setup** → **Start setup**:
   - Downloads and installs Foundry Local if needed
   - Starts the Foundry server
   - Downloads and loads `Phi-4-mini-instruct` (falls back to `*-generic-cpu` on VMs without a GPU)
4. After setup, disconnect the network and chat still works.
5. Uninstall from Apps & Features. Conversations under `%USERPROFILE%\.openjarvis` and Foundry models stay unless you run [`windows/scripts/uninstall-cleanup.ps1`](../../windows/scripts/uninstall-cleanup.ps1) `-RemoveData`.

## Demo walkthrough (re-record on Ultra)

1. Install the Burn bundle → launch OpenJarvis.
2. Setup → Start setup → wait for “Setup complete”.
3. Chat: send a short prompt → watch streamed tokens → Stop to cancel.
4. Confirm conversation appears in history; restart the app and reopen it.
5. Change model / agent; confirm status returns to Ready.
6. Settings: theme light/dark; cloud toggle off; hardware line shows engine, model, execution provider.
7. Approvals page loads (empty is OK if no pending tools).
8. Kill `jarvis` in Task Manager; confirm UI stays responsive and recovers.

## Build from source (developers)

### Prerequisites

See [version pins](windows-winui-versions.md). You need:

- Windows 11 24H2 (build 26100) or later on ARM64. Surface Laptop Ultra ships Windows 11 26H1 and does not take 26H2.
- Visual Studio 2022 (or Build Tools) with the **WinUI / Windows App SDK** workload
- .NET 9 SDK (or a newer SDK that can target `net9.0-windows10.0.26100.0`)
- Rust `aarch64-pc-windows-msvc` (for `openjarvis_rust`)
- WiX Toolset 5
- `uv`

```powershell
cd OpenJarvis
$env:NUGET_PACKAGES = "$env:USERPROFILE\.nuget\packages"
.\windows\scripts\publish-arm64.ps1
```

That publishes a self-contained `win-arm64` app to `dist/OpenJarvis-win-arm64`, syncs the Python backend (`--extra server --group desktop-native`), and builds the MSI + Burn bundle into `dist/` when WiX builds succeed.

Manual publish (app only):

```powershell
dotnet publish windows\OpenJarvis.WinUI\OpenJarvis.WinUI.csproj `
  -c Release -r win-arm64 --self-contained true `
  /p:Platform=ARM64 /p:WindowsAppSDKSelfContained=true
```

## Runtime layout

| Path | Role |
|------|------|
| `Program Files\OpenJarvis\OpenJarvis.exe` | WinUI 3 shell |
| `Program Files\OpenJarvis\payload\` | Staged venv + source copied on first launch |
| `%LOCALAPPDATA%\OpenJarvis\venv` | CPython 3.12 + OpenJarvis |
| `%LOCALAPPDATA%\OpenJarvis\src` | Backend tree used by `uv run` fallbacks |
| `%LOCALAPPDATA%\OpenJarvis\runtime\` | Downloaded Foundry MSIX cache |
| `%USERPROFILE%\.openjarvis\config.toml` | Engine host, `allow_cloud` |
| `%USERPROFILE%\.openjarvis\winui-conversations.json` | Chat history |

The supervisor attaches to an existing healthy `http://127.0.0.1:8000` if one is already running.

## Changing the chat agent or model

The agent and model combos restart `jarvis serve` with the new `--agent` / `--model`. Supported agents: `simple`, `orchestrator`, `react`. `openhands` only works if that extra imported on this machine.

## Cloud opt-in

`[engine] allow_cloud = false` by default. Settings → **Allow cloud inference** writes that flag. `jarvis serve` then attaches `CloudEngine` on the next start. Until then, API keys on the machine do not send prompts off-device.

## Windows AI APIs

Settings probes `Microsoft.Windows.AI.Generative.LanguageModel` and WinML types with `ApiInformation.IsTypePresent`. Those APIs are **not** the chat engine. Chat always goes through Foundry Local → `foundry_local` → agents and tools.

## Related docs

- [Version pins](windows-winui-versions.md)
- [Acceptance checklist](windows-winui-acceptance.md)
- [Known issues](windows-winui-known-issues.md)
