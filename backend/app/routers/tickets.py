from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select

from app.analytics import month_bounds
from app.deps import DB, EditorUser, StaffUser, ensure_plant_scope
from app.domain import sla as sla_rules
from app.models import OPEN_STATUSES, Ticket
from app.schemas import TicketDetail, TicketPage, TicketPatch
from app.services import (
    SLA_TYPES,
    TicketRuleError,
    change_status,
    demo_now,
    load_catalogue,
    ticket_out,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=TicketPage)
async def list_tickets(
    db: DB,
    _: StaffUser,
    type: str | None = None,
    plant_id: int | None = None,
    service_id: int | None = None,
    provider_id: int | None = None,
    status: str | None = None,
    priority: int | None = None,
    open: bool | None = None,
    sla: Annotated[str | None, Query(description="Comma-separated: on_track, at_risk, breached (open tickets)")] = None,
    breached: bool | None = Query(None, description="Only tickets with a stored response or resolution breach"),
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$", description="Created in this month"),
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> TicketPage:
    # Without a type filter the ticket list shows incidents and requests (the records with an SLA).
    query = select(Ticket).where(Ticket.type == type if type else Ticket.type.in_(SLA_TYPES))
    for column, value in (
        (Ticket.plant_id, plant_id),
        (Ticket.service_id, service_id),
        (Ticket.provider_id, provider_id),
        (Ticket.status, status),
        (Ticket.priority, priority),
    ):
        if value is not None:
            query = query.where(column == value)
    if open is not None:
        query = query.where(Ticket.status.in_(OPEN_STATUSES) if open else Ticket.status.not_in(OPEN_STATUSES))
    if breached:
        query = query.where(or_(Ticket.response_breached.is_(True), Ticket.resolution_breached.is_(True)))
    if month:
        start, end = month_bounds(month)
        query = query.where(Ticket.created_at >= start, Ticket.created_at < end)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Ticket.key.ilike(pattern), Ticket.title.ilike(pattern)))
    query = query.order_by(Ticket.created_at.desc(), Ticket.id.desc())

    now = await demo_now(db)
    catalogue = await load_catalogue(db)
    if sla:
        # Live SLA state depends on the demo clock, so it is filtered after loading (open tickets only).
        wanted = {s.strip() for s in sla.split(",")}
        candidates = (await db.scalars(query.where(Ticket.status.in_(OPEN_STATUSES)))).unique().all()
        views = [ticket_out(t, now, catalogue) for t in candidates]
        views = [v for v in views if v.response_status in wanted or v.resolution_status in wanted]
        views.sort(key=lambda v: (v.resolution_status != "breached", v.priority, v.created_at))
        return TicketPage(items=views[(page - 1) * size : page * size], total=len(views))

    total = await db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = (await db.scalars(query.offset((page - 1) * size).limit(size))).unique().all()
    return TicketPage(items=[ticket_out(t, now, catalogue) for t in rows], total=total or 0)


async def _get(db: DB, ticket_id: int) -> Ticket:
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    return ticket


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket(ticket_id: int, db: DB, _: StaffUser) -> TicketDetail:
    ticket = await _get(db, ticket_id)
    now = await demo_now(db)
    catalogue = await load_catalogue(db)
    linked = []
    if ticket.type == "problem":
        linked = (
            await db.scalars(select(Ticket).where(Ticket.problem_id == ticket.id).order_by(Ticket.created_at))
        ).all()
    elif ticket.type == "change":
        linked = (
            await db.scalars(select(Ticket).where(Ticket.caused_by_change_id == ticket.id).order_by(Ticket.created_at))
        ).all()
    problem = await db.get(Ticket, ticket.problem_id) if ticket.problem_id else None
    change = await db.get(Ticket, ticket.caused_by_change_id) if ticket.caused_by_change_id else None
    service = catalogue.services[ticket.service_id]
    return TicketDetail(
        **ticket_out(ticket, now, catalogue).model_dump(),
        support_hours_label=sla_rules.CALENDARS[service.support_hours].label,
        plant_timezone=catalogue.plants[ticket.plant_id].timezone,
        linked=[ticket_out(t, now, catalogue) for t in linked],
        problem=ticket_out(problem, now, catalogue) if problem else None,
        caused_by_change=ticket_out(change, now, catalogue) if change else None,
    )


@router.patch("/{ticket_id}", response_model=TicketDetail)
async def update_ticket(ticket_id: int, body: TicketPatch, db: DB, user: EditorUser) -> TicketDetail:
    ticket = await _get(db, ticket_id)
    ensure_plant_scope(user, ticket.plant_id)
    if ticket.type not in SLA_TYPES:
        raise HTTPException(409, "Problems and changes are updated on their own pages")
    if body.title is not None:
        ticket.title = body.title
    if body.status is not None:
        try:
            change_status(ticket, body.status, await demo_now(db), await load_catalogue(db))
        except TicketRuleError as error:
            raise HTTPException(409, str(error)) from error
    await db.commit()
    return await get_ticket(ticket_id, db, user)
