"use client";

import { useState } from "react";
import AppShell from "@/components/AppShell";
import ImprovementForm from "@/components/ImprovementForm";
import {
  Button,
  Card,
  ErrorMessage,
  Loading,
  PageTitle,
  Select,
  StatusBadge,
  TableWrap,
  Td,
  Th,
} from "@/components/ui";
import { canEdit, useAuth } from "@/lib/auth";
import { formatDate, label } from "@/lib/format";
import { useApi, useApiMutation } from "@/lib/hooks";
import type { Improvement } from "@/lib/types";

const STATUSES = ["proposed", "approved", "in_progress", "done", "rejected"];

export default function ImprovementsPage() {
  return (
    <AppShell>
      <Improvements />
    </AppShell>
  );
}

function StatusSelect({ item }: { item: Improvement }) {
  const update = useApiMutation<{ status: string }, Improvement>("PATCH", `/improvements/${item.id}`);
  return (
    <select
      aria-label={`Status of ${item.title}`}
      value={item.status}
      disabled={update.isPending}
      onChange={(e) => update.mutate({ status: e.target.value })}
      className="rounded border border-slate-300 bg-white px-1.5 py-1 text-xs"
    >
      {STATUSES.map((s) => (
        <option key={s} value={s}>
          {label(s)}
        </option>
      ))}
    </select>
  );
}

function Improvements() {
  const { user } = useAuth();
  const [status, setStatus] = useState("");
  const [adding, setAdding] = useState(false);
  const items = useApi<Improvement[]>(
    `/improvements${status === "overdue" ? "?overdue=true" : status ? `?status=${status}` : ""}`,
  );
  const all = useApi<Improvement[]>("/improvements");
  const counts = {
    open: (all.data ?? []).filter((i) => !["done", "rejected"].includes(i.status)).length,
    overdue: (all.data ?? []).filter((i) => i.overdue).length,
    done: (all.data ?? []).filter((i) => i.status === "done").length,
  };
  const mayAdd = user?.role === "sqm" || user?.role === "plant_lead";

  return (
    <>
      <PageTitle
        title="Improvement register (CSI)"
        subtitle="Every corrective action from service reviews, KPI breaches and problems, with an owner, a due date and the KPI it should move. Overdue actions are followed up in the next service review."
        actions={
          mayAdd && (
            <Button variant="primary" onClick={() => setAdding(true)} data-testid="new-improvement">
              New improvement
            </Button>
          )
        }
      />
      <div className="mb-4 flex flex-wrap items-end gap-6">
        <Select
          label="Show"
          value={status}
          onChange={setStatus}
          options={[
            { value: "", label: "All" },
            { value: "overdue", label: "Overdue" },
            ...STATUSES.map((s) => ({ value: s, label: label(s) })),
          ]}
        />
        <p className="text-sm text-slate-600">
          <strong>{counts.open}</strong> open · <strong className="text-red-700">{counts.overdue}</strong> overdue ·{" "}
          <strong>{counts.done}</strong> done
        </p>
      </div>
      {adding && (
        <Card className="mb-6" title="New improvement">
          <ImprovementForm onDone={() => setAdding(false)} />
        </Card>
      )}
      <Card>
        <ErrorMessage error={items.error} />
        {!items.data ? (
          <Loading />
        ) : (
          <TableWrap>
            <thead className="bg-slate-50">
              <tr>
                <Th>Improvement</Th>
                <Th>Source</Th>
                <Th>Scope</Th>
                <Th>Owner</Th>
                <Th>Due</Th>
                <Th>KPI (baseline → target)</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100" data-testid="improvement-table">
              {items.data.map((i) => (
                <tr key={i.id} className={i.overdue ? "bg-red-50/50" : ""}>
                  <Td className="max-w-md">
                    <p className="font-medium">{i.title}</p>
                    <p className="text-xs text-slate-500">{i.description}</p>
                    {i.expected_benefit && (
                      <p className="mt-1 text-xs text-emerald-700">Benefit: {i.expected_benefit}</p>
                    )}
                  </Td>
                  <Td className="text-xs">{label(i.source)}</Td>
                  <Td className="text-xs">
                    {[i.plant_code, i.service_name, i.provider_name].filter(Boolean).join(" · ") || "All plants"}
                  </Td>
                  <Td className="text-xs">{i.owner}</Td>
                  <Td className="whitespace-nowrap text-xs">
                    {formatDate(i.due_date)}
                    {i.overdue && <span className="block font-semibold text-red-700">overdue</span>}
                  </Td>
                  <Td className="text-xs">
                    {i.kpi ? `${i.kpi}: ${i.kpi_baseline ?? "–"} → ${i.kpi_target ?? "–"}` : "–"}
                  </Td>
                  <Td>{canEdit(user, i.plant_id) ? <StatusSelect item={i} /> : <StatusBadge status={i.status} />}</Td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>
    </>
  );
}
