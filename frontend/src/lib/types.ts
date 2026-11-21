// Shapes of the API responses (see the OpenAPI docs at /docs).

export type Role = "sqm" | "plant_lead" | "management" | "supplier";
export type Rag = "green" | "amber" | "red" | "no_data";

export interface Me {
  id: number;
  email: string;
  full_name: string;
  title: string;
  role: Role;
  plant_id: number | null;
  plant_code: string | null;
  provider_id: number | null;
}

export interface Plant {
  id: number;
  code: string;
  name: string;
  country: string;
  timezone: string;
  products: string;
}

export interface SlaTarget {
  priority: number;
  response_min: number;
  resolution_min: number;
  is_exception: boolean;
}

export interface Service {
  id: number;
  name: string;
  description: string;
  service_type: string;
  owner_name: string;
  owner_email: string;
  provider_name: string;
  provider_id: number | null;
  delivered_by_plant_it: boolean;
  support_hours: string;
  support_hours_label: string;
  criticality: string;
  lifecycle: "pipeline" | "live" | "retired";
  categories: string[];
  sla_targets: SlaTarget[];
}

export interface KpiCard {
  key: string;
  name: string;
  unit: string;
  value: number | null;
  rag: Rag;
  previous: number | null;
  delta: number | null;
  definition: string;
  formula: string;
  target_text: string;
  higher_is_better: boolean;
  detail: Record<string, unknown>;
}

export interface KpiSummary {
  month: string;
  period_start: string;
  period_end: string;
  is_partial: boolean;
  kpis: KpiCard[];
}

export interface KpiTrend {
  months: string[];
  series: Record<string, (number | null)[]>;
}

export interface PlantRow {
  plant_id: number;
  plant_code: string;
  plant_name: string;
  resolved: number;
  open: number;
  values: Record<string, number | null>;
  rag: Record<string, Rag>;
}

export interface Ticket {
  id: number;
  key: string;
  external_key: string | null;
  type: "incident" | "request" | "problem" | "change";
  plant_id: number;
  plant_code: string;
  service_id: number;
  service_name: string;
  provider_id: number;
  provider_name: string;
  priority: number;
  impact: string | null;
  urgency: string | null;
  status: string;
  category: string;
  title: string;
  source: string;
  created_at: string;
  first_response_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  pending_since: string | null;
  paused_minutes: number;
  reopen_count: number;
  response_target_min: number | null;
  resolution_target_min: number | null;
  response_business_min: number | null;
  resolution_business_min: number | null;
  response_breached: boolean | null;
  resolution_breached: boolean | null;
  response_status: string | null;
  resolution_status: string | null;
  response_elapsed_min: number | null;
  resolution_elapsed_min: number | null;
  response_due_at: string | null;
  resolution_due_at: string | null;
  problem_id: number | null;
  caused_by_change_id: number | null;
  change_type: string | null;
  planned_start: string | null;
  planned_end: string | null;
  outcome: string | null;
  problem_status: string | null;
  root_cause: string | null;
  workaround: string | null;
  source_sla_note: string | null;
}

export interface TicketDetail extends Ticket {
  support_hours_label: string;
  plant_timezone: string;
  linked: Ticket[];
  problem: Ticket | null;
  caused_by_change: Ticket | null;
}

export interface TicketPage {
  items: Ticket[];
  total: number;
}

export interface Scorecard {
  provider_id: number;
  name: string;
  short_name: string;
  kind: "central" | "plant_it" | "external";
  agreement: string;
  contract_ref: string;
  target_pct: number;
  plant_code: string | null;
  tickets: number;
  resolution_compliance: number | null;
  response_compliance: number | null;
  mttr_hours: number | null;
  breaches: number;
  p1_incidents: number;
  previous_resolution_compliance: number | null;
  trend: "up" | "down" | "flat";
  rag: Rag;
  top_breach_services: { service: string; breaches: number }[];
  escalation_contact: string;
}

export interface ScorecardDetail {
  month: string;
  scorecard: Scorecard;
  trend: {
    month: string;
    tickets: number;
    resolution_compliance: number | null;
    response_compliance: number | null;
    mttr_hours: number | null;
  }[];
  breaches: Ticket[];
  improvements: { id: number; title: string; status: string; due_date: string | null; owner: string }[];
}

export interface Candidate {
  plant_id: number;
  plant_code: string;
  plant_name: string;
  service_id: number;
  service_name: string;
  category: string;
  count: number;
  first_seen: string;
  last_seen: string;
  suggested_title: string;
  incidents: Ticket[];
}

export interface Improvement {
  id: number;
  title: string;
  description: string;
  source: string;
  service_id: number | null;
  service_name: string | null;
  plant_id: number | null;
  plant_code: string | null;
  provider_id: number | null;
  provider_name: string | null;
  owner: string;
  status: string;
  due_date: string | null;
  overdue: boolean;
  expected_benefit: string;
  kpi: string | null;
  kpi_baseline: number | null;
  kpi_target: number | null;
  created_at: string;
  completed_at: string | null;
}

export interface MonthlyReport {
  month: string;
  period_start: string;
  period_end: string;
  is_partial: boolean;
  summary: string[];
  kpis: KpiCard[];
  trend: KpiTrend;
  plants: PlantRow[];
  suppliers: Scorecard[];
  top_breaches: Ticket[];
  major_incidents: Ticket[];
  problems: Ticket[];
  problem_candidates: {
    plant_code: string;
    service_name: string;
    category: string;
    count: number;
    last_seen: string;
  }[];
  changes: { completed: number; successful: number; success_rate: number | null; rag: Rag; not_successful: Ticket[] };
  improvements: { open: Improvement[]; done_in_month: Improvement[]; overdue: Improvement[] };
  next_actions: string[];
}

export interface Meta {
  demo_now: string;
  simulated_days: number;
  calendars: { code: string; label: string }[];
  priorities: { priority: number; label: string; example: string; response_min: number; resolution_min: number }[];
  priority_matrix: { impact: string; urgency: string; priority: number }[];
  at_risk_share: number;
  kpis: { key: string; name: string; unit: string; definition: string; formula: string; target_text: string }[];
  mttr_targets_hours: Record<string, number>;
  problem_rule: { min_incidents: number; window_days: number };
  supplier_amber_band: number;
}

export interface ImportPreview {
  total_rows: number;
  valid_rows: number;
  detected: Record<string, string>;
  rows: {
    row: number;
    key: string;
    type: string;
    plant_code: string;
    service_name: string;
    priority: number;
    status: string;
    created_at: string;
    resolved_at: string | null;
    title: string;
  }[];
  skipped: { row: number; message: string }[];
  warnings: string[];
}

export interface ImportResult {
  created: number;
  updated: number;
  skipped: { row: number; message: string }[];
  warnings: string[];
}

export interface SimulationResult {
  demo_now: string;
  created: number;
  resolved: number;
  new_breaches: number;
  changes: number;
  messages: string[];
}
