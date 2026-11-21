"""SLA engine: support-hours calendars, business time, due dates and SLA status.

Pure functions without a database, so every rule can be tested in isolation.

The rule in one sentence: the SLA clock only runs during the service's support hours,
in the plant's local time, and it stops while we wait for the user (status Pending).
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ONE_MINUTE = timedelta(minutes=1)
MAX_SEARCH_DAYS = 400  # a due date further away than this means a broken calendar


@dataclass(frozen=True)
class Calendar:
    """Weekly support hours. ``start is None`` means 24x7."""

    code: str
    label: str
    weekdays: frozenset[int]  # Monday = 0 ... Sunday = 6
    start: time | None = None
    end: time | None = None

    @property
    def is_24x7(self) -> bool:
        return self.start is None


CALENDARS: dict[str, Calendar] = {
    "24x7": Calendar("24x7", "24x7 (around the clock)", frozenset(range(7))),
    "shift": Calendar("shift", "Shift hours Mon–Fri 06:00–22:00", frozenset(range(5)), time(6), time(22)),
    "office": Calendar("office", "Office hours Mon–Fri 07:00–17:00", frozenset(range(5)), time(7), time(17)),
}

# --- Priority = impact x urgency (ITIL) -------------------------------------------------

LEVELS = ("high", "medium", "low")
PRIORITY_MATRIX: dict[tuple[str, str], int] = {
    ("high", "high"): 1,
    ("high", "medium"): 2,
    ("medium", "high"): 2,
    ("high", "low"): 3,
    ("medium", "medium"): 3,
    ("low", "high"): 3,
    ("medium", "low"): 4,
    ("low", "medium"): 4,
    ("low", "low"): 4,
}
PRIORITY_LABELS = {1: "P1 Critical", 2: "P2 High", 3: "P3 Medium", 4: "P4 Low"}
PRIORITY_EXAMPLES = {
    1: "Production line stopped or many users affected, no workaround",
    2: "Production impaired or a key function is down",
    3: "One user or one function affected, a workaround exists",
    4: "Minor issue or standard request",
}

# Default SLA policy in minutes: (first response, resolution). Services may have exceptions.
DEFAULT_SLA_POLICY: dict[int, tuple[int, int]] = {
    1: (15, 4 * 60),
    2: (30, 8 * 60),
    3: (2 * 60, 16 * 60),
    4: (8 * 60, 40 * 60),
}

AT_RISK_SHARE = 0.75  # an open ticket is "at risk" once 75% of the target is used


def priority_from(impact: str, urgency: str) -> int:
    return PRIORITY_MATRIX[(impact, urgency)]


# --- Business time -----------------------------------------------------------------------


def _window(day: date, calendar: Calendar, tz: ZoneInfo) -> tuple[datetime, datetime] | None:
    """Support window of one local day, or None if the service is closed that day."""
    if day.weekday() not in calendar.weekdays:
        return None
    assert calendar.start is not None and calendar.end is not None
    return datetime.combine(day, calendar.start, tz), datetime.combine(day, calendar.end, tz)


def _utc_span(start: datetime, end: datetime) -> timedelta:
    # Subtract in UTC: Python subtracts wall-clock times when both sides share a tzinfo,
    # which would be wrong on the days the clocks change.
    return end.astimezone(UTC) - start.astimezone(UTC)


def business_minutes_between(start: datetime, end: datetime, calendar: Calendar, tz: ZoneInfo) -> int:
    """Minutes between two moments that fall inside the support hours (rounded down)."""
    if end <= start:
        return 0
    if calendar.is_24x7:
        return _utc_span(start, end) // ONE_MINUTE

    total = timedelta()
    day = start.astimezone(tz).date()
    last_day = end.astimezone(tz).date()
    while day <= last_day:
        window = _window(day, calendar, tz)
        if window:
            span_start, span_end = max(start, window[0]), min(end, window[1])
            if span_end > span_start:
                total += _utc_span(span_start, span_end)
        day += timedelta(days=1)
    return total // ONE_MINUTE


def add_business_minutes(start: datetime, minutes: int, calendar: Calendar, tz: ZoneInfo) -> datetime:
    """The moment when ``minutes`` of support time have passed after ``start`` (the "due at")."""
    if calendar.is_24x7:
        return (start + timedelta(minutes=minutes)).astimezone(UTC)

    remaining = timedelta(minutes=minutes)
    day = start.astimezone(tz).date()
    for _ in range(MAX_SEARCH_DAYS):
        window = _window(day, calendar, tz)
        if window and window[1] > start:
            span_start = max(start, window[0])
            available = _utc_span(span_start, window[1])
            if remaining <= available:
                return span_start.astimezone(UTC) + remaining
            remaining -= available
        day += timedelta(days=1)
    raise ValueError(f"No support window found within {MAX_SEARCH_DAYS} days for calendar {calendar.code}")


# --- SLA results and live status ---------------------------------------------------------


def sla_status(elapsed_min: int | None, target_min: int | None, is_open: bool) -> str:
    """on_track / at_risk / breached for open tickets, met / breached for finished ones."""
    if elapsed_min is None or target_min is None:
        return "no_target"
    if not is_open:
        return "met" if elapsed_min <= target_min else "breached"  # exactly on target counts as met
    if elapsed_min > target_min:
        return "breached"
    if elapsed_min >= AT_RISK_SHARE * target_min:
        return "at_risk"
    return "on_track"


@dataclass(frozen=True)
class SlaMeasurement:
    """Measured SLA times (in support-hour minutes) and whether the targets were missed."""

    response_minutes: int | None
    resolution_minutes: int | None
    response_breached: bool | None
    resolution_breached: bool | None


def measure(
    *,
    created_at: datetime,
    first_response_at: datetime | None,
    resolved_at: datetime | None,
    paused_minutes: int,
    calendar: Calendar,
    tz: ZoneInfo,
    response_target_min: int | None,
    resolution_target_min: int | None,
) -> SlaMeasurement:
    """Measure a ticket once it has responded / resolved. Missing timestamps give ``None``."""
    response = resolution = None
    response_breached = resolution_breached = None
    if first_response_at is not None:
        response = business_minutes_between(created_at, first_response_at, calendar, tz)
        if response_target_min is not None:
            response_breached = response > response_target_min
    if resolved_at is not None:
        resolution = max(0, business_minutes_between(created_at, resolved_at, calendar, tz) - paused_minutes)
        if resolution_target_min is not None:
            resolution_breached = resolution > resolution_target_min
    return SlaMeasurement(response, resolution, response_breached, resolution_breached)


@dataclass(frozen=True)
class SlaClock:
    """Live view of an open ticket's SLA at a given moment (the demo clock's "now")."""

    response_elapsed: int | None
    resolution_elapsed: int
    response_status: str
    resolution_status: str
    response_due_at: datetime | None
    resolution_due_at: datetime | None


def live_clock(
    *,
    now: datetime,
    created_at: datetime,
    first_response_at: datetime | None,
    paused_minutes: int,
    pending_since: datetime | None,
    calendar: Calendar,
    tz: ZoneInfo,
    response_target_min: int | None,
    resolution_target_min: int | None,
) -> SlaClock:
    """Elapsed time, status and due dates for a ticket that is still open."""
    paused_now = paused_minutes
    if pending_since is not None:  # the clock is stopped right now
        paused_now += business_minutes_between(pending_since, now, calendar, tz)
    resolution_elapsed = max(0, business_minutes_between(created_at, now, calendar, tz) - paused_now)

    if first_response_at is None:
        response_elapsed = business_minutes_between(created_at, now, calendar, tz)
        response_status = sla_status(response_elapsed, response_target_min, is_open=True)
    else:
        response_elapsed = business_minutes_between(created_at, first_response_at, calendar, tz)
        response_status = sla_status(response_elapsed, response_target_min, is_open=False)

    response_due = add_business_minutes(created_at, response_target_min, calendar, tz) if response_target_min else None
    resolution_due = None
    if resolution_target_min is not None and pending_since is None:
        resolution_due = add_business_minutes(created_at, resolution_target_min + paused_now, calendar, tz)

    return SlaClock(
        response_elapsed=response_elapsed,
        resolution_elapsed=resolution_elapsed,
        response_status=response_status,
        resolution_status=sla_status(resolution_elapsed, resolution_target_min, is_open=True),
        response_due_at=response_due,
        resolution_due_at=resolution_due,
    )
