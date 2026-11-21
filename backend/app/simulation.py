"""'Simulate next day': moves the demo clock forward by one day and creates that day's activity.

The random generator is seeded with the date, so the same day always produces the same events.
"""

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import catalogue_data as data
from app.domain.problems import WINDOW_DAYS
from app.models import OPEN_STATUSES, Ticket
from app.schemas import SimulationResult
from app.seed import CHANGES_PER_MONTH, WORKDAYS_PER_MONTH, DemoGenerator
from app.services import SLA_TYPES, change_status, demo_state, live_clock, load_catalogue, next_key

RESOLVE_CHANCE = {1: 0.95, 2: 0.85, 3: 0.5, 4: 0.3}  # chance that an open ticket is resolved today
AUTO_CLOSE_AFTER = timedelta(days=3)
WAITING_FOR_DECISION = timedelta(days=30)  # very old requests wait for a budget decision, not for IT

# A recurring issue appears once a day; after three days it becomes a problem candidate.
RECURRING = [
    ("ILL", "Email & collaboration", "Mailbox", "Outlook search does not find new emails"),
    ("INN", "Plant network (LAN & Wi-Fi)", "Wi-Fi coverage", "Wi-Fi drops at the paint shop"),
    ("SAL", "ERP – production & logistics", "Printing from ERP", "Shipping labels from ERP print twice"),
    ("RHV", "Warehouse scanners & MDM", "App / MDM", "Warehouse app freezes after MDM update"),
]


def _random_moment(rng: random.Random, start: datetime, end: datetime, tz: ZoneInfo | None = None) -> datetime:
    """A random moment in (start, end), preferring local working hours when a time zone is given."""
    span = int((end - start).total_seconds())
    moment = start + timedelta(seconds=rng.randint(1, span - 1))
    for _ in range(5):
        if tz is None or 6 <= moment.astimezone(tz).hour < 18:
            break
        moment = start + timedelta(seconds=rng.randint(1, span - 1))
    return moment


async def simulate_next_day(db: AsyncSession) -> SimulationResult:
    state = await demo_state(db, lock=True)
    start = state.demo_now
    end = start + timedelta(days=1)
    rng = random.Random(f"simulate-{end.date().isoformat()}")
    catalogue = await load_catalogue(db)
    gen = DemoGenerator(catalogue, rng, end)
    resolved = breaches = 0

    # Let the generator know the recent incidents, so random noise does not form problem candidates
    # (candidates in the simulation come from the RECURRING list below).
    recent = await db.execute(
        select(Ticket.plant_id, Ticket.service_id, Ticket.category, Ticket.created_at).where(
            Ticket.type == "incident",
            Ticket.problem_id.is_(None),
            Ticket.created_at >= start - timedelta(days=WINDOW_DAYS),
        )
    )
    for plant_id, service_id, category, created_at in recent.all():
        gen.recent_incidents[(plant_id, service_id, category)].append(created_at)

    # 1. Work on open tickets.
    open_tickets = (
        (
            await db.scalars(
                select(Ticket)
                .where(Ticket.type.in_(SLA_TYPES), Ticket.status.in_(OPEN_STATUSES))
                .order_by(Ticket.created_at, Ticket.id)
            )
        )
        .unique()
        .all()
    )
    for ticket in open_tickets:
        before = live_clock(ticket, start, catalogue)
        moment = _random_moment(rng, max(start, ticket.created_at), end)
        if end - ticket.created_at > WAITING_FOR_DECISION:
            pass  # waits for a decision outside IT
        elif ticket.status == "Pending" and rng.random() < 0.5:
            change_status(ticket, "In progress", moment, catalogue)  # the user answered
        elif ticket.status != "Pending" and rng.random() < RESOLVE_CHANCE[ticket.priority]:
            change_status(ticket, "Resolved", moment, catalogue)
            resolved += 1
            breaches += (
                bool(ticket.resolution_breached) and before is not None and before.resolution_status != "breached"
            )
        elif ticket.status == "New":
            change_status(ticket, "In progress", moment, catalogue)
        after = live_clock(ticket, end, catalogue)
        if before and after and before.resolution_status != "breached" and after.resolution_status == "breached":
            breaches += 1

    # 2. Users confirm fixes (close) or reopen tickets whose fix did not hold.
    recently_resolved = (await db.scalars(select(Ticket).where(Ticket.status == "Resolved"))).unique().all()
    for ticket in recently_resolved:
        if ticket.resolved_at and ticket.resolved_at + AUTO_CLOSE_AFTER <= end:
            change_status(ticket, "Closed", ticket.resolved_at + AUTO_CLOSE_AFTER, catalogue)
        elif ticket.resolved_at and ticket.resolved_at < start and rng.random() < 0.03:
            change_status(ticket, "In progress", _random_moment(rng, start, end), catalogue)

    # 3. New tickets and changes of the day.
    created = changes = 0
    for code, *_rest, monthly_volume in data.PLANTS:
        plant = gen.plant_by_code[code]
        tz = ZoneInfo(plant.timezone)
        local_day = end.astimezone(tz).date()
        weekend = local_day.weekday() >= 5
        expected = monthly_volume / WORKDAYS_PER_MONTH * (0.08 if weekend else 1.0)
        for _ in range(max(0, round(rng.gauss(expected, expected * 0.3)))):
            if gen.random_ticket(plant, _random_moment(rng, start, end, tz), "simulated", weekend):
                created += 1
        if not weekend and rng.random() < CHANGES_PER_MONTH / WORKDAYS_PER_MONTH:
            gen.random_change(plant, local_day, "simulated")
            changes += 1

    plant_code, service_name, category, title = RECURRING[(state.simulated_days // 3) % len(RECURRING)]
    plant = gen.plant_by_code[plant_code]
    gen.story_incident(
        plant,
        gen.service_by_name[service_name],
        category,
        title,
        _random_moment(rng, start, end, ZoneInfo(plant.timezone)),
    )
    gen.tickets[-1].source = "simulated"
    created += 1

    gen.tickets.sort(key=lambda t: t.created_at)
    for ticket in gen.tickets:
        ticket.key = await next_key(db, ticket.type)
        if ticket.resolved_at and ticket.resolved_at <= end:
            resolved += 1
            breaches += bool(ticket.resolution_breached)
    db.add_all(gen.tickets)

    state.demo_now = end
    state.simulated_days += 1
    await db.commit()

    local = end.astimezone(ZoneInfo("Europe/Vienna"))
    return SimulationResult(
        demo_now=end,
        created=created,
        resolved=resolved,
        new_breaches=breaches,
        changes=changes,
        messages=[
            f"Demo clock moved to {local:%a %d %b %Y, %H:%M} (Vienna time).",
            f"{created} new tickets, {resolved} resolved, {breaches} new SLA breaches, {changes} changes.",
            f"A recurring issue was reported again: '{title}' at {plant.name}.",
        ],
    )
