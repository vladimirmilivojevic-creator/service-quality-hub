"""Database tables.

Like in ServiceNow, all record types (incident, service request, problem, change) share one
``tickets`` table; type-specific columns are simply empty for the other types.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime

# Allowed values (kept as plain strings so they read well in the database and in exports).
TICKET_TYPES = ("incident", "request", "problem", "change")
TICKET_STATUSES = ("New", "In progress", "Pending", "Resolved", "Closed")
OPEN_STATUSES = ("New", "In progress", "Pending")
PROVIDER_KINDS = ("central", "plant_it", "external")
LIFECYCLE = ("pipeline", "live", "retired")
CRITICALITY = ("critical", "high", "medium", "low")
ROLES = ("sqm", "plant_lead", "management", "supplier")
CHANGE_TYPES = ("standard", "normal", "emergency")
CHANGE_OUTCOMES = ("successful", "failed", "rolled_back", "caused_incident")
PROBLEM_STATUSES = ("investigating", "known_error", "resolved")
IMPROVEMENT_STATUSES = ("proposed", "approved", "in_progress", "done", "rejected")
IMPROVEMENT_SOURCES = ("kpi_breach", "service_review", "problem", "idea")


class Plant(Base):
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String(64))
    products: Mapped[str] = mapped_column(String(200))


class Provider(Base):
    """Who delivers a service: the central IT provider, a plant IT team or an external vendor."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    short_name: Mapped[str] = mapped_column(String(20), unique=True)
    kind: Mapped[str] = mapped_column(String(10))  # PROVIDER_KINDS
    plant_id: Mapped[int | None] = mapped_column(ForeignKey("plants.id"))  # only for plant IT teams
    target_pct: Mapped[float] = mapped_column(Float)  # agreed resolution SLA compliance (OLA or contract)
    contract_ref: Mapped[str] = mapped_column(String(80))
    escalation_contact: Mapped[str] = mapped_column(String(120))

    plant: Mapped[Plant | None] = relationship(lazy="joined")


class Service(Base):
    """One entry of the service catalogue (and of the portfolio, via ``lifecycle``)."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text)
    service_type: Mapped[str] = mapped_column(String(10))  # "business" or "technical"
    owner_name: Mapped[str] = mapped_column(String(80))
    owner_email: Mapped[str] = mapped_column(String(120))
    # Central and external services name their provider; plant IT services use each plant's own team.
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"))
    delivered_by_plant_it: Mapped[bool] = mapped_column(Boolean, default=False)
    support_hours: Mapped[str] = mapped_column(String(10))  # key of domain.sla.CALENDARS
    criticality: Mapped[str] = mapped_column(String(10))
    lifecycle: Mapped[str] = mapped_column(String(10), default="live")
    categories: Mapped[str] = mapped_column(String(300))  # comma-separated ticket categories

    provider: Mapped[Provider | None] = relationship(lazy="joined")


class SlaTarget(Base):
    """SLA targets per priority. ``service_id`` empty = default policy; set = exception for one service."""

    __tablename__ = "sla_targets"
    __table_args__ = (UniqueConstraint("service_id", "priority"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"))
    priority: Mapped[int] = mapped_column(Integer)
    response_min: Mapped[int] = mapped_column(Integer)
    resolution_min: Mapped[int] = mapped_column(Integer)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    full_name: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(12))  # ROLES
    plant_id: Mapped[int | None] = mapped_column(ForeignKey("plants.id"))  # plant IT lead
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"))  # supplier login
    password_hash: Mapped[str] = mapped_column(String(100))


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(30), unique=True)  # INC-10234, ITSD-12 ...
    external_key: Mapped[str | None] = mapped_column(String(60), unique=True)  # key in the source tool
    type: Mapped[str] = mapped_column(String(10), index=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    priority: Mapped[int] = mapped_column(Integer)
    impact: Mapped[str | None] = mapped_column(String(6))
    urgency: Mapped[str | None] = mapped_column(String(6))
    status: Mapped[str] = mapped_column(String(12), index=True)
    category: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(12), default="seed")  # seed / simulated / jsm_import / manual

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    first_response_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    pending_since: Mapped[datetime | None] = mapped_column(UTCDateTime)
    paused_minutes: Mapped[int] = mapped_column(Integer, default=0)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)

    # SLA targets are frozen when the ticket is created, so later policy changes never rewrite history.
    response_target_min: Mapped[int | None] = mapped_column(Integer)
    resolution_target_min: Mapped[int | None] = mapped_column(Integer)
    # SLA results are written when the ticket gets its first response / is resolved.
    response_business_min: Mapped[int | None] = mapped_column(Integer)
    resolution_business_min: Mapped[int | None] = mapped_column(Integer)
    response_breached: Mapped[bool | None] = mapped_column(Boolean)
    resolution_breached: Mapped[bool | None] = mapped_column(Boolean)

    # Links: an incident can belong to a problem and can be caused by a change.
    problem_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"))
    caused_by_change_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"))

    # Change fields
    change_type: Mapped[str | None] = mapped_column(String(10))
    planned_start: Mapped[datetime | None] = mapped_column(UTCDateTime)
    planned_end: Mapped[datetime | None] = mapped_column(UTCDateTime)
    outcome: Mapped[str | None] = mapped_column(String(16))

    # Problem fields
    problem_status: Mapped[str | None] = mapped_column(String(14))
    root_cause: Mapped[str | None] = mapped_column(Text)
    workaround: Mapped[str | None] = mapped_column(Text)

    # Reference values from the source tool (kept for comparison, never used for KPIs)
    source_sla_note: Mapped[str | None] = mapped_column(String(200))

    plant: Mapped[Plant] = relationship(lazy="joined")
    service: Mapped[Service] = relationship(lazy="joined")
    provider: Mapped[Provider] = relationship(lazy="joined")


class Improvement(Base):
    """Continual improvement (CSI) register."""

    __tablename__ = "improvements"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(16))  # IMPROVEMENT_SOURCES
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"))
    plant_id: Mapped[int | None] = mapped_column(ForeignKey("plants.id"))
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"))
    owner: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(12), default="proposed")
    due_date: Mapped[date | None] = mapped_column(Date)
    expected_benefit: Mapped[str] = mapped_column(String(200), default="")
    kpi: Mapped[str | None] = mapped_column(String(40))
    kpi_baseline: Mapped[float | None] = mapped_column(Float)
    kpi_target: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    service: Mapped[Service | None] = relationship(lazy="joined")
    plant: Mapped[Plant | None] = relationship(lazy="joined")
    provider: Mapped[Provider | None] = relationship(lazy="joined")


class DemoState(Base):
    """The demo has its own clock. Every "now" in the app comes from here, never from the system clock."""

    __tablename__ = "demo_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    demo_now: Mapped[datetime] = mapped_column(UTCDateTime)
    simulated_days: Mapped[int] = mapped_column(Integer, default=0)
    ticket_counter: Mapped[int] = mapped_column(Integer, default=10000)
