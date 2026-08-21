# ROADMAP.md — Sprint & Phase Plan

Two numbering schemes exist in the source documents — both reproduced as-is rather than merged, so
neither drifts from what was actually contracted.

## SOW Phase 2 — sprint deliverables (contractual, S1-S8)

| Sprint | Ref | Deliverable | Acceptance criterion |
|---|---|---|---|
| S1 | D1.1 | Aruba API discovery doc — confirmed endpoint, credentials, schema | Reviewed and agreed by client Network Engineering |
| S1 | D1.2 | Site-to-service mapping template, >=20% of sites | Template reviewed with client, gaps identified and planned |
| S2 | D2.1 | Live Aruba Central API integration — wireless shows real-time data | Client validates wireless data against Aruba Central portal |
| S2 | D2.2 | Wireless demo mode retired — POC banner removed | Dashboard shows live data on every page load |
| S3 | D3.1 | AVD discovery doc — Log Analytics assessment and integration design | Reviewed and agreed before build |
| S3 | D3.2 | Application URL discovery — confirmed URLs, network paths, probe location | All three app URLs confirmed with SAP team |
| S4 | D4.1 | AVD Services pillar live — host pool availability, session health | Client validates against Azure portal |
| S4 | D4.2 | Application Availability pillar live — S/4HANA, ECC, M3 probes | UP/DEGRADED/DOWN states trigger correctly |
| S5 | D5.1 | Zabbix discovery doc | Reviewed and agreed before build |
| S5 | D5.2 | Printing Services pillar live | Client validates against Zabbix dashboard |
| S6 | D6.1 | Site health model design doc — scoring formula, config approach | Signed off by client before build |
| S6 | D6.2 | Site health engine — dynamic scoring by configured services per site | Scores demonstrably differ across differently-configured sites |
| S6 | D6.3 | Country consolidation from site scores | Country score changes when a member site changes status |
| S7 | D7.1 | Capacity planning report | Reviewed, production provisioning agreed |
| S7 | D7.2 | Authentication study and proposal | Client selects preferred auth approach |
| S8 | D8.1 | Full five-pillar integrated dashboard, site+country hierarchy | All five pillars live simultaneously |
| S8 | D8.2 | Country selector on overall GBS score | Client validates country/site scores reflect underlying data |
| S8 | D8.3 | UAT completion | Formal client sign-off on all sprint deliverables |

## POC Closure Report — integration roadmap (Phase 1-5)

1. **Aruba Central Live API** — activate live wireless integration, replace CSV ingestion. Dependency: M2M credentials from Network Engineering.
2. **AVD + Application Availability** — Azure Monitor Log Analytics + synthetic URL monitoring (S/4HANA, ECC, M3). Dependency: Azure Service Principal, AVD workspace, app URLs from SAP team.
3. **Printing Services** — Zabbix JSON-RPC. Dependency: Zabbix read-only account, web API URL.
4. **Site-Level Health Model** — dynamic per-site scoring, country consolidation, GBS composite with selector. Dependency: service-to-site mapping data from client (this is SOW D1.2 / action item A4).
5. **Production Dashboard** — card grid + slide-in drawer, auth/RBAC, automated PDF reporting, HA. Dependency: infrastructure provisioning, identity provider config.

## Capability Overview — phase framing (client-facing narrative)

Phase 2: live Aruba API (one config change). Phase 3: AVD. Phase 4: Applications. Phase 5: Printing.
Phase 6: PDF reports, alerting, HA/DR, RBAC, operations handover. Each phase is a standalone
deliverable with its own SOW — client commits one phase at a time based on demonstrated results.

## Open action items carried from POC closure (owners/dates not yet assigned in source)

- A1 — Provision Aruba Central M2M API credentials (resolved — see STATUS.md, credentials obtained).
- A4 — Site-to-service mapping data (= SOW D1.2, currently the critical path — see STATUS.md).
- A7 — Agree Green/Amber/Red thresholds per pillar with GBS service owners.
- P2 — `sw_country_groups` table needs real country values matching the SolarWinds custom property.
- P3 — Nightly data-retention job (90-day) needs scheduling by DBA team.
