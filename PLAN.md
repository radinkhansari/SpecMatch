# Plan

## Order of work

1. Commit orientation documents first to satisfy Task 1.
2. Reproduce the three filed issues with failing tests:
   - duplicate records after re-running ingest
   - tier boundary misclassification
   - empty list after changing a console filter
3. Fix each issue with small, isolated commits that reference the issue number.
4. Build the matching engine behind `services/matching/interfaces.py`.
5. Wire the engine into startup or an explicit service path so persisted match
   results exist for the API and review console.
6. Implement `/matches` and review persistence.
7. Complete the review console route and template workflow.
8. Extend tests for engine behavior, tier boundaries, and endpoint contracts.
9. Extend Docker/CI, update `CLAUDE.md`, and finish README.

## Branch and PR strategy

I will keep the work reviewable in small phases instead of landing everything at once.

Planned sequence:

1. `docs-and-issues`
   - orientation docs first
   - failing tests for Issues #1, #2, and #3
   - isolated fixes for each issue
2. `matching-engine`
   - retrieval, normalization, scoring, tier assignment
   - persisted top-k candidates and engine tests
3. `api-review-console`
   - `/matches` endpoints
   - persisted and auditable review flow
   - review console route/template completion
4. `ci-and-readme`
   - CI completion
   - Docker verification
   - CLAUDE.md and README finalization

Even if I am the only reviewer, I still want the work split into PR-sized change sets so the history shows diagnosis, implementation order, and verification clearly.


## Matching engine approach

I plan to implement a lexical baseline with explicit, inspectable signals:

- Retrieval:
  normalize text, expand common abbreviations, compare token overlap, and
  prefer same-category and same-unit candidates when available so the scorer
  does not evaluate the full catalog every time.
- Scoring:
  combine at least these signals from `config/settings.yaml`:
  - string similarity
  - category agreement
  - unit compatibility
- Tie-breaking and reviewability:
  persist the top `k` scored candidates with per-signal breakdowns so the API
  and console can explain why a record landed in green, yellow, or red.

This keeps the first version deterministic, debuggable, and easy to defend in
the walkthrough.

## Risk areas

- Ambiguous abbreviations across material families could inflate lexical
  similarity unless normalization is opinionated.
- The current SQLite schema is minimal; making reviews auditable without
  breaking existing behavior needs careful schema evolution.
- The app currently ingests data at startup. If matching also runs there, I
  need to preserve idempotency and keep restart behavior predictable.
- The review console bug may be split between route behavior and template form
  values, so the failing test needs to prove the real cause.

## Time budget

- 1 to 1.5h: orientation, repo mapping, failing issue tests
- 1 to 2h: issue fixes and regression coverage
- 3 to 4h: matching engine, persistence, and engine tests
- 1.5 to 2h: matches API and review console
- 1 to 1.5h: Docker, CI, CLAUDE.md, README, final verification

## What I will optimize for

- Correct contracts over extra features
- Explainable scoring over opaque heuristics
- Idempotent startup behavior
- Tests that prove the README claims

## Success criteria

A successful submission should show all of the following:

- the three filed issues are reproduced with failing tests before their fixes
- matching behavior is explainable, deterministic, and driven by config weights and thresholds
- the resulting tier distribution is meaningful rather than collapsing most records into one bucket
- review decisions are persisted in a way that is auditable and consistent with the frozen API contracts
- `docker compose up --build` works from a clean clone and data survives container restarts
- CI is green on the final state and includes tests, lint, Docker build, and schema-freeze enforcement
- the git history is small-step and reviewable rather than one large final dump


## Verification checklist

Before considering the project complete, I want to verify all of the following:

- all existing and new tests pass locally
- the three issue-reproduction tests fail before their fixes and pass after
- the matching tests prove at least one confident green, one yellow-for-review, and one deliberate red case
- all API responses conform to `backend/app/models/schemas.py` without modifying the schema file
- the review console reflects persisted review actions correctly
- `docker compose up --build` succeeds from a clean clone path
- persisted data survives an application/container restart
- CI is green on the final branch
- README documents any meaningful deviation from this plan