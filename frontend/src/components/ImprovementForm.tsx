"use client";

import { useState } from "react";
import { Button, ErrorMessage } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useApiMutation, usePlants, useServices } from "@/lib/hooks";
import type { Improvement } from "@/lib/types";

export interface ImprovementDraft {
  title?: string;
  description?: string;
  source?: string;
  service_id?: number | null;
  plant_id?: number | null;
  provider_id?: number | null;
  kpi?: string | null;
  kpi_baseline?: number | null;
  kpi_target?: number | null;
}

const input = "w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm";

/** Add an item to the improvement (CSI) register, optionally pre-filled from a scorecard or a problem. */
export default function ImprovementForm({ draft = {}, onDone }: { draft?: ImprovementDraft; onDone: () => void }) {
  const { user } = useAuth();
  const plants = usePlants().data ?? [];
  const services = useServices().data ?? [];
  const create = useApiMutation<Record<string, unknown>, Improvement>("POST", "/improvements");
  const [form, setForm] = useState({
    title: draft.title ?? "",
    description: draft.description ?? "",
    source: draft.source ?? "service_review",
    service_id: draft.service_id ? String(draft.service_id) : "",
    plant_id: user?.role === "plant_lead" ? String(user.plant_id) : draft.plant_id ? String(draft.plant_id) : "",
    owner: user?.full_name ?? "",
    due_date: "",
    expected_benefit: "",
  });
  const set =
    (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm({ ...form, [field]: e.target.value });

  return (
    <form
      className="grid gap-3 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate(
          {
            ...form,
            service_id: form.service_id ? Number(form.service_id) : null,
            plant_id: form.plant_id ? Number(form.plant_id) : null,
            provider_id: draft.provider_id ?? null,
            due_date: form.due_date || null,
            kpi: draft.kpi ?? null,
            kpi_baseline: draft.kpi_baseline ?? null,
            kpi_target: draft.kpi_target ?? null,
          },
          { onSuccess: onDone },
        );
      }}
    >
      <label className="text-xs font-medium text-slate-500 sm:col-span-2">
        Title
        <input
          required
          minLength={3}
          value={form.title}
          onChange={set("title")}
          className={input}
          data-testid="improvement-title"
        />
      </label>
      <label className="text-xs font-medium text-slate-500 sm:col-span-2">
        What will change and why
        <textarea rows={2} value={form.description} onChange={set("description")} className={input} />
      </label>
      <label className="text-xs font-medium text-slate-500">
        Source
        <select value={form.source} onChange={set("source")} className={input}>
          <option value="service_review">Service review</option>
          <option value="kpi_breach">KPI breach</option>
          <option value="problem">Problem</option>
          <option value="idea">Idea</option>
        </select>
      </label>
      <label className="text-xs font-medium text-slate-500">
        Owner
        <input required minLength={2} value={form.owner} onChange={set("owner")} className={input} />
      </label>
      <label className="text-xs font-medium text-slate-500">
        Service
        <select value={form.service_id} onChange={set("service_id")} className={input}>
          <option value="">–</option>
          {services.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs font-medium text-slate-500">
        Plant
        <select
          value={form.plant_id}
          onChange={set("plant_id")}
          className={input}
          disabled={user?.role === "plant_lead"}
        >
          <option value="">All plants</option>
          {plants.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <label className="text-xs font-medium text-slate-500">
        Due date
        <input type="date" value={form.due_date} onChange={set("due_date")} className={input} />
      </label>
      <label className="text-xs font-medium text-slate-500">
        Expected benefit
        <input value={form.expected_benefit} onChange={set("expected_benefit")} className={input} />
      </label>
      {draft.kpi && (
        <p className="text-xs text-slate-500 sm:col-span-2">
          Linked KPI: {draft.kpi} · baseline {draft.kpi_baseline ?? "–"} · target {draft.kpi_target ?? "–"}
        </p>
      )}
      <div className="flex items-center gap-2 sm:col-span-2">
        <Button type="submit" variant="primary" disabled={create.isPending} data-testid="improvement-save">
          {create.isPending ? "Saving…" : "Add to register"}
        </Button>
        <Button type="button" onClick={onDone}>
          Cancel
        </Button>
        <ErrorMessage error={create.error} />
      </div>
    </form>
  );
}
