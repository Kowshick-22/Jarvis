# Local OpenJarvis with native Codex

This fork is independent of the former voice-satellite deployment repository.
Its integration branch is `develop`; changes are reviewed before activation.
The official base is `091068cb94804f4dfbe57af2114adba89245612b`.

## Scope

The native CloudEngine sends Responses requests directly to ChatGPT. No CLI
inference bridge, proxy backend or old satellite process is used. ChatGPT
inference remains remote; local Whisper and Kokoro keep audio on the computer.
The browser's microphone button performs dictation. This installation does not
provide an always-listening wake-word service.

The transport correction handles ChatGPT SSE, assistant history and native
model routing. The configured Codex model remains first in the browser model
list and is accepted at startup even when the built-in catalog is outdated.

## Local account authentication (explicit opt-in)

Keep an existing `codex login` session. The following environment variables
contain configuration, not credentials:

```sh
export OPENAI_CODEX_USE_LOCAL_AUTH=1
export OPENAI_CODEX_BASE_URL=https://chatgpt.com/backend-api/codex
```

The engine reads the user's private Codex auth cache into memory for each
request. It does not copy credentials into this repository, configuration,
command arguments or logs. An explicit `OPENAI_CODEX_API_KEY` retains precedence
for existing users; unset it to use local account authentication.

Within two minutes of token expiry, the engine asks `codex app-server` to renew
its managed ChatGPT session with `account/read` and `refreshToken=true`. Codex
owns token rotation and cache writes. The helper sends initialization and
account methods only; it creates no agent thread and runs no model or tool.
The process has a 45-second deadline and is terminated/reaped afterward.
Refresh failures are sanitized and backed off for 60 seconds. Revoked sessions
or revoked access can still require the user to sign in again; no unattended
software can guarantee permanent authentication.

Reference: https://learn.chatgpt.com/docs/app-server#auth-endpoints

## Installation and startup

Use the official README/manual installation procedure in this checkout and its
own Python environment. The optional `desktop` and `voice` extras enable local
dictation and speech. CPU-only PyTorch avoids installing CUDA for Kokoro.

Keep private runtime configuration outside Git under
`~/.local/share/openjarvis-official-trial/config.toml`. On the tested notebook,
the configured speech backends are Faster-Whisper small/CPU/int8 and Kokoro
pm_alex/0.90/CPU, in Brazilian Portuguese. These are application configuration,
not source overrides.

After review and merge, run using this checkout's Python:

```sh
.venv/bin/python scripts/launch-local-codex.py
```

The launcher starts the official daemon with explicit cloud/model/simple-agent
arguments, binds only `127.0.0.1:8001`, waits for readiness, then opens the UI.
It reuses an already-ready server and does not replace another process. It
does not create a systemd service or enable login startup.

Stop only this installation:

```sh
OPENJARVIS_HOME="$HOME/.local/share/openjarvis-official-trial" .venv/bin/jarvis stop
```

Do not reactivate the old satellite or alter the pinned server/voice checkouts.

## Evidence and limits

Run the network-free contract tests with the existing installed dependencies:

```sh
PYTHONPATH=src .venv/bin/python -B tests/native_codex_contract.py
```

The tests cover Responses transport/history/errors, browser model ordering,
startup selection, private-cache rotation, refresh error backoff, helper process
cleanup, credential destination restrictions and launcher behavior. A live
isolated check also renewed the managed Codex session and obtained a correct
synthetic response through the native engine. No private transcript or audio is
part of these tests.

Chat and browser microphone/response playback were validated with the previous
reviewed transport correction. This additional auth/startup patch is isolated
until review and merge; those earlier UI results do not claim it is deployed.
The simple agent provides chat, not an autonomous executor or automatic access
to the user's Codex app plugins. Optional external connectors need their own
configuration and authorization. Reboot/login persistence is not claimed.
