"""KPI definitions, targets and RAG (red / amber / green) rules.

The numbers themselves are counted in SQL (see ``app/analytics.py``); this module only holds
the definitions and the small rules that turn a number into a colour. All targets live here,
in one place, and the "How it works" page shows exactly these values.
"""

from dataclasses import dataclass
from statistics import median

GREEN, AMBER, RED, NO_DATA = "green", "amber", "red", "no_data"


@dataclass(frozen=True)
class KpiDefinition:
    key: str
    name: str
    unit: str  # "%", "h" or "tickets"
    higher_is_better: bool
    green: float  # threshold for green
    amber: float  # threshold for amber; beyond it is red
    definition: str
    formula: str
    target_text: str


KPIS: dict[str, KpiDefinition] = {
    k.key: k
    for k in [
        KpiDefinition(
            "sla_resolution",
            "SLA compliance – resolution",
            "%",
            True,
            95,
            90,
            "Share of tickets resolved within their resolution target (support hours, pauses excluded).",
            "resolved within target ÷ resolved in period × 100",
            "≥ 95 % green · 90–95 % amber · < 90 % red",
        ),
        KpiDefinition(
            "sla_response",
            "SLA compliance – response",
            "%",
            True,
            98,
            95,
            "Share of tickets that got a first response from IT within the response target.",
            "responded within target ÷ responded in period × 100",
            "≥ 98 % green · 95–98 % amber · < 95 % red",
        ),
        KpiDefinition(
            "mttr",
            "MTTR – incidents",
            "h",
            False,
            0,
            0,
            "Mean time to resolve incidents, counted in support hours. Median and per-priority values are shown too.",
            "sum of resolution times ÷ number of resolved incidents",
            "P1 ≤ 4 h and P2 ≤ 8 h green · up to 25 % over amber · more red",
        ),
        KpiDefinition(
            "backlog_over_30",
            "Backlog older than 30 days",
            "tickets",
            False,
            0,
            5,
            "Open incidents and requests at the end of the period that are older than 30 calendar days.",
            "count of open tickets with age > 30 days at period end",
            "0 green · 1–5 amber · > 5 red",
        ),
        KpiDefinition(
            "reopen_rate",
            "Reopen rate",
            "%",
            False,
            5,
            8,
            "Share of resolved tickets that the user reopened at least once (the fix did not hold).",
            "resolved tickets reopened at least once ÷ resolved × 100",
            "≤ 5 % green · 5–8 % amber · > 8 % red",
        ),
        KpiDefinition(
            "change_success",
            "Change success rate",
            "%",
            True,
            95,
            90,
            "Share of completed changes that worked. Failed, rolled back or incident-causing changes "
            "count as not successful.",
            "successful changes ÷ completed changes × 100",
            "≥ 95 % green · 90–95 % amber · < 90 % red",
        ),
    ]
}

# MTTR targets per priority, in hours (P3 / P4 are shown but have no MTTR target).
MTTR_TARGET_HOURS = {1: 4.0, 2: 8.0}
MTTR_AMBER_TOLERANCE = 1.25  # up to 25 % over target is amber

BACKLOG_AGE_BUCKETS = ("0–2 days", "3–7 days", "8–30 days", "> 30 days")


def rag(key: str, value: float | None) -> str:
    """Colour of a KPI value against its target. Boundaries belong to the better colour."""
    if value is None:
        return NO_DATA
    kpi = KPIS[key]
    if kpi.higher_is_better:
        return GREEN if value >= kpi.green else AMBER if value >= kpi.amber else RED
    return GREEN if value <= kpi.green else AMBER if value <= kpi.amber else RED


def mttr_rag(mttr_by_priority: dict[int, float | None]) -> str:
    """Green if P1 and P2 are within target; amber if at most 25 % over; otherwise red."""
    colours = []
    for priority, target in MTTR_TARGET_HOURS.items():
        value = mttr_by_priority.get(priority)
        if value is None:
            continue
        if value <= target:
            colours.append(GREEN)
        elif value <= target * MTTR_AMBER_TOLERANCE:
            colours.append(AMBER)
        else:
            colours.append(RED)
    if not colours:
        return NO_DATA
    return RED if RED in colours else AMBER if AMBER in colours else GREEN


def percent(part: int, whole: int) -> float | None:
    return round(part * 100 / whole, 1) if whole else None


def hours(minutes: list[int]) -> tuple[float | None, float | None]:
    """(average, median) of a list of minutes, in hours with one decimal."""
    if not minutes:
        return None, None
    return round(sum(minutes) / len(minutes) / 60, 1), round(median(minutes) / 60, 1)


def backlog_bucket(age_days: float) -> str:
    if age_days <= 2:
        return BACKLOG_AGE_BUCKETS[0]
    if age_days <= 7:
        return BACKLOG_AGE_BUCKETS[1]
    if age_days <= 30:
        return BACKLOG_AGE_BUCKETS[2]
    return BACKLOG_AGE_BUCKETS[3]


def change_vs(previous: float | None, current: float | None) -> float | None:
    """Difference to the previous period (percentage points or hours)."""
    if previous is None or current is None:
        return None
    return round(current - previous, 1)
