# =============================================================================
# GBS Service Health Dashboard - CSV Timestamp Updater
# =============================================================================
# Rebases all CSV timestamps to the current time so the trend chart
# and real-time simulation always work regardless of when files were generated.
#
# Two modes:
#   1. 7-day file  - preserves relative hourly shape, anchors latest = NOW()
#   2. Snapshots   - spaces each file 10 minutes apart, latest = NOW()
#
# Usage:
#   powershell.exe -ExecutionPolicy Bypass -File .\update_timestamps.ps1
#   powershell.exe -ExecutionPolicy Bypass -File .\update_timestamps.ps1 -DataFolder "D:\gbs\data"
#   powershell.exe -ExecutionPolicy Bypass -File .\update_timestamps.ps1 -SnapshotIntervalMinutes 5
# =============================================================================

param(
    [string] $DataFolder              = "C:\CustomProjects\dashboard\gbs\gbs-poc\data",
    [string] $SevendayFile            = "aruba_health_7day.csv",
    [string] $ActiveFile              = "aruba_health.csv",
    [string] $SamplesFolder           = "realtimesamples",
    [int]    $SnapshotIntervalMinutes = 10
)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
function Get-Timestamp { return Get-Date -Format "HH:mm:ss" }
function Log-Info  ($m) { Write-Host "  [$(Get-Timestamp)]  INFO   $m" -ForegroundColor White  }
function Log-OK    ($m) { Write-Host "  [$(Get-Timestamp)]  OK     $m" -ForegroundColor Green  }
function Log-Warn  ($m) { Write-Host "  [$(Get-Timestamp)]  WARN   $m" -ForegroundColor Yellow }
function Log-Err   ($m) { Write-Host "  [$(Get-Timestamp)]  ERROR  $m" -ForegroundColor Red    }
function Log-Step  ($m) { Write-Host "  [$(Get-Timestamp)]  STEP   $m" -ForegroundColor Cyan   }

function Format-CsvTimestamp ($dt) {
    # Outputs ISO 8601 UTC string matching the CSV format: 2026-05-18T14:00:00Z
    return $dt.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

# --------------------------------------------------------------------------
# Banner
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  GBS Dashboard - CSV Timestamp Updater" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Data folder       : $DataFolder" -ForegroundColor DarkGray
Write-Host "  7-day file        : $SevendayFile" -ForegroundColor DarkGray
Write-Host "  Samples folder    : $SamplesFolder" -ForegroundColor DarkGray
Write-Host "  Snapshot spacing  : $SnapshotIntervalMinutes minutes" -ForegroundColor DarkGray
Write-Host "  Run time (UTC)    : $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# --------------------------------------------------------------------------
# Validate paths
# --------------------------------------------------------------------------
if (-not (Test-Path $DataFolder)) {
    Log-Err "Data folder not found: $DataFolder"
    exit 1
}

# =============================================================================
# PART 1 - Update 7-day trend file
# =============================================================================
Log-Step "Part 1 - Updating 7-day trend file"

$sevendayPath = Join-Path $DataFolder $SevendayFile

if (-not (Test-Path $sevendayPath)) {
    Log-Warn "7-day file not found: $sevendayPath - skipping"
} else {

    # Read all rows
    $rows = Import-Csv -Path $sevendayPath

    if ($rows.Count -eq 0) {
        Log-Warn "7-day file is empty - skipping"
    } else {

        Log-Info "Loaded $($rows.Count) rows from $SevendayFile"

        # Find the earliest and latest existing timestamps
        $existingTimestamps = $rows | ForEach-Object {
            [datetime]::ParseExact($_.timestamp, "yyyy-MM-ddTHH:mm:ssZ",
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::AssumeUniversal)
        }

        $oldEarliest = ($existingTimestamps | Measure-Object -Minimum).Minimum
        $oldLatest   = ($existingTimestamps | Measure-Object -Maximum).Maximum
        $spanHours   = ($oldLatest - $oldEarliest).TotalHours

        Log-Info "Existing range : $($oldEarliest.ToString('yyyy-MM-ddTHH:mm:ssZ')) to $($oldLatest.ToString('yyyy-MM-ddTHH:mm:ssZ'))"
        Log-Info "Span           : $([math]::Round($spanHours, 1)) hours"

        # New anchor: latest timestamp = current hour (truncated to hour)
        $nowUtc       = (Get-Date).ToUniversalTime()
        $newLatest    = [datetime]::new($nowUtc.Year, $nowUtc.Month, $nowUtc.Day,
                            $nowUtc.Hour, 0, 0, [System.DateTimeKind]::Utc)
        $newEarliest  = $newLatest.AddHours(-$spanHours)

        Log-Info "New range      : $($newEarliest.ToString('yyyy-MM-ddTHH:mm:ssZ')) to $($newLatest.ToString('yyyy-MM-ddTHH:mm:ssZ'))"

        # Rebase each row: offset from old earliest -> add to new earliest
        $updated = $rows | ForEach-Object {
            $oldTs = [datetime]::ParseExact($_.timestamp, "yyyy-MM-ddTHH:mm:ssZ",
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::AssumeUniversal)

            $offsetHours = ($oldTs - $oldEarliest).TotalHours
            $newTs       = $newEarliest.AddHours($offsetHours)

            # Return a copy with updated timestamp
            $copy            = $_ | Select-Object *
            $copy.timestamp  = Format-CsvTimestamp $newTs
            $copy
        }

        # Backup original
        $backupPath = $sevendayPath -replace "\.csv$", "_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
        Copy-Item -Path $sevendayPath -Destination $backupPath
        Log-Info "Backed up original to: $(Split-Path $backupPath -Leaf)"

        # Write updated file (preserve column order)
        $headers    = ($rows | Get-Member -MemberType NoteProperty).Name
        $headerLine = $headers -join ","

        $lines = @($headerLine)
        foreach ($row in $updated) {
            $values = $headers | ForEach-Object { $row.$_ }
            $lines += $values -join ","
        }

        [System.IO.File]::WriteAllLines($sevendayPath, $lines,
            [System.Text.UTF8Encoding]::new($false))  # UTF-8 without BOM

        Log-OK "Updated $($updated.Count) rows in $SevendayFile"

        # Also update the active data file
        $activePath = Join-Path $DataFolder $ActiveFile
        Copy-Item -Path $sevendayPath -Destination $activePath -Force
        Log-OK "Copied to active file: $ActiveFile"
    }
}

Write-Host ""

# =============================================================================
# PART 2 - Update snapshot files in realtimesamples
# =============================================================================
Log-Step "Part 2 - Updating snapshot files in $SamplesFolder"

$samplesPath = Join-Path $DataFolder $SamplesFolder

if (-not (Test-Path $samplesPath)) {
    Log-Warn "Samples folder not found: $samplesPath - skipping"
} else {

    $snapFiles = Get-ChildItem -Path $samplesPath -Filter "*.csv" | Sort-Object Name

    if ($snapFiles.Count -eq 0) {
        Log-Warn "No CSV files found in $samplesPath - skipping"
    } else {

        Log-Info "Found $($snapFiles.Count) snapshot files"

        # Timestamps work backwards from NOW:
        # Last snapshot  = NOW
        # Second-to-last = NOW - interval
        # etc.
        # This simulates a live outage that ended just now.
        $nowUtc    = (Get-Date).ToUniversalTime()
        $total     = $snapFiles.Count
        $processed = 0

        foreach ($file in $snapFiles) {
            $rows = Import-Csv -Path $file.FullName

            if ($rows.Count -eq 0) {
                Log-Warn "  $($file.Name): empty, skipping"
                continue
            }

            # Index from end: last file = 0 steps back, first file = (total-1) steps back
            $stepsBack  = $total - 1 - $processed
            $newTs      = $nowUtc.AddMinutes(-$stepsBack * $SnapshotIntervalMinutes)
            $newTsStr   = Format-CsvTimestamp $newTs

            $oldTs = $rows[0].timestamp

            # Update all rows in this file to the new timestamp
            $updated = $rows | ForEach-Object {
                $copy           = $_ | Select-Object *
                $copy.timestamp = $newTsStr
                $copy
            }

            # Write back
            $headers    = ($rows | Get-Member -MemberType NoteProperty).Name
            $headerLine = $headers -join ","
            $lines      = @($headerLine)
            foreach ($row in $updated) {
                $values = $headers | ForEach-Object { $row.$_ }
                $lines += $values -join ","
            }

            [System.IO.File]::WriteAllLines($file.FullName, $lines,
                [System.Text.UTF8Encoding]::new($false))

            $label = $file.BaseName -replace "^snapshot_\d+_", "" -replace "_", " "
            Write-Host "  [$(Get-Timestamp)]  OK     $($file.Name): $oldTs -> $newTsStr ($label)" -ForegroundColor Green

            $processed++
        }

        Log-OK "Updated $processed snapshot files"
    }
}

Write-Host ""

# =============================================================================
# Summary
# =============================================================================
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host "  Timestamps updated successfully." -ForegroundColor Green
Write-Host "  Run this script each time before starting the dashboard" -ForegroundColor Green
Write-Host "  or before running simulate_realtime.ps1" -ForegroundColor Green
Write-Host "  ============================================================" -ForegroundColor Green
Write-Host ""
