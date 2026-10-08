# Requires: Windows ARM64, .NET 9 SDK, Visual Studio 2022 WinUI workload, Rust aarch64-pc-windows-msvc, WiX 5, uv.
# Produces: dist/OpenJarvis-win-arm64/ (app) and dist/OpenJarvis-1.0.0-arm64.msi
[CmdletBinding()]
param(
    [string]$Configuration = "Release",
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$WinUi = Join-Path $Root "windows\OpenJarvis.WinUI"
$PublishDir = Join-Path $WinUi "bin\publish\win-arm64"
$Dist = Join-Path $Root "dist\OpenJarvis-win-arm64"

Write-Host "Publishing WinUI ARM64 app..."
dotnet publish $WinUi -c $Configuration -r win-arm64 --self-contained true `
    /p:Platform=ARM64 /p:WindowsAppSDKSelfContained=true `
    -o $PublishDir

Write-Host "Preparing backend payload..."
& (Join-Path $PSScriptRoot "prepare-payload.ps1") -PublishDir $PublishDir

if (Get-Command wix -ErrorAction SilentlyContinue) {
    Write-Host "Building MSI..."
    $InstallerDir = Join-Path $Root "windows\installer"
    Push-Location $InstallerDir
    try {
        dotnet build OpenJarvis.Installer.wixproj -c $Configuration -p:PublishDir=$PublishDir
    } finally {
        Pop-Location
    }
} else {
    Write-Host "WiX is not on PATH. Skipping MSI. Zip the publish folder for a sideload build."
}

New-Item -ItemType Directory -Force -Path $Dist | Out-Null
Copy-Item -Recurse -Force "$PublishDir\*" $Dist
Write-Host "Output: $Dist"
