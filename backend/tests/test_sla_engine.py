"""The SLA engine: business time in support hours, local time zones, pauses and status."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain import sla

VIENNA = ZoneInfo("Europe/Vienna")
SAO_PAULO = ZoneInfo("America/Sao_Paulo")
OFFICE = sla.CALENDARS["office"]  # Mon-Fri 07:00-17:00
SHIFT = sla.CALENDARS["shift"]  # Mon-Fri 06:00-22:00
ALWAYS = sla.CALENDARS["24x7"]


def local(tz: ZoneInfo, *args: int) -> datetime:
    return datetime(*args, tzinfo=tz)


def test_24x7_counts_every_minute():
    start = datetime(2026, 11, 20, 22, 0, tzinfo=UTC)
    assert sla.business_minutes_between(start, start + timedelta(hours=5), ALWAYS, VIENNA) == 300
    assert sla.add_business_minutes(start, 300, ALWAYS, VIENNA) == start + timedelta(hours=5)


def test_office_hours_skip_the_night():
    # Created Tuesday 16:00, resolved Wednesday 09:00 local: 1 h on Tuesday + 2 h on Wednesday.
    start, end = local(VIENNA, 2026, 11, 17, 16), local(VIENNA, 2026, 11, 18, 9)
    assert sla.business_minutes_between(start, end, OFFICE, VIENNA) == 180


def test_office_hours_skip_the_weekend():
    # Friday 16:30 -> Monday 07:30 local: 30 min on Friday + 30 min on Monday.
    start, end = local(VIENNA, 2026, 11, 20, 16, 30), local(VIENNA, 2026, 11, 23, 7, 30)
    assert sla.business_minutes_between(start, end, OFFICE, VIENNA) == 60


def test_due_date_moves_over_the_weekend():
    # A P3 response target of 2 h, ticket created Friday 16:00 -> due Monday 08:00 local.
    due = sla.add_business_minutes(local(VIENNA, 2026, 11, 20, 16), 120, OFFICE, VIENNA)
    assert due == local(VIENNA, 2026, 11, 23, 8).astimezone(UTC)


def test_ticket_created_outside_support_hours_starts_at_opening_time():
    due = sla.add_business_minutes(local(VIENNA, 2026, 11, 18, 23), 30, SHIFT, VIENNA)
    assert due == local(VIENNA, 2026, 11, 19, 6, 30).astimezone(UTC)


def test_spring_clock_change_24x7_counts_real_minutes():
    # 29 March 2026: clocks jump from 02:00 to 03:00 in Vienna. 01:30 -> 03:30 local is only 60 real minutes.
    start, end = local(VIENNA, 2026, 3, 29, 1, 30), local(VIENNA, 2026, 3, 29, 3, 30)
    assert sla.business_minutes_between(start, end, ALWAYS, VIENNA) == 60


def test_autumn_clock_change_24x7_counts_real_minutes():
    # 25 October 2026: clocks go back from 03:00 to 02:00. 00:00 -> 04:00 local is 5 real hours.
    start, end = local(VIENNA, 2026, 10, 25, 0), local(VIENNA, 2026, 10, 25, 4)
    assert sla.business_minutes_between(start, end, ALWAYS, VIENNA) == 300


def test_office_hours_around_clock_change_keep_local_opening_times():
    # Friday 27 March 16:00 (CET) -> Monday 30 March 08:00 (CEST): 1 h + 1 h, whatever the UTC offset.
    start, end = local(VIENNA, 2026, 3, 27, 16), local(VIENNA, 2026, 3, 30, 8)
    assert sla.business_minutes_between(start, end, OFFICE, VIENNA) == 120
    due = sla.add_business_minutes(start, 120, OFFICE, VIENNA)
    assert due == datetime(2026, 3, 30, 6, 0, tzinfo=UTC)  # 08:00 CEST


def test_brazil_plant_uses_its_own_local_time():
    # 07:00-17:00 in Sao Paulo is 10:00-20:00 UTC. A ticket at 09:00 UTC waits until 10:00 UTC.
    start = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
    assert sla.business_minutes_between(start, datetime(2026, 11, 18, 11, 0, tzinfo=UTC), OFFICE, SAO_PAULO) == 60
    assert sla.add_business_minutes(start, 30, OFFICE, SAO_PAULO) == datetime(2026, 11, 18, 10, 30, tzinfo=UTC)


def test_measure_subtracts_pending_time_from_resolution_only():
    start = local(VIENNA, 2026, 11, 17, 8)
    result = sla.measure(
        created_at=start,
        first_response_at=start + timedelta(minutes=20),
        resolved_at=start + timedelta(hours=6),
        paused_minutes=120,
        calendar=OFFICE,
        tz=VIENNA,
        response_target_min=30,
        resolution_target_min=240,
    )
    assert result.response_minutes == 20 and result.response_breached is False
    assert result.resolution_minutes == 240 and result.resolution_breached is False  # 360 - 120 paused


def test_exactly_on_target_is_met_one_minute_more_is_breached():
    start = local(VIENNA, 2026, 11, 17, 8)
    on_target = sla.measure(
        created_at=start,
        first_response_at=None,
        resolved_at=start + timedelta(minutes=240),
        paused_minutes=0,
        calendar=OFFICE,
        tz=VIENNA,
        response_target_min=15,
        resolution_target_min=240,
    )
    assert on_target.resolution_breached is False and on_target.response_minutes is None
    late = sla.measure(
        created_at=start,
        first_response_at=None,
        resolved_at=start + timedelta(minutes=241),
        paused_minutes=0,
        calendar=OFFICE,
        tz=VIENNA,
        response_target_min=15,
        resolution_target_min=240,
    )
    assert late.resolution_breached is True


@pytest.mark.parametrize(
    ("elapsed", "is_open", "expected"),
    [
        (10, True, "on_track"),
        (74, True, "on_track"),
        (75, True, "at_risk"),
        (100, True, "at_risk"),
        (101, True, "breached"),
        (100, False, "met"),
        (101, False, "breached"),
        (None, True, "no_target"),
    ],
)
def test_sla_status(elapsed, is_open, expected):
    assert sla.sla_status(elapsed, 100, is_open) == expected


def test_live_clock_stops_while_pending():
    created = local(VIENNA, 2026, 11, 17, 8)
    now = local(VIENNA, 2026, 11, 17, 12)
    running = sla.live_clock(
        now=now,
        created_at=created,
        first_response_at=created + timedelta(minutes=10),
        paused_minutes=0,
        pending_since=None,
        calendar=OFFICE,
        tz=VIENNA,
        response_target_min=30,
        resolution_target_min=240,
    )
    paused = sla.live_clock(
        now=now,
        created_at=created,
        first_response_at=created + timedelta(minutes=10),
        paused_minutes=0,
        pending_since=local(VIENNA, 2026, 11, 17, 10),
        calendar=OFFICE,
        tz=VIENNA,
        response_target_min=30,
        resolution_target_min=240,
    )
    assert running.resolution_elapsed == 240 and running.resolution_status == "at_risk"
    assert paused.resolution_elapsed == 120 and paused.resolution_status == "on_track"
    assert paused.resolution_due_at is None  # no due date while the clock is stopped
    assert running.response_status == "met"


@pytest.mark.parametrize(
    ("impact", "urgency", "priority"),
    [("high", "high", 1), ("high", "medium", 2), ("medium", "high", 2), ("medium", "medium", 3), ("low", "low", 4)],
)
def test_priority_matrix(impact, urgency, priority):
    assert sla.priority_from(impact, urgency) == priority


def test_add_and_between_agree_on_random_moments():
    start = local(VIENNA, 2026, 11, 13, 15, 47)
    for minutes in (1, 59, 600, 601, 2400, 4000):
        due = sla.add_business_minutes(start, minutes, SHIFT, VIENNA)
        assert sla.business_minutes_between(start, due, SHIFT, VIENNA) == minutes
