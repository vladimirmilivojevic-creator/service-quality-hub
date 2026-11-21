"""Problem candidates: recurring incidents that probably share one root cause.

Rule: at least 3 incidents with the same plant, service and category within the last 14 days,
that are not yet linked to a problem record.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

MIN_INCIDENTS = 3
WINDOW_DAYS = 14


@dataclass(frozen=True)
class IncidentRef:
    id: int
    key: str
    plant_id: int
    service_id: int
    category: str
    title: str
    created_at: datetime


@dataclass
class Candidate:
    plant_id: int
    service_id: int
    category: str
    incidents: list[IncidentRef] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.incidents)

    @property
    def first_seen(self) -> datetime:
        return min(i.created_at for i in self.incidents)

    @property
    def last_seen(self) -> datetime:
        return max(i.created_at for i in self.incidents)


def find_candidates(unlinked_incidents: list[IncidentRef], now: datetime) -> list[Candidate]:
    """Group recent unlinked incidents and keep the groups that reach the threshold."""
    since = now - timedelta(days=WINDOW_DAYS)
    groups: dict[tuple[int, int, str], Candidate] = defaultdict(lambda: Candidate(0, 0, ""))
    for incident in unlinked_incidents:
        if not since <= incident.created_at <= now:
            continue
        key = (incident.plant_id, incident.service_id, incident.category)
        group = groups[key]
        group.plant_id, group.service_id, group.category = key
        group.incidents.append(incident)

    candidates = [g for g in groups.values() if g.count >= MIN_INCIDENTS]
    for candidate in candidates:
        candidate.incidents.sort(key=lambda i: i.created_at)
    # Biggest groups first; for equal size the most recent one first.
    return sorted(candidates, key=lambda c: (-c.count, -c.last_seen.timestamp()))
