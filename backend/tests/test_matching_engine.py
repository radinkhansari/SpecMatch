import os
import tempfile

from app.core.db import get_conn
from app.models.schemas import Tier
from app.services.ingest import run_ingest
from app.services.matching.engine import LexicalMatchingEngine


def _seeded_conn():
    tmp = tempfile.TemporaryDirectory()
    previous_data_dir = os.environ.get("DATA_DIR")
    os.environ["DATA_DIR"] = tmp.name
    conn = get_conn()
    run_ingest(conn)
    return conn, tmp, previous_data_dir


def _restore_data_dir(previous_data_dir: str | None) -> None:
    if previous_data_dir is None:
        os.environ.pop("DATA_DIR", None)
    else:
        os.environ["DATA_DIR"] = previous_data_dir


def test_match_record_finds_confident_concrete_candidate():
    conn, tmp, previous_data_dir = _seeded_conn()
    try:
        record = conn.execute("SELECT * FROM records WHERE record_id = ?", ("SRC-0004",)).fetchone()

        result = LexicalMatchingEngine(conn).match_record(record)

        assert result.record_id == "SRC-0004"
        assert result.tier is Tier.green
        assert result.candidates[0].catalog_id == "CAT-0041"
        assert result.candidates[0].score >= 0.85
        assert set(result.candidates[0].signals) == {
            "string_similarity",
            "category_agreement",
            "unit_compatibility",
        }
    finally:
        conn.close()
        tmp.cleanup()
        _restore_data_dir(previous_data_dir)


def test_match_record_sends_misc_allowance_to_red_queue():
    conn, tmp, previous_data_dir = _seeded_conn()
    try:
        record = conn.execute("SELECT * FROM records WHERE record_id = ?", ("SRC-0074",)).fetchone()

        result = LexicalMatchingEngine(conn).match_record(record)

        assert result.record_id == "SRC-0074"
        assert result.tier is Tier.red
        assert result.candidates[0].score < 0.60
    finally:
        conn.close()
        tmp.cleanup()
        _restore_data_dir(previous_data_dir)


def test_match_all_persists_one_match_per_record():
    conn, tmp, previous_data_dir = _seeded_conn()
    try:
        results = LexicalMatchingEngine(conn).match_all()
        persisted = conn.execute("SELECT COUNT(*) AS count FROM matches").fetchone()["count"]

        assert len(results) == 150
        assert persisted == 150
    finally:
        conn.close()
        tmp.cleanup()
        _restore_data_dir(previous_data_dir)
