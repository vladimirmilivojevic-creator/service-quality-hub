"""Supplier scorecards: the central IT provider, the plant IT teams and external vendors side by side."""

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app import analytics
from app.deps import DB, CurrentUser
from app.models import Improvement, Provider, User
from app.services import demo_now, load_catalogue, ticket_out

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

MONTH = Query(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM; default: last full month")


def _visible_provider(user: User, provider_id: int | None) -> int | None:
    """A supplier login only ever sees its own scorecard."""
    if user.role != "supplier":
        return provider_id
    if provider_id is not None and provider_id != user.provider_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Suppliers can only see their own scorecard")
    return user.provider_id


@router.get("")
async def list_scorecards(db: DB, user: CurrentUser, month: str | None = MONTH) -> dict:
    now = await demo_now(db)
    month = month or analytics.last_full_month(now)
    rows = await analytics.scorecards(db, month, now, only_provider=_visible_provider(user, None))
    return {"month": month, "is_partial": analytics.period_for(month, now).is_partial, "rows": rows}


@router.get("/{provider_id}/scorecard")
async def scorecard(provider_id: int, db: DB, user: CurrentUser, month: str | None = MONTH) -> dict:
    provider_id = _visible_provider(user, provider_id)
    provider = await db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(404, "Provider not found")
    now = await demo_now(db)
    month = month or analytics.last_full_month(now)
    row = (await analytics.scorecards(db, month, now, only_provider=provider_id))[0]
    period = analytics.period_for(month, now)
    breaches = await analytics.breached_tickets(db, period, analytics.Filters(provider_id=provider_id))
    catalogue = await load_catalogue(db)
    improvements = (
        await db.scalars(select(Improvement).where(Improvement.provider_id == provider_id).order_by(Improvement.id))
    ).all()
    return {
        "month": month,
        "scorecard": row,
        "trend": await analytics.scorecard_trend(db, provider_id, month, now),
        "breaches": [ticket_out(t, now, catalogue).model_dump() for t in breaches],
        "improvements": [
            {"id": i.id, "title": i.title, "status": i.status, "due_date": i.due_date, "owner": i.owner}
            for i in improvements
        ],
    }
