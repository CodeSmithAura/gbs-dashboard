# GBS Service Health Dashboard — Wireless POC

**Phase 1 · File-Based Data Ingestion · Docker**

A fully runnable proof-of-concept for the GBS Wireless Health Dashboard.
Reads Aruba health data from a CSV file, processes it through a normalisation
pipeline, stores metrics in TimescaleDB, and serves a live React dashboard —
all in Docker with no external dependencies.

---

## Environments

| Environment | Command | Data source | Images |
|---|---|---|---|
| **Developer** | `make dev-up` | Bind-mounted `./data/` — edit CSV freely on host | Built from source |
| **Customer** | `make customer-up` | Named Docker volume `gbs_data` — updated via `docker cp` | Pre-built `.tar` files |

---

## Quick Start — Developer

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start all containers (builds images from source)
make dev-up

# 3. Open dashboard
open http://localhost:3000
```

Backend hot-reloads on `.py` changes. Frontend hot-reloads on `.jsx` changes.
CSV edits on the host are visible instantly — trigger ingest with `make ingest`.

---

## Quick Start — Customer (offline)

> Full instructions are in **GBS_Installation_Guide_v1.0.docx**

```bash
# 1. Load pre-built images (from USB / shared folder)
docker load -i gbs-backend.tar
docker load -i gbs-frontend.tar

# 2. Create data volume and load CSV (once)
make customer-init-volume

# 3. Start application
make customer-up

# 4. Open dashboard
open http://localhost:3000
```

---

## What Starts

```
gbs_db        TimescaleDB (PostgreSQL 15)    localhost:5432
gbs_backend   FastAPI + ingestion worker     localhost:8000
gbs_frontend  React (Vite dev server)        localhost:3000
```

The backend ingests the CSV on startup, then every 60 seconds (dev: 10 seconds).

---

## Developer Commands

```bash
# Lifecycle
make dev-up              # build and start (developer)
make dev-down            # stop developer containers
make customer-up         # start customer containers (pre-built images)
make customer-down       # stop customer containers

# Data
make ingest              # trigger ingestion cycle immediately
make summary             # print current wireless summary JSON
make alerts              # print active alerts JSON

# CSV — developer (bind mount — just edit ./data/aruba_health.csv directly)
# CSV — customer (named volume)
make customer-update-csv CSV=data/new_file.csv

# Build images for customer delivery
make build-images        # outputs gbs-backend.tar + gbs-frontend.tar

# Database
make psql                # open psql shell in db container
make reset-db            # drop and re-initialise DB (destructive)

# Observability
make logs                # tail all container logs
make logs-backend        # tail backend logs only
make health              # check backend /health endpoint
make status              # show container status

make help                # show all commands
```

---

## Project Structure

```
gbs-poc/
│
├── docker-compose.yml            Base — shared service definitions
├── docker-compose.dev.yml        Developer overlay — build from source, bind mounts
├── docker-compose.customer.yml   Customer overlay — pre-built images, named volume
├── Makefile                      All dev and delivery commands
├── .env.example                  Environment variable template
├── README.md                     This file
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py               FastAPI entrypoint + asyncio lifespan
│       ├── core/
│       │   ├── config.py         All settings (env-driven, extra vars ignored)
│       │   └── database.py       SQLAlchemy engine + session
│       ├── models/
│       │   ├── schemas.py        Pydantic: ArubaRawRecord, SiteHealth, WirelessSummary
│       │   └── orm.py            SQLAlchemy ORM: WirelessMetric, DashboardConfig
│       ├── services/
│       │   ├── ingestion.py      ★ Pluggable connector (FileConnector / ArubaAPIConnector stub)
│       │   ├── normaliser.py     Score formula + Green/Amber/Red logic
│       │   └── db_writer.py      TimescaleDB persistence + trend query
│       ├── api/
│       │   └── wireless.py       REST: /summary /sites /alerts /trend /ingest/trigger
│       └── workers/
│           └── scheduler.py      asyncio polling loop (replaces APScheduler)
│   └── tests/
│       └── test_pipeline.py      20 smoke tests — schema, scoring, normaliser, connectors
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js            Proxy → http://backend:8000 (Docker internal hostname)
│   └── src/
│       ├── App.jsx               Root layout
│       ├── index.css             CSS custom properties + global styles
│       ├── pages/Dashboard.jsx   Main dashboard page
│       ├── components/
│       │   ├── common/           PocBanner, Header, Footer
│       │   └── dashboard/        ScoreGauge, KpiCard, SiteTable, AlertFeed, TrendChart
│       ├── hooks/useDashboard.js Auto-refresh hook (30s)
│       └── utils/
│           ├── api.js            All API calls — single place
│           └── helpers.js        Status colours, date formatters
│
├── infra/
│   └── init.sql                  TimescaleDB hypertable + seed config
│
└── data/
    ├── aruba_health.csv           Active data file (developer — edit freely)
    ├── aruba_health_7day.csv      7-day 2,016-row dataset (trend chart demo)
    └── samples/
        ├── aruba_health_sample.csv   12-site snapshot (CSV)
        └── aruba_health_sample.json  Same data in JSON format
```

---

## API Reference

Interactive docs: `http://localhost:8000/docs`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | App health, DB status, last ingest, source type |
| `GET` | `/api/v1/wireless/summary` | Overall score, status, KPI aggregates |
| `GET` | `/api/v1/wireless/sites` | Per-site health breakdown |
| `GET` | `/api/v1/wireless/alerts` | Active alerts sorted by severity |
| `GET` | `/api/v1/wireless/trend?hours=168` | Hourly trend (default 7 days) |
| `POST` | `/api/v1/wireless/ingest/trigger` | Manually trigger ingestion cycle |

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/test_pipeline.py -v
```

20 tests covering schema validation, score computation, normaliser, summary
builder, alert extraction, and file connectors (CSV + JSON + missing file).

---

## Health Score Formula

```
composite_score = (site_health_score / 100 × 50)
                + (ap_online / ap_total   × 30)
                + alert_penalty

alert_penalty:  none = 0   info = −2   warning = −10   critical = −20
```

| Score | Status |
|---|---|
| ≥ 80 | 🟢 Green — Healthy |
| 60–79 | 🟡 Amber — Degraded |
| < 60 | 🔴 Red — Critical |

Thresholds are stored in `dashboard_config` (PostgreSQL) — adjustable without code changes.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DATA_SOURCE_TYPE` | `file` | `file` for POC · `api` for Phase 2 |
| `DATA_SOURCE_FORMAT` | `csv` | `csv` or `json` |
| `DATA_SOURCE_PATH` | `/app/data/aruba_health.csv` | Path inside backend container |
| `POLL_INTERVAL_SECONDS` | `60` (customer) / `10` (dev) | How often ingestion runs |
| `ARUBA_BASE_URL` | _(blank)_ | Phase 2 — Aruba Central API base URL |
| `ARUBA_CLIENT_ID` | _(blank)_ | Phase 2 — OAuth 2.0 client ID |
| `ARUBA_CLIENT_SECRET` | _(blank)_ | Phase 2 — OAuth 2.0 client secret |

---

## Updating the CSV

**Developer** — edit `./data/aruba_health.csv` directly on the host, then:
```bash
make ingest
```

**Customer** — copy a new file into the named volume, then trigger ingest:
```bash
make customer-update-csv CSV=data/new_aruba_health.csv
```

---

## Customer Delivery

```bash
# 1. Build and export images
make build-images
# outputs: gbs-backend.tar  gbs-frontend.tar

# 2. Hand over these files to the customer:
#    gbs-backend.tar
#    gbs-frontend.tar
#    docker-compose.yml
#    docker-compose.customer.yml
#    infra/init.sql
#    data/aruba_health_7day.csv
#    GBS_Installation_Guide_v1.0.docx
```

Customer follows **GBS_Installation_Guide_v1.0.docx** — no internet required
after the one-time Docker Desktop install.

---

## Phase 2 Upgrade (Live Aruba API)

Change two env vars in `docker-compose.customer.yml` — nothing else:

```yaml
environment:
  DATA_SOURCE_TYPE: api
  ARUBA_BASE_URL: https://apigw-prod2.central.arubanetworks.com
  ARUBA_CLIENT_ID: your-client-id
  ARUBA_CLIENT_SECRET: your-client-secret
  ARUBA_CUSTOMER_ID: your-customer-id
```

Then implement `ArubaAPIConnector.fetch()` in `backend/app/services/ingestion.py`
(the stub and interface are already in place). Normaliser, DB, BFF, and
React dashboard are all unchanged.

---
