# STATUS.md — Current State

Last updated: 21 August 2026. This file is meant to be overwritten as status changes — keep it
current, not historical. Move anything that reads as a lesson learned into `LEARNINGS.md` instead.

## Current sprint

**Sprint 1** (SOW Phase 2, Weeks 1-2) — Aruba discovery + site-to-service mapping template. Roughly
half done by deliverable count; site mapping (D1.2) is the bigger risk to closing the milestone.

| Ref | Deliverable | Status |
|---|---|---|
| D1.1 | Aruba API discovery doc (endpoint/credential/schema confirmation) | In progress, functionally ahead of scope but not closeable — see gaps below |
| D1.2 | Site-to-service mapping template, >=20% of sites | Not started — template built and ready to send, no site data collected yet |

D1.1 is not closeable until: (a) the two engineering gaps below are addressed or explicitly
sequenced, and (b) the discovery doc gets formal review/sign-off from the client's Network
Engineering team.

## Live API status (Aruba Central, wireless pillar)

| Endpoint | Status |
|---|---|
| `POST /oauth2/token` | Working — refresh_token grant only. `client_credentials` is NOT supported for this integration type (corrects an earlier LLD/HLD assumption) |
| `GET /monitoring/v2/aps` | Working, paginated |
| `GET /monitoring/v2/clients` | Working, paginated; no per-site aggregate count endpoint exists — counts aggregated client-side from the full list |
| `GET /central/v1/notifications` | Working, paginated (fixed 21 Aug 2026 — see engineering follow-ups below) |
| `GET /aiops/v2/sites/health` | 404 — no bulk per-site composite score endpoint exists on the real API. Falls back to AP-ratio-only scoring |
| SSID / SD-WAN uplink endpoints | Not yet implemented or tested against live API |

## Engineering follow-ups (analysis done 21 Aug 2026)

Scoped ahead of sharing the discovery doc with Network Engineering, so the follow-ups list reads as
sequenced work rather than unowned gaps.

1. **Alert pagination — fixed 21 Aug 2026.** `_fetch_alerts` (`app/services/ingestion.py`) called
   `/central/v1/notifications` with a flat `limit=100`, no paging loop, so `alert_severity` per site
   (which drives the composite score's alert penalty and status colour) was derived from whichever
   alerts landed in page one — a site could display healthier than it actually was at scale. Fix:
   `_fetch_alerts` now routes through the same `_fetch_all_pages` helper the AP and client fetches
   already used, extended with an `extra_params` passthrough (for the `state=Open` filter) and a
   50-page safety cap that logs a warning if hit rather than looping or truncating silently. Also
   preserves the pre-existing `notifications`/`alerts` key-fallback (response envelope still isn't
   confirmed from Aruba's docs). Added `backend/tests/test_aruba_pagination.py` (9 tests, mocks `_get`
   directly — no real HTTP/OAuth) closing the "no test coverage for the Aruba connector" gap noted
   below.
   Note: SolarWinds' `_QUERY_ALERTS` (SWQL, `TOP {limit}` capped at 500, LAN pillar) has the same
   silent-truncation shape but was **not** touched by this fix — different transport (SWQL has no
   offset/cursor support the way the Aruba REST API does), still tracked under "Other known gaps"
   below, not yet sequenced.

2. **Credential storage** (deferred, sequenced after #1 — #1 is now done, so this is next up when
   picked up) — Aruba refresh token and SolarWinds password persisted in plaintext `.env`,
   contradicts the HLD's own Vault/Key Vault design. `ingestion.py`'s `_persist_refresh_token` also
   writes each newly-rotated refresh token back into that plaintext file at runtime, on every token
   refresh — not just a static provisioning-time exposure, but the module docstring's "tokens stored
   in memory only, never written to disk" claim (`app/services/ingestion.py` lines ~31-34) is
   inaccurate as a result. Stays parked per explicit decision; keep it visibly listed as deferred, not
   silently dropped, when this status goes external.

3. **POC banner + demo simulation mode removal** (sequence after #1, once live path is trusted) —
   Two separate pieces:
   - `PocBanner.jsx` — already scoped in the LLD as a one-line `return null` change.
   - The built-in 10-step outage simulation ("Run Demo" / "Stop Demo", see
     `GBS_POC_Capability_Overview.txt`) that cycles real Aruba snapshots to fake live data during
     stakeholder demos — not documented in the LLD (added after v1.0), implementation not yet
     located in source. Confirm which file(s) implement it before sizing the removal.
   This isn't scope creep: SOW Phase 2 Sprint 2 deliverable **D2.2** already contracts "demo mode
   retired, POC banner removed" with acceptance criterion "dashboard shows live data on every page
   load." Recommended order: fix alert pagination first, confirm the live Aruba path holds up, then
   remove the demo fallback — pulling the safety net before the live path is proven risks a bad
   moment during a stakeholder-facing session.

## Other known gaps (API/architecture review, 19 Aug 2026 — not yet actioned)

- SolarWinds connector opens/closes a separate httpx client per fetch call (3 handshakes per LAN
  cycle) despite the module docstring claiming one reused client.
- `_QUERY_ALERTS` hard-capped at 500 (`SW_ALERT_LIMIT`) with no indicator if the true count exceeds
  it — same silent-truncation class as the Aruba notifications gap.
- `_QUERY_NODES` has no WHERE clause, no row cap, no pagination — pulls every Orion node every cycle.
- `backend/app/lan.py` is a stale near-duplicate of `app/api/lan.py`, missing newer validation —
  dead-file risk if someone wires in the wrong copy.
- No auth/RBAC on any API route (HLD decision D.9, open).
- CORS is `allow_origins=["*"]`, flagged in-code as POC-only.
- No SLA/uptime %, alert aging/MTTA/MTTR, or admin UI for thresholds yet — tracked as Part 3
  production-readiness items, not yet scheduled.

## Not yet started

AVD pillar, Application Availability pillar, Printing pillar, site-level dynamic health model,
country/GBS composite rollup, auth/RBAC, PDF reporting, HA/DR.
