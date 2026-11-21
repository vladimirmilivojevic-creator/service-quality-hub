"""Monthly service review: one report with everything a service review meeting needs.

Sections follow a typical review agenda: summary, KPIs against targets, plants, suppliers,
top breaches, major incidents, problems, changes, the improvement register and next actions.
The report only reads data, so the same month always gives the same report.
"""

import io
from datetime import timedelta

import pandas as pd
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import analytics
from app.domain import kpis as k
from app.domain.problems import WINDOW_DAYS, IncidentRef, find_candidates
from app.models import Improvement, Ticket
from app.routers.improvements import improvement_out
from app.services import demo_now, load_catalogue, ticket_out

TOP_BREACHES = 10


def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "no data"
    if unit == "%":
        return f"{value:.1f} %"
    if unit == "h":
        return f"{value:.1f} h"
    return f"{value:.0f}"


def summary_points(cards: list[dict], suppliers: list[dict], overdue: int, candidates: int) -> list[str]:
    """3-5 sentences a manager reads first. Simple rules, no free text generation."""
    points = []
    red = [c for c in cards if c["rag"] == "red"]
    amber = [c for c in cards if c["rag"] == "amber"]
    green = [c for c in cards if c["rag"] == "green"]
    if red or amber:
        worst = (red or amber)[0]
        points.append(
            f"Needs attention: {worst['name']} at {_fmt(worst['value'], worst['unit'])} ({worst['rag']}; "
            f"target {worst['target_text'].split(' green')[0]})."
        )
    if green:
        points.append(f"On target: {', '.join(c['name'] for c in green)}.")
    with_delta = [c for c in cards if c["delta"] is not None and c["unit"] == "%"]
    if with_delta:
        biggest = max(with_delta, key=lambda c: abs(c["delta"]))
        direction = "up" if biggest["delta"] > 0 else "down"
        points.append(
            f"Biggest change vs last month: {biggest['name']} {direction} {abs(biggest['delta']):.1f} points."
        )
    red_suppliers = [s for s in suppliers if s["rag"] == "red"]
    if red_suppliers:
        names = ", ".join(
            f"{s['name']} ({_fmt(s['resolution_compliance'], '%')} vs {s['target_pct']:.0f} %)" for s in red_suppliers
        )
        points.append(f"Providers below their agreement: {names}.")
    if overdue or candidates:
        points.append(f"{overdue} overdue improvement actions and {candidates} open problem candidates.")
    return points[:5]


def next_actions(
    cards: list[dict], plants: list[dict], suppliers: list[dict], overdue: list, candidates: list
) -> list[str]:
    actions = []
    for s in suppliers:
        if s["rag"] == "red":
            actions.append(
                f"Service review with {s['name']}: resolution compliance {_fmt(s['resolution_compliance'], '%')} "
                f"against {s['target_pct']:.0f} % ({s['agreement']}); agree corrective actions and dates."
            )
    for plant in plants:
        if plant["rag"]["backlog_over_30"] in ("amber", "red"):
            actions.append(
                f"{plant['plant_name']}: clear {plant['values']['backlog_over_30']:.0f} tickets older than 30 days."
            )
        if plant["rag"]["change_success"] == "red":
            actions.append(f"{plant['plant_name']}: review failed changes in the next CAB meeting.")
    for card in cards:
        if card["key"] == "reopen_rate" and card["rag"] != "green":
            actions.append("Check reopened tickets: is 'resolved' confirmed with the user?")
    for c in candidates[:3]:
        actions.append(
            f"Decide on problem candidate: {c['count']} × '{c['category']}' – {c['service_name']} at {c['plant_code']}."
        )
    if overdue:
        actions.append(f"Follow up {len(overdue)} overdue improvement actions with their owners.")
    return actions or ["No corrective actions needed; keep monitoring."]


async def monthly_report(db: AsyncSession, month: str) -> dict:
    now = await demo_now(db)
    period = analytics.period_for(month, now)
    filters = analytics.Filters()
    catalogue = await load_catalogue(db)

    summary = await analytics.kpi_summary(db, month, now, filters)
    trend = await analytics.kpi_trend(db, month, now, filters)
    plants = await analytics.kpis_by_plant(db, month, now, filters)
    suppliers = await analytics.scorecards(db, month, now)
    breaches = await analytics.breached_tickets(db, period, filters, limit=TOP_BREACHES)

    major = (
        (
            await db.scalars(
                select(Ticket)
                .where(Ticket.type == "incident", Ticket.priority == 1)
                .where(Ticket.created_at >= period.start, Ticket.created_at < period.end)
                .order_by(Ticket.created_at)
            )
        )
        .unique()
        .all()
    )

    problems = (
        (
            await db.scalars(
                select(Ticket)
                .where(Ticket.type == "problem", Ticket.created_at < period.end)
                .where(or_(Ticket.resolved_at.is_(None), Ticket.resolved_at >= period.start))
                .order_by(Ticket.created_at)
            )
        )
        .unique()
        .all()
    )
    recent = (
        (
            await db.scalars(
                select(Ticket).where(
                    Ticket.type == "incident",
                    Ticket.problem_id.is_(None),
                    Ticket.created_at >= period.end - timedelta(days=WINDOW_DAYS),
                    Ticket.created_at < period.end,
                )
            )
        )
        .unique()
        .all()
    )
    refs = [IncidentRef(t.id, t.key, t.plant_id, t.service_id, t.category, t.title, t.created_at) for t in recent]
    candidates = [
        {
            "plant_code": catalogue.plants[c.plant_id].code,
            "service_name": catalogue.services[c.service_id].name,
            "category": c.category,
            "count": c.count,
            "last_seen": c.last_seen,
        }
        for c in find_candidates(refs, period.end)
    ]

    changes = (
        (
            await db.scalars(
                select(Ticket)
                .where(Ticket.type == "change", Ticket.outcome.is_not(None))
                .where(Ticket.planned_end >= period.start, Ticket.planned_end < period.end)
                .order_by(Ticket.planned_start)
            )
        )
        .unique()
        .all()
    )
    successful = sum(1 for c in changes if c.outcome == "successful")

    items = (await db.scalars(select(Improvement).order_by(Improvement.id))).unique().all()
    period_last_day = (period.end - timedelta(seconds=1)).date()
    register = [improvement_out(i, period_last_day) for i in items if i.created_at < period.end]
    done_in_month = [i for i in register if i.completed_at and period.start <= i.completed_at < period.end]
    open_items = [i for i in register if i.status not in ("done", "rejected")]
    overdue = [i for i in open_items if i.overdue]

    cards = summary["kpis"]
    return {
        "month": month,
        "period_start": period.start,
        "period_end": period.end,
        "is_partial": period.is_partial,
        "summary": summary_points(cards, suppliers, len(overdue), len(candidates)),
        "kpis": cards,
        "trend": trend,
        "plants": plants,
        "suppliers": suppliers,
        "top_breaches": [ticket_out(t, now, catalogue).model_dump() for t in breaches],
        "major_incidents": [ticket_out(t, now, catalogue).model_dump() for t in major],
        "problems": [ticket_out(p, now, catalogue).model_dump() for p in problems],
        "problem_candidates": candidates,
        "changes": {
            "completed": len(changes),
            "successful": successful,
            "success_rate": k.percent(successful, len(changes)),
            "rag": k.rag("change_success", k.percent(successful, len(changes))),
            "not_successful": [
                ticket_out(c, now, catalogue).model_dump() for c in changes if c.outcome != "successful"
            ],
        },
        "improvements": {
            "open": [i.model_dump() for i in open_items],
            "done_in_month": [i.model_dump() for i in done_in_month],
            "overdue": [i.model_dump() for i in overdue],
        },
        "next_actions": next_actions(cards, plants, suppliers, overdue, candidates),
    }


def report_xlsx(report: dict) -> bytes:
    """The same report as an Excel workbook (pandas + openpyxl), built in memory."""
    kpi_rows = [
        {
            "KPI": c["name"],
            "Value": c["value"],
            "Unit": c["unit"],
            "RAG": c["rag"],
            "Previous month": c["previous"],
            "Change": c["delta"],
            "Target": c["target_text"],
            "Formula": c["formula"],
        }
        for c in report["kpis"]
    ]
    trend = pd.DataFrame(report["trend"]["series"], index=report["trend"]["months"]).rename_axis("Month")
    plants = pd.DataFrame(
        [
            {"Plant": p["plant_name"], "Resolved": p["resolved"], "Open at period end": p["open"]}
            | {k.KPIS[key].name: value for key, value in p["values"].items()}
            for p in report["plants"]
        ]
    )
    suppliers = pd.DataFrame(
        [
            {
                "Provider": s["name"],
                "Agreement": s["agreement"],
                "Target %": s["target_pct"],
                "Tickets": s["tickets"],
                "Resolution compliance %": s["resolution_compliance"],
                "Response compliance %": s["response_compliance"],
                "MTTR h": s["mttr_hours"],
                "Breaches": s["breaches"],
                "P1 incidents": s["p1_incidents"],
                "Trend": s["trend"],
                "RAG": s["rag"],
            }
            for s in report["suppliers"]
        ]
    )
    breaches = pd.DataFrame(
        [
            {
                "Ticket": t["key"],
                "Plant": t["plant_code"],
                "Service": t["service_name"],
                "Provider": t["provider_name"],
                "Priority": f"P{t['priority']}",
                "Title": t["title"],
                "Resolution min (target)": f"{t['resolution_business_min']} ({t['resolution_target_min']})",
                "Response breached": t["response_breached"],
                "Resolution breached": t["resolution_breached"],
            }
            for t in report["top_breaches"]
        ]
    )
    register = report["improvements"]["open"] + report["improvements"]["done_in_month"]
    improvements = pd.DataFrame(
        [
            {
                "Title": i["title"],
                "Status": i["status"],
                "Owner": i["owner"],
                "Due": i["due_date"],
                "Overdue": i["overdue"],
                "Plant": i["plant_code"],
                "Provider": i["provider_name"],
                "KPI": i["kpi"],
                "Baseline": i["kpi_baseline"],
                "Target": i["kpi_target"],
            }
            for i in register
        ]
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame({"Monthly service review": [f"Month: {report['month']}", *report["summary"]]}).to_excel(
            writer, sheet_name="Summary", index=False
        )
        pd.DataFrame(kpi_rows).to_excel(writer, sheet_name="KPI", index=False)
        trend.to_excel(writer, sheet_name="KPI trend")
        plants.to_excel(writer, sheet_name="Plants", index=False)
        suppliers.to_excel(writer, sheet_name="Suppliers", index=False)
        breaches.to_excel(writer, sheet_name="Breaches", index=False)
        improvements.to_excel(writer, sheet_name="Improvements", index=False)
        for sheet in writer.sheets.values():
            for column in sheet.columns:
                width = max(len(str(cell.value or "")) for cell in column)
                sheet.column_dimensions[column[0].column_letter].width = min(60, max(10, width + 2))
    return buffer.getvalue()
