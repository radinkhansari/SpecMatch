# SpecMatch — AI assistant context

SpecMatch matches messy construction-material records to a canonical catalog,
assigns confidence tiers, exposes results through FastAPI, and provides a
server-rendered Jinja2 review console.

## Non-negotiable contracts

- `backend/app/models/schemas.py` is frozen. Never modify it.
- API responses must conform to the frozen Pydantic models.
- Matching weights and tier thresholds come from `config/settings.yaml`; never
  hardcode them in engine logic.
- Tier thresholds are inclusive lower bounds.
- Review decisions must be persisted and auditable.

## Local architecture

- `backend/app/core/db.py` owns SQLite schema and connection creation.
- `backend/app/services/ingest.py` treats fixture CSVs as snapshots.
- `backend/app/services/matching/engine.py` owns lexical retrieval, weighted
  scoring, tiering, and match persistence.
- `backend/app/routers/matches.py` owns `/matches` and review API contracts.
- `backend/app/routers/console.py` owns server-rendered records and review UI.
- `backend/app/templates/` contains Jinja2 pages.

## Error and logging conventions

Follow `CONTRIBUTING.md`:

- external dependency failures must log a structured `dependency_failure`
  event with enough context to reproduce
- wrap dependency failures in `app.core.errors.DependencyError`
- keep log events structured, not interpolated prose strings

## Commands

```bash
cd backend
pytest
```

```bash
python3 -m ruff check .
```

```bash
docker compose up --build
```

## Implementation guidance

- Prefer small commits: failing test first, implementation second.
- Keep router code thin where practical; persistence and matching behavior
  should remain easy to test.
- Do not weaken existing tests to hide regressions.
- Use the existing SQLite store; add schema only when a requirement needs it,
  such as audit history.
- Keep review UI behavior consistent with the API review path so there is one
  source of truth for persisted decisions.
