"use client";

import Link from "next/link";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import {
  Card,
  ErrorMessage,
  Loading,
  PageTitle,
  RagBadge,
  Select,
  StatusBadge,
  TableWrap,
  Td,
  Th,
} from "@/components/ui";
import { formatDateTime, formatValue, monthLabel, previousMonth, recentMonths } from "@/lib/format";
import { useApi, useMeta, usePlants } from "@/lib/hooks";
import type { Rag, Ticket } from "@/lib/types";

interface ChangeMonth {
  month: string;
  success_rate: number | null;
  rag: Rag;
  completed: number;
  successful: number;
  scheduled: number;
  by_type: Record<string, number>;
  items: Ticket[];
}

export default function ChangesPage() {
  return (
    <AppShell>
      <Changes />
    </AppShell>
  );
}

function Changes() {
  const meta = useMeta();
  const plants = usePlants().data ?? [];
  const [month, setMonth] = useState("");
  const [plant, setPlant] = useState("");
  const selected = month || previousMonth(meta.data?.demo_now);
  const data = useApi<ChangeMonth>(meta.data ? `/changes?month=${selected}${plant ? `&plant_id=${plant}` : ""}` : null);

  return (
    <>
      <PageTitle
        title="Changes"
        subtitle="Change enablement: standard (pre-approved, low risk), normal (assessed and approved) and emergency changes. A change counts as successful only if it did not fail, was not rolled back and did not cause an incident."
        actions={
          <>
            <Select
              label="Month"
              value={selected}
              onChange={setMonth}
              options={recentMonths(meta.data?.demo_now).map((m) => ({ value: m, label: monthLabel(m) }))}
            />
            <Select
              label="Plant"
              value={plant}
              onChange={setPlant}
              options={[
                { value: "", label: "All plants" },
                ...plants.map((p) => ({ value: String(p.id), label: p.name })),
              ]}
            />
          </>
        }
      />
      <ErrorMessage error={data.error} />
      {!data.data ? (
        <Loading />
      ) : (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-4">
            <Card title="Change success rate">
              <RagBadge rag={data.data.rag}>{formatValue(data.data.success_rate, "%")}</RagBadge>
              <p className="mt-2 text-xs text-slate-500">target ≥ 95 %</p>
            </Card>
            <Card title="Completed">
              <p className="text-xl font-semibold">{data.data.completed}</p>
              <p className="text-xs text-slate-500">{data.data.successful} successful</p>
            </Card>
            <Card title="Scheduled">
              <p className="text-xl font-semibold">{data.data.scheduled}</p>
            </Card>
            <Card title="By type">
              <p className="text-sm">
                {Object.entries(data.data.by_type)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(" · ")}
              </p>
            </Card>
          </div>
          <Card title={`Changes – ${monthLabel(data.data.month)}`}>
            <TableWrap>
              <thead className="bg-slate-50">
                <tr>
                  <Th>Change</Th>
                  <Th>Plant</Th>
                  <Th>Service</Th>
                  <Th>Type</Th>
                  <Th>Planned window (plant time)</Th>
                  <Th>Outcome</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100" data-testid="change-table">
                {data.data.items.map((c) => (
                  <tr key={c.id} className={c.outcome && c.outcome !== "successful" ? "bg-red-50/40" : ""}>
                    <Td>
                      <Link href={`/tickets/${c.id}`} className="font-medium text-brand-700 hover:underline">
                        {c.key}
                      </Link>
                      <p className="text-xs text-slate-600">{c.title}</p>
                    </Td>
                    <Td>{c.plant_code}</Td>
                    <Td className="max-w-[12rem]">{c.service_name}</Td>
                    <Td className="capitalize">{c.change_type}</Td>
                    <Td className="whitespace-nowrap text-xs">{formatDateTime(c.planned_start)}</Td>
                    <Td>
                      {c.outcome ? (
                        <StatusBadge status={c.outcome} />
                      ) : (
                        <span className="text-xs text-slate-500">scheduled</span>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </Card>
        </>
      )}
    </>
  );
}
