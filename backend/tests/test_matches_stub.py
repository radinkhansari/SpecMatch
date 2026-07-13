from app.core.db import get_conn
from app.services.matching.engine import LexicalMatchingEngine


def _seed_matches() -> None:
    conn = get_conn()
    try:
        LexicalMatchingEngine(conn).match_all()
    finally:
        conn.close()


def test_list_matches_returns_persisted_results(client):
    _seed_matches()

    resp = client.get("/matches", params={"limit": 5})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 150
    assert len(body["items"]) == 5
    assert set(body["items"][0]) == {
        "record_id",
        "source_text",
        "tier",
        "candidates",
        "selected_catalog_id",
        "review",
        "matched_at",
    }


def test_list_matches_filters_by_tier(client):
    _seed_matches()

    resp = client.get("/matches", params={"tier": "green", "limit": 50})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert {item["tier"] for item in body["items"]} == {"green"}


def test_review_match_persists_decision_and_audit_row(client):
    _seed_matches()
    conn = get_conn()
    try:
        before_count = conn.execute(
            "SELECT COUNT(*) AS count FROM match_reviews WHERE record_id = ?",
            ("SRC-0004",),
        ).fetchone()["count"]
    finally:
        conn.close()

    resp = client.post(
        "/matches/SRC-0004/review",
        json={"action": "accept", "catalog_id": None, "note": "looks right"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["review"]["action"] == "accept"
    assert body["review"]["note"] == "looks right"
    assert body["selected_catalog_id"] == body["candidates"][0]["catalog_id"]

    conn = get_conn()
    try:
        audit_count = conn.execute(
            "SELECT COUNT(*) AS count FROM match_reviews WHERE record_id = ?",
            ("SRC-0004",),
        ).fetchone()["count"]
    finally:
        conn.close()
    assert audit_count == before_count + 1
