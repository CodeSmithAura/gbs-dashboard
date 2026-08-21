# GBS Service Health Dashboard — Sprint 1 Status Note

**Prepared for:** Karthik
**Date:** 20 August 2026
**Sprint:** Sprint 1 (Weeks 1–2) — Discovery: Aruba + Site Health Model initiation — Milestone 1

## Summary

Sprint 1 carries two deliverables under Milestone 1. The Aruba side is functionally ahead of where Sprint 1 asks it to be, but isn't closed out yet. The site mapping side hasn't started. Overall, Sprint 1 is roughly half done by deliverable count, with the open half (site mapping) being the bigger risk to closing the milestone.

## Deliverable status


| Ref | Deliverable | Acceptance criterion | Status |
|---|---|---|---|
| D1.1 | Aruba API discovery document — confirmed endpoint, credentials, data schema | Document reviewed and agreed by client Network Engineering team | **In progress, ahead of scope.** The Aruba credential blocker is resolved and the live connector is functionally working against Aruba's real API (OAuth token refresh, AP inventory, client counts, and alerts all confirmed) — closer to Sprint 2's "live integration" bar than Sprint 1's "discovery" bar. Not yet closeable: the intended per-site composite health score endpoint doesn't exist on Aruba's API (currently falls back to an AP-ratio approximation), alert fetching has no pagination, the OAuth refresh token is stored in plaintext rather than in the HLD's designated secret store, and the formal document review/sign-off with Network Engineering hasn't happened. |
| D1.2 | Site-to-service mapping template populated for ≥20% of sites | Template reviewed with client, gaps identified and planned | **Not started.** No template exists yet and no site data has been collected. This is independent of the Aruba work and needs its own push — see next steps. |

## Open items and owners

- **Aruba discovery doc sign-off** — BMI Technology to close the four technical gaps above, then route the doc to the client's Network Engineering team for formal review and agreement.
- **Site mapping data** — the *template* is BMI Technology's deliverable (Sprint 1); the underlying data on which services exist at each site is the client's GBS / IT Operations team's responsibility (SOW dependency C2), due Sprint 3 Day 1, with full coverage required before the Sprint 6 site health model build. The POC closure report logged this as action item A4 with no named owner — worth pinning down a specific contact.
- **Secrets management** — Aruba refresh token (and SolarWinds password) need to move into proper secret storage before production credentials are issued; flagged in both the HLD and the recent API review.

## Next steps

1. Send the site mapping template (attached) to the client GBS / IT Operations contact and request the first batch of site data.
2. Decide on the site-health scoring redesign (per-AP aggregation) now that the bulk composite-score endpoint is confirmed unavailable.
3. Fix alert pagination and move the Aruba token to secure storage.
4. Schedule the Network Engineering review session to formally close D1.1.

