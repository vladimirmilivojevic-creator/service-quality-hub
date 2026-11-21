"""Problem management: candidates from recurring incidents, problem records and known errors."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.deps import DB, EditorUser, StaffUser, ensure_plant_scope
from app.domain.problems import WINDOW_DAYS, IncidentRef, find_candidates
from app.models import Ticket
from app.routers.tickets import get_ticket
from app.schemas import ProblemCreate, ProblemPatch, TicketDetail
from app.services import demo_now, load_catalogue, new_ticket, next_key, ticket_out

router = APIRouter(prefix="/problems", tags=["problems"])


@router.get("/candidates")
async def problem_candidates(db: DB, _: StaffUser) -> list[dict]:
    """Groups of at least 3 similar, unlinked incidents in the last 14 days."""
    now = await demo_now(db)
    rows = (
        (
            await db.scalars(
                select(Ticket).where(
                    Ticket.type == "incident",
                    Ticket.problem_id.is_(None),
                    Ticket.created_at >= now - timedelta(days=WINDOW_DAYS),
                    Ticket.created_at <= now,
                )
            )
        )
        .unique()
        .all()
    )
    by_id = {t.id: t for t in rows}
    refs = [IncidentRef(t.id, t.key, t.plant_id, t.service_id, t.category, t.title, t.created_at) for t in rows]
    catalogue = await load_catalogue(db)
    result = []
    for candidate in find_candidates(refs, now):
        plant = catalogue.plants[candidate.plant_id]
        service = catalogue.services[candidate.service_id]
        result.append(
            {
                "plant_id": plant.id,
                "plant_code": plant.code,
                "plant_name": plant.name,
                "service_id": service.id,
                "service_name": service.name,
                "category": candidate.category,
                "count": candidate.count,
                "first_seen": candidate.first_seen,
                "last_seen": candidate.last_seen,
                "suggested_title": f"Recurring '{candidate.category}' incidents – {service.name} at {plant.name}",
                "incidents": [ticket_out(by_id[i.id], now, catalogue).model_dump() for i in candidate.incidents],
            }
        )
    return result


@router.get("")
async def list_problems(db: DB, _: StaffUser) -> list[dict]:
    now = await demo_now(db)
    catalogue = await load_catalogue(db)
    problems = (
        await db.scalars(select(Ticket).where(Ticket.type == "problem").order_by(Ticket.created_at.desc()))
    ).all()
    counts = dict(
        (
            await db.execute(
                select(Ticket.problem_id, func.count())
                .where(Ticket.problem_id.is_not(None))
                .group_by(Ticket.problem_id)
            )
        ).all()
    )
    return [{**ticket_out(p, now, catalogue).model_dump(), "incident_count": counts.get(p.id, 0)} for p in problems]


@router.post("", response_model=TicketDetail, status_code=201)
async def create_problem(body: ProblemCreate, db: DB, user: EditorUser) -> TicketDetail:
    incidents = (await db.scalars(select(Ticket).where(Ticket.id.in_(body.incident_ids)))).unique().all()
    if len(incidents) != len(set(body.incident_ids)):
        raise HTTPException(404, "One or more incidents were not found")
    if any(t.type != "incident" for t in incidents):
        raise HTTPException(409, "Only incidents can be linked to a problem")
    if any(t.problem_id is not None for t in incidents):
        raise HTTPException(409, "One or more incidents already belong to a problem")
    groups = {(t.plant_id, t.service_id) for t in incidents}
    if len(groups) != 1:
        raise HTTPException(409, "All incidents of a problem must have the same plant and service")
    plant_id, service_id = groups.pop()
    ensure_plant_scope(user, plant_id)

    now = await demo_now(db)
    catalogue = await load_catalogue(db)
    first = min(incidents, key=lambda t: t.created_at)
    problem = new_ticket(
        catalogue,
        key=await next_key(db, "problem"),
        ticket_type="problem",
        plant_id=plant_id,
        service_id=service_id,
        priority=min(t.priority for t in incidents),
        category="Problem",
        title=body.title or f"Recurring: {first.title}",
        created_at=now,
        source="manual",
    )
    problem.status, problem.problem_status, problem.first_response_at = "In progress", "investigating", now
    db.add(problem)
    await db.flush()
    for incident in incidents:
        incident.problem_id = problem.id
    await db.commit()
    return await get_ticket(problem.id, db, user)


@router.get("/{problem_id}", response_model=TicketDetail)
async def get_problem(problem_id: int, db: DB, user: StaffUser) -> TicketDetail:
    detail = await get_ticket(problem_id, db, user)
    if detail.type != "problem":
        raise HTTPException(404, "Problem not found")
    return detail


@router.patch("/{problem_id}", response_model=TicketDetail)
async def update_problem(problem_id: int, body: ProblemPatch, db: DB, user: EditorUser) -> TicketDetail:
    problem = await db.get(Ticket, problem_id)
    if problem is None or problem.type != "problem":
        raise HTTPException(404, "Problem not found")
    ensure_plant_scope(user, problem.plant_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(problem, field, value)
    if body.problem_status == "known_error" and not (problem.workaround or "").strip():
        raise HTTPException(409, "A known error needs a documented workaround")
    if body.problem_status == "resolved":
        if not (problem.root_cause or "").strip():
            raise HTTPException(409, "Document the root cause before resolving the problem")
        now = await demo_now(db)
        problem.status, problem.resolved_at, problem.closed_at = "Closed", now, now
    elif body.problem_status in ("investigating", "known_error"):
        problem.status, problem.resolved_at, problem.closed_at = "In progress", None, None
    await db.commit()
    return await get_ticket(problem_id, db, user)
