"""Deterministic demo data: about six months of tickets for five plants, with six built-in stories.

``random.Random(42)`` makes every run produce exactly the same data, so tests can check fixed numbers.

The stories (what the demo is meant to show):
1. AlpNet Carrier (WAN) misses its contract at Vale Verde in September and October -> red scorecard.
2. Innfeld: "MES terminal freezes at line 3" four times in ten days -> problem -> firmware change -> fixed.
3. Salzbach: Printwise label printers have a poor MTTR in September and a good one in October (spares on site).
4. A failed ERP release on a Friday evening causes three P2 incidents -> change success rate drops.
5. Illerau: old P4 requests older than 30 days -> backlog age turns amber.
6. Rhinval: Workplace tickets are often reopened -> improvement "resolve only after the user confirms".
"""

import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import catalogue_data as data
from app.domain import sla
from app.domain.problems import MIN_INCIDENTS, WINDOW_DAYS
from app.models import (
    DemoState,
    Improvement,
    Plant,
    Provider,
    Service,
    SlaTarget,
    Ticket,
    User,
)
from app.security import hash_password
from app.services import KEY_PREFIX, Catalogue, load_catalogue, new_ticket, record_sla_results

TITLES: dict[str, list[str]] = {
    "Login / authorisation": ["Cannot log in to ERP", "ERP role missing after transfer", "ERP session locked"],
    "Performance": ["System very slow at shift start", "Transactions time out", "Screens load slowly"],
    "Interface error": ["Booking not transferred to warehouse", "Interface job failed overnight"],
    "Printing from ERP": ["Delivery note does not print", "Production order print stuck in queue"],
    "Master data change": ["Change material master data", "New storage location needed"],
    "Terminal freeze": ["MES terminal frozen", "Terminal does not react to scan"],
    "Interface to ERP": ["Production confirmations missing in ERP", "Order not visible in MES"],
    "Machine data missing": ["No machine data from welding robot", "Counter values missing"],
    "Login": ["Badge login fails at terminal", "Operator cannot log in to MES"],
    "License": ["CAD licence not available", "Licence server unreachable"],
    "Data exchange": ["Drawing release not synchronised", "STEP export fails"],
    "Workstation graphics": ["Graphics driver crash in CAD", "3D model renders black"],
    "Mailbox": ["Mailbox full", "Emails not arriving", "Outlook keeps asking for password"],
    "Meetings": ["No audio in online meeting", "Meeting room screen not connecting"],
    "Calendar": ["Shared calendar not visible", "Meeting invitations missing"],
    "Shared mailbox access": ["Access to shared mailbox purchasing", "Add colleague to quality mailbox"],
    "Password reset": ["Password reset", "Account locked after holiday"],
    "New account": ["Account for new colleague", "Account for temporary worker"],
    "VPN": ["VPN does not connect", "VPN drops every few minutes"],
    "Permissions": ["Access to project folder", "Write permission for drawing archive"],
    "Wi-Fi coverage": ["No Wi-Fi in hall 4", "Wi-Fi weak at loading dock"],
    "Switch / port": ["Network port dead at workstation", "Switch in hall 2 restarts"],
    "Network outage": ["Network down in office building", "Assembly line without network"],
    "Line down": ["WAN line to data centre down", "Plant offline from central systems"],
    "Packet loss / latency": ["High latency to ERP", "Packet loss on WAN line"],
    "Bandwidth": ["WAN line saturated during backup", "Video calls break up"],
    "Hardware fault": ["Laptop does not start", "Monitor flickers", "Docking station not working"],
    "Software install": ["Install PDF editor", "Install measurement software"],
    "New device": ["New laptop for new colleague", "Replace old PC"],
    "Peripheral": ["Keyboard not working", "Headset not recognised"],
    "Label printer": ["Label printer prints blank labels", "Label printer offline", "Labels misaligned"],
    "Office printer": ["Printer jams", "Printer offline"],
    "Toner / supplies": ["Toner empty", "Label rolls needed"],
    "Print queue": ["Print jobs stuck", "Wrong default printer"],
    "Scanner hardware": ["Scanner trigger broken", "Scanner display cracked"],
    "Battery": ["Scanner battery empty after two hours", "Battery does not charge"],
    "App / MDM": ["Warehouse app crashes", "Scanner not enrolled in MDM"],
    "Wi-Fi roaming": ["Scanner loses connection between aisles"],
    "Restore request": ["Restore deleted folder", "Restore file from last week"],
    "Backup failure": ["Nightly backup failed on file server", "Backup job missed"],
}

CHANGE_TITLES = {
    "ERP – production & logistics": ["ERP transport: new report", "ERP patch level update", "ERP authorisation update"],
    "MES – shop-floor data collection": ["MES terminal software update", "New MES workstation at line"],
    "PLM / CAD engineering": ["CAD client update", "PLM server patching"],
    "Email & collaboration": ["Mail gateway rule update", "Meeting room device update"],
    "Identity & access (accounts, VPN)": ["VPN client rollout", "Password policy update"],
    "Plant network (LAN & Wi-Fi)": ["Switch firmware update", "New Wi-Fi access points"],
    "WAN connectivity": ["Carrier router maintenance", "WAN bandwidth upgrade"],
    "Workplace (PCs & laptops)": ["Monthly Windows patches", "Standard software package update"],
    "Printing & label printing": ["Printer driver update", "Label template change"],
    "Warehouse scanners & MDM": ["MDM profile update", "Warehouse app release"],
    "Backup & restore": ["Backup schedule change", "Backup agent update"],
}
CHANGE_WEIGHTS = {
    "ERP – production & logistics": 3,
    "MES – shop-floor data collection": 2,
    "PLM / CAD engineering": 1,
    "Email & collaboration": 1,
    "Identity & access (accounts, VPN)": 1,
    "Plant network (LAN & Wi-Fi)": 2,
    "WAN connectivity": 1,
    "Workplace (PCs & laptops)": 4,
    "Printing & label printing": 1,
    "Warehouse scanners & MDM": 1,
    "Backup & restore": 1,
}
CHANGES_PER_MONTH = 12
WORKDAYS_PER_MONTH = 21.7
AUTO_CLOSE_DAYS = (2, 3, 5)  # users confirm the fix, then the ticket closes


@dataclass(frozen=True)
class Quality:
    """How well a provider performs at a plant in a given month (drives the generated SLA results)."""

    response_breach: float = 0.015
    resolution_breach: float = 0.03
    fraction: tuple[float, float] = (0.1, 0.85)  # resolution time as a share of the target
    reopen: float = 0.025
    reopen_every: int = 0  # if set: exactly every n-th ticket is reopened (keeps a story stable)


def story_quality(plant_code: str, provider_short: str, service_name: str, when: datetime) -> Quality:
    month = when.month
    if provider_short == "ALPNET" and plant_code == "VVD" and month in (9, 10):
        return Quality(response_breach=0.1, resolution_breach=0.4, fraction=(0.5, 1.3))  # story 1
    if provider_short == "ALPNET" and plant_code == "VVD" and month == 11:
        return Quality(resolution_breach=0.12)
    if provider_short == "PRINTWISE" and plant_code == "SAL" and month == 9 and when.day <= 20:
        return Quality(resolution_breach=0.3, fraction=(0.6, 1.6))  # story 3, before the spare printers
    if provider_short == "PRINTWISE" and plant_code == "SAL" and month in (9, 10, 11):
        return Quality(resolution_breach=0.0, fraction=(0.05, 0.25))  # story 3, after: a spare printer is swapped in
    if plant_code == "RHV" and service_name.startswith("Workplace"):
        return Quality(reopen_every=7) if month <= 10 else Quality(reopen=0.02)  # story 6
    if provider_short == "IT-VVD" and month == 10:
        return Quality(resolution_breach=0.08)
    return Quality()


def _weighted(rng: random.Random, items: list, weights: list):
    return rng.choices(items, weights=weights, k=1)[0]


class DemoGenerator:
    """Creates ticket objects for one or more days. Shared by the seed and the "Simulate next day" button."""

    def __init__(self, catalogue: Catalogue, rng: random.Random, now: datetime):
        self.cat = catalogue
        self.rng = rng
        self.now = now
        self.tickets: list[Ticket] = []
        # (plant, service, category) -> creation times of unlinked random incidents, so that random noise
        # alone never forms a problem candidate; candidates in the demo come from the stories.
        self.recent_incidents: dict[tuple[int, int, str], list[datetime]] = defaultdict(list)
        self.live_services = [s for s in catalogue.services.values() if s.lifecycle == "live"]
        self.service_by_name = {s.name: s for s in catalogue.services.values()}
        self.plant_by_code = {p.code: p for p in catalogue.plants.values()}
        self.weights = {s.id: w for s, w in self._volume_weights()}
        self.story_counter = 0

    def _volume_weights(self):
        volume = {row[0]: row[9] for row in data.SERVICES}
        return [(s, volume[s.name]) for s in self.live_services]

    # --- random tickets -----------------------------------------------------------------

    def random_created_at(self, day: date, tz: ZoneInfo, weekend: bool) -> datetime:
        if weekend or self.rng.random() < 0.1:  # some tickets come from the night shift
            minute = self.rng.randint(0, 24 * 60 - 1)
        else:
            minute = self.rng.randint(6 * 60 + 30, 17 * 60 + 30)
        local = datetime.combine(day, time(minute // 60, minute % 60), tz)
        return local.astimezone(UTC)

    def _pick_category(self, plant: Plant, service: Service, created: datetime) -> str | None:
        categories = service.categories.split(",")
        for _ in range(6):
            category = self.rng.choice(categories)
            if category in data.REQUEST_CATEGORIES:
                return category
            bucket = self.recent_incidents[(plant.id, service.id, category)]
            recent = [t for t in bucket if created - t < timedelta(days=WINDOW_DAYS)]
            if len(recent) < MIN_INCIDENTS - 1:
                return category
        return None

    def random_ticket(self, plant: Plant, created: datetime, source: str, weekend: bool = False) -> Ticket | None:
        services = self.live_services
        if weekend:
            services = [s for s in services if s.support_hours == "24x7"]
        service = _weighted(self.rng, services, [self.weights[s.id] for s in services])
        category = self._pick_category(plant, service, created)
        if category is None:
            return None
        ticket_type = "request" if category in data.REQUEST_CATEGORIES else "incident"
        if ticket_type == "request":
            priority = _weighted(self.rng, [3, 4], [40, 60])
        elif service.criticality in ("critical", "high"):
            priority = _weighted(self.rng, [1, 2, 3, 4], [3, 14, 55, 28])
        else:  # a calendar or a single laptop never stops a production line: no P1
            priority = _weighted(self.rng, [2, 3, 4], [6, 56, 38])
        impact, urgency = self.rng.choice([cell for cell, p in sla.PRIORITY_MATRIX.items() if p == priority])
        ticket = new_ticket(
            self.cat,
            key="",
            ticket_type=ticket_type,
            plant_id=plant.id,
            service_id=service.id,
            priority=priority,
            category=category,
            title=self.rng.choice(TITLES[category]),
            created_at=created,
            source=source,
            impact=impact,
            urgency=urgency,
        )
        if ticket_type == "incident":
            self.recent_incidents[(plant.id, service.id, category)].append(created)
        self.play_out(ticket)
        self.tickets.append(ticket)
        return ticket

    def play_out(self, ticket: Ticket, quality: Quality | None = None, reopened: bool | None = None) -> None:
        """Decide when IT responds and resolves, then cut everything off at the demo clock's "now"."""
        rng = self.rng
        calendar, tz = self.cat.clock_for(ticket)
        if quality is None:
            plant = self.cat.plants[ticket.plant_id]
            provider = self.cat.providers[ticket.provider_id]
            service = self.cat.services[ticket.service_id]
            quality = story_quality(plant.code, provider.short_name, service.name, ticket.created_at)
        response_target, resolution_target = ticket.response_target_min, ticket.resolution_target_min
        assert response_target is not None and resolution_target is not None

        if rng.random() < quality.response_breach:
            response = int(response_target * rng.uniform(1.05, 2.0))
        else:
            response = max(1, int(response_target * rng.uniform(0.05, 0.7)))
        fraction = rng.uniform(*quality.fraction)
        if rng.random() < quality.resolution_breach:
            fraction = rng.uniform(1.05, 2.5)
        resolution = max(response + 1, int(resolution_target * fraction))
        paused = rng.randint(30, 480) if rng.random() < 0.12 else 0
        if reopened is None and quality.reopen_every:
            self.story_counter += 1
            reopened = self.story_counter % quality.reopen_every == 0
        elif reopened is None:
            reopened = rng.random() < quality.reopen

        first_response_at = sla.add_business_minutes(ticket.created_at, response, calendar, tz)
        resolved_at = sla.add_business_minutes(ticket.created_at, resolution + paused, calendar, tz)
        self.apply_timeline(ticket, first_response_at, resolved_at, paused, reopened)

    def apply_timeline(
        self, ticket: Ticket, first_response_at: datetime, resolved_at: datetime, paused: int, reopened: bool
    ) -> None:
        now = self.now
        ticket.first_response_at = first_response_at if first_response_at <= now else None
        if resolved_at <= now:
            ticket.resolved_at = resolved_at
            ticket.paused_minutes = paused
            ticket.reopen_count = 1 if reopened else 0
            closed_at = resolved_at + timedelta(days=self.rng.choice(AUTO_CLOSE_DAYS))
            if closed_at <= now:
                ticket.status, ticket.closed_at = "Closed", closed_at
            else:
                ticket.status = "Resolved"
        elif ticket.first_response_at is None:
            ticket.status = "New"
        elif self.rng.random() < 0.12:
            ticket.status = "Pending"
            ticket.pending_since = max(ticket.first_response_at, now - timedelta(hours=self.rng.randint(1, 20)))
        else:
            ticket.status = "In progress"
        record_sla_results(ticket, self.cat)

    # --- changes --------------------------------------------------------------------------

    def random_change(self, plant: Plant, day: date, source: str, outcome: str | None = None) -> Ticket:
        rng = self.rng
        names = list(CHANGE_WEIGHTS)
        service = self.service_by_name[_weighted(rng, names, [CHANGE_WEIGHTS[n] for n in names])]
        change_type = _weighted(rng, ["standard", "normal", "emergency"], [55, 40, 5])
        tz = ZoneInfo(plant.timezone)
        if change_type == "normal":
            start_local = datetime.combine(day, time(18, 0), tz)  # agreed change window after the day shift
            created = start_local - timedelta(days=rng.randint(3, 10))
        elif change_type == "standard":
            start_local = datetime.combine(day, time(rng.randint(9, 15), 0), tz)
            created = start_local - timedelta(days=1)
        else:
            start_local = datetime.combine(day, time(rng.randint(7, 20), 0), tz)
            created = start_local - timedelta(hours=2)
        start = start_local.astimezone(UTC)
        return self.make_change(
            plant=plant,
            service=service,
            title=rng.choice(CHANGE_TITLES[service.name]),
            change_type=change_type,
            created=created.astimezone(UTC),
            start=start,
            end=start + timedelta(hours=rng.randint(1, 3)),
            source=source,
            outcome=outcome,
        )

    def make_change(
        self,
        *,
        plant: Plant,
        service: Service,
        title: str,
        change_type: str,
        created: datetime,
        start: datetime,
        end: datetime,
        source: str,
        outcome: str | None = None,
    ) -> Ticket:
        change = new_ticket(
            self.cat,
            key="",
            ticket_type="change",
            plant_id=plant.id,
            service_id=service.id,
            priority=3,
            category=change_type.capitalize() + " change",
            title=title,
            created_at=created,
            source=source,
        )
        change.change_type, change.planned_start, change.planned_end = change_type, start, end
        if end <= self.now:
            change.outcome = outcome or _weighted(
                self.rng,
                ["successful", "failed", "rolled_back", "caused_incident"],
                [975, 8, 10, 7],
            )
            change.status, change.resolved_at, change.closed_at = "Closed", end, end + timedelta(hours=1)
        else:
            change.status = "New"  # scheduled
        self.tickets.append(change)
        return change

    def make_problem(
        self,
        *,
        plant: Plant,
        service: Service,
        title: str,
        created: datetime,
        status: str,
        root_cause: str | None,
        workaround: str | None,
        resolved: datetime | None = None,
    ) -> Ticket:
        problem = new_ticket(
            self.cat,
            key="",
            ticket_type="problem",
            plant_id=plant.id,
            service_id=service.id,
            priority=2,
            category="Problem",
            title=title,
            created_at=created,
            source="seed",
        )
        problem.problem_status, problem.root_cause, problem.workaround = status, root_cause, workaround
        problem.first_response_at = created
        if status == "resolved" and resolved is not None:
            problem.status, problem.resolved_at, problem.closed_at = "Closed", resolved, resolved
        else:
            problem.status = "In progress"
        self.tickets.append(problem)
        return problem

    def story_incident(
        self,
        plant: Plant,
        service: Service,
        category: str,
        title: str,
        local: datetime,
        priority: int = 3,
        quality: Quality | None = None,
    ) -> Ticket:
        impact, urgency = next(cell for cell, p in sla.PRIORITY_MATRIX.items() if p == priority)
        ticket = new_ticket(
            self.cat,
            key="",
            ticket_type="incident",
            plant_id=plant.id,
            service_id=service.id,
            priority=priority,
            category=category,
            title=title,
            created_at=local.astimezone(UTC),
            source="seed",
            impact=impact,
            urgency=urgency,
        )
        self.play_out(ticket, quality=quality or Quality(response_breach=0, resolution_breach=0), reopened=False)
        self.tickets.append(ticket)
        return ticket


def _local(plant: Plant, year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(plant.timezone))


async def create_master_data(db: AsyncSession) -> Catalogue:
    plants = {
        code: Plant(code=code, name=name, country=country, timezone=tz, products=products)
        for code, name, country, tz, products, _ in data.PLANTS
    }
    db.add_all(plants.values())
    await db.flush()

    providers = {}
    for name, short, kind, plant_code, target, contract, escalation in data.PROVIDERS:
        providers[short] = Provider(
            name=name,
            short_name=short,
            kind=kind,
            plant_id=plants[plant_code].id if plant_code else None,
            target_pct=target,
            contract_ref=contract,
            escalation_contact=escalation,
        )
    db.add_all(providers.values())
    await db.flush()

    services = {}
    for name, description, stype, owner, provider, hours, crit, lifecycle, categories, _ in data.SERVICES:
        services[name] = Service(
            name=name,
            description=description,
            service_type=stype,
            owner_name=owner,
            owner_email=owner.lower().replace(" ", ".") + "@valdora.example",
            provider_id=providers[provider].id if provider else None,
            delivered_by_plant_it=provider is None,
            support_hours=hours,
            criticality=crit,
            lifecycle=lifecycle,
            categories=",".join(categories),
        )
    db.add_all(services.values())
    await db.flush()

    targets = [
        SlaTarget(service_id=None, priority=p, response_min=r, resolution_min=s)
        for p, (r, s) in sla.DEFAULT_SLA_POLICY.items()
    ]
    for service_name, exceptions in data.SLA_EXCEPTIONS.items():
        for priority, (response, resolution) in exceptions.items():
            targets.append(
                SlaTarget(
                    service_id=services[service_name].id,
                    priority=priority,
                    response_min=response,
                    resolution_min=resolution,
                )
            )
    db.add_all(targets)

    password_hash = hash_password(data.DEMO_PASSWORD)
    for email, name, title, role, plant_code, provider in data.USERS:
        db.add(
            User(
                email=email,
                full_name=name,
                title=title,
                role=role,
                plant_id=plants[plant_code].id if plant_code else None,
                provider_id=providers[provider].id if provider else None,
                password_hash=password_hash,
            )
        )
    await db.flush()

    return Catalogue(
        plants={p.id: p for p in plants.values()},
        services={s.id: s for s in services.values()},
        providers={p.id: p for p in providers.values()},
        policy={(t.service_id, t.priority): (t.response_min, t.resolution_min) for t in targets},
    )


def generate_history(gen: DemoGenerator) -> None:
    """Random everyday tickets and changes from HISTORY_START until the demo clock."""
    rng = gen.rng
    for code, *_rest, monthly_volume in data.PLANTS:
        plant = gen.plant_by_code[code]
        tz = ZoneInfo(plant.timezone)
        per_workday = monthly_volume / WORKDAYS_PER_MONTH
        day = data.HISTORY_START.date()
        while day <= gen.now.date():
            weekend = day.weekday() >= 5
            expected = per_workday * (0.08 if weekend else 1.0)
            count = max(0, round(rng.gauss(expected, expected * 0.3)))
            for _ in range(count):
                created = gen.random_created_at(day, tz, weekend)
                if created < gen.now:
                    gen.random_ticket(plant, created, "seed", weekend)
            if not weekend and rng.random() < CHANGES_PER_MONTH / WORKDAYS_PER_MONTH:
                gen.random_change(plant, day, "seed")
            day += timedelta(days=1)


def generate_stories(gen: DemoGenerator) -> dict[str, list]:
    """The six stories. Returns links that need database ids (set after the first flush)."""
    p = gen.plant_by_code
    s = gen.service_by_name
    links: dict[str, list] = defaultdict(list)

    # Story 2 - Innfeld: MES terminal freezes at line 3 -> problem -> firmware change -> no more freezes.
    inn, mes = p["INN"], s["MES – shop-floor data collection"]
    for month, day_, hour in [(7, 14, 7), (7, 28, 13)]:
        gen.story_incident(
            inn, mes, "Terminal freeze", "MES terminal at line 3 frozen", _local(inn, 2026, month, day_, hour), 2
        )
    mes_incidents = [
        gen.story_incident(inn, mes, "Terminal freeze", "MES terminal at line 3 frozen", _local(inn, 2026, 8, d, h), 2)
        for d, h in [(3, 6), (5, 14), (7, 22), (11, 9)]
    ]
    mes_problem = gen.make_problem(
        plant=inn,
        service=mes,
        title="Recurring MES terminal freezes at line 3",
        created=_local(inn, 2026, 8, 12, 10).astimezone(UTC),
        status="resolved",
        root_cause="Terminal firmware 4.2 leaks memory after about 72 hours of uptime.",
        workaround="Restart the terminal at every shift change.",
        resolved=_local(inn, 2026, 8, 20, 9).astimezone(UTC),
    )
    gen.make_change(
        plant=inn,
        service=mes,
        title="Firmware update MES terminals line 3 (4.2 -> 4.3)",
        change_type="normal",
        created=_local(inn, 2026, 8, 13, 11).astimezone(UTC),
        start=_local(inn, 2026, 8, 19, 18).astimezone(UTC),
        end=_local(inn, 2026, 8, 19, 20).astimezone(UTC),
        source="seed",
        outcome="successful",
    )
    links["problem:" + mes_problem.title] = [mes_problem, mes_incidents]

    # Story 1 - Vale Verde: the WAN carrier misses its contract for two months.
    vvd, wan = p["VVD"], s["WAN connectivity"]
    poor_wan = Quality(response_breach=0.1, resolution_breach=0.45, fraction=(0.5, 1.3))
    wan_incidents = []
    for month, days in [(9, [2, 5, 9, 12, 16, 19, 23, 26, 29]), (10, [1, 6, 9, 13, 16, 21, 24, 28])]:
        for d in days:
            category = gen.rng.choice(["Line down", "Packet loss / latency"])
            title = "WAN line to data centre down" if category == "Line down" else "High latency to ERP from Vale Verde"
            wan_incidents.append(
                gen.story_incident(
                    vvd, wan, category, title, _local(vvd, 2026, month, d, gen.rng.randint(7, 18)), 2, poor_wan
                )
            )
    wan_problem = gen.make_problem(
        plant=vvd,
        service=wan,
        title="Unstable WAN line Vale Verde – carrier backbone",
        created=_local(vvd, 2026, 9, 20, 10).astimezone(UTC),
        status="known_error",
        root_cause="Overloaded carrier backbone segment between Vale Verde and the data centre.",
        workaround="Automatic failover to the LTE backup line; MES traffic is prioritised.",
    )
    links["problem:" + wan_problem.title] = [wan_problem, wan_incidents]

    # Story 3 - Salzbach: label printers lose their network settings after power cuts (September).
    sal, printing = p["SAL"], s["Printing & label printing"]
    poor_print = Quality(resolution_breach=0.4, fraction=(0.7, 1.6))
    printer_incidents = [
        gen.story_incident(
            sal,
            printing,
            "Label printer",
            "Label printer at shipping offline",
            _local(sal, 2026, 9, d, h),
            3,
            poor_print,
        )
        for d, h in [(1, 8), (3, 10), (7, 15), (9, 7), (11, 13), (14, 9), (16, 11)]
    ]
    printer_problem = gen.make_problem(
        plant=sal,
        service=printing,
        title="Label printers lose network settings after power cuts",
        created=_local(sal, 2026, 9, 18, 9).astimezone(UTC),
        status="resolved",
        root_cause="Printers had no DHCP reservation and fell back to a default address after a power cut.",
        workaround="Swap in a spare printer from the shift store room.",
        resolved=_local(sal, 2026, 9, 30, 15).astimezone(UTC),
    )
    links["problem:" + printer_problem.title] = [printer_problem, printer_incidents]

    # Story 4 - a failed ERP release on a Friday evening, three P2 incidents on Monday morning.
    erp = s["ERP – production & logistics"]
    erp_change = gen.make_change(
        plant=inn,
        service=erp,
        title="ERP release 26.10 – logistics module (all plants)",
        change_type="normal",
        created=_local(inn, 2026, 10, 5, 10).astimezone(UTC),
        start=_local(inn, 2026, 10, 9, 18).astimezone(UTC),
        end=_local(inn, 2026, 10, 9, 21).astimezone(UTC),
        source="seed",
        outcome="caused_incident",
    )
    erp_incidents = [
        gen.story_incident(
            p[code],
            erp,
            "Interface error",
            "Goods receipt booking fails after ERP release",
            _local(p[code], 2026, 10, 12, h, m),
            2,
        )
        for code, h, m in [("INN", 6, 15), ("SAL", 6, 40), ("ILL", 7, 5)]
    ]
    erp_problem = gen.make_problem(
        plant=inn,
        service=erp,
        title="ERP release 26.10 broke goods receipt booking",
        created=_local(inn, 2026, 10, 12, 9).astimezone(UTC),
        status="resolved",
        root_cause=(
            "Untested interface change to the warehouse module; the release went live on a Friday evening "
            "without a key-user test."
        ),
        workaround="Book goods receipts manually in the warehouse transaction until the fix.",
        resolved=_local(inn, 2026, 10, 14, 12).astimezone(UTC),
    )
    links["problem:" + erp_problem.title] = [erp_problem, erp_incidents]
    links["caused_by:" + erp_change.title] = [erp_change, erp_incidents]
    # More unsuccessful changes in October, so the change success rate drops below target.
    for code, d, outcome in [("RHV", 14, "rolled_back"), ("ILL", 20, "failed"), ("VVD", 22, "rolled_back")]:
        gen.random_change(p[code], date(2026, 10, d), "seed", outcome=outcome)

    # Story 5 - Illerau: P4 requests waiting for budget approval since September.
    ill, workplace = p["ILL"], s["Workplace (PCs & laptops)"]
    for d, title in [
        (14, "CAD monitor for engineering (budget approval pending)"),
        (17, "Second screen for planning office"),
        (22, "Laptop replacement for maintenance team"),
        (25, "Docking stations for meeting rooms"),
    ]:
        created = _local(ill, 2026, 9, d, 9).astimezone(UTC)
        request = new_ticket(
            gen.cat,
            key="",
            ticket_type="request",
            plant_id=ill.id,
            service_id=workplace.id,
            priority=4,
            category="New device",
            title=title,
            created_at=created,
            source="seed",
            impact="low",
            urgency="low",
        )
        calendar, tz = gen.cat.clock_for(request)
        request.first_response_at = sla.add_business_minutes(created, 90, calendar, tz)
        request.status = "In progress"
        record_sla_results(request, gen.cat)
        gen.tickets.append(request)

    # Open problem candidates right now (recent, not yet linked to a problem).
    rhv, identity = p["RHV"], s["Identity & access (accounts, VPN)"]
    for d, h in [(9, 8), (12, 10), (16, 14)]:
        gen.story_incident(
            rhv, identity, "VPN", "VPN drops after the latest Windows update", _local(rhv, 2026, 11, d, h), 3
        )
    scanners = s["Warehouse scanners & MDM"]
    for d, h in [(6, 7), (10, 9), (13, 6), (17, 8)]:
        gen.story_incident(
            vvd, scanners, "Battery", "Scanner battery drains in the cold store", _local(vvd, 2026, 11, d, h), 3
        )

    return links


def improvements(gen: DemoGenerator) -> list[Improvement]:
    p, s = gen.plant_by_code, gen.service_by_name
    provider = {pr.short_name: pr for pr in gen.cat.providers.values()}
    rows = [
        # title, description, source, service, plant, provider, owner, status, due, benefit,
        # kpi, baseline, target, created, done
        (
            "Quarterly service review with AlpNet, second line and named escalation contact for Vale Verde",
            "AlpNet missed the WAN contract at Vale Verde in September and October. Agree a second line (LTE backup), "
            "a named escalation contact and a quarterly review with an action list.",
            "service_review",
            "WAN connectivity",
            "VVD",
            "ALPNET",
            "Mara Lindner",
            "in_progress",
            date(2026, 12, 15),
            "WAN compliance back to the 97 % contract target",
            "sla_resolution",
            68.8,
            97.0,
            date(2026, 10, 20),
            None,
        ),
        (
            "Spare label printers on site (Salzbach)",
            "Keep two pre-configured spare label printers in the shift store room, so the line can swap "
            "them in minutes.",
            "problem",
            "Printing & label printing",
            "SAL",
            "PRINTWISE",
            "Eva Lindner",
            "done",
            date(2026, 9, 30),
            "MTTR for label printers below 4 h",
            "mttr",
            18.3,
            4.0,
            date(2026, 9, 18),
            date(2026, 9, 30),
        ),
        (
            "No ERP changes on Fridays; freeze 3 working days before month-end closing",
            "After the failed ERP release on Friday 9 October: ERP releases only Tuesday to Thursday, "
            "and a change freeze "
            "before month-end closing. Key-user test is mandatory.",
            "kpi_breach",
            "ERP – production & logistics",
            None,
            "VIS",
            "Mara Lindner",
            "approved",
            date(2026, 11, 30),
            "Change success rate back above 95 %",
            "change_success",
            90.0,
            95.0,
            date(2026, 10, 15),
            None,
        ),
        (
            "Resolve only after the user confirms (Rhinval Workplace)",
            "Workplace tickets at Rhinval are often reopened. The technician sets 'Resolved' only after "
            "a short call or "
            "confirmation from the user.",
            "kpi_breach",
            "Workplace (PCs & laptops)",
            "RHV",
            "IT-RHV",
            "Plant IT Lead Rhinval",
            "in_progress",
            date(2026, 11, 15),
            "Reopen rate below 5 %",
            "reopen_rate",
            15.0,
            5.0,
            date(2026, 10, 2),
            None,
        ),
        (
            "Clean up Illerau backlog older than 30 days",
            "Four device requests wait for budget approval since September. Agree a decision with the "
            "cost-centre owners "
            "or cancel the requests.",
            "kpi_breach",
            "Workplace (PCs & laptops)",
            "ILL",
            "IT-ILL",
            "Plant IT Lead Illerau",
            "proposed",
            date(2026, 11, 27),
            "No open tickets older than 30 days",
            "backlog_over_30",
            4.0,
            0.0,
            date(2026, 11, 3),
            None,
        ),
        (
            "MES terminal firmware standard for all plants",
            "Firmware 4.3 fixed the line 3 freezes at Innfeld. Roll it out as the standard at all plants.",
            "problem",
            "MES – shop-floor data collection",
            "INN",
            "IT-INN",
            "Daniel Huber",
            "done",
            date(2026, 9, 15),
            "No terminal freezes caused by firmware",
            None,
            None,
            None,
            date(2026, 8, 21),
            date(2026, 9, 10),
        ),
        (
            "Knowledge article: VPN after Windows update",
            "Write a short fix guide for the service desk so the VPN issue is solved at first contact.",
            "idea",
            "Identity & access (accounts, VPN)",
            "RHV",
            "VIS",
            "Jonas Keller",
            "proposed",
            date(2026, 12, 4),
            "Faster resolution at first contact",
            None,
            None,
            None,
            date(2026, 11, 17),
            None,
        ),
        (
            "Shift handover checklist for all Plant IT teams",
            "One checklist for open P1/P2 tickets, planned changes and known errors at every shift change.",
            "idea",
            None,
            None,
            None,
            "Mara Lindner",
            "approved",
            date(2027, 1, 31),
            "Fewer tickets lost between shifts",
            None,
            None,
            None,
            date(2026, 10, 28),
            None,
        ),
        (
            "Monthly service review with Printwise including MTTR per plant",
            "Add MTTR per plant and the list of breaches to the Printwise review pack.",
            "service_review",
            "Printing & label printing",
            None,
            "PRINTWISE",
            "Mara Lindner",
            "done",
            date(2026, 10, 20),
            "Transparent supplier performance per plant",
            None,
            None,
            None,
            date(2026, 10, 1),
            date(2026, 10, 20),
        ),
        (
            "Self-service password reset",
            "Let users reset their own password; about 15 % of all requests are password resets.",
            "idea",
            "Identity & access (accounts, VPN)",
            None,
            "VIS",
            "Jonas Keller",
            "approved",
            date(2027, 2, 28),
            "Fewer password tickets",
            None,
            None,
            None,
            date(2026, 9, 12),
            None,
        ),
        (
            "Scanner battery replacement cycle in the cold store (Vale Verde)",
            "Batteries lose capacity in the cold store. Agree a replacement cycle with ScanPoint.",
            "problem",
            "Warehouse scanners & MDM",
            "VVD",
            "SCANPOINT",
            "Tomas Novak",
            "proposed",
            date(2026, 12, 5),
            "Scanners last a full shift",
            None,
            None,
            None,
            date(2026, 11, 14),
            None,
        ),
        (
            "Printing support hours for three-shift plants",
            "Extend Printwise support hours to 24x7. Rejected: cost too high; spare printers cover the night shift.",
            "service_review",
            "Printing & label printing",
            None,
            "PRINTWISE",
            "Mara Lindner",
            "rejected",
            None,
            "Night-shift coverage",
            None,
            None,
            None,
            date(2026, 10, 6),
            None,
        ),
        (
            "Monitor WAN availability from the plant side (Vale Verde)",
            "Measure line availability ourselves instead of relying on the carrier's report.",
            "kpi_breach",
            "WAN connectivity",
            "VVD",
            "IT-VVD",
            "Plant IT Lead Vale Verde",
            "in_progress",
            date(2026, 10, 31),
            "Own availability numbers for the service review",
            None,
            None,
            None,
            date(2026, 10, 5),
            None,
        ),
    ]
    result = []
    for (
        title,
        description,
        source,
        service,
        plant,
        prov,
        owner,
        status,
        due,
        benefit,
        kpi,
        base,
        target,
        created,
        done,
    ) in rows:
        result.append(
            Improvement(
                title=title,
                description=description,
                source=source,
                service_id=s[service].id if service else None,
                plant_id=p[plant].id if plant else None,
                provider_id=provider[prov].id if prov else None,
                owner=owner,
                status=status,
                due_date=due,
                expected_benefit=benefit,
                kpi=kpi,
                kpi_baseline=base,
                kpi_target=target,
                created_at=datetime.combine(created, time(9), UTC),
                completed_at=datetime.combine(done, time(15), UTC) if done else None,
            )
        )
    return result


async def seed_demo(db: AsyncSession, *, now: datetime = data.DEMO_START, seed: int = 42) -> None:
    """Create all demo data from scratch (expects empty tables)."""
    catalogue = await create_master_data(db)
    await generate_activity(db, catalogue, now=now, seed=seed)


async def generate_activity(db: AsyncSession, catalogue: Catalogue, *, now: datetime, seed: int) -> None:
    """Tickets, changes, problems, improvements and the demo clock for an existing catalogue."""
    gen = DemoGenerator(catalogue, random.Random(seed), now)
    generate_history(gen)
    links = generate_stories(gen)

    # Keys are numbered in creation order, like in a real ITSM tool.
    gen.tickets.sort(key=lambda t: t.created_at)
    counter = 10000
    for ticket in gen.tickets:
        counter += 1
        ticket.key = f"{KEY_PREFIX[ticket.type]}-{counter}"
    db.add_all(gen.tickets)
    await db.flush()

    for name, (record, incidents) in links.items():
        for incident in incidents:
            if name.startswith("problem:"):
                incident.problem_id = record.id
            else:
                incident.caused_by_change_id = record.id

    db.add_all(improvements(gen))
    db.add(DemoState(id=1, demo_now=now, simulated_days=0, ticket_counter=counter))
    await db.commit()


async def seed_if_empty(db: AsyncSession) -> bool:
    if await db.get(DemoState, 1) is not None:
        return False
    await seed_demo(db)
    return True


def _restore_catalogue_rows(services: list[Service]) -> list[SlaTarget]:
    """Undo catalogue edits made in the demo and return the original SLA targets."""
    by_name = {s.name: s for s in services}
    for name, description, stype, owner, _provider, hours, crit, lifecycle, categories, _ in data.SERVICES:
        service = by_name[name]
        service.description, service.service_type, service.owner_name = description, stype, owner
        service.owner_email = owner.lower().replace(" ", ".") + "@valdora.example"
        service.support_hours, service.criticality, service.lifecycle = hours, crit, lifecycle
        service.categories = ",".join(categories)
    targets = [
        SlaTarget(service_id=None, priority=p, response_min=r, resolution_min=s)
        for p, (r, s) in sla.DEFAULT_SLA_POLICY.items()
    ]
    for service_name, exceptions in data.SLA_EXCEPTIONS.items():
        for priority, (response, resolution) in exceptions.items():
            targets.append(
                SlaTarget(
                    service_id=by_name[service_name].id,
                    priority=priority,
                    response_min=response,
                    resolution_min=resolution,
                )
            )
    return targets


async def reset_demo(db: AsyncSession) -> None:
    """ "Reset demo": activity is generated again; plants, providers and users keep their ids,
    so everybody who is logged in stays logged in."""
    await db.execute(Ticket.__table__.update().values(problem_id=None, caused_by_change_id=None))
    for table in (Improvement, Ticket, SlaTarget, DemoState):
        await db.execute(delete(table))
    services = list((await db.scalars(select(Service).order_by(Service.id))).all())
    db.add_all(_restore_catalogue_rows(services))
    await db.commit()
    await generate_activity(db, await load_catalogue(db), now=data.DEMO_START, seed=42)
