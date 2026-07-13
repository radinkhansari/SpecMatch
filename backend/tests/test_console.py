from app.core.db import get_conn
from app.services.matching.engine import LexicalMatchingEngine


def _seed_matches() -> None:
    conn = get_conn()
    try:
        LexicalMatchingEngine(conn).match_all()
    finally:
        conn.close()


def test_record_table_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SRC-" in resp.text


def test_category_filter_narrows_results(client):
    resp = client.get("/", params={"category": "Concrete"})
    assert resp.status_code == 200
    assert "CONC" in resp.text
    assert "GYP BD" not in resp.text


def test_all_category_filter_shows_all_records(client):
    resp = client.get("/", params={"category": "All"})
    assert resp.status_code == 200
    assert "SRC-" in resp.text
    assert "No records." not in resp.text


def test_review_panel_shows_tier_queue_and_candidate_signals(client):
    _seed_matches()

    resp = client.get("/review", params={"tier": "red"})

    assert resp.status_code == 200
    assert "Review queue" in resp.text
    assert "Red" in resp.text
    assert "SRC-0074" in resp.text
    assert "string_similarity" in resp.text
    assert "category_agreement" in resp.text
    assert "unit_compatibility" in resp.text


def test_review_console_accept_action_persists_and_redirects(client):
    _seed_matches()

    resp = client.post("/review/SRC-0004/accept", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/review")

    followup = client.get("/matches", params={"tier": "green"})
    reviewed = [
        item for item in followup.json()["items"] if item["record_id"] == "SRC-0004"
    ][0]
    assert reviewed["review"]["action"] == "accept"
    assert reviewed["selected_catalog_id"] == reviewed["candidates"][0]["catalog_id"]
