"""Supplier scorecard rules: how a provider's SLA result is judged against its agreement.

Internal providers (the central IT provider and each plant's IT team) are measured against an
OLA (operational level agreement). External vendors are measured against their contract.
The scorecard compares everyone on the same numbers, calculated by the same SLA engine.
"""

from app.domain.kpis import AMBER, GREEN, NO_DATA, RED

AMBER_BAND = 5.0  # up to 5 percentage points below target is amber
TREND_DEADBAND = 0.5  # smaller changes than this show as "flat"


def scorecard_rag(compliance_pct: float | None, target_pct: float) -> str:
    """Green at or above target, amber up to 5 points below, red further below."""
    if compliance_pct is None:
        return NO_DATA
    if compliance_pct >= target_pct:
        return GREEN
    if compliance_pct >= target_pct - AMBER_BAND:
        return AMBER
    return RED


def trend(previous: float | None, current: float | None) -> str:
    """'up', 'down' or 'flat' compared with the previous month."""
    if previous is None or current is None:
        return "flat"
    delta = current - previous
    if delta > TREND_DEADBAND:
        return "up"
    if delta < -TREND_DEADBAND:
        return "down"
    return "flat"


def agreement_label(kind: str) -> str:
    return "OLA" if kind in ("central", "plant_it") else "Contract"
