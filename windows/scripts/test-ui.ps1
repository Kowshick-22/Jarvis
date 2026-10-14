# Drives the installed WinUI app through Windows UI Automation:
#   1. accepts the local-AI consent screen if it is showing,
#   2. sends a prompt and waits for the reply to be saved to history,
#   3. sends a long prompt and presses Stop mid-reply,
#   4. restarts the app and checks the conversation is still listed.
# Start the app first (for example with new-test-profile.ps1 -Launch), from a
# shell where OPENJARVIS_HOME points at the same profile.
[CmdletBinding()]
param(
    [string]$AppPath = (Join-Path $env:ProgramFiles "OpenJarvis\OpenJarvis.exe"),
    [string]$ApiUrl = "http://127.0.0.1:8000",
    [int]$ReadyTimeoutSec = 900,
    [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$AE = [System.Windows.Automation.AutomationElement]
$Descendants = [System.Windows.Automation.TreeScope]::Descendants

$configDir = if ($env:OPENJARVIS_HOME) { $env:OPENJARVIS_HOME } else { Join-Path $env:USERPROFILE ".openjarvis" }
$conversationsPath = Join-Path $configDir "winui-conversations.json"
$results = New-Object System.Collections.Generic.List[object]

function Add-Result([string]$Check, [bool]$Pass, [string]$Detail) {
    $results.Add([pscustomobject]@{ Check = $Check; Result = $(if ($Pass) { "PASS" } else { "FAIL" }); Detail = $Detail })
}

function Get-AppWindow {
    $proc = Get-Process -Name OpenJarvis -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $proc) { throw "OpenJarvis isn't running. Start it first." }
    for ($i = 0; $i -lt 60; $i++) {
        $cond = New-Object System.Windows.Automation.PropertyCondition($AE::ProcessIdProperty, $proc.Id)
        $window = $AE::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
        if ($window) { return @{ Process = $proc; Window = $window } }
        Start-Sleep -Milliseconds 500
    }
    throw "Couldn't find the OpenJarvis window."
}

function Find-ByName($root, [string]$name, [int]$timeoutSec = 10) {
    $cond = New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty, $name)
    $clock = [Diagnostics.Stopwatch]::StartNew()
    do {
        $el = $root.FindFirst($Descendants, $cond)
        if ($el) { return $el }
        Start-Sleep -Milliseconds 250
    } while ($clock.Elapsed.TotalSeconds -lt $timeoutSec)
    return $null
}

function Invoke-Element($el) {
    $el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
}

function Send-Prompt($window, [string]$text) {
    $box = Find-ByName $window "Message"
    if (-not $box) { throw "Chat input not found. Is the Chat page open?" }
    $box.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($text)
    Invoke-Element (Find-ByName $window "Send message")
}

function Get-ActiveConversation {
    if (-not (Test-Path $conversationsPath)) { return $null }
    $file = Get-Content $conversationsPath -Raw | ConvertFrom-Json
    return $file.conversations.($file.activeId)
}

function Wait-Ready {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    do {
        try { if ((Invoke-WebRequest -Uri "$ApiUrl/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { return $clock.Elapsed.TotalSeconds } } catch { }
        Start-Sleep -Seconds 1
    } while ($clock.Elapsed.TotalSeconds -lt $ReadyTimeoutSec)
    return -1
}

$app = Get-AppWindow

# 1. Consent (only shown on a profile that hasn't accepted it yet)
$consent = Find-ByName $app.Window "Use Foundry Local and continue" 5
if ($consent) {
    $running = @(Get-CimInstance Win32_Process -Filter "Name='jarvis.exe'").Count
    Invoke-Element $consent
    Add-Result "Consent gate" ($running -eq 0) "no backend running before consent; accepted"
}
$ready = Wait-Ready
Add-Result "Setup reaches ready" ($ready -ge 0) $(if ($ready -ge 0) { "API healthy after $([int]$ready) s" } else { "not healthy within $ReadyTimeoutSec s" })
if ($ready -lt 0) {
    $results | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
    exit 1
}
# Setup finishes just before the Chat page appears.
$null = Find-ByName $app.Window "Message" 30

# 2. Send a prompt and wait for the saved reply
$clock = [Diagnostics.Stopwatch]::StartNew()
Send-Prompt $app.Window "Reply with one short sentence about the moon."
do {
    Start-Sleep -Milliseconds 500
    $conv = Get-ActiveConversation
    $reply = if ($conv) { @($conv.Messages | Where-Object { $_.Role -eq "assistant" })[-1].Content } else { "" }
} until (($reply -and $reply.Length -gt 5) -or $clock.Elapsed.TotalSeconds -gt 180)
Add-Result "Chat reply" ([bool]$reply -and $reply.Length -gt 5) ("reply saved after {0} s: '{1}'" -f [int]$clock.Elapsed.TotalSeconds, $(if ($reply) { $reply.Substring(0, [Math]::Min(60, $reply.Length)) } else { "" }))

# 3. Stop mid-reply
Send-Prompt $app.Window "Count slowly from one to two hundred, one number per line."
$stop = Find-ByName $app.Window "Stop generation"
Start-Sleep -Seconds 4
if ($stop) { Invoke-Element $stop }
$send = Find-ByName $app.Window "Send message"
$clock = [Diagnostics.Stopwatch]::StartNew()
while ($send -and -not $send.Current.IsEnabled -and $clock.Elapsed.TotalSeconds -lt 15) { Start-Sleep -Milliseconds 250 }
$responsive = (Get-Process -Id $app.Process.Id).Responding
Add-Result "Stop" ([bool]$stop -and $send.Current.IsEnabled -and $responsive) "Stop pressed; Send enabled=$($send.Current.IsEnabled); UI responding=$responsive"

# 4. Restart and check the conversation is listed
if (-not $SkipRestart) {
    $title = (Get-ActiveConversation).Title
    Stop-Process -Id $app.Process.Id -Force
    Start-Sleep -Seconds 2
    Start-Process -FilePath $AppPath | Out-Null
    $app = Get-AppWindow
    $null = Wait-Ready
    $listed = Find-ByName $app.Window $title 30
    Add-Result "History after restart" ([bool]$listed) "conversation '$title' listed=$([bool]$listed)"
}

$results | Format-Table -AutoSize -Wrap | Out-String -Width 200 | Write-Host
if ($results.Result -contains "FAIL") { exit 1 }
