"use client";

import { useState } from "react";
import AppShell from "@/components/AppShell";
import TicketTable from "@/components/TicketTable";
import { Button, Card, ErrorMessage, Loading, PageTitle, Select } from "@/components/ui";
import { useApi, usePlants, useServices } from "@/lib/hooks";
import type { TicketPage } from "@/lib/types";

const PAGE_SIZE = 25;

export default function TicketsPage() {
  return (
    <AppShell>
      <Tickets />
    </AppShell>
  );
}

function Tickets() {
  const plants = usePlants().data ?? [];
  const services = useServices().data ?? [];
  const [filters, setFilters] = useState({ type: "", plant_id: "", service_id: "", priority: "", state: "", q: "" });
  const [page, setPage] = useState(1);
  const set = (key: keyof typeof filters) => (value: string) => {
    setFilters({ ...filters, [key]: value });
    setPage(1);
  };

  const params = new URLSearchParams({ page: String(page), size: String(PAGE_SIZE) });
  for (const key of ["type", "plant_id", "service_id", "priority", "q"] as const) {
    if (filters[key]) params.set(key, filters[key]);
  }
  if (filters.state === "open") params.set("open", "true");
  if (filters.state === "risk") params.set("sla", "at_risk,breached");
  if (filters.state === "breached") params.set("breached", "true");
  const tickets = useApi<TicketPage>(`/tickets?${params}`);
  const pages = tickets.data ? Math.max(1, Math.ceil(tickets.data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <PageTitle
        title="Tickets"
        subtitle="Incidents and service requests from all plants, with the SLA target frozen at creation and the measured result."
      />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Select
          label="Type"
          value={filters.type}
          onChange={set("type")}
          options={[
            { value: "", label: "Incidents & requests" },
            { value: "incident", label: "Incidents" },
            { value: "request", label: "Service requests" },
          ]}
        />
        <Select
          label="Plant"
          value={filters.plant_id}
          onChange={set("plant_id")}
          options={[{ value: "", label: "All plants" }, ...plants.map((p) => ({ value: String(p.id), label: p.name }))]}
        />
        <Select
          label="Service"
          value={filters.service_id}
          onChange={set("service_id")}
          options={[
            { value: "", label: "All services" },
            ...services.map((s) => ({ value: String(s.id), label: s.name })),
          ]}
        />
        <Select
          label="Priority"
          value={filters.priority}
          onChange={set("priority")}
          options={[{ value: "", label: "All" }, ...[1, 2, 3, 4].map((p) => ({ value: String(p), label: `P${p}` }))]}
        />
        <Select
          label="SLA"
          value={filters.state}
          onChange={set("state")}
          testId="filter-sla"
          options={[
            { value: "", label: "All tickets" },
            { value: "open", label: "Open" },
            { value: "risk", label: "Open: at risk or breached" },
            { value: "breached", label: "Breached (any time)" },
          ]}
        />
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
          Search
          <input
            value={filters.q}
            onChange={(e) => set("q")(e.target.value)}
            placeholder="Key or title"
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm text-slate-800"
          />
        </label>
      </div>
      <Card title={tickets.data ? `${tickets.data.total} tickets` : "Tickets"}>
        <ErrorMessage error={tickets.error} />
        {tickets.data ? <TicketTable tickets={tickets.data.items} /> : <Loading />}
        <div className="mt-4 flex items-center justify-end gap-2 text-sm">
          <Button disabled={page <= 1} onClick={() => setPage(page - 1)}>
            ← Previous
          </Button>
          <span className="text-slate-500">
            Page {page} of {pages}
          </span>
          <Button disabled={page >= pages} onClick={() => setPage(page + 1)}>
            Next →
          </Button>
        </div>
      </Card>
    </>
  );
}
