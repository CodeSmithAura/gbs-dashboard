# CLAUDE.md — Base Template

A project-agnostic instruction file for AI assistants, built on clean code and clean architecture
principles. Copy into any repository, fill the `[SLOT]` sections, delete what does not apply.

**Design constraints for this file itself:**
- Rules only. Status, roadmap, org charts, and history live in `docs/` — never here.
- Every rule must be checkable. If an assistant cannot tell whether it complied, rewrite the rule.
- Under ~200 lines. Length competes with obedience: prose you add is attention you remove.
- Examples beat description. Ten lines of real signature outperform three paragraphs of English.

---

## 1. Non-negotiables

Violating any of these is a defect regardless of whether tests pass.

1. **Business rules never touch I/O.** Core logic is pure functions over data already in memory —
   no database calls, no HTTP, no filesystem, no clock, no environment reads. Inject what you need.
2. **The dependency rule holds.** Imports flow inward only (§3). An inward-pointing import means
   the abstraction is wrong — stop and raise it, do not work around it.
3. **Policy is data, not code.** Thresholds, weightings, limits, feature flags, and business
   constants live in config or a config table. A hardcoded business number is a defect.
4. **Presentation never reaches past its adapter.** UI talks to the API layer; it does not query the
   database, call third-party services directly, or reimplement server-side logic.
5. **Never invent an interface.** Do not assume a schema, column, endpoint, config key, env var, or
   library method exists. Read the code or ask. Guessing is worse than admitting ignorance.
6. **Never regenerate a whole file.** If a change would touch more than ~30% of a file, stop and
   describe the plan before editing.
7. **Never commit a secret.** No credential, token, key, or connection string in source, logs,
   tests, fixtures, or documentation. Reference the variable name only.

---

## 2. Repo map [SLOT]

> Mandatory. Without an accurate tree, an assistant places new files by guesswork and your layering
> decays within a dozen commits. Regenerate with `tree -L 2 -I 'node_modules|.venv|dist'`.

```
[paste real directory tree, one comment per directory explaining what belongs there]
```

---

## 3. The dependency rule

Name your layers and state the direction explicitly. Adapt the labels; keep the arrows.

```
  adapters (UI, HTTP clients, DB drivers, vendor SDKs, CLI)
        │  depends on
        ▼
  application (use cases, orchestration, transactions)
        │  depends on
        ▼
  domain (entities, business rules, calculations) — depends on NOTHING
```

Stated as import rules:

- `domain/` imports only the standard library and its own modules. No framework, no ORM, no client.
- `application/` imports `domain/` and abstract interfaces. Never a concrete adapter.
- `adapters/` import `application/` and `domain/`. They are the only place vendor SDKs appear.
- Shared data contracts (schemas, DTOs) may be imported by any layer, and import nothing themselves.

**The test:** you should be able to delete every adapter and still run the domain tests.

---

## 4. Vertical slice: how a feature gets added [SLOT]

Define the one canonical path a new feature takes, and require it in order. This is the single most
useful thing in the file — it tells an assistant the *shape* of correct work.

```
[e.g. adapter/connector → schema validation → mapper to internal model →
 persistence writer → application use case → API endpoint → UI component]
```

Rules:
- Do not skip or reorder stages.
- Each stage is a separate, reviewable change where practical.
- If a stage feels unnecessary for this feature, say so and ask — do not silently drop it.

---

## 5. Boundaries: what must stay swappable

For each external dependency, state the abstraction and the swap mechanism.

- Every external system sits behind an interface defined by *your* code, not the vendor's shape.
- Swapping an implementation (fake ↔ live, vendor A ↔ vendor B, file ↔ API) must be a
  **configuration change, never a code change**. If your design needs an edit to swap, it is wrong.
- Vendor types do not leak past the adapter. Map to internal models at the boundary.
- One adapter per external system. Do not let two vendors share a module.

[SLOT: list the project's interfaces and the config key that selects the implementation]

---

## 6. State, lifecycle & concurrency

The two most expensive bug classes in practice. Both are lifecycle errors.

- **Stateful clients are long-lived singletons.** Anything holding a connection pool, cache, or
  auth token (OAuth, refresh tokens, session cookies) is created once at module or app scope.
  Creating one inside a loop, request, or poll cycle silently resets its state — tokens never
  refresh, pools exhaust, caches never warm.
- **Stateless helpers are cheap — create them freely.** The rule above applies only to state.
- **Never capture mutable state in a closure that outlives the render or call.** Pass the current
  value explicitly (a ref, an argument, a parameter) rather than relying on capture. This covers
  React hooks, event handlers, callbacks, timers, and goroutine/task captures alike.
- **Every stateful component has a documented lifecycle:** who creates it, when, who disposes it.
  If you cannot answer all three, do not add it.

---

## 7. Configuration, secrets & environments

- Config is read **once at startup**, validated, and passed down. No `getenv` scattered through
  business logic.
- Locate config files by walking up from the module's own path — never a hardcoded relative path
  that breaks with working directory.
- **Mark every development-only setting as such, inline.** Disabled TLS verification, permissive
  CORS, seeded randomness, verbose logging, mock toggles. Unlabelled shortcuts get promoted to
  production by whoever reads the file next — human or model.
- Fail fast and loudly on missing or invalid config at startup. Never default silently.
- If an insecure setting is the fix for an error, say so and surface the real error instead.

---

## 8. Errors & observability

- **Distinguish failure classes** in both handling and logging: input/validation, authentication,
  upstream/transient, and internal defect. Collapsing them causes hours of misdirected debugging —
  an upstream 500 immediately after a successful auth handshake is not an auth bug.
- Never swallow an exception. Never catch broadly without re-raising or logging with context.
- Errors crossing a boundary are translated into that layer's vocabulary, not passed raw.
- Log the identifiers needed to trace a request. Never log payloads containing secrets or PII.

---

## 9. Code conventions

- Follow the conventions already in the file you are editing over any general style preference.
- Name things after what they mean in the problem domain, not their mechanism.
- A function does one thing at one level of abstraction. If you need a comment to separate its
  parts, it is two functions.
- Comments explain *why*, never *what*. Delete commented-out code rather than shipping it.
- No new dependency without asking first.
- Delete dead code. Do not archive it in the repository.

[SLOT: formatter, linter, type-checker, and any language-specific rules]

---

## 10. Change discipline

- **Surgical diffs.** Change what the task requires and nothing adjacent. Unrelated cleanup is a
  separate change.
- **Analysis before implementation.** State the cause before proposing the fix.
- Do not reformat, rename, or restructure files you were not asked to touch.
- Preserve existing public interfaces unless changing them is the task.

---

## 11. Debugging protocol

Follow in order. Do not skip ahead.

1. **Ground truth first.** Inspect the data at its source — query the database, read the raw
   payload, check the actual file. Do this before reading any application code.
2. **Verify each layer outward.** Confirm the backend response with `curl`/equivalent before
   investigating the client.
3. **Only then inspect logic**, at the narrowest layer the evidence implicates.

**Two failed fixes is a hard stop.** Report what you observed, what you ruled out, and what you
need. Speculative iteration costs more than the question would have.

[SLOT: known traps specific to this project]

---

## 12. Testing & commands [SLOT]

> An assistant that cannot run your tests cannot verify its own work.

```bash
# install
# run (each service)
# test — full suite and single test
# lint / format / typecheck
```

- Domain logic requires unit tests with no I/O. Adapters are tested against fakes or recordings.
- New behaviour ships with a test. Bug fixes ship with a test that fails without the fix.

---

## 13. Naming & taxonomy

- Define **canonical identifiers** for the project's core concepts and use them everywhere in code,
  database columns, and API payloads.
- Client-facing, marketing, or legacy labels stay in documents and UI strings. They never become
  identifiers. Where the two differ, map once at the boundary.

[SLOT: canonical identifier list]

---

## 14. When instructions do not cover the case

Ask. Specifically:

- Do not infer a convention from a single example.
- Do not resolve a conflict between this file and existing code by silently picking one — flag it.
- Do not expand scope because an adjacent problem looks easy.
- Requirements recorded as binding are not negotiable. Do not design around them; if one appears
  infeasible, raise it rather than substituting your own.

---

## Appendix A — Maintaining this file

Review at every milestone. The file is working if a competent newcomer could make a correct first
change from it alone.

| Smell | Fix |
|---|---|
| Contains dates, statuses, percentages, or "currently…" | Move to `docs/STATUS.md` |
| Contains sprint plans, people, or project history | Move to `docs/ROADMAP.md`, `docs/PROJECT.md` |
| A rule an assistant cannot verify it followed | Restate with a concrete threshold or example |
| A war story explaining a past bug | Promote the rule; move the story to `docs/LEARNINGS.md` |
| Describes an interface in prose | Replace with the real signature |
| Repo map is stale | Regenerate — a wrong map is worse than none |
| Over ~200 lines | Cut background; rules earn their place, context does not |

Order matters: rules first, context last. Attention decays down the file.

---

## Appendix B — Anti-pattern catalogue

Recurring failure modes worth naming, so they can be rejected by name in review.

| Anti-pattern | Symptom | Rule violated |
|---|---|---|
| Stateful client per iteration | Tokens expire, pools exhaust, caches never warm | §6 |
| Stale closure capture | UI acts on a value from a previous render | §6 |
| Hardcoded business constant | Threshold change requires a deploy | §1.3 |
| Vendor type leaking inward | Domain code imports an SDK model | §3 |
| Dev shortcut in production | Disabled verification, permissive CORS | §7 |
| Presentation-layer query | UI reads the database or a vendor API directly | §1.4 |
| Client label as identifier | Renaming a product breaks the schema | §13 |
| Whole-file regeneration | Unreviewable diff, silent behaviour loss | §1.6 |
| Speculative fixing | Several attempts, no diagnosis | §11 |
