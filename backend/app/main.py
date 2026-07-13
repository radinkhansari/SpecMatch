import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db import get_conn
from app.core.logging import configure_logging, log_event
from app.routers import console, health, matches, records
from app.services.ingest import run_ingest
from app.services.matching.engine import LexicalMatchingEngine

logger = logging.getLogger(__name__)


def seed_matches_if_empty() -> None:
    conn = get_conn()
    try:
        match_count = conn.execute("SELECT COUNT(*) AS n FROM matches").fetchone()["n"]
        if match_count:
            log_event(logger, logging.INFO, "matching_seed_skipped", match_rows=match_count)
            return
        results = LexicalMatchingEngine(conn).match_all()
        log_event(logger, logging.INFO, "matching_seeded", match_rows=len(results))
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    run_ingest()
    seed_matches_if_empty()
    log_event(logger, logging.INFO, "app_started")
    yield


app = FastAPI(title="SpecMatch", lifespan=lifespan)

app.include_router(health.router)
app.include_router(records.router)
app.include_router(matches.router)
app.include_router(console.router)
