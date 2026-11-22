"""How a Jira Service Management CSV export is mapped onto ServiceQualityHub.

Everything a Service Quality Manager may need to adjust for another JSM site lives in this one
file: column names, issue types, priorities, statuses, plant and service names, date formats.
"""

# Jira repeats a column for fields with several values (e.g. three "Labels" columns);
# pandas names them "Labels", "Labels.1", "Labels.2" ... The importer reads all of them.

COLUMN_KEY = "Issue key"
COLUMN_SUMMARY = "Summary"
COLUMN_ISSUE_TYPE = "Issue Type"
COLUMN_STATUS = "Status"
COLUMN_PRIORITY = "Priority"
COLUMN_CREATED = "Created"
COLUMN_RESOLVED = "Resolved"
COLUMN_REQUEST_TYPE = "Custom field (Request Type)"
# Jira's built-in "Date of First Response" field, if the site exports it. Unlike "Created", Jira writes this
# field in UTC with milliseconds (e.g. "2026-11-22 15:20:19.743").
COLUMNS_FIRST_RESPONSE = ["Custom field ([CHART] Date of First Response)", "Custom field (Date of First Response)"]
FIRST_RESPONSE_TIMEZONE = "UTC"
# JSM's own SLA fields: kept as a reference note only. Our engine calculates the SLA itself.
# In an export they show the remaining time as hours:minutes; a negative value means breached ("-49:30").
COLUMNS_JSM_SLA = ["Custom field (Time to first response)", "Custom field (Time to resolution)"]

# Where to find the plant: the first column that contains a known plant name or code wins.
PLANT_COLUMNS = ["Custom field (Site)", "Custom field (Plant)", "Components", "Component/s", "Labels"]
# Where to find the service: aliases in these columns, then the request type.
SERVICE_COLUMNS = ["Labels", "Components", "Component/s", "Custom field (Service)"]

REQUIRED_COLUMNS = [COLUMN_KEY, COLUMN_SUMMARY, COLUMN_ISSUE_TYPE, COLUMN_STATUS, COLUMN_PRIORITY, COLUMN_CREATED]

ISSUE_TYPES = {
    "incident": "incident",
    "[system] incident": "incident",
    "service request": "request",
    "[system] service request": "request",
    "service request with approvals": "request",
    "[system] service request with approvals": "request",
    "it help": "request",
    "[system] it help": "request",
    "problem": "problem",
    "[system] problem": "problem",
    "change": "change",
    "[system] change": "change",
}

PRIORITIES = {"highest": 1, "critical": 1, "high": 2, "medium": 3, "low": 4, "lowest": 4}

STATUSES = {
    "open": "New",
    "new": "New",
    "to do": "New",
    "waiting for support": "New",
    "in progress": "In progress",
    "work in progress": "In progress",
    "escalated": "In progress",
    "under investigation": "In progress",
    "reopened": "In progress",
    "awaiting implementation": "In progress",
    "implementing": "In progress",
    "waiting for customer": "Pending",
    "pending": "Pending",
    "waiting for approval": "Pending",
    "resolved": "Resolved",
    "done": "Resolved",
    "completed": "Resolved",
    "closed": "Closed",
    "canceled": "Closed",
    "cancelled": "Closed",
    "declined": "Closed",
}

# Words that point to a service (matched in labels / components, case-insensitive).
SERVICE_ALIASES = {
    "erp": "ERP – production & logistics",
    "mes": "MES – shop-floor data collection",
    "plm": "PLM / CAD engineering",
    "cad": "PLM / CAD engineering",
    "email": "Email & collaboration",
    "e-mail": "Email & collaboration",
    "collaboration": "Email & collaboration",
    "identity": "Identity & access (accounts, VPN)",
    "access": "Identity & access (accounts, VPN)",
    "account": "Identity & access (accounts, VPN)",
    "vpn": "Identity & access (accounts, VPN)",
    "network": "Plant network (LAN & Wi-Fi)",
    "lan": "Plant network (LAN & Wi-Fi)",
    "wifi": "Plant network (LAN & Wi-Fi)",
    "wi-fi": "Plant network (LAN & Wi-Fi)",
    "wan": "WAN connectivity",
    "workplace": "Workplace (PCs & laptops)",
    "laptop": "Workplace (PCs & laptops)",
    "pc": "Workplace (PCs & laptops)",
    "hardware": "Workplace (PCs & laptops)",
    "printing": "Printing & label printing",
    "printer": "Printing & label printing",
    "label-printer": "Printing & label printing",
    "scanner": "Warehouse scanners & MDM",
    "scanners": "Warehouse scanners & MDM",
    "mdm": "Warehouse scanners & MDM",
    "backup": "Backup & restore",
}

# Request types of the JSM IT service management template that clearly belong to one service.
REQUEST_TYPE_SERVICES = {
    "request a new account": "Identity & access (accounts, VPN)",
    "get a guest wifi account": "Plant network (LAN & Wi-Fi)",
    "reset password": "Identity & access (accounts, VPN)",
    "request hardware": "Workplace (PCs & laptops)",
    "request new hardware": "Workplace (PCs & laptops)",
    "request new software": "Workplace (PCs & laptops)",
    "get it help": None,
    "report an incident": None,
    "report a system problem": None,
    "report broken hardware": "Workplace (PCs & laptops)",
    "request admin access": "Identity & access (accounts, VPN)",
    "onboard new employees": "Identity & access (accounts, VPN)",
    "ask a question": None,
}

# JSM exports dates as text in the exporting user's format and time zone, e.g. "21/Nov/26 3:45 PM".
DATE_FORMATS = [
    "%d/%b/%y %I:%M %p",
    "%d/%b/%Y %I:%M %p",
    "%d/%b/%y %H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%d.%m.%Y %H:%M",
    "%d.%m.%y %H:%M",
    "%m/%d/%Y %H:%M",
    "%m/%d/%y %I:%M %p",
]
DEFAULT_TIMEZONE = "Europe/Vienna"
