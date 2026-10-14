# Creates an isolated OpenJarvis profile for testing (OPENJARVIS_HOME) with
# local-only settings, and can reset the app to a clean first launch.
# Your real profile (%USERPROFILE%\.openjarvis) is never touched.
[CmdletBinding()]
param(
    # Folder for the test profile. Emptied and recreated on every run.
    [string]$ProfileDir = (Join-Path $env:TEMP "openjarvis-test-profile"),
    # Delete the copied backend runtime (%LOCALAPPDATA%\OpenJarvis\python,
    # venv, src) so the next launch copies it fresh from the install.
    [switch]$ResetRuntime,
    # Start the installed app with this profile once it's ready.
    [switch]$Launch,
    [string]$AppPath = (Join-Path $env:ProgramFiles "OpenJarvis\OpenJarvis.exe")
)

$ErrorActionPreference = "Stop"

if ($ResetRuntime -or $Launch) {
    if (Get-Process -Name OpenJarvis, jarvis -ErrorAction SilentlyContinue) {
        throw "OpenJarvis is running. Close it (and any jarvis.exe) first."
    }
}

if (Test-Path $ProfileDir) { Remove-Item -Recurse -Force $ProfileDir }
New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null
# Python's TOML parser rejects a byte-order mark, so write UTF-8 without one.
$config = "[engine]`ndefault = `"foundry_local`"`nallow_cloud = false`n"
[IO.File]::WriteAllText((Join-Path $ProfileDir "config.toml"), $config, (New-Object Text.UTF8Encoding $false))
Write-Host "Test profile: $ProfileDir (local inference only, cloud off)"

if ($ResetRuntime) {
    $runtime = Join-Path $env:LOCALAPPDATA "OpenJarvis"
    foreach ($name in @("python", "venv", "src")) {
        $dir = Join-Path $runtime $name
        if (Test-Path $dir) {
            # \\?\ lets .NET delete paths longer than 260 characters.
            [IO.Directory]::Delete("\\?\$dir", $true)
            Write-Host "Removed $dir"
        }
    }
}

if ($Launch) {
    if (-not (Test-Path $AppPath)) { throw "OpenJarvis is not installed at $AppPath." }
    $env:OPENJARVIS_HOME = $ProfileDir
    $app = Start-Process -FilePath $AppPath -PassThru
    Write-Host "Started OpenJarvis (PID $($app.Id)) with OPENJARVIS_HOME=$ProfileDir"
} else {
    Write-Host "To use it:"
    Write-Host "  `$env:OPENJARVIS_HOME = '$ProfileDir'"
    Write-Host "  & '$AppPath'"
}
