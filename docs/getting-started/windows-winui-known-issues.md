---
title: WinUI known issues and limitations
description: Scope cuts vs Tauri, Parallels caveats, and upstream Ultra notes
---

# WinUI known issues and limitations

## Intentional scope (vs Tauri/React desktop)

The WinUI shell matches the acceptance checklist (chat, stream, cancel, history, model/agent, settings, tool activity, approvals). It is **not** a full port of the React app.

| Not in WinUI | Notes |
|--------------|-------|
| Managed Agents studio | Serve-time agents (`simple` / `orchestrator` / `react`) only |
| Data Sources / connectors UI | Backend routes still available on localhost |
| Memory browser UI | Same |
| Dashboard / energy / traces | Same |
| Deep Research mode | Same |
| Speech (STT/TTS) | No reliable Windows ARM64 wheels |
| Markdown / math / code highlight | Plain text message bubbles |
| Command palette / model pull UI | Combo of `/v1/models` only |
| Cloud API key vault UI | Cloud stays off until Settings → Allow cloud; keys not managed in WinUI |
| Approvals bell overlay | Dedicated Approvals page |

## Runtime / hardware

Retested on this Parallels guest on 2026-10-12 (Windows 11 26H2 build 26300, 6 GB RAM). The unpackaged debug build of `OpenJarvis.exe` stayed up through Chat, Approvals, Setup, and Settings (~222 MB working set, idle on Chat). No new `APPCRASH`.

- **Parallels / VMs without a GPU:** Setup falls back to `*-generic-cpu` catalog ids when GPU/WebGPU load fails. This guest’s display is the Parallels Display Adapter (0 B). Settings and `/v1/info` report `CPUExecutionProvider`, CPU fallback, and no GPU. The live serve model was `gemma-4-e2b-it-generic-cpu:3`.
- **Foundry model ids:** Chat completions need the versioned catalog id, for example `Phi-4-mini-instruct-generic-cpu:5` or `Phi-4-mini-instruct-generic-gpu:5` (`foundry model info phi-4-mini`). The short alias alone is not the id the server is using.
- **Tool calling on the loaded CPU model:** `/v1/info` for `gemma-4-e2b-it-generic-cpu:3` reports tools unsupported. Foundry returned HTTP 500 during the tool probe (its tool template failed while reading `function.name`). The Chat status line shows “tools unavailable”. **Confirmed 2026-10-12: this is a bug in Foundry Local's own packaged chat template for `gemma-4-e2b-it`, not OpenJarvis code** — relaunching the WinUI shell headlessly and hitting `/v1/info` reproduces the identical Jinja2 traceback (`Trying to access property 'name' on null! at row 93`) straight from Foundry. There is nothing to patch on our side; avoid that catalog id until Foundry ships a fix.
- **Tool-calling probe false negative — fixed 2026-10-12:** `check_tool_calling()` in [`foundry_local.py`](../../src/openjarvis/engine/foundry_local.py) sent `max_tokens: 64`, which truncated reasoning models (Qwen3, DeepSeek-R1, Phi-4-mini-reasoning — all marked tool-capable in the Foundry catalog) before they finished spending tokens on `reasoning_content` and got to the actual `tool_calls` payload (`finish_reason: "length"`). The probe then reported `supported: false`, even though the model genuinely supports tool calling. Raised to `max_tokens: 512` and added a distinct "truncated before completing a tool call" reason for when it still happens. Verified live: `qwen3-0.6b-generic-cpu:4` went from a false `tool_calling.supported: false` to a correct `true` in `/v1/info`, confirmed against the real shipped WinUI shell (not just a unit test). Regression tests added in `tests/engine/test_foundry_local.py`.
- **Small reasoning models don't reliably call tools through `native_react` — model limitation, not a bug:** with `qwen3-0.6b-generic-cpu:4` (the only tool-capable model that fits this VM's ~1.3 GB free RAM) loaded under the `react` agent, asking it to use the `calculator` tool for arithmetic it can't do in its head (`847 * 293`, `29384 * 9283`) returns a wrong, hallucinated answer with `tool_calls: null` — it never emits the `Action:`/`Thought:` structure `native_react`'s text protocol expects, even when told explicitly to use the tool. No error is logged; the model simply answers directly. This is consistent with the project's documented default (`Phi-4-mini-instruct`, ~3.8B) being the real target model — it needs ~5 GB free RAM that this 6 GB VM doesn't have. **Tool use through a real agent conversation is still unverified end-to-end on this hardware**; it needs either more RAM on this VM or the Surface Ultra (24 GB).
- **Surface Laptop Ultra acceleration evidence:** Fill EP / NVIDIA rows on-device after upstream push. Parallels results do not prove N1X GPU/NPU.
- **RAM:** This guest has 6.0 GB total and about 1.1–1.5 GB free with Foundry already running. Cached `phi-4-mini` CPU weights are 4.8 GB (GPU/WebGPU variant 3.7 GB); cached `gemma-4-e2b-it` CPU weights are 5.9 GB. `qwen3-0.6b-generic-cpu` (593 MB) is the only tool-capable catalog id confirmed to load on this VM. Use a smaller CPU catalog id on a 6 GB VM.
- **Unsigned installer:** CI and local Burn/MSI builds are unsigned. The `winui-arm64` workflow and WiX projects have no signing cert. **Unresolved — needs a decision**: buy a code-signing cert, self-sign and accept the SmartScreen warning, or ship unsigned and document the click-through. Not something that can be fixed without that choice.
- **Foundry version:** Setup pins Foundry Local **0.11.0** (`cli-preview-0.11.0`). This guest’s CLI and daemon are both 0.11.0. Older docs mentioning 0.10.1 WinML assets still work as a manual fallback.
- **Backend crash recovery — verified 2026-10-12:** killed the supervised `jarvis.exe` child process directly while `OpenJarvis.exe` (the WinUI shell) stayed running. The shell's `BackendSupervisor` detected the gap, relaunched `jarvis serve` with a fresh PID, and `/health` returned 200 again within ~15 seconds — all without the WinUI window restarting or losing responsiveness.
- **Backend-not-installed error path — verified 2026-10-12:** installed the Burn bundle without the backend payload (`-SkipPayload`, simulating a build where the Python/Rust runtime wasn't bundled) and launched the installed `Program Files\OpenJarvis\OpenJarvis.exe`. `AppPaths.DevProjectRoot()` correctly found no dev checkout above `Program Files\OpenJarvis`, `JarvisExecutable()` returned empty, and `BackendSupervisor` threw the intended `"The OpenJarvis backend is not installed. Repair or reinstall OpenJarvis from Apps & Features."` — surfaced via the MainWindow `ErrorBar` with exponential backoff retry, not a hang or silent failure.
- **Burn bundle (the actual end-user installer) — verified end-to-end 2026-10-12:** built fresh via `publish-arm64.ps1 -SkipPayload` on this ARM64 host and ran `OpenJarvis-1.0.0-arm64.exe /quiet`. The `NativeMachine = 43620` condition evaluated true, the MSI applied (exit 0x0), and the app registered twice in Apps & Features (bundle + MSI) as expected for a Burn/MSI pair. Previously only the inner MSI had been confirmed; this closes that gap. Uninstalled the same way afterward (`/uninstall /quiet`) — both registry entries and `C:\Program Files\OpenJarvis` were removed cleanly, while `%USERPROFILE%\.openjarvis\winui-conversations.json` (user data) was left in place, matching the documented behavior below. **Not re-verified in this pass:** the full backend-payload bundling step (`prepare-payload.ps1` — fresh embeddable CPython download + `openjarvis_rust` compiled from source via `uv sync --group desktop-native`) was skipped here to avoid a heavy Rust build on this VM's ~1.3 GB free RAM; that path is already exercised by the `winui-arm64` GitHub Actions workflow on a proper `windows-11-arm` runner.

## Updates and uninstall

- In-app update checks use `UpdateManifestUrl` in `appsettings.json`. A missing `appsettings.json`, an empty URL, or a failed download skips the check. The pinned URL (`winui-arm64-latest.json` on the latest GitHub release) returned HTTP 404 on 2026-10-12, so this build finds no update, because **no release with that tag/asset has ever been published**. Added [`windows/scripts/make-update-manifest.ps1`](../../windows/scripts/make-update-manifest.ps1) to generate the manifest `UpdateChecker.cs` expects (`{Version, Url, Notes}`); it only writes the file — publishing an actual GitHub release with the Burn bundle + this manifest attached is still an outstanding step that needs sign-off, since it's a public, hard-to-reverse action.
- Uninstall via Apps & Features removes the app. User data under `%USERPROFILE%\.openjarvis` and Foundry models remain unless [`windows/scripts/uninstall-cleanup.ps1`](../../windows/scripts/uninstall-cleanup.ps1) `-RemoveData` is run. Verified 2026-10-12 via the Burn bundle's own `/uninstall` path (see above), not just the MSI.

## Outstanding decisions (not code fixes)

- **Scope cuts sign-off:** the "Intentional scope" table above (Speech, Managed Agents studio, Data Sources/connectors UI, Memory browser, Dashboard/energy/traces, Deep Research, Markdown/code rendering, command palette, cloud key vault) is documented here but has not been explicitly confirmed as agreed scope by the project owner. Needs an explicit yes/no.
- **Installer signing:** see above — needs a cert decision, not an engineering fix.
- **Cutting the first GitHub release:** needed before update-checking can do anything other than silently skip.
