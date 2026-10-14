# Checks the OpenJarvis backend the WinUI app is running: health, /v1/info,
# streamed chat, cancelling a stream, memory, and (optionally) crash recovery.
# Prints one PASS/FAIL line per check and exits 1 if any check fails.
[CmdletBinding()]
param(
    [string]$ApiUrl = "http://127.0.0.1:8000",
    # Model to chat with. Defaults to the model the backend reports.
    [string]$Model = "",
    # Kill jarvis.exe and time how long the app's supervisor takes to recover.
    # Needs the WinUI app running (it restarts the backend).
    [switch]$CrashTest
)

$ErrorActionPreference = "Stop"
$results = New-Object System.Collections.Generic.List[object]

function Add-Result([string]$Check, [bool]$Pass, [string]$Detail) {
    $results.Add([pscustomobject]@{ Check = $Check; Result = $(if ($Pass) { "PASS" } else { "FAIL" }); Detail = $Detail })
}

function Test-Healthy {
    try { return (Invoke-WebRequest -Uri "$ApiUrl/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 }
    catch { return $false }
}

# Streams a chat completion and returns timing for the first and last content delta.
function Invoke-StreamedChat([string]$Prompt, [int]$MaxTokens, [int]$StopAfterMs = 0) {
    $body = @{
        model = $Model
        stream = $true
        max_tokens = $MaxTokens
        messages = @(@{ role = "user"; content = $Prompt })
    } | ConvertTo-Json -Depth 4
    $req = [System.Net.HttpWebRequest]::Create("$ApiUrl/v1/chat/completions")
    $req.Method = "POST"
    $req.ContentType = "application/json"
    $req.Timeout = 300000
    $req.ReadWriteTimeout = 300000
    $bytes = [Text.Encoding]::UTF8.GetBytes($body)
    $req.ContentLength = $bytes.Length
    $stream = $req.GetRequestStream()
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Close()

    $clock = [Diagnostics.Stopwatch]::StartNew()
    $first = $null; $last = $null; $deltas = 0; $done = $false
    $resp = $req.GetResponse()
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
    try {
        while (-not $reader.EndOfStream) {
            if ($StopAfterMs -gt 0 -and $clock.ElapsedMilliseconds -ge $StopAfterMs) { break }
            $line = $reader.ReadLine()
            if ($line -notlike "data: *") { continue }
            $data = $line.Substring(6)
            if ($data -eq "[DONE]") { $done = $true; break }
            try { $content = ($data | ConvertFrom-Json).choices[0].delta.content } catch { continue }
            if ($content) {
                $deltas++
                if ($null -eq $first) { $first = $clock.ElapsedMilliseconds }
                $last = $clock.ElapsedMilliseconds
            }
        }
    } finally {
        # Closing mid-stream is how a client cancels.
        $reader.Close(); $resp.Close()
    }
    [pscustomobject]@{ FirstMs = $first; LastMs = $last; Deltas = $deltas; Done = $done }
}

# 1. Health
$healthy = Test-Healthy
Add-Result "Health" $healthy "GET $ApiUrl/health"
if (-not $healthy) {
    $results | Format-Table -AutoSize | Out-String | Write-Host
    throw "The backend at $ApiUrl isn't healthy. Start OpenJarvis and wait for 'OpenJarvis is ready'."
}

# 2. Info
$info = Invoke-RestMethod -Uri "$ApiUrl/v1/info"
if (-not $Model) { $Model = $info.model }
$ep = $info.hardware.execution_provider
Add-Result "Info" ([bool]$info.model) ("model={0}; execution_provider={1}; cpu_fallback={2}; arch={3}; allow_cloud={4}; tools={5}" -f `
    $info.model, $ep, $info.hardware.execution_provider_fallback, $info.hardware.arch, $info.allow_cloud, $info.tool_calling.supported)
Add-Result "Cloud off by default" (-not $info.allow_cloud) "allow_cloud=$($info.allow_cloud)"

# 3. Streamed chat
$chat = Invoke-StreamedChat "Write three sentences about Windows on ARM." 128
$decode = if ($chat.Deltas -gt 1 -and $chat.LastMs -gt $chat.FirstMs) {
    [math]::Round(($chat.Deltas - 1) * 1000.0 / ($chat.LastMs - $chat.FirstMs), 1)
} else { 0 }
Add-Result "Streamed chat" ($chat.Deltas -gt 1 -and $chat.Done) ("{0} deltas; first token {1} ms; ~{2} tokens/s" -f $chat.Deltas, $chat.FirstMs, $decode)

# 4. Cancel mid-stream, then confirm the server is still healthy
$null = Invoke-StreamedChat "Count from one to two hundred, one number per line." 512 3000
Start-Sleep -Seconds 1
Add-Result "Cancel mid-stream" (Test-Healthy) "client disconnected after 3 s; server still healthy"

# 5. Memory store and search
$marker = "openjarvis-test-" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$stored = Invoke-RestMethod -Uri "$ApiUrl/v1/memory/store" -Method Post -ContentType "application/json" `
    -Body (@{ content = "Memory check marker $marker"; metadata = @{ source = "test-backend.ps1" } } | ConvertTo-Json)
$found = Invoke-RestMethod -Uri "$ApiUrl/v1/memory/search" -Method Post -ContentType "application/json" `
    -Body (@{ query = $marker; top_k = 3 } | ConvertTo-Json)
$hit = [bool](@($found.results) | Where-Object { $_.content -match $marker })
Add-Result "Memory store/search" ($stored.status -eq "stored" -and $hit) "stored=$($stored.status); found=$hit"

# 6. Crash recovery (optional)
if ($CrashTest) {
    $before = @(Get-CimInstance Win32_Process -Filter "Name='jarvis.exe'")
    if ($before.Count -eq 0) {
        Add-Result "Crash recovery" $false "no jarvis.exe running (is the app supervising the backend?)"
    } else {
        $before | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        $clock = [Diagnostics.Stopwatch]::StartNew()
        $wentDown = $false; $recovered = $false
        while ($clock.Elapsed.TotalSeconds -lt 120) {
            Start-Sleep -Milliseconds 500
            if (Test-Healthy) { if ($wentDown) { $recovered = $true; break } } else { $wentDown = $true }
        }
        $after = @(Get-CimInstance Win32_Process -Filter "Name='jarvis.exe'") | ForEach-Object { $_.ProcessId }
        Add-Result "Crash recovery" $recovered ("healthy again after {0} s; jarvis PID {1} -> {2}" -f `
            [int]$clock.Elapsed.TotalSeconds, ($before.ProcessId -join ","), ($after -join ","))
    }
}

$results | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
if ($results.Result -contains "FAIL") { exit 1 }
