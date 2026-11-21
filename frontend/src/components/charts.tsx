"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { shortMonth } from "@/lib/format";

const BRAND = "#255a96";
const RAG_FILL = { green: "#10b981", amber: "#f59e0b", red: "#ef4444", no_data: "#cbd5e1" };

/** Tiny line for KPI cards (last six months). */
export function Sparkline({ values }: { values: (number | null)[] }) {
  const data = values.map((v, i) => ({ i, v }));
  return (
    <div className="h-10 w-full" aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={BRAND}
            strokeWidth={2}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
          <YAxis hide domain={["auto", "auto"]} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Six-month trend with an optional target line. */
export function TrendChart({
  months,
  series,
  target,
  unit = "%",
  height = 220,
}: {
  months: string[];
  series: { name: string; values: (number | null)[]; color?: string }[];
  target?: number;
  unit?: string;
  height?: number;
}) {
  const data = months.map((m, i) => ({
    month: shortMonth(m),
    ...Object.fromEntries(series.map((s) => [s.name, s.values[i]])),
  }));
  const colors = [BRAND, "#0f766e", "#9333ea"];
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="month" tick={{ fontSize: 12 }} />
          <YAxis
            tick={{ fontSize: 12 }}
            domain={unit === "%" ? [(min: number) => Math.max(0, Math.floor(min - 5)), 100] : ["auto", "auto"]}
          />
          <Tooltip formatter={(value) => (typeof value === "number" ? `${value.toFixed(1)} ${unit}` : String(value))} />
          {target !== undefined && (
            <ReferenceLine
              y={target}
              stroke="#ef4444"
              strokeDasharray="6 4"
              label={{ value: `target ${target}`, fontSize: 11, fill: "#b91c1c", position: "insideBottomRight" }}
            />
          )}
          {series.map((s, i) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name}
              stroke={s.color ?? colors[i % colors.length]}
              strokeWidth={2.5}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal bars: compliance per provider, coloured by RAG, with each provider's own target in the tooltip. */
export function ComplianceBars({
  rows,
}: {
  rows: { name: string; value: number | null; target: number; rag: keyof typeof RAG_FILL }[];
}) {
  const data = rows.map((r) => ({ ...r, value: r.value ?? 0 }));
  return (
    <div style={{ height: Math.max(180, rows.length * 34) }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="name" width={170} tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value, _name, item) => [
              `${Number(value).toFixed(1)} % (target ${(item.payload as { target: number }).target} %)`,
              "Resolution SLA",
            ]}
          />
          <Bar dataKey="value" isAnimationActive={false} radius={[0, 4, 4, 0]}>
            {data.map((d) => (
              <Cell key={d.name} fill={RAG_FILL[d.rag]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
