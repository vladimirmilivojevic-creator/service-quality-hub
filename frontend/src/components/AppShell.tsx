"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { formatDateTime, label } from "@/lib/format";
import { useMeta, useSimulateDay } from "@/lib/hooks";
import type { Role, SimulationResult } from "@/lib/types";

const STAFF: Role[] = ["sqm", "plant_lead", "management"];
const NAV: { href: string; label: string; roles: Role[] }[] = [
  { href: "/", label: "Dashboard", roles: STAFF },
  { href: "/catalogue", label: "Catalogue", roles: STAFF },
  { href: "/tickets", label: "Tickets", roles: STAFF },
  { href: "/suppliers", label: "Suppliers", roles: STAFF },
  { href: "/problems", label: "Problems", roles: STAFF },
  { href: "/changes", label: "Changes", roles: STAFF },
  { href: "/improvements", label: "Improvements", roles: STAFF },
  { href: "/reports/monthly", label: "Monthly review", roles: STAFF },
  { href: "/import", label: "Import", roles: ["sqm"] },
  { href: "/how-it-works", label: "How it works", roles: [...STAFF, "supplier"] },
];

export function FictionBanner() {
  return (
    <div className="no-print bg-slate-900 px-4 py-1.5 text-center text-xs text-slate-200">
      Demo of a fictional company (Valdora Machinery Group). All plants, people, suppliers and numbers are invented.
    </div>
  );
}

/** Layout for logged-in pages: navigation filtered by role, demo clock, redirect to /login if needed. */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const meta = useMeta();
  const simulate = useSimulateDay();
  const [result, setResult] = useState<SimulationResult | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!result) return;
    const timer = setTimeout(() => setResult(null), 9000);
    return () => clearTimeout(timer);
  }, [result]);

  if (loading || !user) return <div className="p-10 text-sm text-slate-400">Loading…</div>;

  const links =
    user.role === "supplier"
      ? [{ href: `/suppliers/${user.provider_id}`, label: "Our scorecard" }, NAV[NAV.length - 1]]
      : NAV.filter((n) => n.roles.includes(user.role));

  return (
    <div className="min-h-screen">
      <FictionBanner />
      <header className="no-print border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <Link
            href={user.role === "supplier" ? `/suppliers/${user.provider_id}` : "/"}
            className="flex items-center gap-2 font-semibold"
          >
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-sm text-white">SQ</span>
            ServiceQualityHub
          </Link>
          <div className="ml-auto flex flex-wrap items-center gap-3 text-sm">
            {meta.data && (
              <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600" data-testid="demo-clock">
                Demo clock: {formatDateTime(meta.data.demo_now)}
              </span>
            )}
            {user.role !== "supplier" && (
              <button
                data-testid="simulate"
                disabled={simulate.isPending}
                onClick={() => simulate.mutate(undefined, { onSuccess: setResult })}
                className="rounded-md border border-brand-600 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-50"
                title="Moves the demo clock one day forward and creates that day's tickets, resolutions and changes"
              >
                {simulate.isPending ? "Simulating…" : "Simulate next day ▶"}
              </button>
            )}
            <div className="text-right leading-tight">
              <p className="font-medium" data-testid="current-user">
                {user.full_name}
              </p>
              <p className="text-xs text-slate-500">
                {label(user.role)}
                {user.plant_code ? ` · ${user.plant_code}` : ""}
              </p>
            </div>
            <button
              onClick={() => {
                logout();
                router.replace("/login");
              }}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-slate-600 hover:bg-slate-50"
            >
              Log out
            </button>
          </div>
          <nav className="flex w-full flex-wrap gap-1">
            {links.map((link) => {
              const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-1.5 text-sm ${active ? "bg-brand-50 font-medium text-brand-700" : "text-slate-600 hover:bg-slate-100"}`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      {result && (
        <div
          role="status"
          data-testid="simulation-result"
          className="no-print fixed bottom-4 right-4 z-40 max-w-sm rounded-xl border border-brand-100 bg-white p-4 text-sm shadow-xl"
        >
          <p className="mb-1 font-semibold text-brand-700">A new day in the demo</p>
          <ul className="list-disc space-y-1 pl-4 text-slate-600">
            {result.messages.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  );
}
