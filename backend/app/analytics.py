"""KPI and scorecard numbers, counted in SQL over the stored SLA results.

Because every ticket stores its frozen targets and its measured result, the KPIs are simple
counts and averages: no SLA is re-calculated here, so reports are fast and never change
retroactively when a policy changes.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import kpis as k
from app.domain import suppliers as sup
from app.models import Plant, Provider, Service, Ticket
from app.services import SLA_TYPES

TREND_MONTHS = 6


# --- periods -------------------------------------------------------------------------------


def month_bounds(month: str) -> tuple[datetime, datetime]:
    year, mon = (int(x) for x in month.split("-"))
    start = datetime(year, mon, 1, tzinfo=UTC)
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=UTC)
    return start, end


def month_of(moment: datetime) -> str:
    return f"{moment.year:04d}-{moment.month:02d}"


def shift_month(month: str, delta: int) -> str:
    year, mon = (int(x) for x in month.split("-"))
    index = year * 12 + (mon - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def last_full_month(now: datetime) -> str:
    return shift_month(month_of(now), -1)


def months_back(month: str, count: int = TREND_MONTHS) -> list[str]:
    return [shift_month(month, -i) for i in range(count - 1, -1, -1)]


@dataclass(frozen=True)
class Period:
    month: str
    start: datetime
    end: datetime  # the demo clock's "now" for the running month
    is_partial: bool


def period_for(month: str, now: datetime) -> Period:
    start, end = month_bounds(month)
    return Period(month, start, min(end, now), end > now)


@dataclass(frozen=True)
class Filters:
    plant_id: int | None = None
    service_id: int | None = None
    provider_id: int | None = None

    def apply(self, query: Select) -> Select:
        if self.plant_id:
            query = query.where(Ticket.plant_id == self.plant_id)
        if self.service_id:
            query = query.where(Ticket.service_id == self.service_id)
        if self.provider_id:
            query = query.where(Ticket.provider_id == self.provider_id)
        return query


def _met(column) -> case:
    return case((column.is_(False), 1), else_=0)


# --- KPI values for one period -------------------------------------------------------------


async def raw_kpis(db: AsyncSession, period: Period, filters: Filters) -> dict:
    """All KPI inputs for one period, as plain numbers."""
    sla_ticket = Ticket.type.in_(SLA_TYPES)
    start, end = period.start, period.end

    resolved_q = filters.apply(
        select(
            func.count(),
            func.coalesce(func.sum(_met(Ticket.resolution_breached)), 0),
            func.coalesce(func.sum(case((Ticket.reopen_count > 0, 1), else_=0)), 0),
        ).where(sla_ticket, Ticket.resolved_at >= start, Ticket.resolved_at < end)
    )
    resolved, resolved_met, reopened = (await db.execute(resolved_q)).one()

    response_q = filters.apply(
        select(func.count(), func.coalesce(func.sum(_met(Ticket.response_breached)), 0)).where(
            sla_ticket,
            Ticket.first_response_at >= start,
            Ticket.first_response_at < end,
            Ticket.response_breached.is_not(None),
        )
    )
    responded, responded_met = (await db.execute(response_q)).one()

    mttr_q = filters.apply(
        select(Ticket.priority, Ticket.resolution_business_min).where(
            Ticket.type == "incident",
            Ticket.resolved_at >= start,
            Ticket.resolved_at < end,
            Ticket.resolution_business_min.is_not(None),
        )
    )
    minutes_by_priority: dict[int, list[int]] = defaultdict(list)
    for priority, minutes in (await db.execute(mttr_q)).all():
        minutes_by_priority[priority].append(minutes)

    backlog_q = filters.apply(
        select(Ticket.created_at).where(
            sla_ticket,
            Ticket.created_at < end,
            or_(Ticket.resolved_at.is_(None), Ticket.resolved_at >= end),
        )
    )
    ages = [(end - created).total_seconds() / 86400 for created in (await db.scalars(backlog_q)).all()]

    change_q = filters.apply(
        select(func.count(), func.coalesce(func.sum(case((Ticket.outcome == "successful", 1), else_=0)), 0)).where(
            Ticket.type == "change",
            Ticket.outcome.is_not(None),
            Ticket.planned_end >= start,
            Ticket.planned_end < end,
        )
    )
    changes, changes_ok = (await db.execute(change_q)).one()

    return {
        "resolved": resolved,
        "resolved_met": resolved_met,
        "reopened": reopened,
        "responded": responded,
        "responded_met": responded_met,
        "minutes_by_priority": dict(minutes_by_priority),
        "backlog_ages": ages,
        "changes": changes,
        "changes_ok": changes_ok,
    }


def kpi_values(raw: dict) -> dict[str, float | None]:
    all_minutes = [m for values in raw["minutes_by_priority"].values() for m in values]
    return {
        "sla_resolution": k.percent(raw["resolved_met"], raw["resolved"]),
        "sla_response": k.percent(raw["responded_met"], raw["responded"]),
        "mttr": k.hours(all_minutes)[0],
        "backlog_over_30": float(sum(1 for age in raw["backlog_ages"] if age > 30)),
        "reopen_rate": k.percent(raw["reopened"], raw["resolved"]),
        "change_success": k.percent(raw["changes_ok"], raw["changes"]),
    }


def kpi_cards(raw: dict, previous_raw: dict | None) -> list[dict]:
    values = kpi_values(raw)
    previous = kpi_values(previous_raw) if previous_raw else {}
    mttr_by_priority = {p: k.hours(m)[0] for p, m in sorted(raw["minutes_by_priority"].items())}
    buckets = {name: 0 for name in k.BACKLOG_AGE_BUCKETS}
    for age in raw["backlog_ages"]:
        buckets[k.backlog_bucket(age)] += 1

    details = {
        "sla_resolution": {"met": raw["resolved_met"], "total": raw["resolved"]},
        "sla_response": {"met": raw["responded_met"], "total": raw["responded"]},
        "mttr": {
            "median": k.hours([m for v in raw["minutes_by_priority"].values() for m in v])[1],
            "by_priority": {str(p): v for p, v in mttr_by_priority.items()},
            "count": sum(len(v) for v in raw["minutes_by_priority"].values()),
        },
        "backlog_over_30": {
            "open": len(raw["backlog_ages"]),
            "average_age_days": round(sum(raw["backlog_ages"]) / len(raw["backlog_ages"]), 1)
            if raw["backlog_ages"]
            else None,
            "buckets": buckets,
        },
        "reopen_rate": {"reopened": raw["reopened"], "total": raw["resolved"]},
        "change_success": {"successful": raw["changes_ok"], "total": raw["changes"]},
    }
    cards = []
    for key, definition in k.KPIS.items():
        value = values[key]
        colour = k.mttr_rag(mttr_by_priority) if key == "mttr" else k.rag(key, value)
        cards.append(
            {
                "key": key,
                "name": definition.name,
                "unit": definition.unit,
                "value": value,
                "rag": colour,
                "previous": previous.get(key),
                "delta": k.change_vs(previous.get(key), value),
                "definition": definition.definition,
                "formula": definition.formula,
                "target_text": definition.target_text,
                "higher_is_better": definition.higher_is_better,
                "detail": details[key],
            }
        )
    return cards


async def kpi_summary(db: AsyncSession, month: str, now: datetime, filters: Filters) -> dict:
    period = period_for(month, now)
    raw = await raw_kpis(db, period, filters)
    previous_raw = await raw_kpis(db, period_for(shift_month(month, -1), now), filters)
    return {
        "month": month,
        "period_start": period.start,
        "period_end": period.end,
        "is_partial": period.is_partial,
        "kpis": kpi_cards(raw, previous_raw),
    }


async def kpi_trend(db: AsyncSession, month: str, now: datetime, filters: Filters) -> dict:
    months = months_back(month)
    series: dict[str, list[float | None]] = {key: [] for key in k.KPIS}
    for m in months:
        values = kpi_values(await raw_kpis(db, period_for(m, now), filters))
        for key in series:
            series[key].append(values[key])
    return {"months": months, "series": series}


async def kpis_by_plant(db: AsyncSession, month: str, now: datetime, filters: Filters) -> list[dict]:
    period = period_for(month, now)
    rows = []
    for plant in (await db.scalars(select(Plant).order_by(Plant.id))).all():
        plant_filters = Filters(plant.id, filters.service_id, filters.provider_id)
        raw = await raw_kpis(db, period, plant_filters)
        values = kpi_values(raw)
        rows.append(
            {
                "plant_id": plant.id,
                "plant_code": plant.code,
                "plant_name": plant.name,
                "resolved": raw["resolved"],
                "open": len(raw["backlog_ages"]),
                "values": values,
                "rag": {
                    key: (
                        k.mttr_rag({p: k.hours(m)[0] for p, m in raw["minutes_by_priority"].items()})
                        if key == "mttr"
                        else k.rag(key, value)
                    )
                    for key, value in values.items()
                },
            }
        )
    return rows


# --- supplier scorecards -------------------------------------------------------------------


async def _provider_stats(db: AsyncSession, period: Period, provider_id: int | None = None) -> dict[int, dict]:
    """Resolved / response / P1 / MTTR numbers per provider for one period."""
    sla_ticket = Ticket.type.in_(SLA_TYPES)
    where_provider = [Ticket.provider_id == provider_id] if provider_id else []
    stats: dict[int, dict] = defaultdict(
        lambda: {"resolved": 0, "resolved_met": 0, "responded": 0, "responded_met": 0, "p1": 0, "minutes": []}
    )

    q = select(Ticket.provider_id, func.count(), func.coalesce(func.sum(_met(Ticket.resolution_breached)), 0)).where(
        sla_ticket, Ticket.resolved_at >= period.start, Ticket.resolved_at < period.end, *where_provider
    )
    for pid, total, met in (await db.execute(q.group_by(Ticket.provider_id))).all():
        stats[pid]["resolved"], stats[pid]["resolved_met"] = total, met

    q = select(Ticket.provider_id, func.count(), func.coalesce(func.sum(_met(Ticket.response_breached)), 0)).where(
        sla_ticket,
        Ticket.first_response_at >= period.start,
        Ticket.first_response_at < period.end,
        Ticket.response_breached.is_not(None),
        *where_provider,
    )
    for pid, total, met in (await db.execute(q.group_by(Ticket.provider_id))).all():
        stats[pid]["responded"], stats[pid]["responded_met"] = total, met

    q = select(Ticket.provider_id, func.count()).where(
        Ticket.type == "incident",
        Ticket.priority == 1,
        Ticket.created_at >= period.start,
        Ticket.created_at < period.end,
        *where_provider,
    )
    for pid, total in (await db.execute(q.group_by(Ticket.provider_id))).all():
        stats[pid]["p1"] = total

    q = select(Ticket.provider_id, Ticket.resolution_business_min).where(
        Ticket.type == "incident",
        Ticket.resolved_at >= period.start,
        Ticket.resolved_at < period.end,
        Ticket.resolution_business_min.is_not(None),
        *where_provider,
    )
    for pid, minutes in (await db.execute(q)).all():
        stats[pid]["minutes"].append(minutes)
    return stats


async def _breaches_by_service(db: AsyncSession, period: Period) -> dict[int, list[dict]]:
    q = (
        select(Ticket.provider_id, Service.name, func.count())
        .join(Service, Service.id == Ticket.service_id)
        .where(
            Ticket.type.in_(SLA_TYPES),
            or_(
                and_(Ticket.resolved_at >= period.start, Ticket.resolved_at < period.end, Ticket.resolution_breached),
                and_(
                    Ticket.first_response_at >= period.start,
                    Ticket.first_response_at < period.end,
                    Ticket.response_breached,
                ),
            ),
        )
        .group_by(Ticket.provider_id, Service.name)
    )
    result: dict[int, list[dict]] = defaultdict(list)
    for pid, service_name, count in (await db.execute(q)).all():
        result[pid].append({"service": service_name, "breaches": count})
    for rows in result.values():
        rows.sort(key=lambda r: (-r["breaches"], r["service"]))
    return result


def _scorecard_row(provider: Provider, current: dict, previous: dict, top_services: list[dict]) -> dict:
    resolution = k.percent(current["resolved_met"], current["resolved"])
    previous_resolution = k.percent(previous["resolved_met"], previous["resolved"])
    return {
        "provider_id": provider.id,
        "name": provider.name,
        "short_name": provider.short_name,
        "kind": provider.kind,
        "agreement": sup.agreement_label(provider.kind),
        "contract_ref": provider.contract_ref,
        "target_pct": provider.target_pct,
        "plant_code": provider.plant.code if provider.plant else None,
        "tickets": current["resolved"],
        "resolution_compliance": resolution,
        "response_compliance": k.percent(current["responded_met"], current["responded"]),
        "mttr_hours": k.hours(current["minutes"])[0],
        "breaches": (current["resolved"] - current["resolved_met"]) + (current["responded"] - current["responded_met"]),
        "p1_incidents": current["p1"],
        "previous_resolution_compliance": previous_resolution,
        "trend": sup.trend(previous_resolution, resolution),
        "rag": sup.scorecard_rag(resolution, provider.target_pct),
        "top_breach_services": top_services[:3],
        "escalation_contact": provider.escalation_contact,
    }


KIND_ORDER = {"central": 0, "plant_it": 1, "external": 2}


async def scorecards(db: AsyncSession, month: str, now: datetime, only_provider: int | None = None) -> list[dict]:
    period = period_for(month, now)
    previous_period = period_for(shift_month(month, -1), now)
    current = await _provider_stats(db, period, only_provider)
    previous = await _provider_stats(db, previous_period, only_provider)
    top = await _breaches_by_service(db, period)
    providers = (await db.scalars(select(Provider))).all()
    if only_provider:
        providers = [p for p in providers if p.id == only_provider]
    providers = sorted(providers, key=lambda p: (KIND_ORDER[p.kind], p.id))
    return [_scorecard_row(p, current[p.id], previous[p.id], top.get(p.id, [])) for p in providers]


async def scorecard_trend(db: AsyncSession, provider_id: int, month: str, now: datetime) -> list[dict]:
    rows = []
    for m in months_back(month):
        stats = (await _provider_stats(db, period_for(m, now), provider_id))[provider_id]
        rows.append(
            {
                "month": m,
                "tickets": stats["resolved"],
                "resolution_compliance": k.percent(stats["resolved_met"], stats["resolved"]),
                "response_compliance": k.percent(stats["responded_met"], stats["responded"]),
                "mttr_hours": k.hours(stats["minutes"])[0],
            }
        )
    return rows


async def breached_tickets(db: AsyncSession, period: Period, filters: Filters, limit: int = 50) -> list[Ticket]:
    q = filters.apply(
        select(Ticket)
        .where(
            Ticket.type.in_(SLA_TYPES),
            or_(
                and_(Ticket.resolved_at >= period.start, Ticket.resolved_at < period.end, Ticket.resolution_breached),
                and_(
                    Ticket.first_response_at >= period.start,
                    Ticket.first_response_at < period.end,
                    Ticket.response_breached,
                ),
            ),
        )
        .order_by(
            Ticket.priority,
            (Ticket.resolution_business_min - Ticket.resolution_target_min).desc().nulls_last(),
            Ticket.id,
        )
        .limit(limit)
    )
    return list((await db.scalars(q)).unique().all())
