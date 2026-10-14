---
title: WinUI ARM64 version pins
description: Windows, SDK, Foundry Local, Python, and driver versions for the WinUI 3 OpenJarvis build
---

# WinUI ARM64 version pins

Versions and tools needed to build and run the WinUI app. Update this page whenever a pin changes.

| Component | Version | Notes |
|-----------|---------|-------|
| Windows | Windows 11 24H2, build **26100** or later | [Foundry Local get started](https://learn.microsoft.com/en-us/windows/ai/foundry-local/get-started) |
| Surface Laptop Ultra OS | Windows 11 **26H1** | N1X devices do not install 26H2; they wait for a later branch |
| Architecture | ARM64 only | x64 installers are refused |
| .NET SDK | **9.0** or newer | Target `net9.0-windows10.0.26100.0` |
| Windows App SDK | **1.7.250606001** | Self-contained with the app |
| Windows SDK build tools | **10.0.26100.1742** | From the WinUI project |
| Visual Studio | 2022 or 2026 (v18), with the ARM64 C++ build tools and Windows 11 SDK (26100) | MSBuild compiles the XAML; `publish-arm64.ps1` falls back to `dotnet publish` if it finds no MSBuild. The MSVC linker also links `openjarvis_rust`. The WinUI workload isn't required: the Windows App SDK comes from NuGet |
| WiX | **5.0.2** | MSI + Burn bundle (`dotnet tool install --global wix --version 5.0.2`) |
| uv | **0.12.19** or newer | Builds the payload from `uv.lock` with `uv sync --frozen`. 0.12.19 is the version the security CI job pins |
| CPython (shipped) | **3.12**, `cpython-3.12-windows-aarch64-none` (uv-managed python-build-standalone) | Copied into the installer as `payload\python`. Native ARM64, so no x64 emulation. The project requires Python < 3.14 |
| numpy | **>= 2.3** on Python 3.11+ | 2.3 is the first numpy with Windows ARM64 wheels. Resolves to 2.3.5 for the shipped Python |
| Rust | **1.88**, `aarch64-pc-windows-msvc` | Pinned by `rust/rust-toolchain.toml`. `uv sync --group desktop-native` builds `openjarvis_rust` |
| LLVM (clang) | Any recent release (`winget install LLVM.LLVM`) | `openjarvis_rust` depends on `ring` (through `rustls`), which needs clang to build for `aarch64-pc-windows-msvc`. `prepare-payload.ps1` adds `C:\Program Files\LLVM\bin` to PATH if clang isn't already on it |
| Foundry Local | **0.11.0** `foundry-0.11.0-win-arm64.msix`. Setup tries `foundry-0.11.0-win-arm64-winml.msix` first, but the 0.11.0 release doesn't publish it (404), so the plain MSIX is what installs | Installed by Setup via `Add-AppxPackage` when `foundry.exe` is missing; release tag `cli-preview-0.11.0`. An already-installed Foundry is used as is, whatever its version |
| Windows ML | Foundry Local 0.11.x / WinML 2.0 | Execution providers downloaded on first run |
| NVIDIA GPU driver | Use the Surface / NVIDIA ARM64 driver for RTX Spark N1X | Floor is whatever Windows Update ships for this SKU; record the exact version on the device in the acceptance doc |
| CUDA (if TensorRT RTX / CUDA EP) | **12.5** recommended by Foundry Local NVIDIA EPs | Confirm on-device; N1X may use a vendor stack instead of desktop CUDA |
| Default model | **Phi-4-mini-instruct** (Foundry 0.11 alias: `phi-4-mini`) | Setup resolves it to a versioned catalog id, trying GPU, then NPU, then CPU variants, and falls back to the CPU variant if the GPU load fails. On a VM without a GPU this ends at `Phi-4-mini-instruct-generic-cpu:5` |

## Execution providers (Foundry Local + Windows ML)

| Provider | Hardware | Expected on Surface Laptop Ultra |
|----------|----------|----------------------------------|
| `NvTensorRTRTXExecutionProvider` | NVIDIA RTX 30-series and later | Preferred if the ARM64 plugin registers |
| `CUDAExecutionProvider` | NVIDIA GPU | Alternate GPU path |
| `WebGPUExecutionProvider` | GPU fallback | Used if NVIDIA plugins are missing |
| `CPUExecutionProvider` | Any CPU | Documented fallback; the UI labels it “CPU fallback” |
| `QNNExecutionProvider` | Qualcomm NPU | Not this device (NVIDIA SoC, not Snapdragon) |

## Preview / Insider

Foundry Local with Windows ML is generally available. Surface Laptop Ultra’s 26H1 image is a device-specific Windows branch, not a Windows Insider channel. No extra Insider flight is required beyond that OEM image.

## Backend extras

The installer's Python payload is `--extra server --group desktop-native` only.

- `openjarvis[desktop]` pulls `faster-whisper` / `ctranslate2`, which don't have reliable Windows ARM64 wheels, so backend speech isn't installed. The WinUI app does dictation and read-aloud with Windows' own speech APIs instead.
- `datasets` (benchmark loaders) is in the `eval` and `dev` extras, not the base install, because it pulls in `pyarrow`, which has no Windows ARM64 wheels.
