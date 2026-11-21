"""Continual improvement (CSI) register."""

from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import DB, EditorUser, StaffUser, ensure_plant_scope
from app.models import Improvement, Plant, Provider, Service
from app.schemas import ImprovementIn, ImprovementOut, ImprovementPatch
from app.services import demo_now

router = APIRouter(prefix="/improvements", tags=["improvements"])

CLOSED = ("done", "rejected")


def is_overdue(item: Improvement, today: date) -> bool:
    return item.due_date is not None and item.due_date < today and item.status not in CLOSED


def improvement_out(item: Improvement, today: date) -> ImprovementOut:
    return ImprovementOut(
        id=item.id,
        title=item.title,
        description=item.description,
        source=item.source,
        service_id=item.service_id,
        service_name=item.service.name if item.service else None,
        plant_id=item.plant_id,
        plant_code=item.plant.code if item.plant else None,
        provider_id=item.provider_id,
        provider_name=item.provider.name if item.provider else None,
        owner=item.owner,
        status=item.status,
        due_date=item.due_date,
        overdue=is_overdue(item, today),
        expected_benefit=item.expected_benefit,
        kpi=item.kpi,
        kpi_baseline=item.kpi_baseline,
        kpi_target=item.kpi_target,
        created_at=item.created_at,
        completed_at=item.completed_at,
    )


@router.get("", response_model=list[ImprovementOut])
async def list_improvements(
    db: DB,
    _: StaffUser,
    status: str | None = None,
    plant_id: int | None = None,
    provider_id: int | None = None,
    overdue: bool | None = None,
) -> list[ImprovementOut]:
    query = select(Improvement).order_by(Improvement.created_at.desc(), Improvement.id.desc())
    if status:
        query = query.where(Improvement.status == status)
    if plant_id:
        query = query.where(Improvement.plant_id == plant_id)
    if provider_id:
        query = query.where(Improvement.provider_id == provider_id)
    today = (await demo_now(db)).date()
    items = [improvement_out(i, today) for i in (await db.scalars(query)).unique().all()]
    if overdue is not None:
        items = [i for i in items if i.overdue == overdue]
    return items


async def _check_references(db: DB, body: ImprovementIn | ImprovementPatch) -> None:
    for model, field in ((Service, "service_id"), (Plant, "plant_id"), (Provider, "provider_id")):
        value = getattr(body, field, None)
        if value is not None and await db.get(model, value) is None:
            raise HTTPException(422, f"Unknown {field.replace('_id', '')}")


@router.post("", response_model=ImprovementOut, status_code=201)
async def create_improvement(body: ImprovementIn, db: DB, user: EditorUser) -> ImprovementOut:
    ensure_plant_scope(user, body.plant_id)
    await _check_references(db, body)
    now = await demo_now(db)
    item = Improvement(**body.model_dump(), created_at=now)
    if item.status == "done":
        item.completed_at = now
    db.add(item)
    await db.commit()
    await db.refresh(item, ["service", "plant", "provider"])  # load the names for the response
    return improvement_out(item, now.date())


@router.patch("/{improvement_id}", response_model=ImprovementOut)
async def update_improvement(improvement_id: int, body: ImprovementPatch, db: DB, user: EditorUser) -> ImprovementOut:
    item = await db.get(Improvement, improvement_id)
    if item is None:
        raise HTTPException(404, "Improvement not found")
    ensure_plant_scope(user, item.plant_id)
    now = await demo_now(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    if body.status is not None:
        item.completed_at = now if body.status == "done" else None
    await db.commit()
    await db.refresh(item, ["service", "plant", "provider"])
    return improvement_out(item, now.date())
