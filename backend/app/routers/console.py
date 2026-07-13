"""Server-rendered review console (Jinja2).

The record table is implemented. The review panel is stubbed — completing
it is Task 5.
"""

from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.db import get_conn
from app.models.schemas import MatchResult, ReviewAction, ReviewRequest, Tier
from app.routers.matches import review_match

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/", response_class=HTMLResponse)
def record_table(request: Request, category: str | None = Query(default=None)):
    if category == "All":
        category = None

    conn = get_conn()
    try:
        categories = [
            row["category"]
            for row in conn.execute(
                "SELECT DISTINCT category FROM records"
                " WHERE category IS NOT NULL AND category != '' ORDER BY category"
            ).fetchall()
        ]
        if category is not None:
            rows = conn.execute(
                "SELECT record_id, raw_text, category, unit, quantity FROM records"
                " WHERE category = ? ORDER BY id",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT record_id, raw_text, category, unit, quantity FROM records"
                " ORDER BY id"
            ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request,
        "records.html",
        {
            "records": rows,
            "categories": categories,
            "selected_category": category,
        },
    )


@router.get("/review", response_class=HTMLResponse)
def review_panel(request: Request, tier: Tier = Query(default=Tier.yellow)):
    conn = get_conn()
    try:
        tier_rows = conn.execute(
            "SELECT tier, COUNT(*) AS n FROM matches GROUP BY tier"
        ).fetchall()
        rows = conn.execute(
            "SELECT payload FROM matches WHERE tier = ? ORDER BY record_id LIMIT 50",
            (tier.value,),
        ).fetchall()
    finally:
        conn.close()
    counts = {t.value: 0 for t in Tier}
    counts.update({row["tier"]: row["n"] for row in tier_rows})
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "counts": counts,
            "matches": [MatchResult.model_validate_json(row["payload"]) for row in rows],
            "selected_tier": tier,
            "tiers": list(Tier),
        },
    )


@router.post("/review/{record_id}/{action}")
def review_action(
    record_id: str,
    action: ReviewAction,
    catalog_id: str | None = Query(default=None),
    note: str | None = Query(default=None),
    tier: Tier = Query(default=Tier.yellow),
):
    review_match(
        record_id,
        ReviewRequest(action=action, catalog_id=catalog_id, note=note),
    )
    return RedirectResponse(f"/review?tier={tier.value}", status_code=303)
