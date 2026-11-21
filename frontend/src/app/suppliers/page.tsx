"use client";

import Link from "next/link";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import { ComplianceBars } from "@/components/charts";
import {
  Card,
  ErrorMessage,
  Loading,
  PageTitle,
  RagBadge,
  RagLegend,
  Select,
  TableWrap,
  Td,
  Th,
  TrendArrow,
} from "@/components/ui";
import { formatValue, label, monthLabel, previousMonth, recentMonths } from "@/lib/format";
import { useApi, useMeta } from "@/lib/hooks";
import type { Scorecard } from "@/lib/types";

export default function SuppliersPage() {
  return (
    <AppShell>
      <Suppliers />
    </AppShell>
  );
}

function Suppliers() {
  const meta = useMeta();
  const [month, setMonth] = useState("");
  const selected = month || previousMonth(meta.data?.demo_now);
  const data = useApi<{ month: string; is_partial: boolean; rows: Scorecard[] }>(
    meta.data ? `/suppliers?month=${selected}` : null,
  );

  return (
    <>
      <PageTitle
        title="Supplier scorecards"
        subtitle="The central IT provider and the plant IT teams are measured against their OLA, external vendors against their contract — all with the same SLA engine, so the numbers are comparable."
        actions={
          <Select
            label="Month"
            value={selected}
            onChange={setMonth}
            options={recentMonths(meta.data?.demo_now).map((m) => ({ value: m, label: monthLabel(m) }))}
          />
        }
      />
      <ErrorMessage error={data.error} />
      {!data.data ? (
        <Loading />
      ) : (
        <div className="space-y-6">
          <Card
            title={`Resolution SLA compliance against each agreement – ${monthLabel(data.data.month)}`}
            info={`Green: at or above the agreed target. Amber: up to ${5} points below. Red: further below.`}
          >
            <ComplianceBars
              rows={data.data.rows.map((r) => ({
                name: r.name,
                value: r.resolution_compliance,
                target: r.target_pct,
                rag: r.rag,
              }))}
            />
            <div className="mt-2">
              <RagLegend />
            </div>
          </Card>
          <Card title="All providers side by side">
            <TableWrap>
              <thead className="bg-slate-50">
                <tr>
                  <Th>Provider</Th>
                  <Th>Agreement</Th>
                  <Th>Tickets</Th>
                  <Th>Resolution SLA</Th>
                  <Th>Response SLA</Th>
                  <Th>MTTR</Th>
                  <Th>Breaches</Th>
                  <Th>P1</Th>
                  <Th>Trend</Th>
                  <Th>Top services with breaches</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100" data-testid="scorecard-table">
                {data.data.rows.map((r) => (
                  <tr key={r.provider_id} className="hover:bg-slate-50">
                    <Td>
                      <Link href={`/suppliers/${r.provider_id}`} className="font-medium text-brand-700 hover:underline">
                        {r.name}
                      </Link>
                      <span className="block text-xs text-slate-400">{label(r.kind)}</span>
                    </Td>
                    <Td className="text-xs">
                      {r.agreement} · target {r.target_pct} %
                      <span className="block text-slate-400">{r.contract_ref}</span>
                    </Td>
                    <Td>{r.tickets}</Td>
                    <Td>
                      <RagBadge rag={r.rag}>{formatValue(r.resolution_compliance, "%")}</RagBadge>
                    </Td>
                    <Td>{formatValue(r.response_compliance, "%")}</Td>
                    <Td>{formatValue(r.mttr_hours, "h")}</Td>
                    <Td>{r.breaches}</Td>
                    <Td>{r.p1_incidents}</Td>
                    <Td>
                      <TrendArrow trend={r.trend} />
                    </Td>
                    <Td className="text-xs">
                      {r.top_breach_services.map((s) => `${s.service} (${s.breaches})`).join(", ") || "–"}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </Card>
        </div>
      )}
    </>
  );
}
