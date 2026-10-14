# On-device acceptance measurements for Surface Laptop Ultra (or any Windows ARM64 host).
# Records time to first SSE token, tokens/sec, execution provider and
# working-set memory for a running OpenJarvis backend.
[CmdletBinding()]
param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    # Versioned Foundry catalog id. Defaults to the model the backend reports.
    [string]$Model = "",
    [string]$Prompt = "Write three sentences about Windows on ARM.",
    # Where to write the JSON. Defaults to docs/getting-started in a checkout,
    # otherwise the current folder.
    [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"
$Result = [ordered]@{
    device = $env:COMPUTERNAME
    os = [System.Environment]::OSVersion.VersionString
    arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    model = $Model
    execution_provider = ""
    cpu_fallback = $false
    # Wait for /health on an already running server, not app start-up time.
    cold_start_ms = $null
    time_to_first_token_ms = $null
    tokens_per_second = $null
    tokens_per_second_source = "usage"
    completion_tokens = $null
    working_set_mb = [ordered]@{}
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$deadline = (Get-Date).AddMinutes(10)
do {
    try {
        $health = Invoke-WebRequest -Uri "$ApiUrl/health" -UseBasicParsing -TimeoutSec 2
        if ($health.StatusCode -eq 200) { break }
    } catch {
        Start-Sleep -Milliseconds 500
    }
} while ((Get-Date) -lt $deadline)
$sw.Stop()
$Result.cold_start_ms = [int]$sw.Elapsed.TotalMilliseconds

try {
    $info = Invoke-RestMethod -Uri "$ApiUrl/v1/info"
    if (-not $Model) { $Model = $info.model }
    $Result.execution_provider = $info.hardware.execution_provider
    $Result.cpu_fallback = [bool]$info.hardware.execution_provider_fallback
} catch {
    Write-Warning "Could not read /v1/info"
}
if (-not $Model) { throw "No model given and /v1/info didn't report one. Pass -Model <catalog id>." }
$Result.model = $Model

$body = @{
    model = $Model
    stream = $true
    max_tokens = 128
    messages = @(@{ role = "user"; content = $Prompt })
} | ConvertTo-Json
$req = [System.Net.HttpWebRequest]::Create("$ApiUrl/v1/chat/completions")
$req.Method = "POST"
$req.ContentType = "application/json"
$bytes = [Text.Encoding]::UTF8.GetBytes($body)
$req.ContentLength = $bytes.Length
$stream = $req.GetRequestStream()
$stream.Write($bytes, 0, $bytes.Length)
$stream.Close()

$clock = [System.Diagnostics.Stopwatch]::StartNew()
$firstMs = $null
$lastMs = $null
$deltas = 0
$usage = $null
$resp = $req.GetResponse()
$reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
while (-not $reader.EndOfStream) {
    $line = $reader.ReadLine()
    if ($line -like "data: *") {
        $data = $line.Substring(6)
        if ($data -eq "[DONE]") { break }
        try {
            $json = $data | ConvertFrom-Json
            if ($json.choices[0].delta.content) {
                $deltas++
                if ($null -eq $firstMs) { $firstMs = $clock.ElapsedMilliseconds }
                $lastMs = $clock.ElapsedMilliseconds
            }
            if ($json.usage.completion_tokens) {
                $usage = $json.usage
            }
        } catch { }
    }
}
$reader.Close()
$resp.Close()

if ($null -ne $firstMs) { $Result.time_to_first_token_ms = [int]$firstMs }
$generationMs = $lastMs - $firstMs
if ($usage) {
    $Result.completion_tokens = $usage.completion_tokens
    if ($generationMs -gt 0) {
        $Result.tokens_per_second = [math]::Round(($usage.completion_tokens - 1) * 1000.0 / $generationMs, 2)
    }
} elseif ($deltas -gt 1 -and $generationMs -gt 0) {
    # Foundry streams carry no usage counts; each SSE content delta is
    # roughly one token, so count deltas after the first one.
    $Result.completion_tokens = $deltas
    $Result.tokens_per_second = [math]::Round(($deltas - 1) * 1000.0 / $generationMs, 2)
    $Result.tokens_per_second_source = "SSE content deltas (approximate)"
}

foreach ($name in @("OpenJarvis", "python", "jarvis", "foundrylocald")) {
    $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($procs) {
        $Result.working_set_mb[$name] = [math]::Round(($procs | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 1)
    }
}

if (-not $OutFile) {
    $docs = Join-Path $PSScriptRoot "..\..\docs\getting-started"
    $OutFile = if (Test-Path $docs) { Join-Path $docs "windows-winui-perf-last.json" } else { Join-Path (Get-Location) "windows-winui-perf-last.json" }
}
$Result | ConvertTo-Json -Depth 6 | Set-Content $OutFile
$Result | ConvertTo-Json -Depth 6
Write-Host "Wrote $OutFile"
