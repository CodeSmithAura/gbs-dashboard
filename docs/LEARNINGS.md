# LEARNINGS.md — Things Discovered the Hard Way

War stories and corrections to earlier design assumptions. If a rule can be stated as a checkable
instruction, promote it to `CLAUDE.md` instead and leave the story here for context.

## Aruba Central API — reality vs. original design

The LLD/HLD were written against Aruba's general API documentation before live credentials existed.
Once connected to the real tenant, several assumptions changed:

- `client_credentials` OAuth grant is **not supported** for this integration type — only
  `refresh_token` works. Any code or docs assuming client_credentials is stale.
- There is **no bulk per-site composite health score endpoint** (`/aiops/v2/sites/health` returns
  404). Aruba's AIOps API is per-AP or global-insight-list shaped, not per-site. The site-health
  scoring redesign question (fetch per-AP, aggregate to site) is still open — don't assume it's
  solved.
- There is **no per-site client-count aggregate endpoint** either — `/monitoring/v2/clients` returns
  the full paginated client list; counts are aggregated client-side. At scale (tens of thousands of
  clients) this is a full paginated fetch every poll cycle for one number per site — worth revisiting
  if poll frequency or client volume grows materially.
- Real endpoint names differ from the originally-assumed v1 paths: `/monitoring/v2/aps`,
  `/monitoring/v2/clients`, `/central/v1/notifications` (not `/monitoring/v1/alerts`).

## Alert/notification endpoints silently under-report at scale

Both `/central/v1/notifications` (Aruba) and `_QUERY_ALERTS` (SolarWinds SWQL, capped at 500 via
`SW_ALERT_LIMIT`) are single-page fetches with no indicator when the true count exceeds the page/cap.
This is the same failure shape in two different connectors — worth checking any *future* connector
(AVD, Zabbix) for the same pattern before it ships, not just patching these two after the fact.

## Connection reuse claims in docstrings aren't always true

The SolarWinds connector's module docstring claims a single `httpx.Client` is reused per cycle, but
`fetch_nodes()`, `fetch_interfaces()`, and `fetch_alerts()` each open and close their own client —
three TCP/TLS/Basic-Auth handshakes per LAN cycle instead of one. Docstring claims about resource
reuse are not verified automatically anywhere — worth spot-checking rather than trusting on sight.

## Stateful-connector-per-cycle trap (see also CLAUDE.md §7)

`CLAUDE.md` already documents the module-level `_TOKEN_MANAGER` requirement as a non-negotiable.
The concrete failure mode it's guarding against: instantiating a connector (and its token manager)
inside a poll cycle causes the OAuth token to silently stop refreshing. This has already bitten this
project once — treat it as a real trap, not a theoretical one, for any new OAuth-backed connector.

## Dead code accumulates quietly

`backend/app/lan.py` is a stale near-duplicate of `app/api/lan.py`, missing newer input validation.
Nobody has deleted it, so it's a live risk that someone edits or wires in the wrong copy later.
General lesson: when a module gets superseded, delete the old one in the same change rather than
leaving both — per `CLAUDE.md` §6 ("delete dead code, do not archive it").

## POC-only shortcuts need to be found before an audit finds them

Plaintext `.env` credential storage and `CORS allow_origins=["*"]` were both flagged as "POC-only" in
comments or design docs from the start, but both were still live findings in the production-readiness
review months later. Labelling a shortcut isn't the same as tracking it to closure — if `CLAUDE.md`
§7's "mark every dev-only setting inline" rule catches something, it still needs a follow-up item
somewhere it will actually get picked up (STATUS.md), not just a code comment.
