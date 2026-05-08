# =============================================================================
# GBS Service Health Dashboard - Real-Time Simulation Script
# =============================================================================
# Simulates live Aruba data updates by cycling through snapshot CSV files.
#
# Usage:
#   powershell.exe -ExecutionPolicy Bypass -File .\simulate_realtime.ps1
#   powershell.exe -ExecutionPolicy Bypass -File .\simulate_realtime.ps1 -IntervalSeconds 30
#   powershell.exe -ExecutionPolicy Bypass -File .\simulate_realtime.ps1 -IntervalSeconds 30 -Loop
# =============================================================================

param(
    [int]    $IntervalSeconds = 60,
    [switch] $Loop            = $false,
    [string] $BackendUrl      = "http://localhost:8000",
    [string] $DataFolder      = "C:\CustomProjects\dashboard\gbs\gbs-poc\data",
    [string] $SamplesFolder   = "C:\CustomProjects\dashboard\gbs\gbs-poc\data\realtimesamples"
)

# Active CSV path
$ActiveFile = Join-Path $DataFolder "aruba_health.csv"

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
function Get-Timestamp {
    return Get-Date -Format "HH:mm:ss"
}

function Log-Info ($msg) {
    Write-Host "  [$(Get-Timestamp)]  INFO   $msg" -ForegroundColor White
}

function Log-OK ($msg) {
    Write-Host "  [$(Get-Timestamp)]  OK     $msg" -ForegroundColor Green
}

function Log-Warn ($msg) {
    Write-Host "  [$(Get-Timestamp)]  WARN   $msg" -ForegroundColor Yellow
}

function Log-Err ($msg) {
    Write-Host "  [$(Get-Timestamp)]  ERROR  $msg" -ForegroundColor Red
}

function Log-Step ($msg) {
    Write-Host "  [$(Get-Timestamp)]  STEP   $msg" -ForegroundColor Cyan
}

# --------------------------------------------------------------------------
# Banner
# --------------------------------------------------------------------------
function Show-Banner {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  GBS Service Health Dashboard - Real-Time Simulation" -ForegroundColor White
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Data folder    : $DataFolder" -ForegroundColor DarkGray
    Write-Host "  Samples folder : $SamplesFolder" -ForegroundColor DarkGray
    Write-Host "  Interval       : $IntervalSeconds seconds" -ForegroundColor DarkGray
    Write-Host "  Loop           : $Loop" -ForegroundColor DarkGray
    Write-Host "  Backend URL    : $BackendUrl" -ForegroundColor DarkGray
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

# --------------------------------------------------------------------------
# Validate folders exist
# --------------------------------------------------------------------------
function Assert-Paths {
    if (-not (Test-Path $DataFolder)) {
        Log-Err "Data folder not found: $DataFolder"
        Log-Err "Update the -DataFolder parameter or the default path in this script."
        exit 1
    }
    if (-not (Test-Path $SamplesFolder)) {
        Log-Err "Samples folder not found: $SamplesFolder"
        Log-Err "Create the folder and copy the snapshot CSV files into it."
        exit 1
    }
}

# --------------------------------------------------------------------------
# Get snapshot files sorted by name
# --------------------------------------------------------------------------
function Get-Snapshots {
    $files = Get-ChildItem -Path $SamplesFolder -Filter "*.csv" | Sort-Object Name
    if ($files.Count -eq 0) {
        Log-Err "No CSV files found in: $SamplesFolder"
        exit 1
    }
    return $files
}

# --------------------------------------------------------------------------
# Backup existing active file
# --------------------------------------------------------------------------
function Backup-ActiveFile {
    if (Test-Path $ActiveFile) {
        $stamp      = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupName = "aruba_health_backup_$stamp.csv"
        $backupPath = Join-Path $DataFolder $backupName
        Copy-Item -Path $ActiveFile -Destination $backupPath -Force
        Log-Info "Backed up existing file as $backupName"
    }
}

# --------------------------------------------------------------------------
# Trigger backend ingest via REST
# --------------------------------------------------------------------------
function Invoke-Ingest {
    $url = "$BackendUrl/api/v1/wireless/ingest/trigger"
    try {
        $resp = Invoke-RestMethod -Uri $url -Method POST -TimeoutSec 10
        Log-OK "Ingest triggered - last_ingested_at: $($resp.last_ingested_at)"
    }
    catch {
        Log-Warn "Could not reach backend at $url"
        Log-Warn "Dashboard will update on next scheduled poll instead."
    }
}

# --------------------------------------------------------------------------
# Fetch and print current dashboard status
# --------------------------------------------------------------------------
function Get-DashboardStatus {
    $url = "$BackendUrl/api/v1/wireless/summary"
    try {
        $s = Invoke-RestMethod -Uri $url -Method GET -TimeoutSec 10

        $score  = [math]::Round($s.overall_score, 1)
        $status = $s.status.ToUpper()

        $color = "White"
        if ($status -eq "GREEN") { $color = "Green"  }
        if ($status -eq "AMBER") { $color = "Yellow" }
        if ($status -eq "RED")   { $color = "Red"    }

        Write-Host "  [$(Get-Timestamp)]  SCORE  $score / 100 - " -NoNewline -ForegroundColor White
        Write-Host $status -ForegroundColor $color
        Write-Host "  [$(Get-Timestamp)]  SITES  Healthy=$($s.sites_healthy)  Degraded=$($s.sites_degraded)  Critical=$($s.sites_critical)" -ForegroundColor DarkGray
        Write-Host "  [$(Get-Timestamp)]  ALERTS Active=$($s.active_alerts)  Critical=$($s.critical_alerts)" -ForegroundColor DarkGray
    }
    catch {
        Log-Warn "Could not fetch dashboard summary - backend may still be ingesting."
    }
}

# --------------------------------------------------------------------------
# Apply one snapshot file
# --------------------------------------------------------------------------
function Apply-Snapshot ($File, $StepNum, $Total) {
    $label = $File.BaseName -replace "^snapshot_\d+_", "" -replace "_", " "

    Write-Host ""
    Write-Host "  ------------------------------------------------------------" -ForegroundColor DarkGray
    Log-Step "Step $StepNum of $Total - $($File.Name)"
    Log-Info "Scenario: $label"

    try {
        Copy-Item -Path $File.FullName -Destination $ActiveFile -Force
        Log-OK "Copied to $ActiveFile"
    }
    catch {
        Log-Err "Failed to copy file: $($_.Exception.Message)"
        return
    }

    Start-Sleep -Milliseconds 500
    Invoke-Ingest

    Start-Sleep -Seconds 2
    Get-DashboardStatus

    Write-Host "  Open dashboard: http://localhost:3000" -ForegroundColor DarkGray
}

# --------------------------------------------------------------------------
# Countdown between snapshots
# --------------------------------------------------------------------------
function Show-Countdown ($Seconds, $NextLabel) {
    Write-Host ""
    for ($i = $Seconds; $i -gt 0; $i--) {
        Write-Host "`r  [$(Get-Timestamp)]  WAIT   Next in $i sec - $NextLabel   " -NoNewline -ForegroundColor DarkGray
        Start-Sleep -Seconds 1
    }
    Write-Host "`r  [$(Get-Timestamp)]  WAIT   Loading next snapshot...          " -ForegroundColor DarkGray
    Write-Host ""
}

# =============================================================================
# MAIN
# =============================================================================
Show-Banner
Assert-Paths

$snapshots = Get-Snapshots
$total     = $snapshots.Count

Log-Info "Found $total snapshot files"
Log-Info "Press Ctrl+C at any time to stop."
Write-Host ""

Backup-ActiveFile

$run = 0

do {
    $run++

    if ($Loop -and $run -gt 1) {
        Write-Host ""
        Write-Host "  ============================================================" -ForegroundColor Cyan
        Write-Host "  Loop $run - restarting sequence" -ForegroundColor Cyan
        Write-Host "  ============================================================" -ForegroundColor Cyan
    }

    for ($i = 0; $i -lt $total; $i++) {

        Apply-Snapshot -File $snapshots[$i] -StepNum ($i + 1) -Total $total

        $isLast = ($i -eq ($total - 1))

        if (-not $isLast) {
            $nextLabel = $snapshots[$i + 1].BaseName -replace "^snapshot_\d+_", "" -replace "_", " "
            Show-Countdown -Seconds $IntervalSeconds -NextLabel $nextLabel
        }
        elseif ($Loop) {
            $nextLabel = $snapshots[0].BaseName -replace "^snapshot_\d+_", "" -replace "_", " "
            Show-Countdown -Seconds $IntervalSeconds -NextLabel $nextLabel
        }
    }

} while ($Loop)

Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host "  Simulation complete - all $total snapshots applied." -ForegroundColor Green
Write-Host "  Last snapshot is still active in: $ActiveFile" -ForegroundColor Green
Write-Host "  Open dashboard: http://localhost:3000" -ForegroundColor Green
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host ""
