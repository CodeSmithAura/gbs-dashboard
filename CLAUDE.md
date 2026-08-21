# CLAUDE.md

Working instructions for AI assistants in this repository — the **GBS Service Health Dashboard**
(real-time infrastructure health monitoring: Overall GBS → Country → Site → Service).

Background, status, and roadmap live in `docs/`. This file is rules only, and is kept evergreen —
if you find status information here, it is a bug.

---

## 1. Non-negotiables

Violating any of these is a defect regardless of whether tests pass.

1. **The frontend never queries the database.** All data reaches React through FastAPI BFF endpoints.
2. **Scoring logic never touches I/O.** Weightings, thresholds, and health calculations are pure
   functions over already-fetched data. No DB calls, no HTTP, no `os.environ` inside them.
3. **Thresholds and weightings are data, not code.** They live in the config table
   (`DashboardConfig` key-value pattern). Hardcoding a Green/Amber/Red boundary is a defect.
4. **Connectors with stateful auth are module-level singletons.** Never instantiate a connector
   inside a poll cycle. (See §7.)
5. **Never regenerate a whole file.** If a change would touch more than ~30% of a file, stop and
   describe the plan before editing.
6. **Never invent a schema, column, endpoint, or config key.** Read the code or ask. If you cannot
   verify it exists, say so rather than guessing.

---

## 2. Repo map

<!-- FILL: replace with real `tree -L 2 -I node_modules` output. Until this is accurate,
     assistants will place new files by guesswork. -->

```
backend/
  connectors/       # BaseConnector subclasses — one module per data source
  schemas/          # Pydantic models — the contract between connector and normaliser
  normalisers/      # raw payload -> canonical internal shape
  scoring/          # pure functions: health calculation, rollups. NO I/O.
  db/               # writers, queries, migrations
  api/              # FastAPI BFF routers
frontend/src/
  components/       # PillarAccordion, PillarRow, LANHealthTile, CountrySelector
  hooks/            # useDashboard.js
docs/               # PROJECT.md, STATUS.md, ROADMAP.md, LEARNINGS.md
```

---

## 3. Dependency rule

Imports flow inward only. An outer layer may import an inner one; never the reverse.

```
api ──► scoring ◄── normalisers ◄── connectors
 │                      │                │
 └──────► db ◄──────────┘         schemas (imported by all)
```

- `scoring/` imports **nothing** from `db/`, `api/`, or `connectors/`.
- `normalisers/` imports `schemas/` only — not `db/`, not `httpx`, not `pyodbc`.
- `connectors/` know about their vendor API and `schemas/`. They do not know about the database.
- If a change requires an inward import, the abstraction is wrong. Stop and raise it.

---

## 4. Adding a new pillar

Every pillar follows the same vertical slice, in this order. Do not skip or reorder.

1. `BaseConnector` subclass implementing `fetch()`
2. Pydantic schema for the raw payload
3. Normaliser → canonical shape
4. DB writer
5. FastAPI BFF endpoint
6. React tile component

Switching a pillar between file-based and live API must be a `DATA_SOURCE_TYPE` config change,
**never** a code change. If your design requires editing code to swap the source, it is wrong.

<!-- FILL: paste the real BaseConnector interface below. Ten lines of actual signature is worth
     more to an assistant than any amount of prose. -->

```python
class BaseConnector(ABC):
    @abstractmethod
    def fetch(self) -> ...:
        ...
```

---

## 5. Stack constraints

- **Backend:** Python, FastAPI.
- **Database:** MS SQL Server, ODBC Driver 18.
  - `TrustServerCertificate=yes` is **POC-only**. Do not carry it into production config or
    propose it as a fix; if certificate validation fails, surface the error.
  - Deduplication uses `ROW_NUMBER() OVER (PARTITION BY ...)`. Match this pattern.
- **Frontend:** React. Accessibility target is WCAG 2.1 AA — every interactive element needs a
  reachable label and visible focus state.
- **Config:** `.env` located by walking up from `__file__`. Never hardcode a relative path.
  `SW_COUNTRY_PROPERTY` is a configurable field name that drives all SWQL queries — read it, never
  inline the literal. Region groups come from the database, not from code.
- **Paths:** forward slashes in Python path strings (Windows hosts).
- **Output encoding:** all generated documents and files are clean ASCII. No smart quotes, em
  dashes, or box-drawing characters.

### Canonical pillar identifiers

Use these in code, DB columns, and API payloads:

```
wireless | lan | avd | apps | printing
```

The A/B/C/D/E lettering is client-facing only. Keep it in `docs/` and in generated reports; never
in an identifier.

---

## 6. Code conventions

- Surgical diffs. Change what the task requires and nothing adjacent.
- Analysis before implementation: state the cause before proposing the fix.
- No new dependency without asking first.
- **React:** never rely on closure capture for values that change between renders. Pass the current
  ref explicitly (e.g. `lanScopeRef.current`) into fetch functions.
- **Errors:** distinguish auth-layer failures from downstream API failures in both logging and
  handling. A 500 from a vendor API after a successful token exchange is not an auth bug.
- **Secrets:** never write a credential, token, or connection string into source, logs, tests, or
  documentation. Reference the env var name only.

---

## 7. Debugging protocol

Follow in order. Do not skip to step 3.

1. **Ground truth first.** Alert-count or data mismatch → query the database directly before
   looking at the API or frontend.
2. **Verify the backend response** with `curl` / `Invoke-RestMethod` before investigating frontend
   code.
3. Only then inspect application logic.

If two attempted fixes have failed, stop. Report findings and ask — do not continue speculatively.

**Known trap:** instantiating a connector (and therefore its token manager) per poll cycle causes
silent token expiry. `_TOKEN_MANAGER` is module-level for this reason. Applies to any OAuth or
refresh-token connector.

---

## 8. Commands

<!-- FILL: real commands. An assistant that cannot run your tests cannot verify its own work. -->

```bash
# run backend
# run frontend
# tests
# lint / format
```

---

## 9. When instructions do not cover the case

Ask. Do not infer a convention from a single example, and do not resolve a conflict between this
file and existing code by picking one silently — flag it.

Client-reported feedback (dynamic per-site scoring, country-level rollup to overall GBS score, CXO
room display target) is a binding requirement, not a nice-to-have. Do not design around it.
