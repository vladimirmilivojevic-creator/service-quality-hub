"use client";

import Link from "next/link";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import { TrendChart } from "@/components/charts";
import {
  Button,
  Card,
  ErrorMessage,
  Loading,
  PageTitle,
  PriorityBadge,
  RagBadge,
  RagDot,
  RagLegend,
  Select,
  StatusBadge,
  TableWrap,
  Td,
  Th,
  TrendArrow,
} from "@/components/ui";
import { download } from "@/lib/api";
import {
  formatDate,
  formatDateTime,
  formatMinutes,
  formatValue,
  label,
  monthLabel,
  previousMonth,
  recentMonths,
  shortMonth,
} from "@/lib/format";
import { useApi, useMeta } from "@/lib/hooks";
import type { Improvement, MonthlyReport, Ticket } from "@/lib/types";

export default function MonthlyReportPage() {
  return (
    <AppShell>
      <Report />
    </AppShell>
  );
}

function Section({
  n,
  title,
  children,
  className = "",
}: {
  n: number;
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={className} title={`${n}. ${title}`}>
      {children}
    </Card>
  );
}

function SmallTickets({ tickets, empty }: { tickets: Ticket[]; empty: string }) {
  if (!tickets.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <TableWrap>
      <thead className="bg-slate-50">
        <tr>
          <Th>Ticket</Th>
          <Th>Plant</Th>
          <Th>Service / provider</Th>
          <Th>Resolution (target)</Th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {tickets.map((t) => (
          <tr key={t.id}>
            <Td>
              <span className="flex items-center gap-2">
                <PriorityBadge priority={t.priority} />
                <Link href={`/tickets/${t.id}`} className="font-medium text-brand-700 hover:underline">
                  {t.key}
                </Link>
              </span>
              <span className="text-xs text-slate-600">{t.title}</span>
            </Td>
            <Td>{t.plant_code}</Td>
            <Td className="text-xs">
              {t.service_name}
              <span className="block text-slate-400">{t.provider_name}</span>
            </Td>
            <Td className="whitespace-nowrap text-xs">
              {formatMinutes(t.resolution_business_min ?? t.resolution_elapsed_min)} (
              {formatMinutes(t.resolution_target_min)})
              {t.resolution_breached && <span className="block text-red-700">resolution breached</span>}
              {t.response_breached && <span className="block text-red-700">response breached</span>}
            </Td>
          </tr>
        ))}
      </tbody>
    </TableWrap>
  );
}

function ImprovementList({ items, empty }: { items: Improvement[]; empty: string }) {
  if (!items.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <ul className="space-y-2 text-sm">
      {items.map((i) => (
        <li key={i.id}>
          <span className="font-medium">{i.title}</span>
          <span className="ml-2 inline-flex items-center gap-2 text-xs text-slate-500">
            <StatusBadge status={i.status} /> {i.owner} · due {formatDate(i.due_date)}
            {i.overdue && <span className="font-semibold text-red-700">overdue</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Report() {
  const meta = useMeta();
  const [month, setMonth] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<unknown>(null);
  const selected = month || previousMonth(meta.data?.demo_now);
  const report = useApi<MonthlyReport>(meta.data ? `/reports/monthly?month=${selected}` : null);

  const excel = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      await download(`/reports/monthly.xlsx?month=${selected}`, `service-review-${selected}.xlsx`);
    } catch (e) {
      setDownloadError(e);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <>
      <PageTitle
        title={`Monthly service review – ${monthLabel(selected)}`}
        subtitle={
          <>
            Valdora Machinery Group · all plants and providers
            {report.data?.is_partial ? " · month to date" : ""} · generated from ServiceQualityHub (fictional demo data)
          </>
        }
        actions={
          <>
            <Select
              label="Month"
              value={selected}
              onChange={setMonth}
              options={recentMonths(meta.data?.demo_now).map((m) => ({ value: m, label: monthLabel(m) }))}
            />
            <Button onClick={() => window.print()} data-testid="print">
              Print / Save as PDF
            </Button>
            <Button variant="primary" onClick={excel} disabled={downloading} data-testid="download-excel">
              {downloading ? "Preparing…" : "Download Excel (.xlsx)"}
            </Button>
          </>
        }
      />
      <ErrorMessage error={report.error ?? downloadError} />
      {!report.data ? (
        <Loading text="Generating the monthly service review…" />
      ) : (
        <div className="space-y-6" data-testid="monthly-report">
          <Section n={1} title="Summary">
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {report.data.summary.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </Section>

          <Section n={2} title="KPIs against targets">
            <TableWrap>
              <thead className="bg-slate-50">
                <tr>
                  <Th>KPI</Th>
                  <Th>Value</Th>
                  <Th>Target</Th>
                  <Th>Previous month</Th>
                  {report.data.trend.months.map((m) => (
                    <Th key={m}>{shortMonth(m)}</Th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {report.data.kpis.map((k) => (
                  <tr key={k.key}>
                    <Td className="font-medium">{k.name}</Td>
                    <Td>
                      <RagBadge rag={k.rag}>{formatValue(k.value, k.unit)}</RagBadge>
                    </Td>
                    <Td className="text-xs text-slate-500">{k.target_text}</Td>
                    <Td className="text-xs">{formatValue(k.previous, k.unit)}</Td>
                    {report.data!.trend.series[k.key].map((v, i) => (
                      <Td key={i} className="text-xs text-slate-600">
                        {formatValue(v, k.unit)}
                      </Td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </TableWrap>
            <div className="mt-3">
              <RagLegend />
            </div>
          </Section>

          <div className="grid gap-6 lg:grid-cols-2">
            <Section n={3} title="Plants">
              <TableWrap>
                <thead className="bg-slate-50">
                  <tr>
                    <Th>Plant</Th>
                    <Th>Resolution</Th>
                    <Th>Response</Th>
                    <Th>MTTR</Th>
                    <Th>&gt;30 d</Th>
                    <Th>Changes</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {report.data.plants.map((p) => (
                    <tr key={p.plant_id}>
                      <Td className="font-medium">{p.plant_name}</Td>
                      {(
                        [
                          ["sla_resolution", "%"],
                          ["sla_response", "%"],
                          ["mttr", "h"],
                          ["backlog_over_30", "tickets"],
                          ["change_success", "%"],
                        ] as const
                      ).map(([key, unit]) => (
                        <Td key={key}>
                          <span className="flex items-center gap-1 whitespace-nowrap text-xs">
                            <RagDot rag={p.rag[key]} />
                            {formatValue(p.values[key], unit)}
                          </span>
                        </Td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </TableWrap>
            </Section>
            <Section n={4} title="Supplier scorecards">
              <TableWrap>
                <thead className="bg-slate-50">
                  <tr>
                    <Th>Provider</Th>
                    <Th>Agreement</Th>
                    <Th>Resolution</Th>
                    <Th>Breaches</Th>
                    <Th>Trend</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {report.data.suppliers.map((s) => (
                    <tr key={s.provider_id}>
                      <Td className="text-sm">{s.name}</Td>
                      <Td className="text-xs">
                        {s.agreement} {s.target_pct} %
                      </Td>
                      <Td>
                        <RagBadge rag={s.rag}>{formatValue(s.resolution_compliance, "%")}</RagBadge>
                      </Td>
                      <Td>{s.breaches}</Td>
                      <Td>
                        <TrendArrow trend={s.trend} />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </TableWrap>
            </Section>
          </div>

          <Section n={5} title="Top 10 SLA breaches" className="print-break">
            <SmallTickets tickets={report.data.top_breaches} empty="No SLA breaches this month." />
          </Section>

          <Section n={6} title="P1 / major incidents">
            <SmallTickets tickets={report.data.major_incidents} empty="No P1 incidents this month." />
          </Section>

          <Section n={7} title="Problems and problem candidates">
            <ul className="space-y-2 text-sm">
              {report.data.problems.map((p) => (
                <li key={p.id}>
                  <Link href={`/tickets/${p.id}`} className="font-medium text-brand-700 hover:underline">
                    {p.key}
                  </Link>{" "}
                  {p.title} <StatusBadge status={p.problem_status} />
                  {p.root_cause && <span className="block text-xs text-slate-500">Root cause: {p.root_cause}</span>}
                </li>
              ))}
            </ul>
            <p className="mt-4 text-xs font-semibold uppercase text-slate-500">Candidates at the end of the month</p>
            {report.data.problem_candidates.length === 0 ? (
              <p className="text-sm text-slate-500">No recurring incidents.</p>
            ) : (
              <ul className="mt-1 text-sm">
                {report.data.problem_candidates.map((c) => (
                  <li key={`${c.plant_code}-${c.service_name}-${c.category}`}>
                    {c.count} × &ldquo;{c.category}&rdquo; – {c.service_name} at {c.plant_code} (last{" "}
                    {formatDateTime(c.last_seen)})
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section n={8} title="Changes">
            <p className="mb-3 text-sm">
              Change success rate{" "}
              <RagBadge rag={report.data.changes.rag}>{formatValue(report.data.changes.success_rate, "%")}</RagBadge> ·{" "}
              {report.data.changes.successful} of {report.data.changes.completed} completed changes successful.
            </p>
            {report.data.changes.not_successful.length > 0 && (
              <ul className="space-y-1 text-sm">
                {report.data.changes.not_successful.map((c) => (
                  <li key={c.id}>
                    <Link href={`/tickets/${c.id}`} className="font-medium text-brand-700 hover:underline">
                      {c.key}
                    </Link>{" "}
                    {c.title} · {c.plant_code} · {formatDateTime(c.planned_start)} <StatusBadge status={c.outcome} />
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section n={9} title="Improvement register">
            <div className="grid gap-6 lg:grid-cols-3">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                  Open ({report.data.improvements.open.length})
                </p>
                <ImprovementList items={report.data.improvements.open} empty="Nothing open." />
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Done this month</p>
                <ImprovementList items={report.data.improvements.done_in_month} empty="Nothing finished this month." />
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase text-red-700">Overdue</p>
                <ImprovementList items={report.data.improvements.overdue} empty="Nothing overdue." />
              </div>
            </div>
          </Section>

          <Section n={10} title="Actions for next month">
            <ol className="list-decimal space-y-1 pl-5 text-sm" data-testid="next-actions">
              {report.data.next_actions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ol>
          </Section>

          <Card title="Resolution SLA trend" className="no-print">
            <TrendChart
              months={report.data.trend.months}
              series={[{ name: "Resolution SLA", values: report.data.trend.series.sla_resolution }]}
              target={95}
            />
          </Card>
          <p className="text-xs text-slate-400">
            Report for {label("sqm")} · same month, same numbers: the report only reads stored SLA results.
          </p>
        </div>
      )}
    </>
  );
}
