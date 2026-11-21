"use client";

import { useState } from "react";
import AppShell from "@/components/AppShell";
import { Card, ErrorMessage, Loading, PageTitle, TableWrap, Td, Th } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { formatMinutes, label } from "@/lib/format";
import { useApiMutation, useServices } from "@/lib/hooks";
import type { Service } from "@/lib/types";

const TABS = [
  { value: "live", label: "Live catalogue" },
  { value: "pipeline", label: "Pipeline" },
  { value: "retired", label: "Retired" },
  { value: "", label: "Whole portfolio" },
];

export default function CataloguePage() {
  return (
    <AppShell>
      <Catalogue />
    </AppShell>
  );
}

function EditableSelect({
  service,
  field,
  options,
}: {
  service: Service;
  field: "support_hours" | "criticality" | "lifecycle";
  options: { value: string; label: string }[];
}) {
  const update = useApiMutation<Record<string, string>, Service>("PATCH", `/services/${service.id}`);
  return (
    <>
      <select
        aria-label={`${field} of ${service.name}`}
        value={service[field]}
        disabled={update.isPending}
        onChange={(e) => update.mutate({ [field]: e.target.value })}
        className="rounded border border-slate-300 bg-white px-1.5 py-1 text-xs"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ErrorMessage error={update.error} />
    </>
  );
}

function Catalogue() {
  const { user } = useAuth();
  const services = useServices();
  const [tab, setTab] = useState("live");
  const isManager = user?.role === "sqm";
  const rows = (services.data ?? []).filter((s) => !tab || s.lifecycle === tab);

  return (
    <>
      <PageTitle
        title="Service catalogue & portfolio"
        subtitle="Every IT service with its owner, provider, support hours, criticality and SLA targets per priority. The portfolio adds services in the pipeline (planned) and retired ones."
      />
      <div className="mb-4 flex flex-wrap gap-1" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.label}
            role="tab"
            aria-selected={tab === t.value}
            onClick={() => setTab(t.value)}
            className={`rounded-md px-3 py-1.5 text-sm ${tab === t.value ? "bg-brand-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <Card
        title={`${rows.length} services`}
        info="Support hours are in each plant's local time. 'Plant IT (each plant)' means every plant's own IT team delivers the service under an OLA. Targets marked * are service exceptions to the default policy."
      >
        <ErrorMessage error={services.error} />
        {!services.data ? (
          <Loading />
        ) : (
          <TableWrap>
            <thead className="bg-slate-50">
              <tr>
                <Th>Service</Th>
                <Th>Owner</Th>
                <Th>Provider</Th>
                <Th>Support hours</Th>
                <Th>Criticality</Th>
                <Th>Lifecycle</Th>
                <Th>SLA targets (response / resolution)</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100" data-testid="catalogue-table">
              {rows.map((s) => (
                <tr key={s.id}>
                  <Td className="max-w-xs">
                    <p className="font-medium">{s.name}</p>
                    <p className="text-xs text-slate-500">{s.description}</p>
                    <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-400">{s.service_type} service</p>
                  </Td>
                  <Td>
                    {s.owner_name}
                    <span className="block text-xs text-slate-400">{s.owner_email}</span>
                  </Td>
                  <Td>{s.provider_name}</Td>
                  <Td>
                    {isManager ? (
                      <EditableSelect
                        service={s}
                        field="support_hours"
                        options={[
                          { value: "24x7", label: "24x7" },
                          { value: "shift", label: "Shift Mon–Fri 06–22" },
                          { value: "office", label: "Office Mon–Fri 07–17" },
                        ]}
                      />
                    ) : (
                      s.support_hours_label
                    )}
                  </Td>
                  <Td>
                    {isManager ? (
                      <EditableSelect
                        service={s}
                        field="criticality"
                        options={["critical", "high", "medium", "low"].map((v) => ({ value: v, label: v }))}
                      />
                    ) : (
                      <span className="capitalize">{s.criticality}</span>
                    )}
                  </Td>
                  <Td>
                    {isManager ? (
                      <EditableSelect
                        service={s}
                        field="lifecycle"
                        options={["pipeline", "live", "retired"].map((v) => ({ value: v, label: label(v) }))}
                      />
                    ) : (
                      label(s.lifecycle)
                    )}
                  </Td>
                  <Td className="whitespace-nowrap text-xs">
                    {s.sla_targets.map((t) => (
                      <p key={t.priority}>
                        <span className="font-semibold">P{t.priority}</span> {formatMinutes(t.response_min)} /{" "}
                        {formatMinutes(t.resolution_min)}
                        {t.is_exception && <span className="text-brand-700"> *</span>}
                      </p>
                    ))}
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>
      {isManager && (
        <p className="mt-3 text-xs text-slate-500">
          Changes apply to new tickets only: every ticket keeps the SLA target it got when it was created.
        </p>
      )}
    </>
  );
}
