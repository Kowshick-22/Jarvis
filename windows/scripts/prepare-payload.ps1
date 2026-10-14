# Stages a standalone ARM64 CPython plus a relocatable venv with OpenJarvis
# (--extra server --group desktop-native) next to the published WinUI app.
# RuntimeBootstrap copies both to %LOCALAPPDATA%\OpenJarvis and repoints the
# venv's pyvenv.cfg at the copied interpreter on first launch.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PublishDir,
    [string]$PythonVersion = "3.12",
    [string]$FoundryVersion = "0.11.0"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Payload = Join-Path $PublishDir "payload"
New-Item -ItemType Directory -Force -Path $Payload | Out-Null

$Arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
if ($Arch -ne "Arm64") {
    Write-Warning "This script is intended for Windows ARM64. Current architecture: $Arch"
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is not on PATH. Install it (winget install astral-sh.uv) and re-run prepare-payload.ps1."
}

# openjarvis_rust pulls ring (via rustls), which needs clang to build for
# aarch64-pc-windows-msvc. The LLVM installer doesn't add itself to PATH.
if (-not (Get-Command clang -ErrorAction SilentlyContinue)) {
    $LlvmBin = Join-Path $env:ProgramFiles "LLVM\bin"
    if (Test-Path (Join-Path $LlvmBin "clang.exe")) {
        $env:PATH = "$LlvmBin;$env:PATH"
    } else {
        throw "clang not found. Install LLVM (winget install LLVM.LLVM) and re-run prepare-payload.ps1."
    }
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo not found. Install Rust (winget install Rustlang.Rustup) and open a new terminal."
}

# Judge native commands by exit code only. Under Windows PowerShell 5.1, a
# redirected stderr line (uv's progress output) becomes an ErrorRecord, which
# "Stop" would turn into a false failure.
function Invoke-Native([string]$What, [scriptblock]$Command) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Command } finally { $ErrorActionPreference = $prev }
    if ($LASTEXITCODE -ne 0) { throw "$What failed with exit $LASTEXITCODE" }
}

# Native ARM64 CPython: an x64 interpreter would run under emulation.
$PythonRequest = "cpython-$PythonVersion-windows-aarch64-none"
$Venv = Join-Path $Payload "venv"
$PythonDir = Join-Path $Payload "python"
foreach ($dir in @($Venv, $PythonDir)) {
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
}
Invoke-Native "uv python install" { uv python install $PythonRequest }

# Ship the interpreter itself: a venv only records the absolute path of its
# base Python, which won't exist on the user's machine. uv's managed builds
# (python-build-standalone) are self-contained and safe to copy.
$FoundPython = (& uv python find --system --no-project $PythonRequest | Select-Object -Last 1)
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $FoundPython)) {
    throw "uv python find $PythonRequest failed."
}
# Ask the interpreter for its install root: this skips any venv and resolves
# uv's minor-version junction (cpython-3.12-... -> cpython-3.12.N-...).
$BasePrefix = (& $FoundPython -c "import os, sys; print(os.path.realpath(sys.base_prefix))" | Select-Object -Last 1)
if (-not (Test-Path (Join-Path $BasePrefix "python.exe"))) {
    throw "Could not resolve the CPython install directory (got '$BasePrefix')."
}
Copy-Item -Recurse -Force $BasePrefix $PythonDir

# --relocatable makes entry points like jarvis.exe find python by relative path.
Invoke-Native "uv venv" { uv venv $Venv --relocatable --python (Join-Path $PythonDir "python.exe") }

Write-Host "Syncing OpenJarvis (server extra + desktop-native Rust extension)..."
# Point uv's project environment at the payload venv so the checkout's own
# .venv is left alone, and install non-editable so the venv doesn't reference
# this checkout.
$PrevProjectEnv = $Env:UV_PROJECT_ENVIRONMENT
$Env:UV_PROJECT_ENVIRONMENT = $Venv
Push-Location $Root
try {
    Invoke-Native "uv sync" {
        uv sync --frozen --no-editable --python (Join-Path $PythonDir "python.exe") --extra server --group desktop-native
    }
} finally {
    Pop-Location
    $Env:UV_PROJECT_ENVIRONMENT = $PrevProjectEnv
}

if (-not (Test-Path (Join-Path $Venv "Scripts\jarvis.exe"))) {
    throw "Payload venv has no Scripts\jarvis.exe after uv sync."
}

# Stage a minimal source tree for uv run fallbacks and config discovery.
$PayloadSrc = Join-Path $Payload "src"
New-Item -ItemType Directory -Force -Path $PayloadSrc | Out-Null
foreach ($item in @("src", "pyproject.toml", "configs", "README.md")) {
    $from = Join-Path $Root $item
    if (Test-Path $from) {
        Copy-Item -Recurse -Force $from (Join-Path $PayloadSrc (Split-Path $item -Leaf))
    }
}

$FoundryNotes = @"
Foundry Local $FoundryVersion (ARM64)
OpenJarvis Setup installs Foundry Local automatically (no terminal).
Manual fallback:
  https://github.com/microsoft/Foundry-Local/releases/tag/cli-preview-$FoundryVersion
  Add-AppxPackage .\foundry-$FoundryVersion-win-arm64-winml.msix
  (or foundry-$FoundryVersion-win-arm64.msix on 0.11+)
  foundry server start
"@
Set-Content -Path (Join-Path $Payload "FOUNDRY_LOCAL.txt") -Value $FoundryNotes

$InstallCmd = Join-Path $Payload "install-runtime.ps1"
@'
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Dest = Join-Path $env:LOCALAPPDATA "OpenJarvis"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
if (Test-Path (Join-Path $Root "python")) {
    Copy-Item -Recurse -Force (Join-Path $Root "python") (Join-Path $Dest "python")
}
if (Test-Path (Join-Path $Root "venv")) {
    Copy-Item -Recurse -Force (Join-Path $Root "venv") (Join-Path $Dest "venv")
    $Cfg = Join-Path $Dest "venv\pyvenv.cfg"
    (Get-Content $Cfg) -replace '^home = .*', "home = $(Join-Path $Dest 'python')" | Set-Content $Cfg
}
if (Test-Path (Join-Path $Root "src")) {
    Copy-Item -Recurse -Force (Join-Path $Root "src") (Join-Path $Dest "src")
}
Write-Host "Runtime staged under $Dest"
'@ | Set-Content -Path $InstallCmd

Write-Host "Payload staged at $Payload"
