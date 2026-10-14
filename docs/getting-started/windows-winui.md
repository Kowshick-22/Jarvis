---
title: WinUI 3 desktop (ARM64)
description: Build and run the unpackaged WinUI 3 OpenJarvis app on Windows ARM64
---

# WinUI 3 desktop (ARM64)

OpenJarvis on Windows ARM64 is an unpackaged WinUI 3 app. After the user approves local setup, it starts Foundry Local (Windows ML), loads the selected model, launches `jarvis serve --engine foundry_local --agent simple`, and uses the same FastAPI contracts as the Tauri desktop.

End users install from the ARM64 bundle. They do not need a terminal, Visual Studio, or the .NET SDK.

## What you get

- Native WinUI 3 chat with Markdown, streaming and cancellation, per-message copy, tool-activity cards, Deep Research, speech dictation, and read-aloud
- Conversation history with search and delete in the upper part of the app-wide navigation pane
- A resizable app navigation pane (width is saved) and the circular OpenJarvis icon on the window, taskbar, and installer
- Native **Dashboard**, **Data Sources** (Connectors and Memory), **Agents** (including managed-agent messaging), **Approvals**, and **Logs** pages
- A Ctrl+K command palette (quick switcher for pages, conversations, models, and agents)
- Cloud and tool API key management in Settings (OpenAI/Anthropic/Google/OpenRouter/Atlas Cloud/Minimax/Tavily)
- Native speech (dictate into chat, read replies aloud) via Windows' own speech APIs, not the backend
- Automatic Foundry Local + `jarvis serve` process supervision (job object, backoff restart)
- A launch-time consent and progress screen; setup installs Foundry Local (ARM64 MSIX via `Add-AppxPackage`) when it is missing
- Local inference by default; cloud engines stay off until Settings opts in
- Offline chat after the first model and execution-provider download

The native pages don't cover every React-client feature. See [known issues](windows-winui-known-issues.md) for the remaining gaps, feature limits, and verification status. The local API remains available at `http://127.0.0.1:8000`.

## End-user install

1. Run `OpenJarvis-1.0.0-arm64.exe` (Burn bundle) or the MSI from the GitHub Actions `winui-arm64` workflow (artifacts are unsigned unless signing is configured).
2. The installer refuses x64 Windows. It requires ARM64.
3. On first launch, review the local-AI notice and select **Use Foundry Local and continue**. Nothing is installed, started, or downloaded before this confirmation.
4. The launch screen then installs and starts Foundry Local if necessary. It resolves `Phi-4-mini-instruct` to a catalog variant (GPU, then NPU, then CPU), downloads and loads it, and starts the OpenJarvis API. If the GPU variant can't load (for example on a VM without a GPU), it falls back to the `*-generic-cpu` variant.
5. The app opens Chat when all three setup steps are ready. Later launches reuse the saved consent and show live progress while checking the engine, model, and API server. Settings → **Setup** shows the current supervisor status and offers **Retry setup**.
6. After the model and execution-provider assets have been downloaded, local chat can run without a network connection.
7. Uninstall from Apps & Features. Conversations under `%USERPROFILE%\.openjarvis` and Foundry models stay unless you run [`windows/scripts/uninstall-cleanup.ps1`](../../windows/scripts/uninstall-cleanup.ps1) `-RemoveData`.

## Demo walkthrough

1. Install the Burn bundle → launch OpenJarvis.
2. On a fresh profile, approve local setup and watch the Inference Engine, AI Model, and API Server steps complete.
3. Chat: send a short prompt → watch streamed tokens → Stop to cancel.
4. Confirm conversation appears in history; restart the app and reopen it.
5. Change the model; confirm status returns to Ready.
6. Settings: theme light/dark; cloud toggle off; hardware line shows engine, model, execution provider.
7. Approvals page loads (empty is OK if no pending tools).
8. Open Dashboard, Data Sources, Agents, and Logs. Create or open an agent and inspect its detail tabs.
9. Press Ctrl+K and switch to a page, conversation, model, or agent.
10. Drag the navigation-pane splitter; restart and confirm its width persists. Confirm the window, taskbar, and Apps & Features icons.
11. Kill `jarvis` in Task Manager; confirm the UI stays responsive and the supervisor recovers.

See the [acceptance checklist](windows-winui-acceptance.md) for what is verified and what needs the Surface or a manual pass.

## Build from source (developers)

### Prerequisites

See [version pins](windows-winui-versions.md). You need:

- Windows 11 24H2 (build 26100) or later on ARM64. Surface Laptop Ultra ships Windows 11 26H1 and does not take 26H2.
- Visual Studio 2022 or 2026 (or Build Tools) with the ARM64 C++ build tools and the Windows 11 SDK (26100). The WinUI workload isn't required: the Windows App SDK comes from NuGet
- .NET 9 SDK (or a newer SDK that can target `net9.0-windows10.0.26100.0`)
- Rust `aarch64-pc-windows-msvc` (for `openjarvis_rust`). `rust/rust-toolchain.toml` pins 1.88: `winget install Rustlang.Rustup`, then open a new terminal
- LLVM/clang (`winget install LLVM.LLVM`), needed to build `ring` for ARM64. The build script finds it in `C:\Program Files\LLVM\bin`
- WiX Toolset 5 (`dotnet tool install --global wix --version 5.0.2`)
- `uv` 0.12.19 or newer, on PATH

```powershell
cd OpenJarvis
$env:NUGET_PACKAGES = "$env:USERPROFILE\.nuget\packages"
.\windows\scripts\publish-arm64.ps1
```

That publishes a self-contained `win-arm64` app to `dist/OpenJarvis-win-arm64` and stages the backend payload next to it:

- a standalone ARM64 CPython 3.12 in `payload\python`;
- a relocatable venv in `payload\venv`, synced from `uv.lock` (`uv sync --frozen --no-editable --extra server --group desktop-native`) without touching the checkout's `.venv`.

It then builds the MSI + Burn bundle into `dist/` when WiX builds succeed. A failed uv step stops the build. Use `-SkipPayload` to reuse the last payload, or `-SkipInstaller` to build only the app.

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
| `Program Files\OpenJarvis\payload\python\` | Standalone ARM64 CPython 3.12 shipped with the installer |
| `Program Files\OpenJarvis\payload\venv\` | Relocatable venv with OpenJarvis (`--extra server --group desktop-native`) |
| `Program Files\OpenJarvis\payload\src\` | Copy of the backend source tree |
| `%LOCALAPPDATA%\OpenJarvis\python` | Copied from `payload\python` on first launch; the venv's base interpreter (~63 MB) |
| `%LOCALAPPDATA%\OpenJarvis\venv` | Copied from `payload\venv` on first launch; `pyvenv.cfg` `home` is rewritten to `%LOCALAPPDATA%\OpenJarvis\python`. Runs `Scripts\jarvis.exe serve` (~139 MB) |
| `%LOCALAPPDATA%\OpenJarvis\src` | Copied from `payload\src`; working directory for `jarvis serve` (~26 MB) |
| `%LOCALAPPDATA%\OpenJarvis\runtime\` | Downloaded Foundry MSIX cache |
| `%LOCALAPPDATA%\OpenJarvis\logs\jarvis-serve.log` | Supervised backend output; each start logs the exact command line |
| `%USERPROFILE%\.openjarvis\config.toml` | Engine host, `allow_cloud` |
| `%USERPROFILE%\.openjarvis\winui-conversations.json` | Chat history |
| `%USERPROFILE%\.openjarvis\winui-settings.json` | WinUI preferences, saved setup consent, and the resolved model id |
| `%USERPROFILE%\.openjarvis\cloud-keys.env` | Cloud-provider keys saved by Settings |

Setting `OPENJARVIS_HOME` moves the `%USERPROFILE%\.openjarvis` files (the app passes it on to `jarvis serve`). It does not move `%LOCALAPPDATA%\OpenJarvis`.

The `%LOCALAPPDATA%\OpenJarvis` copies are made only when missing, so upgrading the app doesn't refresh them (see [known issues](windows-winui-known-issues.md)).

The supervisor attaches to an existing healthy `http://127.0.0.1:8000` if one is already running. A build run from inside a source checkout falls back to `uv run --extra server --project <checkout> jarvis serve`, but only when `%LOCALAPPDATA%\OpenJarvis\venv` doesn't exist.

## Changing the chat agent or model

The model picker loads the selected Foundry model and restarts `jarvis serve` with the new `--model`. Chat always starts the backend with `--agent simple`, matching the Tauri desktop; it has no chat-agent picker. Managed and tool-using agents are created from the **Agents** page.

## Cloud opt-in

`[engine] allow_cloud = false` by default. Settings → **Allow cloud inference** writes that flag; restart OpenJarvis for `jarvis serve` to attach cloud engines. Provider keys can be saved and hot-reloaded separately, but prompts remain local until cloud inference is explicitly enabled.

## Windows AI APIs

Settings probes `Microsoft.Windows.AI.Generative.LanguageModel` and WinML types with `ApiInformation.IsTypePresent`. Those APIs are **not** the chat engine. Chat always goes through Foundry Local → `foundry_local` → agents and tools.

## Related docs

- [Version pins](windows-winui-versions.md)
- [Acceptance checklist](windows-winui-acceptance.md)
- [Known issues](windows-winui-known-issues.md)
