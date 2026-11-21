"""Demo master data for the fictional Valdora Machinery Group.

The company, plants, people, suppliers and numbers are invented for this demo.
"""

from datetime import UTC, datetime

# The demo clock starts here (Wednesday, 10:00 in Austria). "Reset demo" returns to this moment.
DEMO_START = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
HISTORY_START = datetime(2026, 5, 1, 0, 0, tzinfo=UTC)

PLANTS = [
    # code, name, country, time zone, products, monthly ticket volume
    ("INN", "Innfeld Works", "AT", "Europe/Vienna", "Crawler dozers, telehandlers", 110),
    ("SAL", "Salzbach Works", "AT", "Europe/Vienna", "Wheel loaders", 100),
    ("ILL", "Illerau Works", "DE", "Europe/Berlin", "Hydraulic excavators", 105),
    ("RHV", "Rhinval Works", "FR", "Europe/Paris", "Mining excavators", 95),
    ("VVD", "Vale Verde Works", "BR", "America/Sao_Paulo", "Excavators for South America", 70),
]

PROVIDERS = [
    # name, short name, kind, plant code (plant IT only), target %, agreement reference, escalation contact
    ("Valdora IT Services", "VIS", "central", None, 95.0, "OLA-VIS-2026", "VIS Service Delivery Manager"),
    ("Plant IT Innfeld", "IT-INN", "plant_it", "INN", 95.0, "OLA-PIT-INN-2026", "Plant IT Lead Innfeld"),
    ("Plant IT Salzbach", "IT-SAL", "plant_it", "SAL", 95.0, "OLA-PIT-SAL-2026", "Plant IT Lead Salzbach"),
    ("Plant IT Illerau", "IT-ILL", "plant_it", "ILL", 95.0, "OLA-PIT-ILL-2026", "Plant IT Lead Illerau"),
    ("Plant IT Rhinval", "IT-RHV", "plant_it", "RHV", 95.0, "OLA-PIT-RHV-2026", "Plant IT Lead Rhinval"),
    ("Plant IT Vale Verde", "IT-VVD", "plant_it", "VVD", 95.0, "OLA-PIT-VVD-2026", "Plant IT Lead Vale Verde"),
    ("AlpNet Carrier", "ALPNET", "external", None, 97.0, "Contract WAN-2024-07", "AlpNet NOC duty manager"),
    (
        "Printwise Managed Print",
        "PRINTWISE",
        "external",
        None,
        95.0,
        "Contract MPS-2025-02",
        "Printwise account manager",
    ),
    ("ScanPoint Mobility", "SCANPOINT", "external", None, 95.0, "Contract MDM-2025-11", "ScanPoint service desk lead"),
]

# Request categories: tickets in these categories are service requests, all others are incidents.
REQUEST_CATEGORIES = {
    "New account",
    "Password reset",
    "Permissions",
    "Software install",
    "New device",
    "Shared mailbox access",
    "Restore request",
    "Toner / supplies",
    "Master data change",
}

SERVICES = [
    # name, description, type, owner, provider short name (None = plant IT), support hours, criticality,
    # lifecycle, categories, relative ticket volume
    (
        "ERP – production & logistics",
        "Production orders, material planning, goods receipt and shipping in the group ERP.",
        "business",
        "Katrin Moser",
        "VIS",
        "shift",
        "high",
        "live",
        ["Login / authorisation", "Performance", "Interface error", "Printing from ERP", "Master data change"],
        12,
    ),
    (
        "MES – shop-floor data collection",
        "Terminals at the assembly lines that book production steps and collect machine data.",
        "business",
        "Daniel Huber",
        None,
        "24x7",
        "critical",
        "live",
        ["Terminal freeze", "Interface to ERP", "Machine data missing", "Login"],
        8,
    ),
    (
        "PLM / CAD engineering",
        "Product data management and CAD workstations for engineering.",
        "business",
        "Pierre Lefevre",
        "VIS",
        "office",
        "medium",
        "live",
        ["License", "Performance", "Data exchange", "Workstation graphics"],
        6,
    ),
    (
        "Email & collaboration",
        "Email, calendars, online meetings and shared mailboxes.",
        "business",
        "Nina Brandt",
        "VIS",
        "office",
        "medium",
        "live",
        ["Mailbox", "Meetings", "Calendar", "Shared mailbox access"],
        10,
    ),
    (
        "Identity & access (accounts, VPN)",
        "User accounts, passwords, permissions and remote access (VPN).",
        "business",
        "Jonas Keller",
        "VIS",
        "office",
        "medium",
        "live",
        ["Password reset", "New account", "VPN", "Permissions"],
        16,
    ),
    (
        "Plant network (LAN & Wi-Fi)",
        "Switches, cabling and Wi-Fi inside the plant, including the shop floor.",
        "technical",
        "Marco Steiner",
        None,
        "24x7",
        "high",
        "live",
        ["Wi-Fi coverage", "Switch / port", "Network outage"],
        5,
    ),
    (
        "WAN connectivity",
        "Lines between the plants and the central data centre, delivered by an external carrier.",
        "technical",
        "Stefan Auer",
        "ALPNET",
        "24x7",
        "critical",
        "live",
        ["Line down", "Packet loss / latency", "Bandwidth"],
        2,
    ),
    (
        "Workplace (PCs & laptops)",
        "Office and engineering PCs, laptops, monitors and standard software.",
        "business",
        "Laura Wenger",
        None,
        "office",
        "low",
        "live",
        ["Hardware fault", "Software install", "New device", "Peripheral"],
        22,
    ),
    (
        "Printing & label printing",
        "Office printers and label printers for parts, pallets and shipping (managed print contract).",
        "business",
        "Eva Lindner",
        "PRINTWISE",
        "shift",
        "high",
        "live",
        ["Label printer", "Office printer", "Toner / supplies", "Print queue"],
        9,
    ),
    (
        "Warehouse scanners & MDM",
        "Handheld scanners in the warehouse and their mobile device management.",
        "business",
        "Tomas Novak",
        "SCANPOINT",
        "shift",
        "high",
        "live",
        ["Scanner hardware", "Battery", "App / MDM", "Wi-Fi roaming"],
        7,
    ),
    (
        "Backup & restore",
        "Daily backups of servers and file shares, and restores on request.",
        "technical",
        "Ines Ferreira",
        "VIS",
        "office",
        "medium",
        "live",
        ["Restore request", "Backup failure"],
        3,
    ),
    (
        "Shop-floor tablets – pilot",
        "Rugged tablets for work instructions at the line. Pilot planned in two plants.",
        "business",
        "Daniel Huber",
        None,
        "shift",
        "medium",
        "pipeline",
        ["Tablet hardware", "Work instructions app"],
        0,
    ),
    (
        "Legacy fax gateway",
        "Fax-to-email gateway. Replaced by email and supplier portals.",
        "technical",
        "Jonas Keller",
        "VIS",
        "office",
        "low",
        "retired",
        ["Fax delivery"],
        0,
    ),
]

# Service-specific SLA exceptions (minutes): MES stops production lines, so P1/P2 are tighter.
SLA_EXCEPTIONS = {
    "MES – shop-floor data collection": {1: (10, 2 * 60), 2: (15, 4 * 60)},
}

USERS = [
    # email, name, title, role, plant code, provider short name
    ("sqm@valdora.example", "Mara Lindner", "Service Quality Manager", "sqm", None, None),
    ("it.innfeld@valdora.example", "Tobias Gruber", "Plant IT Lead – Innfeld", "plant_lead", "INN", None),
    ("cio@valdora.example", "Helena Vogt", "Head of IT (read-only)", "management", None, None),
    (
        "supplier.alpnet@valdora.example",
        "Rui Carvalho",
        "Service Delivery Manager – AlpNet",
        "supplier",
        None,
        "ALPNET",
    ),
]
DEMO_PASSWORD = "demo1234"
