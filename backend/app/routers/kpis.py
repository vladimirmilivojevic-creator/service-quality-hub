from fastapi import APIRouter, Query

from app import analytics
from app.deps import DB, StaffUser
from app.services import demo_now

router = APIRouter(prefix="/kpis", tags=["kpis"])

MONTH = Query(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM; default: the demo clock's current month")


async def _month(db: DB, month: str | None) -> tuple[str, object]:
    now = await demo_now(db)
    return month or analytics.month_of(now), now


@router.get("")
async def kpi_summary(
    db: DB,
    _: StaffUser,
    month: str | None = MONTH,
    plant_id: int | None = None,
    service_id: int | None = None,
    provider_id: int | None = None,
) -> dict:
    """KPI cards (value, RAG, change to the previous month, definition) for a month and filters."""
    month, now = await _month(db, month)
    filters = analytics.Filters(plant_id, service_id, provider_id)
    return await analytics.kpi_summary(db, month, now, filters)


@router.get("/trend")
async def kpi_trend(
    db: DB,
    _: StaffUser,
    month: str | None = MONTH,
    plant_id: int | None = None,
    service_id: int | None = None,
    provider_id: int | None = None,
) -> dict:
    """The same KPIs for the six months up to the selected month."""
    month, now = await _month(db, month)
    return await analytics.kpi_trend(db, month, now, analytics.Filters(plant_id, service_id, provider_id))


@router.get("/by-plant")
async def kpis_by_plant(
    db: DB, _: StaffUser, month: str | None = MONTH, service_id: int | None = None, provider_id: int | None = None
) -> list[dict]:
    """One row per plant: is service quality the same at every site?"""
    month, now = await _month(db, month)
    return await analytics.kpis_by_plant(db, month, now, analytics.Filters(None, service_id, provider_id))
