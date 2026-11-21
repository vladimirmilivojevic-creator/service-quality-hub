"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import { TrendChart } from "@/components/charts";
import ImprovementForm from "@/components/ImprovementForm";
import TicketTable from "@/components/TicketTable";
import {
  Button,
  Card,
  ErrorMessage,
  Loading,
  PageTitle,
  RagBadge,
  Select,
  StatusBadge,
  TrendArrow,
} from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { formatDate, formatValue, label, monthLabel, previousMonth, recentMonths } from "@/lib/format";
import { useApi, useMeta } from "@/lib/hooks";
import type { ScorecardDetail } from "@/lib/types";

export default function SupplierPage() {
  return (
    <AppShell>
      <Supplier />
    </AppShell>
  );
}

function Supplier() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const meta = useMeta();
  const [month, setMonth] = useState("");
  const [adding, setAdding] = useState(false);
  const selected = month || previousMonth(meta.data?.demo_now);
  const detail = useApi<ScorecardDetail>(meta.data ? `/suppliers/${id}/scorecard?month=${selected}` : null);

  if (detail.error) return <ErrorMessage error={detail.error} />;
  if (!detail.data) return <Loading />;
  const { scorecard: s, trend, breaches, improvements } = detail.data;
  const canAdd = user?.role === "sqm";

  return (
    <>
      <PageTitle
        title={s.name}
        subtitle={`${label(s.kind)} · ${s.agreement} ${s.contract_ref} · target ${s.target_pct} % of tickets resolved within SLA · escalation: ${s.escalation_contact}`}
        actions={
          <>
            <Select
              label="Month"
              value={selected}
              onChange={setMonth}
              options={recentMonths(meta.data?.demo_now).map((m) => ({ value: m, label: monthLabel(m) }))}
            />
            {canAdd && (
              <Button variant="primary" onClick={() => setAdding(true)} data-testid="add-improvement">
                Add improvement
              </Button>
            )}
          </>
        }
      />
      {adding && (
        <Card className="mb-6" title="New improvement for this provider">
          <ImprovementForm
            draft={{
              title: `Improve ${s.name} SLA compliance`,
              source: "service_review",
              provider_id: s.provider_id,
              kpi: "sla_resolution",
              kpi_baseline: s.resolution_compliance,
              kpi_target: s.target_pct,
            }}
            onDone={() => setAdding(false)}
          />
        </Card>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card title="Resolution SLA">
          <RagBadge rag={s.rag}>{formatValue(s.resolution_compliance, "%")}</RagBadge>
          <p className="mt-2 text-xs text-slate-500">
            target {s.target_pct} % · <TrendArrow trend={s.trend} /> vs{" "}
            {formatValue(s.previous_resolution_compliance, "%")}
          </p>
        </Card>
        <Card title="Response SLA">
          <p className="text-xl font-semibold">{formatValue(s.response_compliance, "%")}</p>
        </Card>
        <Card title="MTTR (incidents)">
          <p className="text-xl font-semibold">{formatValue(s.mttr_hours, "h")}</p>
        </Card>
        <Card title="Breaches">
          <p className="text-xl font-semibold">{s.breaches}</p>
          <p className="text-xs text-slate-500">{s.tickets} tickets resolved</p>
        </Card>
        <Card title="P1 incidents">
          <p className="text-xl font-semibold">{s.p1_incidents}</p>
        </Card>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card
          className="lg:col-span-2"
          title="Six-month trend"
          info="Resolution and response SLA compliance per month; the dashed line is the agreed target."
        >
          <TrendChart
            months={trend.map((t) => t.month)}
            series={[
              { name: "Resolution SLA", values: trend.map((t) => t.resolution_compliance) },
              { name: "Response SLA", values: trend.map((t) => t.response_compliance) },
            ]}
            target={s.target_pct}
          />
        </Card>
        <Card title="Improvement actions">
          {improvements.length === 0 ? (
            <p className="text-sm text-slate-500">No improvement actions yet.</p>
          ) : (
            <ul className="space-y-3">
              {improvements.map((i) => (
                <li key={i.id} className="text-sm">
                  <p className="font-medium">{i.title}</p>
                  <p className="flex items-center gap-2 text-xs text-slate-500">
                    <StatusBadge status={i.status} /> {i.owner} · due {formatDate(i.due_date)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Card className="mt-6" title={`SLA breaches – ${monthLabel(detail.data.month)}`}>
        <TicketTable tickets={breaches} showProvider={false} />
      </Card>
    </>
  );
}
