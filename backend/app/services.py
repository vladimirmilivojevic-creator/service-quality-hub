"""Ticket lifecycle and helpers shared by the API, the CSV importer, the seed and the simulator.

Everything that changes a ticket goes through these functions, so the SLA targets are always
frozen at creation and the SLA results are always written by the same engine.
"""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import sla
from app.models import OPEN_STATUSES, DemoState, Plant, Provider, Service, SlaTarget, Ticket

KEY_PREFIX = {"incident": "INC", "request": "REQ", "problem": "PRB", "change": "CHG"}
SLA_TYPES = ("incident", "request")  # problems and changes have no response / resolution SLA


class TicketRuleError(ValueError):
    """A change that the process does not allow (shown to the user as HTTP 409)."""


# --- Demo clock ----------------------------------------------------------------------------


async def demo_state(db: AsyncSession, *, lock: bool = False) -> DemoState:
    """The single demo-clock row. ``lock=True`` (SELECT ... FOR UPDATE on PostgreSQL) serialises writers,
    so two parallel requests can never hand out the same ticket number or move the clock twice."""
    query = select(DemoState).where(DemoState.id == 1)
    if lock:
        query = query.with_for_update()
    state = await db.scalar(query)
    if state is None:
        raise RuntimeError("Demo data is missing: run the seed first")
    return state


async def demo_now(db: AsyncSession) -> datetime:
    return (await demo_state(db)).demo_now


async def next_key(db: AsyncSession, ticket_type: str) -> str:
    state = await demo_state(db, lock=True)
    state.ticket_counter += 1
    return f"{KEY_PREFIX[ticket_type]}-{state.ticket_counter}"


# --- Catalogue lookups ---------------------------------------------------------------------


@dataclass
class Catalogue:
    """Everything needed to route and measure tickets, loaded once per request or batch."""

    plants: dict[int, Plant]
    services: dict[int, Service]
    providers: dict[int, Provider]
    policy: dict[tuple[int | None, int], tuple[int, int]]  # (service_id | None, priority) -> targets

    def plant_it_team(self, plant_id: int) -> Provider:
        return next(p for p in self.providers.values() if p.kind == "plant_it" and p.plant_id == plant_id)

    def provider_for(self, service: Service, plant_id: int) -> Provider:
        """Plant IT services are delivered by the plant's own IT team, the rest by the named provider."""
        if service.delivered_by_plant_it or service.provider_id is None:
            return self.plant_it_team(plant_id)
        return self.providers[service.provider_id]

    def targets(self, service_id: int, priority: int) -> tuple[int, int]:
        """(response, resolution) minutes: the service's exception if it has one, else the default policy."""
        return self.policy.get((service_id, priority)) or self.policy[(None, priority)]

    def clock_for(self, ticket: Ticket) -> tuple[sla.Calendar, ZoneInfo]:
        """Support hours of the ticket's service, in the time zone of the ticket's plant."""
        service = self.services[ticket.service_id]
        plant = self.plants[ticket.plant_id]
        return sla.CALENDARS[service.support_hours], ZoneInfo(plant.timezone)


async def load_catalogue(db: AsyncSession) -> Catalogue:
    # Ordered by id: the demo generator walks these lists, so the order must be the same on every database.
    plants = {p.id: p for p in (await db.scalars(select(Plant).order_by(Plant.id))).all()}
    services = {s.id: s for s in (await db.scalars(select(Service).order_by(Service.id))).all()}
    providers = {p.id: p for p in (await db.scalars(select(Provider).order_by(Provider.id))).all()}
    policy = {
        (t.service_id, t.priority): (t.response_min, t.resolution_min) for t in await db.scalars(select(SlaTarget))
    }
    return Catalogue(plants, services, providers, policy)


# --- Ticket lifecycle ----------------------------------------------------------------------


def freeze_targets(ticket: Ticket, catalogue: Catalogue) -> None:
    """Copy today's SLA targets onto the ticket. They never change afterwards."""
    if ticket.type in SLA_TYPES:
        ticket.response_target_min, ticket.resolution_target_min = catalogue.targets(ticket.service_id, ticket.priority)
    else:
        ticket.response_target_min = ticket.resolution_target_min = None


def record_sla_results(ticket: Ticket, catalogue: Catalogue) -> None:
    """(Re)calculate the stored SLA results from the ticket's timestamps."""
    if ticket.type not in SLA_TYPES:
        return
    calendar, tz = catalogue.clock_for(ticket)
    result = sla.measure(
        created_at=ticket.created_at,
        first_response_at=ticket.first_response_at,
        resolved_at=ticket.resolved_at,
        paused_minutes=ticket.paused_minutes or 0,
        calendar=calendar,
        tz=tz,
        response_target_min=ticket.response_target_min,
        resolution_target_min=ticket.resolution_target_min,
    )
    ticket.response_business_min = result.response_minutes
    ticket.resolution_business_min = result.resolution_minutes
    ticket.response_breached = result.response_breached
    ticket.resolution_breached = result.resolution_breached


def new_ticket(
    catalogue: Catalogue,
    *,
    key: str,
    ticket_type: str,
    plant_id: int,
    service_id: int,
    priority: int,
    category: str,
    title: str,
    created_at: datetime,
    source: str,
    impact: str | None = None,
    urgency: str | None = None,
    external_key: str | None = None,
) -> Ticket:
    service = catalogue.services[service_id]
    ticket = Ticket(
        key=key,
        external_key=external_key,
        type=ticket_type,
        plant_id=plant_id,
        service_id=service_id,
        provider_id=catalogue.provider_for(service, plant_id).id,
        priority=priority,
        impact=impact,
        urgency=urgency,
        status="New",
        category=category,
        title=title,
        source=source,
        created_at=created_at,
        paused_minutes=0,
        reopen_count=0,
    )
    freeze_targets(ticket, catalogue)
    return ticket


def change_status(ticket: Ticket, new_status: str, now: datetime, catalogue: Catalogue) -> None:
    """Move a ticket to a new status and keep timestamps, pauses and SLA results consistent."""
    old = ticket.status
    if new_status == old:
        return
    if now < ticket.created_at:
        raise TicketRuleError("The new status cannot be earlier than the ticket's creation")
    calendar, tz = catalogue.clock_for(ticket)

    # Leaving "Pending": the waiting time is added to the pause so the resolution clock skips it.
    if old == "Pending" and ticket.pending_since is not None:
        ticket.paused_minutes += sla.business_minutes_between(ticket.pending_since, now, calendar, tz)
        ticket.pending_since = None

    if new_status in ("In progress", "Pending", "Resolved") and ticket.first_response_at is None:
        ticket.first_response_at = now  # the first action by IT counts as the first response

    if new_status == "Pending":
        ticket.pending_since = now
    elif new_status == "Resolved":
        ticket.resolved_at = now
    elif new_status == "Closed":
        if ticket.resolved_at is None:
            ticket.resolved_at = now
        ticket.closed_at = now
    elif new_status in ("New", "In progress") and old in ("Resolved", "Closed"):
        # Reopened: the fix did not hold. The resolution clock continues from the original creation.
        ticket.reopen_count += 1
        ticket.resolved_at = None
        ticket.closed_at = None

    ticket.status = new_status
    record_sla_results(ticket, catalogue)


def is_open(ticket: Ticket) -> bool:
    return ticket.status in OPEN_STATUSES


def live_clock(ticket: Ticket, now: datetime, catalogue: Catalogue) -> sla.SlaClock | None:
    if ticket.type not in SLA_TYPES or not is_open(ticket):
        return None
    calendar, tz = catalogue.clock_for(ticket)
    return sla.live_clock(
        now=now,
        created_at=ticket.created_at,
        first_response_at=ticket.first_response_at,
        paused_minutes=ticket.paused_minutes or 0,
        pending_since=ticket.pending_since,
        calendar=calendar,
        tz=tz,
        response_target_min=ticket.response_target_min,
        resolution_target_min=ticket.resolution_target_min,
    )


# --- API views ------------------------------------------------------------------------------


def ticket_out(ticket: Ticket, now: datetime, catalogue: Catalogue):
    """Ticket as the API shows it, including the live SLA clock for open tickets."""
    from app.schemas import TicketOut  # local import: schemas are an API concern

    clock = live_clock(ticket, now, catalogue)
    fields = {name: getattr(ticket, name) for name in TicketOut.model_fields if hasattr(Ticket, name)}
    fields.update(
        plant_code=catalogue.plants[ticket.plant_id].code,
        service_name=catalogue.services[ticket.service_id].name,
        provider_name=catalogue.providers[ticket.provider_id].name,
        paused_minutes=ticket.paused_minutes or 0,
        reopen_count=ticket.reopen_count or 0,
    )
    if clock is not None:
        fields.update(
            response_status=clock.response_status,
            resolution_status=clock.resolution_status,
            response_elapsed_min=clock.response_elapsed,
            resolution_elapsed_min=clock.resolution_elapsed,
            response_due_at=clock.response_due_at,
            resolution_due_at=clock.resolution_due_at,
        )
    elif ticket.type in SLA_TYPES:
        fields.update(
            response_status=sla.sla_status(ticket.response_business_min, ticket.response_target_min, is_open=False),
            resolution_status=sla.sla_status(ticket.resolution_business_min, ticket.resolution_target_min, False),
        )
    return TicketOut(**fields)
