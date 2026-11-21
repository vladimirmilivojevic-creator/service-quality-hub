"""Plants, the service catalogue (with portfolio status and SLA targets) and the rules for the
"How it works" page."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select

from app.deps import DB, CurrentUser, ManagerUser, StaffUser
from app.domain import kpis, problems, sla, suppliers
from app.models import Plant, Service, SlaTarget
from app.schemas import PlantOut, ServiceOut, ServicePatch, SlaTargetOut
from app.services import Catalogue, demo_state, load_catalogue

router = APIRouter(tags=["catalogue"])


@router.get("/plants", response_model=list[PlantOut])
async def list_plants(db: DB, _: CurrentUser) -> list[Plant]:
    return list((await db.scalars(select(Plant).order_by(Plant.id))).all())


def _service_out(service: Service, catalogue: Catalogue) -> ServiceOut:
    targets = []
    for priority in sorted(sla.DEFAULT_SLA_POLICY):
        response, resolution = catalogue.targets(service.id, priority)
        targets.append(
            SlaTargetOut(
                priority=priority,
                response_min=response,
                resolution_min=resolution,
                is_exception=(service.id, priority) in catalogue.policy,
            )
        )
    return ServiceOut(
        id=service.id,
        name=service.name,
        description=service.description,
        service_type=service.service_type,
        owner_name=service.owner_name,
        owner_email=service.owner_email,
        provider_name=service.provider.name if service.provider else "Plant IT (each plant)",
        provider_id=service.provider_id,
        delivered_by_plant_it=service.delivered_by_plant_it,
        support_hours=service.support_hours,
        support_hours_label=sla.CALENDARS[service.support_hours].label,
        criticality=service.criticality,
        lifecycle=service.lifecycle,
        categories=service.categories.split(","),
        sla_targets=targets,
    )


@router.get("/services", response_model=list[ServiceOut])
async def list_services(db: DB, _: StaffUser, lifecycle: str | None = None) -> list[ServiceOut]:
    query = select(Service).order_by(Service.id)
    if lifecycle:
        query = query.where(Service.lifecycle == lifecycle)
    catalogue = await load_catalogue(db)
    return [_service_out(s, catalogue) for s in (await db.scalars(query)).all()]


@router.patch("/services/{service_id}", response_model=ServiceOut)
async def update_service(service_id: int, body: ServicePatch, db: DB, _: ManagerUser) -> ServiceOut:
    service = await db.get(Service, service_id)
    if service is None:
        raise HTTPException(404, "Service not found")
    changes = body.model_dump(exclude_unset=True, exclude={"sla_overrides"})
    for field, value in changes.items():
        setattr(service, field, value)
    if body.sla_overrides is not None:
        # New targets only apply to new tickets: existing tickets keep their frozen targets.
        await db.execute(delete(SlaTarget).where(SlaTarget.service_id == service_id))
        priorities = [o.priority for o in body.sla_overrides]
        if len(priorities) != len(set(priorities)):
            raise HTTPException(422, "Each priority may appear only once")
        for override in body.sla_overrides:
            if override.response_min >= override.resolution_min:
                raise HTTPException(422, "The response target must be shorter than the resolution target")
            db.add(SlaTarget(service_id=service_id, **override.model_dump()))
    await db.commit()
    await db.refresh(service)
    return _service_out(service, await load_catalogue(db))


@router.get("/meta", tags=["meta"])
async def rules(db: DB) -> dict:
    """All rules and targets in one place, for the "How it works" page (public, no login needed)."""
    state = await demo_state(db)
    return {
        "demo_now": state.demo_now,
        "simulated_days": state.simulated_days,
        "calendars": [{"code": c.code, "label": c.label} for c in sla.CALENDARS.values()],
        "priorities": [
            {
                "priority": p,
                "label": sla.PRIORITY_LABELS[p],
                "example": sla.PRIORITY_EXAMPLES[p],
                "response_min": r,
                "resolution_min": s,
            }
            for p, (r, s) in sla.DEFAULT_SLA_POLICY.items()
        ],
        "priority_matrix": [
            {"impact": i, "urgency": u, "priority": sla.PRIORITY_MATRIX[(i, u)]} for i in sla.LEVELS for u in sla.LEVELS
        ],
        "at_risk_share": sla.AT_RISK_SHARE,
        "kpis": [
            {
                "key": d.key,
                "name": d.name,
                "unit": d.unit,
                "definition": d.definition,
                "formula": d.formula,
                "target_text": d.target_text,
            }
            for d in kpis.KPIS.values()
        ],
        "mttr_targets_hours": kpis.MTTR_TARGET_HOURS,
        "problem_rule": {"min_incidents": problems.MIN_INCIDENTS, "window_days": problems.WINDOW_DAYS},
        "supplier_amber_band": suppliers.AMBER_BAND,
    }
