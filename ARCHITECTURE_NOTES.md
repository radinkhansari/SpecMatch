# Architecture Notes

## System sketch

```text
source_records.csv + catalog.csv
            |
            v
  app.main.lifespan()
            |
            v
 app.services.ingest.run_ingest()
   |- init_schema() -> SQLite tables in backend/var or DATA_DIR
   |- ingest_catalog() -> catalog table
   `- ingest_records() -> records table
            |
            +------------------------------+
            |                              |
            v                              v
 app.routers.records                 app.services.matching.*
   GET /records                        retrieve -> score -> tier -> persist
   reads records table                 writes matches table
            |                              |
            v                              v
 records.html                      app.routers.matches / app.routers.console
                                     GET /matches, POST /matches/{id}/review,
                                     GET /review
                                              |
                                              v
                                         review.html
```

## How the pieces connect

- `backend/app/main.py` creates the FastAPI app, configures logging during
  lifespan startup, and runs ingest before serving requests.
- `backend/app/core/db.py` owns the SQLite path, connection factory, and
  schema creation. All persisted state goes through this module.
- `backend/app/services/ingest.py` reads fixture CSVs from `data/` and loads
  them into SQLite.
- `backend/app/config.py` loads `config/settings.yaml` and exposes matching
  weights and tier thresholds through `get_settings()`.
- `backend/app/routers/` contains the HTTP layer:
  - `health.py` reads aggregate counts from SQLite.
  - `records.py` pages through ingested source records.
  - `matches.py` is the API surface for persisted match results and review
    actions; it is stubbed in the starter.
  - `console.py` renders the server-side HTML console. The records page is
    implemented; the review panel is stubbed in the starter.
- `backend/app/services/matching/` defines the retrieval/scoring/orchestration
  interfaces and tier assignment helper. The engine implementation is the core
  missing piece.
- `backend/app/models/schemas.py` is the frozen contract boundary between the
  service layer and the API/UI responses.

## Contract and persistence notes

- [`backend/app/models/schemas.py`](/Users/radinkhansari/Desktop/SpecMatch/backend/app/models/schemas.py) is the frozen contract boundary for API and review data. It must remain unchanged even if an implementation detail feels awkward; any disagreement with the contract belongs in the README, not in code changes.
- SQLite is the single persisted state store for this project. Today it contains `records`, `catalog`, and `matches`.
- `records` stores ingested source rows from `source_records.csv`.
- `catalog` stores canonical catalog entries from `catalog.csv`.
- `matches` currently stores one persisted JSON payload per `record_id`, keyed by the source record.
- That schema is enough for a current match snapshot, but likely not enough by itself for a full audit trail of human review decisions. If review history must be auditable over time, the implementation will likely need an additional review-history structure rather than overwriting a single current state in place.


## Required answers

### 1. Trace one record from `source_records.csv` to the review console

Using `SRC-0004` (`CONC RM 50MPA W/ 25% SLAG`) as the example, the intended
path is:

1. `data/source_records.csv`
2. `backend/app/services/ingest.py:_read_csv()`
3. `backend/app/services/ingest.py:ingest_records()`
4. SQLite `records` table created by `backend/app/core/db.py:init_schema()`
5. `backend/app/services/matching/engine.py:LexicalMatchingEngine.match_all()`
   after it loads the record, retrieves catalog candidates, scores them, and
   assigns a tier
6. SQLite `matches` table in `backend/app/core/db.py`
7. `backend/app/routers/console.py:review_panel()`
8. `backend/app/templates/review.html`

Today the path stops at step 4 for the review workflow because the matching
engine and review panel are still stubbed in the starter.

### 2. Where are tier thresholds defined, and how do I move the review/accept boundary without touching Python?

They are defined in [`config/settings.yaml`](/Users/radinkhansari/Desktop/SpecMatch/config/settings.yaml)
under:

- `tiers.accept_min`
- `tiers.review_min`

`backend/app/config.py:get_settings()` reads those values into
`TierThresholds`, and `backend/app/services/matching/tiering.py:assign_tier()`
uses them. To move the review/accept boundary, change `tiers.accept_min` in
`settings.yaml` and restart the app or clear the cached settings in process.
No Python code change is required.

### 3. What does `CONTRIBUTING.md` require when an external dependency fails?

Quoted convention:

> Every call to an external dependency (filesystem, network, subprocess,
> database file) must catch the dependency's specific exception type at the
> call site, log a structured `dependency_failure` event that includes the
> dependency name and enough context to reproduce, and re-raise as
> `app.core.errors.DependencyError` using `raise ... from exc`.

One existing place that follows it is
[`backend/app/config.py`](/Users/radinkhansari/Desktop/SpecMatch/backend/app/config.py:45),
where reading `settings.yaml` catches `OSError`, logs
`dependency_failure`, and raises `DependencyError` from the original
exception. Another is
[`backend/app/services/ingest.py`](/Users/radinkhansari/Desktop/SpecMatch/backend/app/services/ingest.py:20),
which applies the same pattern when reading fixture CSV files.


## Current gaps and implementation pressure points

- The starter repository is complete enough to ingest data, expose health information, and render the records table, but it does not yet complete the core matching workflow.
- The matching engine in `backend/app/services/matching/engine.py` is still stubbed, so no real candidate retrieval, scoring, or tiered decisioning exists yet.
- The `/matches` endpoints are stubbed, so persisted match retrieval and review submission are not implemented yet.
- The review console route and `review.html` template are stubbed, so the yellow/red review workflow stops before a human can actually act on results.
- `schemas.py` is frozen, which means the implementation has to adapt to the existing contracts rather than reshaping the contracts to fit the implementation.
- Review auditability needs deliberate design. The existing `matches` table stores one JSON payload per `record_id`; if the requirement is to preserve review history, I will likely need to add history-oriented persistence rather than simply replacing the latest state.
- `assign_tier()` currently uses `>` for `accept_min` even though `config/settings.yaml` describes both tier thresholds as inclusive lower bounds. That is the likely root cause of the boundary-tier bug.
- The records console currently uses `value="All"` for the unfiltered category option while the backend treats any non-`None` category as a real filter value. That is the likely cause of the empty-list filter bug.

## Observations before implementation

- The starter persists records and catalog rows, but not review decisions in an
  auditable structure yet.
- `matches` currently stores only one JSON payload per `record_id`, so review
  auditability will need either an additional table or an append-only history
  design layered on top of the existing schema.
- `assign_tier()` currently uses `>` for `accept_min` even though the config
  comment says both thresholds are inclusive lower bounds. That is likely the
  root of Issue #2.
- The records console currently uses `value="All"` for the unfiltered category
  option while the backend treats any non-`None` category as a real filter
  value. That likely explains the empty-list filter issue described in the
  task.
