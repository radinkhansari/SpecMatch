"""Match endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from app.core.db import get_conn
from app.models.schemas import (
    MatchesResponse,
    MatchResult,
    Review,
    ReviewAction,
    ReviewRequest,
    Tier,
)

router = APIRouter()


def _match_from_payload(payload: str) -> MatchResult:
    return MatchResult.model_validate_json(payload)


@router.get("/matches", response_model=MatchesResponse)
def list_matches(
    tier: Tier | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MatchesResponse:
    conn = get_conn()
    try:
        where = ""
        params: tuple[object, ...] = ()
        if tier is not None:
            where = " WHERE tier = ?"
            params = (tier.value,)
        total = conn.execute(f"SELECT COUNT(*) AS n FROM matches{where}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT payload FROM matches{where} ORDER BY record_id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    finally:
        conn.close()
    return MatchesResponse(
        total=total,
        items=[_match_from_payload(row["payload"]) for row in rows],
    )


@router.post("/matches/{record_id}/review", response_model=MatchResult)
def review_match(record_id: str, body: ReviewRequest) -> MatchResult:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT payload FROM matches WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Match not found")

        result = _match_from_payload(row["payload"])
        candidate_ids = {candidate.catalog_id for candidate in result.candidates}
        selected_catalog_id = _selected_catalog_id(body, result, candidate_ids)
        reviewed_at = datetime.now(UTC)
        review = Review(
            action=body.action,
            catalog_id=selected_catalog_id,
            note=body.note,
            reviewed_at=reviewed_at,
        )
        updated = result.model_copy(
            update={"selected_catalog_id": selected_catalog_id, "review": review}
        )
        conn.execute(
            "INSERT INTO match_reviews (record_id, action, catalog_id, note, reviewed_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                record_id,
                body.action.value,
                selected_catalog_id,
                body.note,
                reviewed_at.isoformat(),
            ),
        )
        conn.execute(
            "UPDATE matches SET payload = ?, tier = ?, matched_at = ? WHERE record_id = ?",
            (
                updated.model_dump_json(),
                updated.tier.value,
                updated.matched_at.isoformat(),
                record_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return updated


def _selected_catalog_id(
    body: ReviewRequest,
    result: MatchResult,
    candidate_ids: set[str],
) -> str | None:
    if body.action is ReviewAction.reject:
        return None
    if body.action is ReviewAction.accept:
        catalog_id = body.catalog_id or (
            result.candidates[0].catalog_id if result.candidates else None
        )
    else:
        catalog_id = body.catalog_id
    if catalog_id is None:
        raise HTTPException(status_code=400, detail="catalog_id is required")
    if catalog_id not in candidate_ids:
        raise HTTPException(status_code=400, detail="catalog_id must be one of the candidates")
    return catalog_id
