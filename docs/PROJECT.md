# PROJECT.md — GBS Service Health Dashboard

Background and architecture context. Rules live in `CLAUDE.md`; current status lives in `STATUS.md`;
sprint/phase plan lives in `ROADMAP.md`. This file does not change often — if you're editing it to
record "what happened this week," it belongs in `STATUS.md` instead.

## What this is

A consolidated, real-time health view across the technology pillars that underpin the client's
Global Business Service (GBS) — the shared-services platform delivering HR and Finance functions
across the organisation. Hierarchy target: **Overall GBS -> Country -> Site -> Service**.

Five planned pillars, lettered A-E for client-facing material only (never used as an identifier —
see `CLAUDE.md` naming rules):

| Pillar | Canonical id | Source system | Status |
|---|---|---|---|
| A — Wireless Health | `wireless` | HPE Aruba Central | Interim file-based ingestion; live API connector built, has known gaps (see STATUS.md) |
| E — LAN Health | `lan` | SolarWinds Observability (SWIS REST API) | Live — 700+ nodes, 30 countries |
| B — AVD Services | `avd` | Azure Monitor Log Analytics | Not started — UI placeholder only |
| C — Application Availability | `apps` | Synthetic URL probes (SAP S/4HANA, ECC, M3) | Not started — UI placeholder only |
| D — Printing Services | `printing` | Zabbix JSON-RPC | Not started — UI placeholder only |

## Architecture (current — Phase 1/2 POC)

Three containers on a private Docker network:

- **gbs_db** — TimescaleDB (PostgreSQL 15). `wireless_metrics` hypertable + `dashboard_config` key/value table.
- **gbs_backend** — FastAPI. Runs an asyncio polling loop (`polling_loop()`), normalises data, persists
  to DB, serves REST API. In-memory `_state` dict serves `/summary`, `/sites`, `/alerts` in <1ms;
  `/trend` queries TimescaleDB directly (historical data doesn't fit in memory).
- **gbs_frontend** — React 18 + Vite. No direct DB access — everything comes from the FastAPI BFF.

Ingestion cycle (one per `POLL_INTERVAL_SECONDS`, immediate on startup):
`get_connector().fetch()` -> `normalise_records()` -> `build_summary()` -> `persist_sites()` -> update `_state`.

Pluggable connector pattern: `BaseConnector` -> `FileConnector` (CSV/JSON, Phase 1) or `ArubaAPIConnector`
(Phase 2, OAuth 2.0 refresh_token grant). Switching source is a `DATA_SOURCE_TYPE` env var change — see
`CLAUDE.md` §4, this is a non-negotiable design constraint, not just current practice.

Health score formula (Wireless pillar):
```
composite_score = (site_health_score / 100 x 50)     # Aruba AI Insights score component
                 + (ap_online / ap_total x 30)         # AP availability component
                 + alert_penalty                       # none=0 info=-2 warning=-10 critical=-20
status = green (>=80) | amber (60-79) | red (<60)
```
Thresholds live in `dashboard_config` (DB), not code — per `CLAUDE.md` §1.3.

## Production direction (binding client requirements)

Captured from the POC demo debrief — per `CLAUDE.md` §9, these are binding, not aspirational:

- **Site-level health is dynamic and configurable** per the services actually present at that site —
  not a fixed formula applied uniformly. A site with only wireless+LAN scores differently from a
  site with all five pillars.
- **Country consolidation**: site scores roll up to country-level scores, which roll up to the
  overall GBS composite score. The country selector proven in the LAN pillar extends to the overall
  score, not just individual pillars.
- **CXO room display**: production dashboard runs continuously on a dedicated screen for leadership
  visibility. Layout direction: card grid with slide-in detail drawer, no scrolling required.

## Where deeper reference material lives

The full discovery/design/SOW documents (Aruba API Discovery Doc, LLD, HLD, SOW Phase 2, POC Closure
Report, Installation Guide, Schema Spec) are one directory up from this repo
(`C:\CustomProjects\dashboard\gbs\`) as source `.docx`/`.md` files, and mirrored in the
"Infrastructure Availability Dashboard" project on claude.ai. This `docs/` folder is the
Claude-Code-facing distillation — update it when those source documents change materially, but don't
try to keep it byte-for-byte in sync; it's meant to be the fast-loading summary, not the archive.

## Repo map

See `CLAUDE.md` §2 for the intended layer structure. `README.md` at the repo root has the
current, maintained file-by-file tree — regenerate `CLAUDE.md`'s repo map from there (or `tree -L 2`)
rather than duplicating it here, so there's exactly one place it can go stale.
