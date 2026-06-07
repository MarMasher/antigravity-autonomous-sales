param(
    [string]$ScriptRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$taskName   = "AntigravityPipeline"
$scriptPath = Join-Path $ScriptRoot "run.py"
$logDir     = Join-Path $ScriptRoot "logs"
$logPath    = Join-Path $logDir "auto_run.log"
$pythonExe  = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $pythonExe) {
    Write-Error "Python not found on PATH. Install Python and ensure it is in your PATH."
    exit 1
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$action  = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "$scriptPath --targets 10" `
    -WorkingDirectory $ScriptRoot

$trigger  = New-ScheduledTaskTrigger -Daily -At "08:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName   $taskName `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -RunLevel   Highest `
    -Force

Write-Host ""
Write-Host "Task registered: $taskName" -ForegroundColor Green
Write-Host "Runs daily at 08:00 AM" -ForegroundColor Cyan
Write-Host ""
Write-Host "To run NOW:"
Write-Host "  Start-ScheduledTask -TaskName $taskName"
Write-Host ""
Write-Host "To check logs:"
Write-Host "  Get-Content $logPath -Tail 50"
