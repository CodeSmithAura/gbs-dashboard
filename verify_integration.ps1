# =============================================================================
# GBS Service Health Dashboard -- Integration Verification Script
# Batch 4: End-to-end check of all API endpoints, both pillars
#
# Usage (from project root, backend must be running):
#   powershell.exe -ExecutionPolicy Bypass -File .\verify_integration.ps1
#   powershell.exe -ExecutionPolicy Bypass -File .\verify_integration.ps1 -BaseUrl "http://localhost:8000"
# =============================================================================

param(
    [string] $BaseUrl = "http://localhost:8000",
    [int]    $TimeoutSec = 10
)

$pass = 0
$fail = 0
$warn = 0

function Get-Timestamp { return Get-Date -Format "HH:mm:ss" }

function Test-Endpoint {
    param(
        [string] $Label,
        [string] $Url,
        [string] $Method = "GET",
        [string[]] $RequiredFields = @(),
        [int]    $ExpectedStatus = 200,
        [bool]   $WarnOnly = $false
    )

    try {
        $resp = Invoke-WebRequest -Uri $Url -Method $Method `
            -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop

        $status = $resp.StatusCode
        $ok     = $status -eq $ExpectedStatus

        if ($ok -and $RequiredFields.Count -gt 0) {
            $body = $resp.Content | ConvertFrom-Json
            foreach ($field in $RequiredFields) {
                $val = $body.$field
                if ($null -eq $val) {
                    $ok = $false
                    Write-Host "  [$(Get-Timestamp)]  FAIL   $Label -- missing field '$field'" -ForegroundColor Red
                    break
                }
            }
        }

        if ($ok) {
            Write-Host "  [$(Get-Timestamp)]  PASS   $Label (HTTP $status)" -ForegroundColor Green
            $script:pass++
        } elseif ($WarnOnly) {
            Write-Host "  [$(Get-Timestamp)]  WARN   $Label (HTTP $status)" -ForegroundColor Yellow
            $script:warn++
        } else {
            Write-Host "  [$(Get-Timestamp)]  FAIL   $Label (HTTP $status)" -ForegroundColor Red
            $script:fail++
        }
    }
    catch {
        $msg = $_.Exception.Message
        if ($WarnOnly) {
            Write-Host "  [$(Get-Timestamp)]  WARN   $Label -- $msg" -ForegroundColor Yellow
            $script:warn++
        } else {
            Write-Host "  [$(Get-Timestamp)]  FAIL   $Label -- $msg" -ForegroundColor Red
            $script:fail++
        }
    }
}

function Test-SecurityHeader {
    param([string] $Url, [string] $Header)
    try {
        $resp = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSec -UseBasicParsing
        $val  = $resp.Headers[$Header]
        if ($val) {
            Write-Host "  [$(Get-Timestamp)]  PASS   Security header: $Header" -ForegroundColor Green
            $script:pass++
        } else {
            Write-Host "  [$(Get-Timestamp)]  FAIL   Security header missing: $Header" -ForegroundColor Red
            $script:fail++
        }
    } catch {
        Write-Host "  [$(Get-Timestamp)]  FAIL   Security header check failed: $Header" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  GBS Dashboard -- Integration Verification" -ForegroundColor White
Write-Host "  Backend: $BaseUrl" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ------ Core health ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Write-Host "  Core" -ForegroundColor White
Test-Endpoint "Health check"    "$BaseUrl/health"   -RequiredFields @("status","db_connected")
Test-Endpoint "Root endpoint"   "$BaseUrl/"
Write-Host ""

# ------ Security headers ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Write-Host "  Security Headers" -ForegroundColor White
Test-SecurityHeader "$BaseUrl/health" "X-Content-Type-Options"
Test-SecurityHeader "$BaseUrl/health" "X-Frame-Options"
Test-SecurityHeader "$BaseUrl/health" "X-XSS-Protection"
Test-SecurityHeader "$BaseUrl/health" "Cache-Control"
Test-SecurityHeader "$BaseUrl/health" "Content-Security-Policy"
Write-Host ""

# ------ Wireless pillar ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Write-Host "  Wireless Pillar" -ForegroundColor White
Test-Endpoint "Wireless summary"    "$BaseUrl/api/v1/wireless/summary"
Test-Endpoint "Wireless sites"      "$BaseUrl/api/v1/wireless/sites"
Test-Endpoint "Wireless alerts"     "$BaseUrl/api/v1/wireless/alerts"
Test-Endpoint "Wireless trend"      "$BaseUrl/api/v1/wireless/trend"
Write-Host ""

# ------ LAN pillar ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Write-Host "  LAN Pillar" -ForegroundColor White
Test-Endpoint "LAN status"          "$BaseUrl/api/v1/lan/status"   -RequiredFields @("sw_connected")
Test-Endpoint "LAN groups"          "$BaseUrl/api/v1/lan/groups"
Test-Endpoint "LAN countries"       "$BaseUrl/api/v1/lan/countries"
Test-Endpoint "LAN summary (all)"   "$BaseUrl/api/v1/lan/summary?scope=all"    -WarnOnly $true
Test-Endpoint "LAN sites (all)"     "$BaseUrl/api/v1/lan/sites?scope=all"      -WarnOnly $true
Test-Endpoint "LAN alerts (all)"    "$BaseUrl/api/v1/lan/alerts?scope=all"     -WarnOnly $true
Test-Endpoint "LAN trend (all)"     "$BaseUrl/api/v1/lan/trend?scope=all"      -WarnOnly $true
Write-Host ""

# ------ Scope validation (security) ---------------------------------------------------------------------------------------------------------------------------------------------
Write-Host "  Scope Validation (Security)" -ForegroundColor White
Test-Endpoint "Invalid scope rejected"       "$BaseUrl/api/v1/lan/summary?scope=INVALID" `
    -ExpectedStatus 400
Test-Endpoint "Overlong scope rejected"      "$BaseUrl/api/v1/lan/summary?scope=country:$('A'*300)" `
    -ExpectedStatus 400
Test-Endpoint "SQL-like scope rejected"      "$BaseUrl/api/v1/lan/summary?scope=country:'; DROP TABLE--" `
    -ExpectedStatus 400
Write-Host ""

# ------ Demo endpoints ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
Write-Host "  Demo Endpoints" -ForegroundColor White
Test-Endpoint "Demo status"         "$BaseUrl/api/v1/demo/status"  -RequiredFields @("running")
Write-Host ""

# ------ Summary ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
$total = $pass + $fail + $warn
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Results: $pass passed  $fail failed  $warn warnings  ($total total)" `
    -ForegroundColor $(if ($fail -gt 0) { "Red" } elseif ($warn -gt 0) { "Yellow" } else { "Green" })

if ($fail -gt 0) {
    Write-Host ""
    Write-Host "  FAIL items may indicate:" -ForegroundColor Red
    Write-Host "    - Backend not running (start uvicorn first)" -ForegroundColor DarkGray
    Write-Host "    - DB not reachable (check DB_HOST in .env)" -ForegroundColor DarkGray
    Write-Host "    - init.sql not run (run in SSMS)" -ForegroundColor DarkGray
    Write-Host "    - SW credentials invalid (check SW_HOST/SW_USER/SW_PASSWORD)" -ForegroundColor DarkGray
}
if ($warn -gt 0) {
    Write-Host ""
    Write-Host "  WARN items are LAN endpoints -- expected if SolarWinds not yet" -ForegroundColor Yellow
    Write-Host "  connected or first ingest cycle still running (wait 60 seconds)." -ForegroundColor DarkGray
}
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
