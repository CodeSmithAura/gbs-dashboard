# =============================================================================
# GBS Service Health Dashboard -- Windows Task Scheduler Setup
# Run this script once as Administrator to register the backend as a
# scheduled task that starts automatically when the VM boots.
#
# Usage (from the project root):
#   powershell.exe -ExecutionPolicy Bypass -File .\infra\windows\setup_task.ps1
#
# To change the project path, update PROJECT_ROOT below or pass as parameter.
# =============================================================================

param(
    [string] $ProjectRoot = "C:\CustomProjects\dashboard\gbs\gbs-poc",
    [string] $TaskName    = "GBS-Dashboard-Backend"
)

$BackendDir  = "$ProjectRoot\backend"
$PythonExe   = "$BackendDir\venv\Scripts\python.exe"
$UvicornArgs = "-m uvicorn app.main:app --host 127.0.0.1 --port 8000"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  GBS Dashboard -- Task Scheduler Setup" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Project root : $ProjectRoot" -ForegroundColor DarkGray
Write-Host "  Backend dir  : $BackendDir" -ForegroundColor DarkGray
Write-Host "  Python       : $PythonExe" -ForegroundColor DarkGray
Write-Host "  Task name    : $TaskName" -ForegroundColor DarkGray
Write-Host ""

# Validate paths
if (-not (Test-Path $PythonExe)) {
    Write-Host "  ERROR: Python not found at $PythonExe" -ForegroundColor Red
    Write-Host "  Run: cd backend && python -m venv venv && venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Remove existing task if present
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  Removed existing task: $TaskName" -ForegroundColor DarkGray
}

# Create the task
$action  = New-ScheduledTaskAction `
    -Execute    $PythonExe `
    -Argument   $UvicornArgs `
    -WorkingDirectory $BackendDir

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId    "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel  Highest

Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "  Task registered: $TaskName" -ForegroundColor Green

# Start it immediately
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3

$state = (Get-ScheduledTask -TaskName $TaskName).State
Write-Host "  Task state: $state" -ForegroundColor $(if ($state -eq "Running") { "Green" } else { "Yellow" })

# Verify backend is responding
Write-Host ""
Write-Host "  Waiting 5 seconds for backend to start..." -ForegroundColor DarkGray
Start-Sleep -Seconds 5

try {
    $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
    Write-Host "  Backend health: OK -- status=$($resp.status)" -ForegroundColor Green
} catch {
    Write-Host "  Backend not yet responding -- check logs or wait a few seconds" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host "  Setup complete. Backend will auto-start on every VM reboot." -ForegroundColor Green
Write-Host "  To check status: Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor DarkGray
Write-Host "  To stop:         Stop-ScheduledTask -TaskName '$TaskName'" -ForegroundColor DarkGray
Write-Host "  To start:        Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor DarkGray
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host ""
