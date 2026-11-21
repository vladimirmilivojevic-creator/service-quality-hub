"""Request and response models (Pydantic v2)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TicketStatus = Literal["New", "In progress", "Pending", "Resolved", "Closed"]
ProblemStatus = Literal["investigating", "known_error", "resolved"]
ImprovementStatus = Literal["proposed", "approved", "in_progress", "done", "rejected"]
ImprovementSource = Literal["kpi_breach", "service_review", "problem", "idea"]
Lifecycle = Literal["pipeline", "live", "retired"]
Criticality = Literal["critical", "high", "medium", "low"]
SupportHours = Literal["24x7", "shift", "office"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Me(BaseModel):
    id: int
    email: str
    full_name: str
    title: str
    role: str
    plant_id: int | None
    plant_code: str | None
    provider_id: int | None


class PlantOut(ORMModel):
    id: int
    code: str
    name: str
    country: str
    timezone: str
    products: str


class SlaTargetOut(BaseModel):
    priority: int
    response_min: int
    resolution_min: int
    is_exception: bool


class ServiceOut(BaseModel):
    id: int
    name: str
    description: str
    service_type: str
    owner_name: str
    owner_email: str
    provider_name: str  # "Plant IT (each plant)" for plant IT services
    provider_id: int | None
    delivered_by_plant_it: bool
    support_hours: str
    support_hours_label: str
    criticality: str
    lifecycle: str
    categories: list[str]
    sla_targets: list[SlaTargetOut]


class SlaOverride(BaseModel):
    priority: int = Field(ge=1, le=4)
    response_min: int = Field(gt=0, le=60 * 24 * 30)
    resolution_min: int = Field(gt=0, le=60 * 24 * 60)


class ServicePatch(BaseModel):
    description: str | None = None
    owner_name: str | None = Field(default=None, min_length=2, max_length=80)
    owner_email: str | None = Field(default=None, max_length=120)
    support_hours: SupportHours | None = None
    criticality: Criticality | None = None
    lifecycle: Lifecycle | None = None
    # Replaces the service's SLA exceptions; an empty list means "use the default policy".
    sla_overrides: list[SlaOverride] | None = None


class TicketOut(BaseModel):
    id: int
    key: str
    external_key: str | None
    type: str
    plant_id: int
    plant_code: str
    service_id: int
    service_name: str
    provider_id: int
    provider_name: str
    priority: int
    impact: str | None
    urgency: str | None
    status: str
    category: str
    title: str
    source: str
    created_at: datetime
    first_response_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    pending_since: datetime | None
    paused_minutes: int
    reopen_count: int
    response_target_min: int | None
    resolution_target_min: int | None
    response_business_min: int | None
    resolution_business_min: int | None
    response_breached: bool | None
    resolution_breached: bool | None
    # Live clock for open tickets (based on the demo clock)
    response_status: str | None = None
    resolution_status: str | None = None
    response_elapsed_min: int | None = None
    resolution_elapsed_min: int | None = None
    response_due_at: datetime | None = None
    resolution_due_at: datetime | None = None
    problem_id: int | None
    caused_by_change_id: int | None
    change_type: str | None
    planned_start: datetime | None
    planned_end: datetime | None
    outcome: str | None
    problem_status: str | None
    root_cause: str | None
    workaround: str | None
    source_sla_note: str | None


class TicketDetail(TicketOut):
    support_hours_label: str
    plant_timezone: str
    linked: list[TicketOut] = []  # incidents of a problem / incidents caused by a change
    problem: TicketOut | None = None
    caused_by_change: TicketOut | None = None


class TicketPage(BaseModel):
    items: list[TicketOut]
    total: int


class TicketPatch(BaseModel):
    status: TicketStatus | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)


class ProblemCreate(BaseModel):
    incident_ids: list[int] = Field(min_length=1, max_length=50)
    title: str | None = Field(default=None, max_length=200)


class ProblemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    problem_status: ProblemStatus | None = None
    root_cause: str | None = Field(default=None, max_length=2000)
    workaround: str | None = Field(default=None, max_length=2000)


class ImprovementIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=4000)
    source: ImprovementSource
    service_id: int | None = None
    plant_id: int | None = None
    provider_id: int | None = None
    owner: str = Field(min_length=2, max_length=80)
    status: ImprovementStatus = "proposed"
    due_date: date | None = None
    expected_benefit: str = Field(default="", max_length=200)
    kpi: str | None = Field(default=None, max_length=40)
    kpi_baseline: float | None = None
    kpi_target: float | None = None


class ImprovementPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    owner: str | None = Field(default=None, min_length=2, max_length=80)
    status: ImprovementStatus | None = None
    due_date: date | None = None
    expected_benefit: str | None = Field(default=None, max_length=200)
    kpi_target: float | None = None


class ImprovementOut(BaseModel):
    id: int
    title: str
    description: str
    source: str
    service_id: int | None
    service_name: str | None
    plant_id: int | None
    plant_code: str | None
    provider_id: int | None
    provider_name: str | None
    owner: str
    status: str
    due_date: date | None
    overdue: bool
    expected_benefit: str
    kpi: str | None
    kpi_baseline: float | None
    kpi_target: float | None
    created_at: datetime
    completed_at: datetime | None


class ImportIssue(BaseModel):
    row: int
    message: str


class ImportPreviewRow(BaseModel):
    row: int
    key: str
    type: str
    plant_code: str
    service_name: str
    priority: int
    status: str
    created_at: datetime
    resolved_at: datetime | None
    title: str


class ImportPreview(BaseModel):
    total_rows: int
    valid_rows: int
    detected: dict[str, str]  # which CSV column was used for what
    rows: list[ImportPreviewRow]
    skipped: list[ImportIssue]
    warnings: list[str]


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: list[ImportIssue]
    warnings: list[str]


class SimulationResult(BaseModel):
    demo_now: datetime
    created: int
    resolved: int
    new_breaches: int
    changes: int
    messages: list[str]
