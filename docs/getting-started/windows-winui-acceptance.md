---
title: WinUI ARM64 acceptance
description: Feature checklist, performance table, and how to measure on Surface Laptop Ultra
---

# WinUI ARM64 acceptance

Run this on a Surface Laptop Ultra (NVIDIA RTX Spark N1X, Windows 11 26H1, ARM64). Fill in the measured columns. Do not invent numbers.

Script: [`windows/scripts/measure-performance.ps1`](../../windows/scripts/measure-performance.ps1)

```powershell
# After OpenJarvis is installed and Setup has finished:
.\windows\scripts\measure-performance.ps1 -Model Phi-4-mini-instruct
```

## Performance

Named model: **Phi-4-mini-instruct** (Foundry catalog alias; record the resolved id from `GET /v1/info`).

| Metric | Result | How measured |
|--------|--------|--------------|
| Resolved model id | _pending device run_ | `/v1/info` `model` |
| Execution provider | _pending device run_ | `/v1/info` `hardware.execution_provider` |
| CPU fallback | _pending device run_ | `/v1/info` `hardware.execution_provider_fallback` |
| Cold start (ms) | _pending device run_ | Process start until `GET /health` returns 200 |
| Time to first token (ms) | _pending device run_ | First SSE `choices[0].delta.content` |
| Tokens per second | _pending device run_ | `completion_tokens / elapsed seconds` after first token |
| Working set — OpenJarvis.exe (MB) | _pending device run_ | Process working set |
| Working set — jarvis / python (MB) | _pending device run_ | Process working set |
| Working set — Foundry (MB) | _pending device run_ | Process working set |

If the NVIDIA EP does not register on N1X, leave the row as CPU/WebGPU and set **CPU fallback** to yes.

## Feature checklist

| Item | Pass? | Notes |
|------|-------|-------|
| ARM64 installer launches without Visual Studio / terminal | | |
| Setup shows download progress and a named error on failure | | |
| Chat streams tokens (SSE `/v1/chat/completions`) | | |
| Stop cancels the in-flight request | | |
| Conversation history survives restart | | |
| Model list comes from Foundry via `/v1/models` | | |
| Agent picker restarts serve (`simple` / `orchestrator` / `react`) | | |
| Tool activity cards appear on `tool_call_start` / `tool_call_end` | | |
| Approvals poll `/v1/approvals/pending` and approve/deny | | |
| Settings theme follows light / dark / system | | |
| Keyboard: tab order, Enter to send, access keys | | |
| Touch targets usable at 100% / 150% / 200% scale | | |
| Narrator reads message box, send, navigation | | |
| Status shows engine, model, execution provider | | |
| Offline chat after Setup (disconnect network) | | |
| Cloud toggle off: prompts stay local even if API keys exist | | |
| Cloud toggle on: explicit Settings save, then restart | | |
| Windows AI API probe listed in Settings (not used for chat) | | |
| Backend crash: UI stays responsive and recovers | | |
| Uninstall removes the app; data remains unless `-RemoveData` | | |

## Hardware notes (Surface Laptop Ultra)

- SoC: NVIDIA RTX Spark N1X (Grace CPU, Blackwell GPU, NVIDIA NPU, unified memory)
- Qualcomm QNN is the wrong accelerator for this SKU
- Minimum RAM config is 24 GB; `Phi-4-mini-instruct` is the default alias for that band
