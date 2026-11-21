from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app import analytics
from app.deps import DB, StaffUser
from app.reports import monthly_report, report_xlsx
from app.services import demo_now

router = APIRouter(prefix="/reports", tags=["reports"])

MONTH = Query(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM; default: the last full month")


async def _month(db: DB, month: str | None) -> str:
    return month or analytics.last_full_month(await demo_now(db))


@router.get("/monthly")
async def monthly(db: DB, _: StaffUser, month: str | None = MONTH) -> dict:
    """The monthly service review for one month (default: the last full month)."""
    return await monthly_report(db, await _month(db, month))


@router.get("/monthly.xlsx")
async def monthly_excel(db: DB, _: StaffUser, month: str | None = MONTH) -> StreamingResponse:
    month = await _month(db, month)
    content = report_xlsx(await monthly_report(db, month))
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="service-review-{month}.xlsx"'},
    )
