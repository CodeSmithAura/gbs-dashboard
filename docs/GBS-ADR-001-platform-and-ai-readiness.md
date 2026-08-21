# ADR-001: Phase 2 Data Platform and AI-Readiness Architecture

| Field | Value |
| --- | --- |
| Reference | GBS-ADR-001 |
| Status | Proposed (pending client ratification) |
| Date | August 2026 |
| Deciders | Programme Sponsor (Client), Integration Architect (BMI Technology), Client Infrastructure/Cloud leads |
| Programme | GBS Service Health Dashboard Consolidation Initiative |
| Related | GBS-SOW-PHASE2-v1.0, GBS-LLD-v1.0, GBS-POC-Closure-Report, Infra Dashboard HLD v1.2 |

---

## 1. Context and Problem Statement

The GBS Service Health Dashboard POC is complete and informally signed off by the client. Live SolarWinds (LAN) data was validated against the source console; Aruba (Wireless) is integrated. The POC runs on Microsoft SQL Server (Windows Server + IIS), with a Python/FastAPI backend and a React frontend.

The database history is relevant to this decision: the platform originally targeted PostgreSQL, but a client-side limitation during the POC led to settling on MS SQL Server. Phase 2 (full five-pillar integration and the site-level health model) is now beginning, which is the correct point to finalise the production technology stack rather than inheriting a POC-expedient choice by default.

The client has stated a forward-looking requirement: the dashboard must be "AI ready." In later stages they intend to build agents that analyse data across the pillars, predict issues, and take preventive measures before failures impact GBS users. The chosen stack must accommodate this without a later re-architecture.

Environment and scale constraints:

- Deployment is on-premises; the production dashboard is intended for a dedicated CXO-room display.
- Estate: ~30 countries, 110+ sites, variable services per site, 700+ LAN nodes (SolarWinds confirmed).
- Existing stack: Windows Server, MS SQL Server, IIS, Python 3.12 / FastAPI, React 18, pluggable per-pillar connectors, BFF pattern.

### What changed since the POC

Two developments materially alter the decision:

1. SQL Server 2025 reached general availability (late 2025) with a native VECTOR data type and VECTOR_DISTANCE as GA features, storing embeddings alongside relational data in-engine. Higher-end vector features (VECTOR_SEARCH, CREATE VECTOR INDEX / DiskANN, AI_GENERATE_EMBEDDINGS) remain in preview and require PREVIEW_FEATURES = ON.
2. Microsoft ships an official, open-source, free SQL MCP Server (built on Data API Builder) that runs on-premises and exposes databases to AI agents via the Model Context Protocol. It is engine-portable across MS SQL, PostgreSQL, Cosmos DB, and MySQL.

Consequence: the agent-facing contract (MCP) sits above the database, so the storage-engine choice no longer locks the AI roadmap. "AI-ready" becomes a layer to add, not a stack to rebuild. This reframes the core question from "which database" to "which storage baseline, plus how the AI/agent layer attaches."

Settled and carried forward in all options: pluggable per-pillar connectors, FastAPI BFF, React frontend. In contest: (1) the storage/analytics engine, (2) how the AI/agent layer attaches.

---

## 2. Decision Drivers

- D1. Minimise migration risk against a working, client-validated POC.
- D2. Client organisational fit: client selected MS SQL and previously declined Postgres; the team is Microsoft-centric.
- D3. On-premises deployment for a CXO-room display; resilience when infrastructure is degraded.
- D4. Time-series fitness for long-horizon trend and predictive workloads across five pillars.
- D5. Vector / RAG readiness for retrieval over runbooks, incident history, and alert descriptions.
- D6. Portability of the AI/agent layer so future agents are decoupled from the storage engine.
- D7. Operational simplicity: number of engines to run, secure, back up, and hand over.
- D8. Data residency across ~30 countries (GDPR and local regulation).
- D9. Cost profile (existing licensing vs new engines vs ongoing cloud spend).

---

## 3. Considered Options

- Option A - Microsoft-native (stay the course, add the AI layer): SQL Server 2025 as unified store (relational + partitioned/columnstore time-series + native VECTOR); Python/FastAPI; React; agent access via Microsoft SQL MCP Server; ML as Python jobs; embeddings/inference via Azure OpenAI or a local model.
- Option B - Purpose-built open-source data platform: migrate to PostgreSQL + TimescaleDB (hypertables, continuous aggregates, columnar compression) + pgvector/pgvectorscale in one engine; same FastAPI/React; agent access via the same MCP layer.
- Option C - Hybrid / polyglot persistence: MS SQL remains the operational system-of-record; a purpose-built analytics + AI sidecar (Postgres + TimescaleDB + pgvector, or a lighter analytical store) holds retained history, embeddings, and feeds ML/agents. AI workloads never touch the production OLTP database.
- Option D - Azure cloud-native / PaaS-forward: Azure SQL or Microsoft Fabric; Azure Monitor as-is; Azure AI Foundry / Agent Service for the agentic layer; Azure ML / Anomaly Detector for prediction.

Condensed pros/cons for each option are in Section 9.

---

## 4. Decision Outcome

Proposed decision (to be ratified with the client):

Adopt Option A (Microsoft-native) as the production baseline, with Option C (hybrid sidecar) pre-agreed as a criteria-based escape hatch. Treat AI-readiness as a layer decision, not a database decision, by committing now to four cross-cutting moves:

1. Adopt MCP as the agent-access contract now (Microsoft SQL MCP Server), even before any agents exist. This decouples all future agents from the storage engine; if time-series or vectors later move to a Timescale sidecar, the agents do not change. This is the single most important AI-ready move.
2. Add an event/stream path (Redis Streams, already in the HLD) so the predictive phase can act on signals in near-real-time, not only on polling ticks.
3. Retain full-fidelity time-series history from day one. Predictive-maintenance models cannot be trained on data that has already been rolled up.
4. Put approval gates and audit around any agent action before "take measures" becomes closed-loop. The dashboard is read-only today; actuation against production systems is a governance decision, not only an engineering one.

Rationale: The deciding factor is organisational, not technical (D2). SQL Server 2025 is now genuinely vector- and agent-capable, so staying on MS SQL is no longer an AI dead-end (D5, D6). The estate volume (~50-60M time-series rows/year, see Section 6) is well within MS SQL's range with partitioning and columnstore, so scale is not a reason to migrate (D4). Re-litigating Postgres (Option B) risks the engagement for a time-series-ergonomics benefit the current data volume does not yet require (D1, D2, D7). Option D conflicts with on-prem deployment, on-prem data sources, and data-residency exposure (D3, D8), absent an explicit client Azure mandate.

Option B's cleaner technical fit is acknowledged; it is not chosen because the cost is organisational risk with limited near-term technical payoff.

---

## 5. Consequences

Positive:

- No migration from the validated POC; Phase 2 build proceeds on known ground.
- Single engine for backup, security, and compliance; easiest sell to a Microsoft-shop security team.
- Agent layer is portable from day one; the storage decision is effectively reversible via the MCP boundary.
- On-prem posture preserved for the CXO-room display.

Negative / costs:

- MS SQL lacks native time-series primitives (hypertables, continuous aggregates, 90%+ columnar compression); partitioning and rollups are hand-rolled.
- Production vector search may need an interim approach while the advanced SQL Server vector features remain in preview.
- Generative/embedding steps depend on Azure OpenAI unless a local model is hosted (see follow-up ADR).

Neutral:

- Introduces an MCP server and an event-stream component as new, but low-footprint and standards-based, elements.

---

## 6. Decision Trigger: when to invoke Option C

The hybrid sidecar is not adopted now but is pre-approved to activate if, during the Sprint 7 capacity-planning work (per GBS-SOW-PHASE2-v1.0), any of the following hold:

- Projected five-pillar write/query load causes the live dashboard queries to exceed agreed latency targets on MS SQL after index optimisation.
- Retained-history storage growth makes on-engine retention impractical without compression MS SQL cannot provide efficiently.
- Predictive-model query patterns (large historical scans, feature extraction) materially contend with the live OLTP workload.

Volume reference (informs the trigger): ~110 sites x ~5 services x 5-minute polling ~= 50-60M time-series rows/year. This is manageable for MS SQL with partitioning + columnstore; the trigger is about ergonomics and workload isolation, not raw feasibility.

If triggered, Option C introduces Postgres in a bounded, justified, low-stakes analytics role - not as a wholesale replacement - which is a materially easier client conversation than Option B.

---

## 7. AI-Readiness Principles (apply regardless of option)

These are the concrete demands the client's agent roadmap places on the stack, agreed as design principles:

1. Stable, well-described semantic model (site, service, pillar-score, alert) that an MCP / Data-API layer can expose to agents.
2. Vector store for retrieval over unstructured context (runbooks, past incidents, alert descriptions).
3. Time-series history retained at real fidelity, because prediction needs the raw shape of the signal.
4. Event/stream path for near-real-time agent reaction ("before the problem happens").
5. Governance for action: human-in-the-loop approval gates and audit before any closed-loop automation touches production systems.

---

## 8. Open Questions for Client Ratification

These may change the recommendation and should be resolved in the platform discussion:

- Q1. Does the client have an Azure-first mandate? If yes, revisit Option D for the AI/agent layer.
- Q2. What are the data-residency constraints across the ~30 countries? Strong constraints push away from cloud vector/agent services.
- Q3. LLM hosting preference: Azure OpenAI vs a locally hosted model (affects Section 5 and a follow-up ADR).
- Q4. Appetite and controls for agent actuation ("take measures"): approval model, audit, and which systems (if any) agents may act upon.

---

## 9. Pros and Cons of the Options (condensed SWOT)

### Option A - Microsoft-native
- Strengths: zero migration risk; maximum client comfort; one engine/one compliance surface; vectors + JSON + relational + MCP in-product; on-prem fit.
- Weaknesses: no native time-series primitives; best vector features still preview; reliance on Azure OpenAI unless a local model is hosted.
- Opportunities: inherits SQL Server 2025 AI-function roadmap without re-architecture; simplest single-vendor security story.
- Threats: ergonomics/perf ceiling if volume or ML query patterns grow; preview-feature behaviour may change before GA.

### Option B - Postgres + TimescaleDB + pgvector
- Strengths: best-in-class time-series ergonomics and compression; vectors + time-series co-located; open-source, no licence cost; matches original HLD.
- Weaknesses: reopens the declined Postgres conversation (organisational, the hard kind); migration effort and risk; Postgres less familiar to a Microsoft-centric ops team.
- Opportunities: production may be the moment the client accepts Postgres for a clearly justified reason; positions platform as vendor-neutral.
- Threats: client refusal wastes discovery effort; ambiguous DBA ownership.

### Option C - Hybrid / polyglot
- Strengths: best-of-both; MS SQL comfort retained; AI/analytics queries isolated from the live display; introduces Postgres in a low-stakes bounded role.
- Weaknesses: two engines to run/secure/back up; new sync/ETL surface and failure mode; more to document and hand over.
- Opportunities: sidecar can start minimal (vector store + retained history) and grow into a feature store; proves Timescale value before any migration talk.
- Threats: sync drift undermines agent trust; complexity may outweigh benefit if MS SQL is never stressed.

### Option D - Azure cloud-native
- Strengths: strongest managed agent tooling; least infra to run; deep fit with AVD/Azure pillars.
- Weaknesses: conflicts with on-prem CXO-room and on-prem sources (SolarWinds 17774, Zabbix, SAP); ongoing cloud cost not yet scoped.
- Opportunities: aligns with an Azure-first mandate if one exists; offloads ops.
- Threats: data-residency exposure across ~30 countries; cost creep; cloud dependency for a system meant to report health during failures.

---

## 10. Follow-up ADRs (to be raised)

- ADR-002: Agent framework selection (e.g. Pydantic AI - fits the Pydantic-heavy codebase - vs Microsoft Agent Framework / Semantic Kernel vs LangGraph).
- ADR-003: LLM and embedding hosting (Azure OpenAI vs locally hosted model), driven by Q2/Q3.
- ADR-004: Vector indexing strategy on the chosen engine (GA vs preview features; interim approach).
- ADR-005: Agent action-governance model (approval gates, audit, permitted systems).

---

## 11. References

- SQL Server 2025 vector GA/preview status: https://www.sqlservercentral.com/articles/vector-search-in-sql-server-2025-storing-embeddings-querying-them-and-what-to-watch-out-for
- SQL Server 2025 vector data type (Microsoft Learn): https://learn.microsoft.com/en-us/sql/t-sql/data-types/vector-data-type?view=sql-server-ver17
- SQL Server 2025 vectors RTM announcement: https://devblogs.microsoft.com/azure-sql/sql-server-2025-embraces-vectors-setting-the-foundation-for-empowering-your-data-with-ai/
- Microsoft SQL MCP Server (overview): https://learn.microsoft.com/en-us/sql/mcp/
- Microsoft SQL MCP Server (announcement): https://devblogs.microsoft.com/azure-sql/introducing-sql-mcp-server/
- TimescaleDB / TigerData (time-series + pgvector): https://www.tigerdata.com/docs

---

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| v0.1 | August 2026 | BMI Technology - Infrastructure Architecture Team | Initial proposed ADR for Phase 2 platform and AI-readiness decision |

Status: Proposed. This ADR seeds the client platform discussion. On ratification, update Status to Accepted, record the agreed option and any deviations, and resolve the open questions in Section 8.
