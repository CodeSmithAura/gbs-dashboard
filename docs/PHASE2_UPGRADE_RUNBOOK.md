# Phase 2 Upgrade Runbook — File to Live Aruba API

**Document:** GBS-RUNBOOK-PHASE2-v1.0  
**Version:** v1.0 — April 2026  
**Prerequisite:** Phase 1 POC running successfully (`make dev-up` works, dashboard loads)

---

## Overview

This runbook moves the GBS dashboard from reading a static CSV file to polling
the live HPE Aruba Central REST API. The change is isolated to:

1. One connector class (`ArubaAPIConnector` — stub already in place)
2. Environment variables (credentials + source type)
3. Removing the POC banner from the frontend

**Nothing else changes.** The normaliser, database schema, BFF API, and React
dashboard are identical in Phase 2.

---

## Pre-requisites — Client Must Complete First

| # | Item | Owner | Status |
|---|---|---|---|
| P1 | Aruba Central OAuth 2.0 app registered — Client ID and Secret obtained | Network Engineering | Pending |
| P2 | API rate limits confirmed — 5-min polling supported across all endpoints | Network Engineering | Pending |
| P3 | Aruba Central subscription tier includes `/aiops/v1/sites/health` (AI Insights) | Network Engineering | Pending |
| P4 | Apache Airflow provisioned (optional — replaces Python scheduler for production) | Infrastructure | Pending |
| P5 | HashiCorp Vault or Azure Key Vault provisioned for credential storage | InfoSec | Pending |
| P6 | Green/Amber/Red thresholds agreed with GBS service owners | GBS Owner + IT Ops | Pending |

Do not proceed until P1 and P2 are confirmed.

---

## Step 1 — Implement `ArubaAPIConnector.fetch()`

Open `backend/app/services/ingestion.py`. Find the stub class:

```python
class ArubaAPIConnector(BaseConnector):
    def fetch(self) -> List[ArubaRawRecord]:
        raise NotImplementedError("ArubaAPIConnector is Phase 2 scope.")
```

Replace the `fetch()` method body with the implementation below:

```python
def fetch(self) -> List[ArubaRawRecord]:
    import httpx, time

    # ── Step 1: Get OAuth 2.0 token ──────────────────────────────────────
    token_url = f"{settings.ARUBA_BASE_URL}/oauth2/token"
    resp = httpx.post(token_url, data={
        "grant_type":    "client_credentials",
        "client_id":     settings.ARUBA_CLIENT_ID,
        "client_secret": settings.ARUBA_CLIENT_SECRET,
    }, timeout=15)
    resp.raise_for_status()
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ── Step 2: Fetch site health scores ─────────────────────────────────
    sites_resp = httpx.get(
        f"{settings.ARUBA_BASE_URL}/aiops/v1/sites/health",
        headers=headers,
        params={"customer_id": settings.ARUBA_CUSTOMER_ID, "limit": 1000},
        timeout=30,
    )
    sites_resp.raise_for_status()
    sites_data = {s["site_id"]: s for s in sites_resp.json().get("sites", [])}

    # ── Step 3: Fetch AP counts ───────────────────────────────────────────
    aps_resp = httpx.get(
        f"{settings.ARUBA_BASE_URL}/monitoring/v1/aps",
        headers=headers,
        params={"customer_id": settings.ARUBA_CUSTOMER_ID, "limit": 1000},
        timeout=30,
    )
    aps_resp.raise_for_status()
    ap_data = {}
    for ap in aps_resp.json().get("aps", []):
        sid = ap.get("site_id")
        if sid not in ap_data:
            ap_data[sid] = {"total": 0, "online": 0}
        ap_data[sid]["total"] += 1
        if ap.get("status") == "Up":
            ap_data[sid]["online"] += 1

    # ── Step 4: Fetch connected clients ───────────────────────────────────
    clients_resp = httpx.get(
        f"{settings.ARUBA_BASE_URL}/monitoring/v1/clients",
        headers=headers,
        params={"customer_id": settings.ARUBA_CUSTOMER_ID, "limit": 1000},
        timeout=30,
    )
    clients_resp.raise_for_status()
    client_counts = {}
    auth_fails = {}
    for c in clients_resp.json().get("clients", []):
        sid = c.get("site_id")
        client_counts[sid] = client_counts.get(sid, 0) + 1
        if c.get("failure_reason"):
            auth_fails[sid] = auth_fails.get(sid, 0) + 1

    # ── Step 5: Fetch alerts ───────────────────────────────────────────────
    alerts_resp = httpx.get(
        f"{settings.ARUBA_BASE_URL}/monitoring/v1/alerts",
        headers=headers,
        params={"customer_id": settings.ARUBA_CUSTOMER_ID, "limit": 1000},
        timeout=30,
    )
    alerts_resp.raise_for_status()
    alert_map = {}
    SEV_RANK = {"critical": 4, "warning": 3, "minor": 2, "info": 1}
    SEV_MAP  = {"critical": "critical", "warning": "warning", "minor": "warning", "info": "info"}
    for a in alerts_resp.json().get("alerts", []):
        sid = a.get("site_id")
        rank = SEV_RANK.get(a.get("severity", ""), 0)
        if sid not in alert_map or rank > alert_map[sid]["rank"]:
            alert_map[sid] = {
                "rank":        rank,
                "severity":    SEV_MAP.get(a.get("severity", ""), "info"),
                "description": a.get("description", ""),
                "count":       0,
            }
        alert_map[sid]["count"] += 1

    # ── Step 6: Build ArubaRawRecord list ─────────────────────────────────
    now = datetime.now(timezone.utc)
    records = []
    for site_id, site in sites_data.items():
        aps   = ap_data.get(site_id, {"total": 0, "online": 0})
        alert = alert_map.get(site_id, {"severity": "none", "description": "", "count": 0})
        records.append(ArubaRawRecord(
            site_id          = site_id,
            site_name        = site.get("site_name", site_id),
            timestamp        = now,
            site_health_score= int(site.get("health_score", 0)),
            ap_total         = aps["total"],
            ap_online        = aps["online"],
            ap_offline       = aps["total"] - aps["online"],
            client_count     = client_counts.get(site_id, 0),
            auth_failures_1h = auth_fails.get(site_id, 0),
            active_alerts    = alert["count"],
            alert_severity   = alert["severity"],
            alert_description= alert["description"],
            ssid_count       = len(site.get("ssids", [])),
            uplink_quality   = site.get("wan_uplink_status", "good"),
        ))
    logger.info(f"Aruba API connector: fetched {len(records)} sites")
    return records
```

Also add `from datetime import timezone` to the imports at the top of `ingestion.py` if not present.

---

## Step 2 — Update Environment Variables

### Developer environment — edit `.env`:

```bash
# Change from:
DATA_SOURCE_TYPE=file

# To:
DATA_SOURCE_TYPE=api
ARUBA_BASE_URL=https://apigw-prod2.central.arubanetworks.com
ARUBA_CLIENT_ID=your-client-id-here
ARUBA_CLIENT_SECRET=your-client-secret-here
ARUBA_CUSTOMER_ID=your-customer-id-here
POLL_INTERVAL_SECONDS=300
```

### Customer environment — edit `docker-compose.customer.yml`:

```yaml
backend:
  environment:
    DATA_SOURCE_TYPE: api
    ARUBA_BASE_URL: https://apigw-prod2.central.arubanetworks.com
    ARUBA_CLIENT_ID: your-client-id-here
    ARUBA_CLIENT_SECRET: your-client-secret-here
    ARUBA_CUSTOMER_ID: your-customer-id-here
    POLL_INTERVAL_SECONDS: 300
```

> Note: For production, credentials should be stored in HashiCorp Vault or
> Azure Key Vault and injected at runtime — not hardcoded in compose files.

---

## Step 3 — Restart the Backend

```bash
# Developer
docker compose restart backend

# Customer
docker compose -f docker-compose.yml -f docker-compose.customer.yml restart backend
```

Watch the logs to confirm a successful API cycle:

```bash
docker compose logs -f backend
```

Expected output:

```
INFO | Ingestion cycle starting...
INFO | Aruba API connector: fetched 12 sites
INFO | DB writer: persisted 12 site records.
INFO | Ingestion cycle complete: 12 sites, overall score=84.2, status=green
```

If you see `401 Unauthorized` — credentials are wrong.  
If you see `403 Forbidden` — subscription tier doesn't include that endpoint.  
If you see `429 Too Many Requests` — increase `POLL_INTERVAL_SECONDS`.

---

## Step 4 — Remove the POC Banner

Open `frontend/src/components/common/PocBanner.jsx`.

Find the condition that shows the purple banner:

```jsx
if (!summary) return null
```

Change it to always return null (or delete the component):

```jsx
export default function PocBanner() {
  return null
}
```

The banner will disappear on the next Vite hot-reload. No rebuild needed in dev.

For the customer image rebuild:

```bash
make build-images
# Re-deliver gbs-frontend.tar to customer
```

---

## Step 5 — Upgrade the Scheduler to Airflow (Optional but Recommended)

The current Python scheduler works for Phase 2 but has no retry logic,
observability, or SLA alerting. For production, replace it with an Airflow DAG.

**New file:** `backend/dags/wireless_ingest_dag.py`

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "gbs-dashboard",
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "email_on_failure": True,
    "email": ["infra-alerts@bmi.com"],
}

def run_cycle():
    from app.workers.scheduler import run_ingestion_cycle
    run_ingestion_cycle()

with DAG(
    "wireless_health_ingest",
    default_args=default_args,
    start_date=datetime(2026, 4, 1),
    schedule_interval=timedelta(minutes=5),
    catchup=False,
) as dag:
    PythonOperator(task_id="ingest", python_callable=run_cycle)
```

Remove the `start_scheduler()` call from `main.py` once Airflow is managing the schedule.

---

## Step 6 — Validate Against Mock API (AC12)

Before deploying with real Aruba credentials, validate the connector
against a mock API server to confirm the upgrade path works end-to-end.

### Start a mock server (one-liner using Python):

```bash
pip install fastapi uvicorn --break-system-packages
```

Save as `mock_aruba.py`:

```python
from fastapi import FastAPI
app = FastAPI()

TOKEN_RESP = {"access_token": "mock-token-abc123", "expires_in": 7200}
SITES_RESP = {"sites": [
    {"site_id": "SITE-MOCK-01", "site_name": "Mock Site 1",
     "health_score": 87, "ssids": ["CORP","GUEST"], "wan_uplink_status": "good"},
    {"site_id": "SITE-MOCK-02", "site_name": "Mock Site 2",
     "health_score": 62, "ssids": ["CORP"], "wan_uplink_status": "fair"},
]}
APS_RESP = {"aps": [
    {"site_id": "SITE-MOCK-01", "status": "Up"},
    {"site_id": "SITE-MOCK-01", "status": "Up"},
    {"site_id": "SITE-MOCK-01", "status": "Down"},
    {"site_id": "SITE-MOCK-02", "status": "Up"},
]}
CLIENTS_RESP = {"clients": [
    {"site_id": "SITE-MOCK-01"}, {"site_id": "SITE-MOCK-01"},
    {"site_id": "SITE-MOCK-02"},
]}
ALERTS_RESP = {"alerts": [
    {"site_id": "SITE-MOCK-02", "severity": "warning",
     "description": "Mock uplink degraded"},
]}

@app.post("/oauth2/token")       # noqa
def token():    return TOKEN_RESP
@app.get("/aiops/v1/sites/health")
def sites():    return SITES_RESP
@app.get("/monitoring/v1/aps")
def aps():      return APS_RESP
@app.get("/monitoring/v1/clients")
def clients():  return CLIENTS_RESP
@app.get("/monitoring/v1/alerts")
def alerts():   return ALERTS_RESP
```

```bash
uvicorn mock_aruba:app --host 0.0.0.0 --port 9000
```

### Point the backend at the mock server:

```bash
# In .env:
DATA_SOURCE_TYPE=api
ARUBA_BASE_URL=http://host.docker.internal:9000
ARUBA_CLIENT_ID=mock-client
ARUBA_CLIENT_SECRET=mock-secret
ARUBA_CUSTOMER_ID=mock-customer
```

```bash
docker compose restart backend
make ingest
make summary
```

Expected: two sites returned (SITE-MOCK-01 green, SITE-MOCK-02 amber).  
Dashboard should reflect these sites — POC confirmed upgrade path works.

---

## Rollback

If the API connector fails in production:

```bash
# Revert to file mode in .env or docker-compose.customer.yml:
DATA_SOURCE_TYPE=file
DATA_SOURCE_PATH=/app/data/aruba_health.csv

docker compose restart backend
```

The CSV data serves immediately. No data is lost — TimescaleDB retains all
previously ingested metrics.

---

## Checklist

| Step | Action | Done |
|---|---|---|
| P1–P6 | Pre-requisites confirmed by client | ☐ |
| 1 | `ArubaAPIConnector.fetch()` implemented | ☐ |
| 2 | Environment variables updated with real credentials | ☐ |
| 3 | Backend restarted — logs show successful API ingest | ☐ |
| 4 | POC banner removed from frontend | ☐ |
| 5 | Airflow DAG deployed (if applicable) | ☐ |
| 6 | Mock API validation passed (AC12) | ☐ |
| — | Dashboard shows live Aruba data | ☐ |
| — | Sign-off obtained from client technical lead (AC11) | ☐ |

---

## Document Control

| Version | Date | Changes | Author |
|---|---|---|---|
| v1.0 | April 2026 | Initial release | Infrastructure Architecture Team |
