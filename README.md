# SpecMatch

SpecMatch is a FastAPI service and server-rendered review console for matching
messy construction-material records to a canonical catalog. It ingests fixture
CSVs, runs an explainable lexical matching engine, assigns confidence tiers, and
lets reviewers accept, override, or reject suggested matches.

`backend/app/models/schemas.py` is frozen. API responses are shaped to those
contracts without modifying the schema file.

## Architecture

```text
data/source_records.csv + data/catalog.csv
              |
              v
     FastAPI lifespan startup
              |
              v
        CSV ingest -> SQLite
              |
              v
   lexical matching engine
      retrieve -> score -> tier -> persist
              |
              v
      /matches API + /review console
              |
              v
       review audit history
```

Core modules:

- `backend/app/services/ingest.py` loads fixture CSVs into SQLite.
- `backend/app/services/matching/engine.py` retrieves, scores, tiers, and
  persists match results.
- `backend/app/routers/matches.py` exposes match listing and review actions.
- `backend/app/routers/console.py` renders the records table and review queue.
- `backend/app/core/db.py` owns SQLite schema and connection creation.
- `config/settings.yaml` owns scoring weights and tier thresholds.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

API and console run at:

```text
http://localhost:8000
```

Useful pages:

- Records console: `http://localhost:8000/`
- Review console: `http://localhost:8000/review`
- API docs: `http://localhost:8000/docs`

Docker stores SQLite data in the named volume `specmatch-data`, mounted at
`/data`, so persisted data survives container restarts.

## Local Development

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Tests And Checks

```bash
cd backend
pytest
```

```bash
python3 -m ruff check .
```

CI runs:

- schema freeze check
- Ruff lint
- pytest
- Docker image build

## API Examples

```bash
curl http://localhost:8000/health
```

```bash
curl "http://localhost:8000/records?limit=10&offset=0"
```

```bash
curl "http://localhost:8000/matches?tier=yellow&limit=5"
```

```bash
curl -X POST http://localhost:8000/matches/SRC-0004/review \
  -H "Content-Type: application/json" \
  -d '{"action":"accept","catalog_id":null,"note":"looks right"}'
```

## Matching Design

The engine is a deterministic lexical baseline. It normalizes source and catalog
text, expands construction abbreviations, retrieves likely catalog entries, and
scores each candidate with three inspectable signals:

- `string_similarity`
- `category_agreement`
- `unit_compatibility`

The composite score uses weights from `config/settings.yaml`. Tier assignment
uses the configured inclusive thresholds:

- `score >= accept_min` -> `green`
- `review_min <= score < accept_min` -> `yellow`
- `score < review_min` -> `red`

Top-k candidates are persisted as serialized `MatchResult` payloads in the
`matches` table. Human review decisions update the current match payload and are
also appended to `match_reviews` for audit history.

Fixture tier distribution for the lexical baseline:

```text
green: 59
yellow: 67
red: 24
```

Representative behavior:

- `SRC-0004`, `CONC RM 50MPA W/ 25% SLAG`, matches `CAT-0041`.
- `SRC-0074`, `MISC MTL ALLOW`, lands in `red`.

## Filed Issue Fixes

Issue #1: duplicate records after re-running ingest.

Cause: `ingest_records()` appended all CSV rows on every run. Fix: treat
`source_records.csv` as a snapshot by clearing `records` before reloading.

Issue #2: accept-threshold boundary classified incorrectly.

Cause: `assign_tier()` used `>` for `accept_min` even though config says the
threshold is inclusive. Fix: use `>=`.

Issue #3: console filter showed an empty list after selecting all categories.

Cause: the template submitted `category=All`, and the route treated `"All"` as
a real category. Fix: normalize `"All"` to the unfiltered state.

## AI Usage

I used Codex to help navigate the unfamiliar codebase, write regression tests,
implement the matching/API/console workflow, and keep Git history split into
reviewable branches and commits. I kept responsibility for the final behavior by
running tests, inspecting diffs, and rejecting or correcting output when it
weakened tests or mixed unrelated changes.

One concrete correction: a full test run exposed that an ingest test leaked
`DATA_DIR` into later tests. I corrected the test to restore the previous
environment state instead of weakening the existing records tests.
