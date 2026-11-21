"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { TrendChart } from "@/components/charts";
import KpiCard from "@/components/KpiCard";
import TicketTable from "@/components/TicketTable";
import {
  Button,
  Card,
  ErrorMessage,
  Loading,
  PageTitle,
  RagDot,
  RagLegend,
  Select,
  TableWrap,
  Td,
  Th,
} from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { formatValue, monthLabel, recentMonths } from "@/lib/format";
import { useApi, useApiMutation, useMeta, usePlants, useProviders, useServices } from "@/lib/hooks";
import type { KpiSummary, KpiTrend, PlantRow, Scorecard, TicketPage } from "@/lib/types";

const PLANT_COLUMNS = [
  { key: "sla_resolution", label: "Resolution SLA", unit: "%" },
  { key: "sla_response", label: "Response SLA", unit: "%" },
  { key: "mttr", label: "MTTR", unit: "h" },
  { key: "backlog_over_30", label: "Backlog > 30 d", unit: "tickets" },
  { key: "reopen_rate", label: "Reopen rate", unit: "%" },
  { key: "change_success", label: "Change success", unit: "%" },
];

export default function DashboardPage() {
  return (
    <AppShell>
      <Dashboard />
    </AppShell>
  );
}

function Dashboard() {
  const { user } = useAuth();
  const router = useRouter();
  const meta = useMeta();
  const plants = usePlants().data ?? [];
  const services = useServices().data ?? [];
  const providers = useProviders();
  const [month, setMonth] = useState("");
  const [plant, setPlant] = useState("");
  const [service, setService] = useState("");
  const [provider, setProvider] = useState("");

  useEffect(() => {
    if (user?.role === "supplier") router.replace(`/suppliers/${user.provider_id}`);
  }, [user, router]);

  const months = recentMonths(meta.data?.demo_now);
  const selectedMonth = month || months[0];
  const filters = new URLSearchParams({ month: selectedMonth });
  if (plant) filters.set("plant_id", plant);
  if (service) filters.set("service_id", service);
  if (provider) filters.set("provider_id", provider);
  const query = meta.data ? filters.toString() : null;

  const summary = useApi<KpiSummary>(query && `/kpis?${query}`);
  const trend = useApi<KpiTrend>(query && `/kpis/trend?${query}`);
  const byPlant = useApi<PlantRow[]>(query && `/kpis/by-plant?${query}`);
  const risky = useApi<TicketPage>(`/tickets?sla=at_risk,breached&size=8${plant ? `&plant_id=${plant}` : ""}`);
  const reset = useApiMutation<void, { demo_now: string }>("POST", "/demo/reset");
  const suppliers = useApi<{ month: string; rows: Scorecard[] }>(
    meta.data ? `/suppliers?month=${selectedMonth}` : null,
  );

  return (
    <>
      <PageTitle
        title="Service quality dashboard"
        subtitle={
          <>
            {monthLabel(selectedMonth)}
            {summary.data?.is_partial ? " (month to date, by the demo clock)" : ""} · KPIs are counted from the SLA
            result stored on every ticket.
          </>
        }
        actions={
          <>
            {user?.role === "sqm" && (
              <Button
                onClick={() => reset.mutate(undefined)}
                disabled={reset.isPending}
                title="Deletes all changes made in the demo and goes back to the starting point"
              >
                {reset.isPending ? "Resetting…" : "Reset demo"}
              </Button>
            )}
            <Link
              href="/reports/monthly"
              data-testid="generate-report"
              className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Generate monthly service review
            </Link>
          </>
        }
      />

      <div className="mb-6 flex flex-wrap items-end gap-3">
        <Select
          label="Month"
          value={selectedMonth}
          onChange={setMonth}
          testId="filter-month"
          options={months.map((m, i) => ({ value: m, label: monthLabel(m) + (i === 0 ? " (to date)" : "") }))}
        />
        <Select
          label="Plant"
          value={plant}
          onChange={setPlant}
          testId="filter-plant"
          options={[{ value: "", label: "All plants" }, ...plants.map((p) => ({ value: String(p.id), label: p.name }))]}
        />
        <Select
          label="Service"
          value={service}
          onChange={setService}
          options={[
            { value: "", label: "All services" },
            ...services.filter((s) => s.lifecycle === "live").map((s) => ({ value: String(s.id), label: s.name })),
          ]}
        />
        <Select
          label="Provider"
          value={provider}
          onChange={setProvider}
          options={[
            { value: "", label: "All providers" },
            ...providers.map((p) => ({ value: String(p.id), label: p.name })),
          ]}
        />
        <div className="ml-auto">
          <RagLegend />
        </div>
      </div>

      <ErrorMessage error={summary.error} />
      {summary.isLoading || !summary.data ? (
        <Loading />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {summary.data.kpis.map((kpi) => (
            <KpiCard key={kpi.key} kpi={kpi} trend={trend.data?.series[kpi.key]} />
          ))}
        </div>
      )}

      <Card
        className="mt-6"
        title="Plants side by side"
        info="The same KPIs for every plant, so differences between sites are visible at a glance. Colours use the same targets as the KPI cards."
      >
        {!byPlant.data ? (
          <Loading />
        ) : (
          <TableWrap>
            <thead className="bg-slate-50">
              <tr>
                <Th>Plant</Th>
                {PLANT_COLUMNS.map((c) => (
                  <Th key={c.key}>{c.label}</Th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100" data-testid="plant-table">
              {byPlant.data.map((row) => (
                <tr key={row.plant_id}>
                  <Td className="font-medium">
                    {row.plant_name}
                    <span className="block text-xs font-normal text-slate-400">{row.resolved} resolved</span>
                  </Td>
                  {PLANT_COLUMNS.map((c) => (
                    <Td key={c.key}>
                      <span className="flex items-center gap-1.5 whitespace-nowrap">
                        <RagDot rag={row.rag[c.key]} />
                        {formatValue(row.values[c.key], c.unit)}
                      </span>
                    </Td>
                  ))}
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <Card
          className="lg:col-span-3"
          title="Resolution SLA – six months"
          info="Share of tickets resolved within target, month by month. The dashed line is the 95 % target."
        >
          {trend.data ? (
            <TrendChart
              months={trend.data.months}
              series={[{ name: "Resolution SLA", values: trend.data.series.sla_resolution }]}
              target={95}
            />
          ) : (
            <Loading />
          )}
        </Card>
        <Card
          className="lg:col-span-2"
          title="Providers below their agreement"
          info="Supplier scorecards compare the central IT provider, the plant IT teams (OLA) and external vendors (contract) on the same numbers."
          actions={
            <Link href="/suppliers" className="text-xs font-medium text-brand-700 hover:underline">
              All scorecards →
            </Link>
          }
        >
          {!suppliers.data ? (
            <Loading />
          ) : (
            <ul className="space-y-2">
              {suppliers.data.rows
                .filter((r) => r.rag !== "green")
                .map((r) => (
                  <li key={r.provider_id}>
                    <Link
                      href={`/suppliers/${r.provider_id}`}
                      className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 hover:bg-slate-50"
                    >
                      <span className="flex items-center gap-2 text-sm">
                        <RagDot rag={r.rag} />
                        {r.name}
                      </span>
                      <span className="text-sm font-medium">
                        {formatValue(r.resolution_compliance, "%")}
                        <span className="ml-1 text-xs font-normal text-slate-500">target {r.target_pct} %</span>
                      </span>
                    </Link>
                  </li>
                ))}
              {suppliers.data.rows.every((r) => r.rag === "green") && (
                <li className="text-sm text-slate-500">All providers meet their agreement this month.</li>
              )}
            </ul>
          )}
        </Card>
      </div>

      <Card
        className="mt-6"
        title="Open tickets at risk or breached"
        info="Live SLA clock by the demo clock. 'At risk' means 75 % of the resolution target is used up; 'breached' means the target is missed."
        actions={
          <Link href="/tickets" className="text-xs font-medium text-brand-700 hover:underline">
            All tickets →
          </Link>
        }
      >
        {risky.data ? <TicketTable tickets={risky.data.items} showProvider={false} /> : <Loading />}
      </Card>
    </>
  );
}
