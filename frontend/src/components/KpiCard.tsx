"use client";

import { Sparkline } from "@/components/charts";
import { Delta, InfoTip, RagBadge } from "@/components/ui";
import { formatValue } from "@/lib/format";
import type { KpiCard as Kpi } from "@/lib/types";

const BORDER = {
  green: "border-t-emerald-500",
  amber: "border-t-amber-500",
  red: "border-t-red-500",
  no_data: "border-t-slate-300",
};

function DetailLine({ kpi }: { kpi: Kpi }) {
  const d = kpi.detail as Record<string, unknown>;
  if (kpi.key === "sla_resolution" || kpi.key === "sla_response")
    return (
      <>
        {String(d.met)} of {String(d.total)} within target
      </>
    );
  if (kpi.key === "mttr") {
    const byPriority = d.by_priority as Record<string, number | null>;
    return (
      <>
        median {formatValue(d.median as number | null, "h")} · P1 {formatValue(byPriority["1"] ?? null, "h")} · P2{" "}
        {formatValue(byPriority["2"] ?? null, "h")}
      </>
    );
  }
  if (kpi.key === "backlog_over_30")
    return (
      <>
        {String(d.open)} open · average age {String(d.average_age_days ?? "–")} days
      </>
    );
  if (kpi.key === "reopen_rate")
    return (
      <>
        {String(d.reopened)} of {String(d.total)} reopened
      </>
    );
  return (
    <>
      {String(d.successful)} of {String(d.total)} changes successful
    </>
  );
}

/** One KPI: value, colour against target, change to last month, six-month sparkline and an explanation. */
export default function KpiCard({ kpi, trend }: { kpi: Kpi; trend?: (number | null)[] }) {
  return (
    <div
      data-testid={`kpi-${kpi.key}`}
      className={`avoid-break flex flex-col gap-2 rounded-xl border border-t-4 border-slate-200 bg-white p-4 shadow-sm ${BORDER[kpi.rag]}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="flex items-center gap-1 text-sm font-medium text-slate-600">
          {kpi.name}
          <InfoTip>
            <strong className="block text-slate-800">{kpi.name}</strong>
            {kpi.definition}
            <span className="mt-2 block font-mono text-[11px] text-slate-500">{kpi.formula}</span>
            <span className="mt-2 block">Target: {kpi.target_text}</span>
          </InfoTip>
        </p>
        <RagBadge rag={kpi.rag} />
      </div>
      <p className="text-3xl font-semibold tracking-tight" data-testid={`kpi-value-${kpi.key}`}>
        {formatValue(kpi.value, kpi.unit)}
      </p>
      <p className="text-xs text-slate-500">
        <DetailLine kpi={kpi} />
      </p>
      <Delta value={kpi.delta} higherIsBetter={kpi.higher_is_better} unit={kpi.unit} />
      {trend && <Sparkline values={trend} />}
    </div>
  );
}
