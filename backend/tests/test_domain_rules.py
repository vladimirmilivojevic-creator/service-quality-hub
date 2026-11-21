"""KPI colours, supplier scorecard rules and the problem candidate rule."""

from datetime import UTC, datetime, timedelta

import pytest

from app.config import normalize_database_url
from app.domain import kpis, suppliers
from app.domain.problems import IncidentRef, find_candidates


@pytest.mark.parametrize(
    ("key", "value", "colour"),
    [
        ("sla_resolution", 95.0, "green"),
        ("sla_resolution", 94.9, "amber"),
        ("sla_resolution", 90.0, "amber"),
        ("sla_resolution", 89.9, "red"),
        ("sla_response", 98.0, "green"),
        ("sla_response", 96.0, "amber"),
        ("reopen_rate", 5.0, "green"),
        ("reopen_rate", 8.0, "amber"),
        ("reopen_rate", 8.1, "red"),
        ("backlog_over_30", 0, "green"),
        ("backlog_over_30", 5, "amber"),
        ("backlog_over_30", 6, "red"),
        ("change_success", 90.0, "amber"),
        ("change_success", None, "no_data"),
    ],
)
def test_rag_boundaries_belong_to_the_better_colour(key, value, colour):
    assert kpis.rag(key, value) == colour


def test_mttr_colour_uses_p1_and_p2_targets():
    assert kpis.mttr_rag({1: 3.5, 2: 7.9, 3: 30.0}) == "green"
    assert kpis.mttr_rag({1: 4.8, 2: 7.0}) == "amber"  # 20 % over the 4 h target
    assert kpis.mttr_rag({1: 6.0, 2: 7.0}) == "red"
    assert kpis.mttr_rag({3: 12.0}) == "no_data"


def test_helpers():
    assert kpis.percent(19, 20) == 95.0
    assert kpis.percent(1, 0) is None
    assert kpis.hours([60, 120, 540]) == (4.0, 2.0)
    assert kpis.hours([]) == (None, None)
    assert [kpis.backlog_bucket(d) for d in (1, 5, 20, 31)] == list(kpis.BACKLOG_AGE_BUCKETS)
    assert kpis.change_vs(90.0, 95.5) == 5.5
    assert kpis.change_vs(None, 95.5) is None


def test_scorecard_rules():
    assert suppliers.scorecard_rag(97.0, 97.0) == "green"
    assert suppliers.scorecard_rag(93.0, 97.0) == "amber"
    assert suppliers.scorecard_rag(68.8, 97.0) == "red"
    assert suppliers.scorecard_rag(None, 95.0) == "no_data"
    assert suppliers.trend(90.0, 95.0) == "up"
    assert suppliers.trend(95.0, 90.0) == "down"
    assert suppliers.trend(95.0, 95.3) == "flat"
    assert suppliers.agreement_label("central") == "OLA"
    assert suppliers.agreement_label("external") == "Contract"


def _incident(i: int, days_ago: float, plant: int = 1, service: int = 2, category: str = "VPN") -> IncidentRef:
    now = datetime(2026, 11, 18, 9, tzinfo=UTC)
    return IncidentRef(i, f"INC-{i}", plant, service, category, "VPN drops", now - timedelta(days=days_ago))


def test_three_similar_incidents_in_14_days_make_a_candidate():
    now = datetime(2026, 11, 18, 9, tzinfo=UTC)
    incidents = [_incident(1, 1), _incident(2, 5), _incident(3, 13)]
    (candidate,) = find_candidates(incidents, now)
    assert candidate.count == 3 and candidate.category == "VPN"
    assert candidate.first_seen < candidate.last_seen


def test_no_candidate_when_too_old_or_different():
    now = datetime(2026, 11, 18, 9, tzinfo=UTC)
    assert find_candidates([_incident(1, 1), _incident(2, 5), _incident(3, 15)], now) == []
    assert find_candidates([_incident(1, 1), _incident(2, 5), _incident(3, 6, plant=2)], now) == []
    assert find_candidates([_incident(1, 1), _incident(2, 5), _incident(3, 6, category="Mailbox")], now) == []


def test_bigger_groups_come_first():
    now = datetime(2026, 11, 18, 9, tzinfo=UTC)
    small = [_incident(i, i) for i in (1, 2, 3)]
    big = [_incident(10 + i, i, service=7) for i in (1, 2, 3, 4)]
    result = find_candidates(small + big, now)
    assert [c.count for c in result] == [4, 3]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/db?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.eu-central-1.aws.neon.tech/db?ssl=require",
        ),
        ("postgres://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgresql+asyncpg://u:p@localhost:5432/db", "postgresql+asyncpg://u:p@localhost:5432/db"),
        ("sqlite+aiosqlite:///./x.db", "sqlite+aiosqlite:///./x.db"),
    ],
)
def test_database_url_is_normalised_for_asyncpg(url, expected):
    assert normalize_database_url(url) == expected
