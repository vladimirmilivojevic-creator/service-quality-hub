// Formatting helpers: numbers, durations, dates and months.

const VIENNA = "Europe/Vienna";

export function formatValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return "–";
  if (unit === "%") return `${value.toFixed(1)} %`;
  if (unit === "h") return `${value.toFixed(1)} h`;
  return `${Math.round(value)}`;
}

/** 135 -> "2 h 15 min" (support-hour minutes). */
export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "–";
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function formatDateTime(iso: string | null | undefined, timeZone: string = VIENNA): string {
  if (!iso) return "–";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  }).format(new Date(iso));
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(
    new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso),
  );
}

export function monthLabel(month: string): string {
  const [year, mon] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" }).format(
    new Date(Date.UTC(year, mon - 1, 1)),
  );
}

export function shortMonth(month: string): string {
  const [year, mon] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { month: "short", timeZone: "UTC" }).format(
    new Date(Date.UTC(year, mon - 1, 1)),
  );
}

/** The six months up to and including the demo clock's month, newest first. */
export function recentMonths(demoNow: string | undefined, count = 7): string[] {
  const now = demoNow ? new Date(demoNow) : new Date();
  const result: string[] = [];
  for (let i = 0; i < count; i++) {
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 1));
    result.push(`${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`);
  }
  return result;
}

export function previousMonth(demoNow: string | undefined): string {
  return recentMonths(demoNow, 2)[1];
}

export const LABELS: Record<string, string> = {
  incident: "Incident",
  request: "Service request",
  problem: "Problem",
  change: "Change",
  on_track: "On track",
  at_risk: "At risk",
  breached: "Breached",
  met: "Met",
  no_target: "No SLA",
  successful: "Successful",
  failed: "Failed",
  rolled_back: "Rolled back",
  caused_incident: "Caused incident",
  investigating: "Investigating",
  known_error: "Known error",
  resolved: "Resolved",
  proposed: "Proposed",
  approved: "Approved",
  in_progress: "In progress",
  done: "Done",
  rejected: "Rejected",
  kpi_breach: "KPI breach",
  service_review: "Service review",
  idea: "Idea",
  pipeline: "Pipeline",
  live: "Live",
  retired: "Retired",
  central: "Central IT provider",
  plant_it: "Plant IT team",
  external: "External vendor",
  sqm: "Service Quality Manager",
  plant_lead: "Plant IT Lead",
  management: "IT Management",
  supplier: "Supplier",
};

export function label(key: string | null | undefined): string {
  if (!key) return "–";
  return LABELS[key] ?? key;
}
