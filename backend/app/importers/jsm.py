"""Import of Jira Service Management CSV exports (with pandas).

1. Read the file: encoding (UTF-8 with or without BOM, or Windows-1252 from Excel) and separator
   (comma, or semicolon from an Austrian/German Excel) are detected.
2. Map every row with the rules in ``jsm_mapping.py``; rows that cannot be mapped are skipped
   with their row number and the reason.
3. Upsert by issue key: importing the same file twice updates the tickets instead of duplicating them.

The SLA is always calculated by ServiceQualityHub's own engine, so tickets from JSM and from
other sources are measured the same way and the plants stay comparable.
"""

import io
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.importers import jsm_mapping as m
from app.models import Ticket
from app.schemas import ImportIssue
from app.services import Catalogue, freeze_targets, new_ticket, record_sla_results

OPEN = ("New", "In progress", "Pending")


class ImportFileError(ValueError):
    """The file as a whole cannot be imported (shown to the user as HTTP 422)."""


@dataclass
class MappedRow:
    row: int  # row number in the file (the header is row 1)
    key: str
    type: str
    plant_id: int
    service_id: int
    priority: int
    status: str
    created_at: datetime
    resolved_at: datetime | None
    first_response_at: datetime | None
    title: str
    category: str
    sla_note: str | None


@dataclass
class MappingResult:
    total_rows: int
    rows: list[MappedRow]
    skipped: list[ImportIssue]
    warnings: list[str]
    detected: dict[str, str]


def read_csv(content: bytes) -> pd.DataFrame:
    text = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if not text or not text.strip():
        raise ImportFileError("The file is empty")
    header = text.splitlines()[0]
    separator = max((",", ";", "\t"), key=header.count)
    try:
        frame = pd.read_csv(io.StringIO(text), sep=separator, dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        raise ImportFileError(f"The file is not a valid CSV: {error}") from error
    frame.columns = [str(c).strip() for c in frame.columns]
    missing = [c for c in m.REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ImportFileError(
            "This does not look like a Jira export. Missing columns: "
            + ", ".join(missing)
            + ". In Jira use: Filters -> Export -> Export CSV (all fields)."
        )
    return frame


def _columns(frame: pd.DataFrame, name: str) -> list[str]:
    """'Labels' plus its repeated copies 'Labels.1', 'Labels.2' ..."""
    pattern = re.compile(rf"^{re.escape(name)}(\.\d+)?$")
    return [c for c in frame.columns if pattern.match(c)]


def _values(row: pd.Series, columns: list[str]) -> list[str]:
    return [str(row[c]).strip() for c in columns if str(row[c]).strip()]


def parse_date(value: str, tz: ZoneInfo) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    for fmt in m.DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=tz).astimezone(UTC)
        except ValueError:
            continue
    raise ValueError(f"cannot read the date '{value}' (expected for example '21/Nov/26 3:45 PM')")


def _normalise(text: str) -> str:
    return text.strip().lower()


def map_rows(
    frame: pd.DataFrame, catalogue: Catalogue, timezone: str = m.DEFAULT_TIMEZONE, now: datetime | None = None
) -> MappingResult:
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ImportFileError(f"Unknown time zone '{timezone}'") from error

    first_response_tz = ZoneInfo(m.FIRST_RESPONSE_TIMEZONE)
    plant_aliases: dict[str, int] = {}
    for plant in catalogue.plants.values():
        for alias in (plant.code, plant.name, plant.name.removesuffix(" Works")):
            plant_aliases[_normalise(alias)] = plant.id
    service_ids = {_normalise(s.name): s.id for s in catalogue.services.values()}
    service_aliases = {alias: service_ids[_normalise(name)] for alias, name in m.SERVICE_ALIASES.items()}

    plant_columns = [(name, _columns(frame, name)) for name in m.PLANT_COLUMNS]
    service_columns = [c for name in m.SERVICE_COLUMNS for c in _columns(frame, name)]
    first_response_columns = [c for c in m.COLUMNS_FIRST_RESPONSE if c in frame.columns]
    sla_columns = [c for c in m.COLUMNS_JSM_SLA if c in frame.columns]
    has_request_type = m.COLUMN_REQUEST_TYPE in frame.columns
    has_resolved = m.COLUMN_RESOLVED in frame.columns

    rows: list[MappedRow] = []
    skipped: list[ImportIssue] = []
    plant_found_in: dict[str, int] = {}
    defaulted_priority = 0

    for index, row in frame.iterrows():
        number = int(index) + 2

        def skip(reason: str, number: int = number) -> None:
            skipped.append(ImportIssue(row=number, message=reason))

        key = str(row[m.COLUMN_KEY]).strip()
        if not key:
            skip("no issue key")
            continue
        issue_type = str(row[m.COLUMN_ISSUE_TYPE]).strip()
        ticket_type = m.ISSUE_TYPES.get(_normalise(issue_type))
        if ticket_type is None:
            skip(f"{key}: issue type '{issue_type}' is not imported")
            continue

        plant_id = None
        for column_name, columns in plant_columns:
            for value in _values(row, columns):
                plant_id = plant_aliases.get(_normalise(value))
                if plant_id:
                    plant_found_in[column_name] = plant_found_in.get(column_name, 0) + 1
                    break
            if plant_id:
                break
        if plant_id is None:
            skip(f"{key}: no plant found in Site, Components or Labels")
            continue

        request_type = str(row[m.COLUMN_REQUEST_TYPE]).strip() if has_request_type else ""
        service_id = None
        for value in _values(row, service_columns):
            service_id = service_aliases.get(_normalise(value)) or service_ids.get(_normalise(value))
            if service_id:
                break
        if service_id is None and m.REQUEST_TYPE_SERVICES.get(_normalise(request_type)):
            service_id = service_ids[_normalise(m.REQUEST_TYPE_SERVICES[_normalise(request_type)])]
        if service_id is None:
            skip(f"{key}: no service found (add a label such as 'erp', 'mes' or 'wan', or map the request type)")
            continue

        priority = m.PRIORITIES.get(_normalise(str(row[m.COLUMN_PRIORITY])))
        if priority is None:
            priority, defaulted_priority = 3, defaulted_priority + 1
        if ticket_type == "request":
            priority = max(priority, 3)  # service requests use P3 or P4

        try:
            created_at = parse_date(str(row[m.COLUMN_CREATED]), tz)
            resolved_at = parse_date(str(row[m.COLUMN_RESOLVED]), tz) if has_resolved else None
            first_response_at = next(
                (parse_date(str(row[c]), first_response_tz) for c in first_response_columns if str(row[c]).strip()),
                None,
            )
        except ValueError as error:
            skip(f"{key}: {error}")
            continue
        if created_at is None:
            skip(f"{key}: no Created date")
            continue

        raw_status = str(row[m.COLUMN_STATUS]).strip()
        status = m.STATUSES.get(_normalise(raw_status)) or ("Resolved" if resolved_at else "In progress")
        if status in OPEN:
            resolved_at = None  # reopened in JSM: the status wins over an old resolution date
        elif resolved_at is None:
            skip(f"{key}: status '{raw_status}' but no Resolved date")
            continue
        if resolved_at is not None and resolved_at < created_at:
            skip(f"{key}: resolved before it was created")
            continue
        if first_response_at is not None and (
            first_response_at < created_at or (resolved_at and first_response_at > resolved_at)
        ):
            first_response_at = None

        note = "; ".join(
            f"{c.removeprefix('Custom field (').rstrip(')')}: {row[c]}" for c in sla_columns if str(row[c]).strip()
        )
        rows.append(
            MappedRow(
                row=number,
                key=key,
                type=ticket_type,
                plant_id=plant_id,
                service_id=service_id,
                priority=priority,
                status=status,
                created_at=created_at,
                resolved_at=resolved_at,
                first_response_at=first_response_at,
                title=str(row[m.COLUMN_SUMMARY]).strip()[:200] or key,
                category=(request_type or issue_type.removeprefix("[System] "))[:60],
                sla_note=note[:200] or None,
            )
        )

    warnings = []
    if defaulted_priority:
        warnings.append(f"{defaulted_priority} rows had no known priority and were imported as P3.")
    if not first_response_columns:
        warnings.append(
            "The export has no first-response date, so the response SLA is not measured for these tickets "
            "(the resolution SLA is)."
        )
    warnings.append("Pending time is not part of a CSV export: the resolution SLA counts the full support time.")
    if now is not None:
        newer = sum(1 for r in rows if r.created_at > now)
        if newer:
            warnings.append(
                f"{newer} tickets are dated after the demo clock ({now:%d %b %Y}); "
                "they count in the KPIs of the month they belong to."
            )
    detected = {
        "separator/encoding": "detected automatically",
        "plant": ", ".join(f"{k} ({v} rows)" for k, v in plant_found_in.items()) or "not found",
        "service": "aliases in " + (", ".join(m.SERVICE_COLUMNS)) + (", request type" if has_request_type else ""),
        "first response": first_response_columns[0] if first_response_columns else "not in export",
        "JSM SLA fields (reference only)": ", ".join(sla_columns) or "not in export",
        "time zone of dates": timezone,
    }
    return MappingResult(len(frame), rows, skipped, warnings, detected)


async def upsert(db: AsyncSession, rows: list[MappedRow], catalogue: Catalogue) -> tuple[int, int]:
    """Create new tickets or update the ones imported before (matched by issue key)."""
    keys = [r.key for r in rows]
    existing = {
        t.external_key: t
        for t in (await db.scalars(select(Ticket).where(Ticket.external_key.in_(keys)))).unique().all()
    }
    created = updated = 0
    for r in rows:
        ticket = existing.get(r.key)
        if ticket is None:
            ticket = new_ticket(
                catalogue,
                key=r.key,
                external_key=r.key,
                ticket_type=r.type,
                plant_id=r.plant_id,
                service_id=r.service_id,
                priority=r.priority,
                category=r.category,
                title=r.title,
                created_at=r.created_at,
                source="jsm_import",
            )
            db.add(ticket)
            existing[r.key] = ticket
            created += 1
        else:
            routing_changed = (ticket.priority, ticket.service_id, ticket.plant_id) != (
                r.priority,
                r.service_id,
                r.plant_id,
            )
            ticket.priority, ticket.service_id, ticket.plant_id = r.priority, r.service_id, r.plant_id
            ticket.provider_id = catalogue.provider_for(catalogue.services[r.service_id], r.plant_id).id
            if routing_changed:
                freeze_targets(ticket, catalogue)  # re-prioritised in JSM: targets follow the new priority
            ticket.title, ticket.category, ticket.created_at = r.title, r.category, r.created_at
            updated += 1

        ticket.status = r.status
        ticket.first_response_at = r.first_response_at
        ticket.resolved_at = r.resolved_at
        ticket.closed_at = r.resolved_at if r.status == "Closed" else None
        ticket.pending_since = None
        ticket.source_sla_note = r.sla_note
        if r.type == "problem":
            ticket.problem_status = "resolved" if r.resolved_at else "investigating"
        record_sla_results(ticket, catalogue)
    await db.commit()
    return created, updated
