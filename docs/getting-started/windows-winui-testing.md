---
title: Testing the WinUI app
description: Install a build of the WinUI ARM64 app and reproduce the acceptance test setup and checks
---

# Testing the WinUI app

How to install a build of the WinUI ARM64 app and run the checks behind the [acceptance checklist](windows-winui-acceptance.md) on your own machine. The scripts are in `windows/scripts` and run in Windows PowerShell 5.1, which ships with Windows.

## 1. Get a build

**From CI (no build tools needed):**

1. Open the repository's **Actions** tab on GitHub, select the **WinUI ARM64** workflow, and open the run for the commit you're testing. You need to be signed in to GitHub.
2. Under **Artifacts**, download **OpenJarvis-1.0.0-arm64-bundle** and unzip it to get `OpenJarvis-1.0.0-arm64.exe`.

**From source:** follow [Build from source](windows-winui.md#build-from-source-developers). The bundle is written to `dist\OpenJarvis-1.0.0-arm64.exe`.

You also need the scripts. Clone the branch you're testing:

```powershell
git clone --branch <branch> https://github.com/<owner>/OpenJarvis.git
cd OpenJarvis
```

## 2. Install

1. If an earlier build is installed, uninstall it from Settings → Apps → Installed apps.
2. Run `OpenJarvis-1.0.0-arm64.exe`. The build is unsigned: at the SmartScreen prompt select **More info → Run anyway**, then approve the administrator prompt.
3. Don't launch the app from the installer. Start it from the test profile in the next step.

## 3. Start from a clean test profile

Run these from the repository folder in **one** PowerShell window, and keep using that window for the checks. The profile setting only applies to apps started from it.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\scripts\new-test-profile.ps1 -ResetRuntime -Launch
```

The script:

- creates an empty profile in `%TEMP%\openjarvis-test-profile` and sets `OPENJARVIS_HOME` to it, so your own conversations, settings and keys in `%USERPROFILE%\.openjarvis` aren't used or changed;
- writes a `config.toml` that keeps inference local (`[engine] default = "foundry_local"`, `allow_cloud = false`);
- with `-ResetRuntime`, deletes the backend runtime in `%LOCALAPPDATA%\OpenJarvis` (`python`, `venv`, `src`), so the app copies it fresh from the installed build, just like a first install;
- with `-Launch`, starts the installed app with this profile.

The app opens on the local-AI consent screen. Leave it there for the UI check, or accept it yourself.

Models stay downloaded in Foundry Local between runs, so only the first test on a machine downloads the model (several GB).

## 4. Run the checks

In the same window:

```powershell
.\windows\scripts\test-ui.ps1
.\windows\scripts\test-backend.ps1 -CrashTest
.\windows\scripts\measure-performance.ps1
```

Each check script prints one PASS/FAIL line per check, and exits with code 1 if any check fails.

| Script | Checks | Checklist rows |
|--------|--------|----------------|
| `test-ui.ps1` | Accepts the consent screen if it's showing (and checks nothing started before that), waits for setup, sends a chat message and waits for the saved reply, presses **Stop** mid-reply, then restarts the app and looks for the conversation in history | Consent, setup, chat streaming, Stop, history after restart |
| `test-backend.ps1 -CrashTest` | `/health`; `/v1/info` (model, execution provider, CPU fallback, cloud setting, tool support); a streamed chat with time to first token and decode speed; cancelling a stream; memory store and search; killing `jarvis.exe` and timing recovery | Status, cloud off, chat, cancel, memory, crash recovery |
| `measure-performance.ps1` | Time to first token, tokens per second (estimated from the stream), execution provider, and memory use of `OpenJarvis`, the backend and `foundrylocald` | Performance table |

`test-ui.ps1` drives the app through Windows UI Automation. Don't use the mouse or keyboard while it runs. `measure-performance.ps1` writes its results to `docs\getting-started\windows-winui-perf-last.json` (git-ignored).

To time first launch and relaunch as in the performance table, run `new-test-profile.ps1` with and without `-ResetRuntime` (close the app first). Time from launch until `test-backend.ps1` or `Invoke-WebRequest http://127.0.0.1:8000/health` first succeeds.

## 5. Manual checks

These have no script. Follow the [demo walkthrough](windows-winui.md#demo-walkthrough) for:

- Dashboard, Data Sources, Agents, Approvals, Logs, Settings and the Ctrl+K palette
- Narrator (Ctrl+Win+Enter), display scaling at 100%, 150% and 200%, and touch
- Offline chat: turn off networking after setup, restart the app, and chat
- Deep Research: in **Data Sources → Connectors**, connect a folder of Markdown notes with **Obsidian / Markdown**, then turn on **Deep Research** in Chat and ask a question the notes answer. The research timeline should show at least one search with hits from your notes, and the answer should use their contents. Deep Research searches connected data only, not the web.
- Uninstall: the app is removed, and the profile and `%LOCALAPPDATA%\OpenJarvis` remain

## 6. Python tests (optional)

The backend test suite needs a development environment. `--extra dev` can't be installed on native ARM64 Python (see [known issues](windows-winui-known-issues.md)), so use x64 Python, which runs under emulation. Install the Rust x64 target with `rustup target add x86_64-pc-windows-msvc`, then:

```powershell
uv python install cpython-3.13-windows-x86_64-none
$libs = Join-Path (Split-Path (uv python find cpython-3.13-windows-x86_64-none --system --no-project)) "libs"
$env:PYO3_CROSS_PYTHON_VERSION = "3.13"
$env:PYO3_CROSS_LIB_DIR = $libs
uv sync --python cpython-3.13-windows-x86_64-none --extra dev --extra server --group desktop-native
uv run pytest tests -n auto -q -m "not live and not cloud and not hub"
```

The test selection is the same as CI's.

## 7. Report results

Include:

- `winver` build number, device model, RAM, and GPU driver version (`Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion`)
- `foundry --version`
- the output of `test-ui.ps1` and `test-backend.ps1 -CrashTest`, and `windows-winui-perf-last.json`
- results of the manual checks
- `%LOCALAPPDATA%\OpenJarvis\logs\jarvis-serve.log` if anything fails

## 8. Clean up

Close OpenJarvis, then:

```powershell
.\windows\scripts\new-test-profile.ps1 -ResetRuntime
Remove-Item -Recurse -Force "$env:TEMP\openjarvis-test-profile"
```

Uninstall the app from Settings → Apps if you no longer need it. Foundry Local and its models stay installed.
