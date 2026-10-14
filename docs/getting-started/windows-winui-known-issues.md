---
title: WinUI known issues and limitations
description: Scope vs Tauri/React desktop, runtime and hardware caveats, build and lifecycle limitations
---

# WinUI known issues and limitations

## Scope vs Tauri/React desktop

The WinUI app covers:

- chat, with Markdown, streaming, cancellation, per-message copy, tool-activity cards, Deep Research, and native dictation and read-aloud;
- conversation history and model selection;
- Settings: theme, cloud opt-in, provider keys;
- Dashboard, Data Sources (Connectors and Memory), Agents (including managed-agent messaging), Approvals and Logs;
- a Ctrl+K command palette.

These are smaller than the React/Tauri desktop, or have a limitation worth knowing:

| Area | Limitation |
|------|------------|
| Chat agent selection | Chat always runs `jarvis serve --agent simple`, as the Tauri desktop does; there is no chat-agent picker. Tool-using and managed agents are created from the Agents page. |
| Approvals badge | Pending approvals appear only on the Approvals page. There is no badge in the navigation pane or title bar. |
| Backend speech (`faster-whisper` / `ctranslate2`) | These packages have no reliable Windows ARM64 wheels, so the installer's Python payload leaves them out (`--extra server --group desktop-native` only). Dictation and read-aloud use Windows' `SpeechRecognizer` / `SpeechSynthesizer` instead, so quality depends on the Windows speech engine rather than Whisper. |
| Cloud provider key storage | Keys saved in Settings (OpenAI, Anthropic, Google, OpenRouter, Atlas Cloud, Minimax, and Tavily through tool credentials) go to a plain file, `cloud-keys.env`, in the user profile, not to DPAPI or Windows Credential Locker. Any local process running as the user can read it. |

## Runtime and hardware

- **VMs without a GPU:** Setup falls back to the `*-generic-cpu` catalog variant when the GPU (WebGPU) variant fails to load. Settings and `/v1/info` then report `CPUExecutionProvider`, CPU fallback, and no GPU.
- **Foundry model ids:** `foundry model load` and chat completions both need a versioned catalog id such as `Phi-4-mini-instruct-generic-cpu:5`; a bare name returns "Model not found". Foundry 0.11 also doesn't accept `Phi-4-mini-instruct` as an alias; its alias is `phi-4-mini`. Setup resolves the configured name against `foundry model list --variants -o json` (GPU, then NPU, then CPU) and saves the resolved id. When calling the API directly, use a versioned id; `foundry model info <alias>` lists them.
- **Tool calling on `gemma-4-e2b-it`:** `/v1/info` reports tools as unsupported for this model. Foundry Local's packaged chat template for it returns HTTP 500 during the tool probe (a Jinja2 `NoneType` error reading `function.name`). That's a Foundry Local bug, not OpenJarvis code. Avoid this model for tool-using agents.
- **Tool-calling probe:** `check_tool_calling()` in `src/openjarvis/engine/foundry_local.py` uses `max_tokens: 512` and `tool_choice: "required"`, so reasoning models, and models that would otherwise decline a trivial prompt, are measured correctly. If a model reports tools as unsupported, the `reason` field of `/v1/info`'s `tool_calling` object shows whether its reply was cut short or it can't call tools.
- **Tool-activity cards with `native_react`:** a calculator prompt on the streaming `/v1/chat/completions` path produces `event: tool_call_start`, then `event: tool_call_end` (with `tool`, JSON-text `arguments`, `success` and `result`), then the final content. `ChatPage.xaml.cs` (`ApplySse()`) renders them.
- **Decode error in backend startup diagnostics:** when `jarvis serve` starts, reading Foundry Local's CLI output can raise `UnicodeDecodeError: 'charmap' codec can't decode byte ...` in a subprocess reader thread, because Windows' default `cp1252` decoding can't handle a non-ASCII byte. The error is caught and the server starts normally, and the traceback appears in `jarvis-serve.log`. The fix is to decode that output as UTF-8 with replacement. The WinUI app's own Foundry CLI calls already decode as UTF-8.
- **Surface Laptop Ultra acceleration:** GPU and NPU evidence is pending. The [acceptance results](windows-winui-acceptance.md) come from an ARM64 VM without a GPU or NPU.
- **RAM:** `Phi-4-mini-instruct-generic-cpu` (~4.8 GB) is the default. The Foundry daemon uses about 4.5 GB with it loaded, so allow roughly 10 GB of free RAM alongside the app and backend. On smaller devices, use `qwen3-0.6b-generic-cpu` (~600 MB).
- **Foundry version:** Setup installs Foundry Local **0.11.0** (`cli-preview-0.11.0`) when Foundry is missing. A Foundry that is already installed is used as is, whatever its version.

## Build and CI

- **Unsigned installer:** the MSI and Burn bundle are unsigned. Neither the `winui-arm64` workflow nor the WiX projects has a code-signing certificate. Before a wide release this needs a decision: buy a certificate, self-sign, or ship unsigned and document the SmartScreen click-through.
- **CI can pass with a missing installer:** a failed backend payload step fails the build, because `prepare-payload.ps1` stops on any uv error and checks that `Scripts\jarvis.exe` exists. The MSI and Burn steps in `publish-arm64.ps1` don't: they warn and return. The workflow also uploads those artifacts with `if-no-files-found: warn`, so a missing MSI or bundle doesn't fail the `winui-arm64` job. The workflow's only tests are the Python `tests/server` / `tests/engine` suites. There is no build-output check or UI test of the WinUI app, and the payload build (including its clang requirement) hasn't been run on the `windows-11-arm` runner.
- **XAML compiler warnings:** the build reports 3 `WMC1506` warnings (OneWay bindings without change notification) in `Views/ApprovalsPage.xaml`, lines 33–35. They don't affect the build.
- **Developing on native ARM64 Python:** `--extra dev` includes `datasets`, which needs `pyarrow`, and pyarrow has no Windows ARM64 wheels. So `uv sync --extra dev` fails on native ARM64 Python while it tries to build pyarrow from source. Use x64 Python 3.13 (it runs under emulation) for a dev environment and the test suite. Building `openjarvis_rust` for that Python on an ARM64 machine is a cross-compile:

    - install the `x86_64-pc-windows-msvc` Rust target;
    - set `PYO3_CROSS_PYTHON_VERSION=3.13`;
    - set `PYO3_CROSS_LIB_DIR` to that Python's `libs` folder.

    The installer payload doesn't need any of this: it uses native ARM64 Python and no `dev` extra.

## Updates and uninstall

- **Updates don't refresh the backend runtime.** On launch, `RuntimeBootstrap` copies `payload\python`, `payload\venv` and `payload\src` to `%LOCALAPPDATA%\OpenJarvis` only if they aren't already there. Installing a newer build therefore updates the WinUI app but keeps the old Python backend. To pick up a new backend, close OpenJarvis and delete `%LOCALAPPDATA%\OpenJarvis\python`, `venv` and `src`; the next launch copies them from the new install. Don't use `uninstall-cleanup.ps1 -RemoveData` for this: it also deletes `%USERPROFILE%\.openjarvis` (conversations, settings, keys).
- **In-app update check:** it reads `UpdateManifestUrl` from `appsettings.json`. A missing file, an empty URL, or a failed download skips the check without an error (`UpdateChecker.cs`). `windows/scripts/make-update-manifest.ps1` generates the manifest the checker expects. Until a GitHub release with a Burn bundle and that manifest is published, the check always skips.
- **Uninstall:** Apps & Features removes the app. These are **not** removed:

    - `%USERPROFILE%\.openjarvis` (conversations, settings, keys);
    - `%LOCALAPPDATA%\OpenJarvis`, including the ~230 MB backend runtime;
    - downloaded Foundry models.

    `windows/scripts/uninstall-cleanup.ps1` `-RemoveData` deletes both folders. It's a separate, manual step, not part of the MSI/Burn uninstall.

## Open decisions

- **Installer signing:** a certificate decision, not an engineering fix.
- **First GitHub release:** needed before the in-app update check can find anything.
