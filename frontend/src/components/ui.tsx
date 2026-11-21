"use client";

import { useState } from "react";
import { label } from "@/lib/format";
import type { Rag } from "@/lib/types";

export function PageTitle({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="no-print flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({
  title,
  info,
  actions,
  children,
  className = "",
}: {
  title?: React.ReactNode;
  info?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`avoid-break rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
            {title}
            {info && <InfoTip>{info}</InfoTip>}
          </h2>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

const RAG_STYLE: Record<Rag, string> = {
  green: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  amber: "bg-amber-100 text-amber-800 ring-amber-600/20",
  red: "bg-red-100 text-red-800 ring-red-600/20",
  no_data: "bg-slate-100 text-slate-500 ring-slate-400/20",
};
const RAG_TEXT: Record<Rag, string> = { green: "Green", amber: "Amber", red: "Red", no_data: "No data" };

export function RagBadge({ rag, children }: { rag: Rag; children?: React.ReactNode }) {
  return (
    <span
      data-rag={rag}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${RAG_STYLE[rag]}`}
    >
      {children ?? RAG_TEXT[rag]}
    </span>
  );
}

export function RagDot({ rag }: { rag: Rag }) {
  const colour = { green: "bg-emerald-500", amber: "bg-amber-500", red: "bg-red-500", no_data: "bg-slate-300" }[rag];
  return <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${colour}`} aria-label={RAG_TEXT[rag]} />;
}

const STATUS_RAG: Record<string, Rag> = {
  on_track: "green",
  met: "green",
  at_risk: "amber",
  breached: "red",
  no_target: "no_data",
  successful: "green",
  failed: "red",
  rolled_back: "amber",
  caused_incident: "red",
  done: "green",
  rejected: "no_data",
  investigating: "amber",
  known_error: "amber",
  resolved: "green",
};

/** SLA state, change outcome or problem status as a coloured pill. */
export function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-slate-400">–</span>;
  return <RagBadge rag={STATUS_RAG[status] ?? "no_data"}>{label(status)}</RagBadge>;
}

export function PriorityBadge({ priority }: { priority: number }) {
  const style = [
    "",
    "bg-red-600 text-white",
    "bg-orange-500 text-white",
    "bg-sky-100 text-sky-800",
    "bg-slate-100 text-slate-700",
  ];
  return <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${style[priority]}`}>P{priority}</span>;
}

/** "ⓘ" with a short explanation, for people who are not IT specialists. */
export function InfoTip({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="Explain"
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setOpen(false)}
        className="grid h-5 w-5 place-items-center rounded-full text-xs font-semibold text-slate-400 hover:bg-slate-100 hover:text-slate-700"
      >
        ⓘ
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-6 z-30 w-72 rounded-lg border border-slate-200 bg-white p-3 text-left text-xs font-normal leading-relaxed text-slate-600 shadow-lg"
        >
          {children}
        </span>
      )}
    </span>
  );
}

export function Delta({
  value,
  higherIsBetter,
  unit,
}: {
  value: number | null;
  higherIsBetter: boolean;
  unit: string;
}) {
  if (value === null || value === 0) return <span className="text-xs text-slate-400">no change</span>;
  const better = higherIsBetter ? value > 0 : value < 0;
  const suffix = unit === "%" ? " pts" : unit === "h" ? " h" : "";
  return (
    <span className={`text-xs font-medium ${better ? "text-emerald-700" : "text-red-700"}`}>
      {value > 0 ? "▲" : "▼"} {Math.abs(value).toFixed(unit === "tickets" ? 0 : 1)}
      {suffix} vs last month
    </span>
  );
}

export function TrendArrow({ trend }: { trend: "up" | "down" | "flat" }) {
  if (trend === "up") return <span className="text-emerald-700">▲</span>;
  if (trend === "down") return <span className="text-red-700">▼</span>;
  return <span className="text-slate-400">▬</span>;
}

export function Loading({ text = "Loading…" }: { text?: string }) {
  return <p className="py-6 text-sm text-slate-400">{text}</p>;
}

export function ErrorMessage({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  return <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>;
}

export function Select({
  label: text,
  value,
  onChange,
  options,
  testId,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  testId?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
      {text}
      <select
        data-testid={testId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Button({
  children,
  variant = "secondary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const styles = {
    primary: "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-300",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:text-slate-400",
    danger: "border border-red-300 bg-white text-red-700 hover:bg-red-50",
  };
  return (
    <button
      {...props}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Th({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return (
    <th
      className={`whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 ${className}`}
    >
      {children}
    </th>
  );
}

export function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2 align-top text-sm ${className}`}>{children}</td>;
}

export function TableWrap({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200">{children}</table>
    </div>
  );
}

export function RagLegend() {
  return (
    <p className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
      <span className="flex items-center gap-1">
        <RagDot rag="green" /> on target
      </span>
      <span className="flex items-center gap-1">
        <RagDot rag="amber" /> close to target, watch it
      </span>
      <span className="flex items-center gap-1">
        <RagDot rag="red" /> target missed, act
      </span>
    </p>
  );
}
