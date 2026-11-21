from fastapi import APIRouter, Query
from sqlalchemy import select

from app import analytics
from app.deps import DB, StaffUser
from app.domain import kpis
from app.models import Ticket
from app.services import demo_now, load_catalogue, ticket_out

router = APIRouter(prefix="/changes", tags=["changes"])


@router.get("")
async def list_changes(
    db: DB,
    _: StaffUser,
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    plant_id: int | None = None,
    outcome: str | None = None,
) -> dict:
    """Changes whose planned window ends in the month, plus the change success rate."""
    now = await demo_now(db)
    month = month or analytics.month_of(now)
    start, end = analytics.month_bounds(month)
    query = select(Ticket).where(Ticket.type == "change", Ticket.planned_end >= start, Ticket.planned_end < end)
    if plant_id:
        query = query.where(Ticket.plant_id == plant_id)
    if outcome:
        query = query.where(Ticket.outcome == outcome)
    changes = (await db.scalars(query.order_by(Ticket.planned_start.desc()))).unique().all()
    catalogue = await load_catalogue(db)

    completed = [c for c in changes if c.outcome]
    successful = sum(1 for c in completed if c.outcome == "successful")
    rate = kpis.percent(successful, len(completed))
    by_type: dict[str, int] = {}
    for change in changes:
        by_type[change.change_type or "normal"] = by_type.get(change.change_type or "normal", 0) + 1
    return {
        "month": month,
        "success_rate": rate,
        "rag": kpis.rag("change_success", rate),
        "completed": len(completed),
        "successful": successful,
        "scheduled": len(changes) - len(completed),
        "by_type": by_type,
        "items": [ticket_out(c, now, catalogue).model_dump() for c in changes],
    }
