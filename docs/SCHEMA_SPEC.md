# Aruba Health Data — File Schema Specification

**Document:** GBS-SCHEMA-v1.0  
**Version:** v1.0 — April 2026  
**Status:** Approved  
**Programme:** GBS Service Health Dashboard — Wireless POC (Phase 1)

---

## 1. Purpose

This document defines the CSV and JSON file schema used to ingest wireless
health data into the GBS Service Health Dashboard during Phase 1 (POC).

All field names are intentionally aligned to the HPE Aruba Central REST API
response schema — this means the Phase 2 connector upgrade requires zero
changes to the normalisation layer.

---

## 2. Supported File Formats

| Format | Extension | Encoding | Structure |
|---|---|---|---|
| CSV | `.csv` | UTF-8 | Header row + one data row per site per timestamp |
| JSON | `.json` | UTF-8 | Array of objects — one object per site per timestamp |

Selected via environment variable: `DATA_SOURCE_FORMAT=csv` or `json`

---

## 3. Field Definitions

### 3.1 Required Fields — All 14 must be present. Missing fields cause the row to be skipped with a warning logged.

| # | Field Name | Data Type | Nullable | Description |
|---|---|---|---|---|
| 1 | `site_id` | String | No | Unique site identifier. Must match Aruba Central site ID format. Example: `SITE-HQ-01` |
| 2 | `site_name` | String | No | Human-readable site name shown in dashboard. Example: `Bangkok HQ — Floor 1` |
| 3 | `timestamp` | ISO 8601 DateTime | No | UTC timestamp when the health snapshot was taken. Example: `2026-04-16T08:30:00Z` |
| 4 | `site_health_score` | Integer (0–100) | No | Aruba AI Insights composite site health score. Values outside 0–100 are clamped. |
| 5 | `ap_total` | Integer ≥ 0 | No | Total number of APs registered at the site. |
| 6 | `ap_online` | Integer ≥ 0 | No | Number of APs currently in online/up state. Must be ≤ `ap_total`. |
| 7 | `ap_offline` | Integer ≥ 0 | No | Number of APs currently offline. Should equal `ap_total − ap_online`. |
| 8 | `client_count` | Integer ≥ 0 | No | Total wireless clients connected at the site at the time of snapshot. |
| 9 | `auth_failures_1h` | Integer ≥ 0 | No | Count of authentication failures recorded in the last 1 hour. |
| 10 | `active_alerts` | Integer ≥ 0 | No | Count of active alerts at the site (any severity). `0` = no alerts. |
| 11 | `alert_severity` | Enum (see §3.2) | No | Highest severity of any active alert. Must be one of the defined enum values. |
| 12 | `alert_description` | String | Yes | Description of the highest-severity active alert. Use empty string `""` if `alert_severity` is `none`. |
| 13 | `ssid_count` | Integer ≥ 0 | No | Number of SSIDs currently active at the site. |
| 14 | `uplink_quality` | Enum (see §3.3) | No | WAN uplink quality. Must be one of the defined enum values. |

### 3.2 `alert_severity` — Valid Values

| Value | Meaning | Dashboard Colour |
|---|---|---|
| `none` | No active alerts | — |
| `info` | Informational alert — no action required | Blue |
| `warning` | Degraded condition — monitor closely | Amber |
| `critical` | Active outage or serious issue — immediate action | Red |

### 3.3 `uplink_quality` — Valid Values

| Value | Meaning |
|---|---|
| `good` | Uplink operating normally |
| `fair` | Uplink degraded — performance impact possible |
| `poor` | Uplink severely degraded — failover may be active |
| `down` | Uplink unreachable |

---

## 4. Validation Rules

The ingestion layer applies these rules to every row. Rows failing validation
are skipped and a warning is logged — the pipeline continues processing
remaining rows.

| Rule | Behaviour on Failure |
|---|---|
| All 14 fields present | Row skipped, warning logged |
| `site_health_score` is an integer | Row skipped |
| `site_health_score` outside 0–100 | Value clamped to range, row accepted |
| `alert_severity` not in enum | Row skipped |
| `uplink_quality` not in enum | Row skipped |
| `timestamp` not parseable as ISO 8601 | Row skipped |
| Integer fields contain non-numeric text | Row skipped |
| `ap_online` > `ap_total` | Row accepted — inconsistency logged as warning |

---

## 5. CSV Format Rules

```
site_id,site_name,timestamp,site_health_score,ap_total,ap_online,ap_offline,client_count,auth_failures_1h,active_alerts,alert_severity,alert_description,ssid_count,uplink_quality
SITE-HQ-01,Bangkok HQ — Floor 1,2026-04-16T08:00:00Z,88,24,24,0,187,2,0,none,,4,good
SITE-BR-02,Branch — Silom,2026-04-16T08:00:00Z,55,16,12,4,67,18,1,critical,Multiple APs offline,3,poor
```

- Header row is mandatory and must appear on line 1
- Column order must match the header — do not reorder columns
- Empty `alert_description` — leave cell blank (two consecutive commas), not quoted empty string
- Timestamps must include timezone suffix (`Z` for UTC or `+07:00` for ICT)
- No BOM (byte order mark) — save as plain UTF-8

---

## 6. JSON Format Rules

```json
[
  {
    "site_id": "SITE-HQ-01",
    "site_name": "Bangkok HQ — Floor 1",
    "timestamp": "2026-04-16T08:00:00Z",
    "site_health_score": 88,
    "ap_total": 24,
    "ap_online": 24,
    "ap_offline": 0,
    "client_count": 187,
    "auth_failures_1h": 2,
    "active_alerts": 0,
    "alert_severity": "none",
    "alert_description": "",
    "ssid_count": 4,
    "uplink_quality": "good"
  }
]
```

- Root element must be a JSON array `[...]`
- Each element is a flat JSON object — no nesting
- Integer fields must be JSON numbers, not strings
- `alert_description` must be present — use empty string `""` if no alert
- Field order within each object does not matter

---

## 7. Health Score Computation

The ingestion layer computes a `composite_score` from each raw record:

```
composite_score = (site_health_score / 100 × 50)
                + (ap_online / ap_total   × 30)
                + alert_penalty

alert_penalty:  none = 0   info = −2   warning = −10   critical = −20

Result is clamped to [0, 100].
```

### Status thresholds (configurable in `dashboard_config` table)

| Composite Score | Status |
|---|---|
| ≥ 80 | `green` — Healthy |
| 60–79 | `amber` — Degraded |
| < 60 | `red` — Critical |

---

## 8. Multi-Row Files (Trend Data)

For the 7-day trend chart to populate, the file must contain multiple
timestamped snapshots for each site — not just a single point-in-time export.

The trend query groups records by hour using `date_trunc('hour', ingested_at)`
in TimescaleDB. Each ingestion cycle adds one row per site to the database,
building up historical data over time.

**Recommended for trend demonstration:** use `aruba_health_7day.csv` which
contains 2,016 rows (12 sites × 7 days × 24 hourly snapshots).

To load it as the active file:

```bash
# Developer
cp data/aruba_health_7day.csv data/aruba_health.csv
make ingest

# Customer
make customer-update-csv CSV=data/aruba_health_7day.csv
```

---

## 9. Phase 2 Alignment

The field names in this schema exactly match the fields returned by the
HPE Aruba Central REST API endpoints:

| This schema field | Aruba Central API field | Aruba API endpoint |
|---|---|---|
| `site_health_score` | `health_score` | `GET /aiops/v1/sites/health` |
| `ap_total` | `total_aps` | `GET /monitoring/v1/aps` |
| `ap_online` | `up_aps` | `GET /monitoring/v1/aps` |
| `ap_offline` | `down_aps` | `GET /monitoring/v1/aps` |
| `client_count` | `client_count` | `GET /monitoring/v1/clients` |
| `auth_failures_1h` | `authentication_failure_count` | `GET /monitoring/v1/clients` |
| `uplink_quality` | `wan_uplink_status` | `GET /sdwan/v1/uplinks/bandwidth` |

Minor field name differences will be handled by the Phase 2 connector mapping
layer — the `ArubaRawRecord` Pydantic model and all downstream normalisation
code remain unchanged.

---

## 10. Document Control

| Version | Date | Changes | Author |
|---|---|---|---|
| v1.0 | April 2026 | Initial release | Infrastructure Architecture Team |
