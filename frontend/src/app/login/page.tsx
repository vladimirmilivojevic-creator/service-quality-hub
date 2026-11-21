"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { FictionBanner } from "@/components/AppShell";
import { API_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const DEMO_USERS = [
  {
    email: "sqm@valdora.example",
    role: "Service Quality Manager",
    sees: "Everything: catalogue, SLA policies, CSV import, improvements, monthly review",
  },
  {
    email: "it.innfeld@valdora.example",
    role: "Plant IT Lead – Innfeld",
    sees: "All KPIs; changes tickets, problems and improvements of the Innfeld plant",
  },
  {
    email: "cio@valdora.example",
    role: "IT Management (read-only)",
    sees: "Dashboard, scorecards and the monthly review",
  },
  { email: "supplier.alpnet@valdora.example", role: "Supplier – AlpNet Carrier", sees: "Only its own scorecard" },
];
const PASSWORD = "demo1234";

/** The free API server sleeps when nobody uses it; this shows when it is awake. */
function ApiStatus() {
  const [state, setState] = useState<"checking" | "online" | "waking">("checking");
  useEffect(() => {
    let stopped = false;
    const ping = async () => {
      try {
        const response = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(8000) });
        if (!stopped) setState(response.ok ? "online" : "waking");
        if (!response.ok && !stopped) setTimeout(ping, 4000);
      } catch {
        if (!stopped) {
          setState("waking");
          setTimeout(ping, 4000);
        }
      }
    };
    ping();
    return () => {
      stopped = true;
    };
  }, []);
  const style = {
    checking: "bg-slate-100 text-slate-600",
    online: "bg-emerald-100 text-emerald-800",
    waking: "bg-amber-100 text-amber-800",
  }[state];
  const text = {
    checking: "Checking the API…",
    online: "API online",
    waking: "Waking up the free API server (up to a minute)…",
  }[state];
  return (
    <span data-testid="api-status" className={`rounded-full px-3 py-1 text-xs font-medium ${style}`}>
      {text}
    </span>
  );
}

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const signIn = async (address: string, secret: string) => {
    setBusy(true);
    setError("");
    try {
      const me = await login(address, secret);
      router.replace(me.role === "supplier" ? `/suppliers/${me.provider_id}` : "/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen">
      <FictionBanner />
      <div className="mx-auto grid max-w-5xl gap-10 px-4 py-12 md:grid-cols-2">
        <div>
          <div className="mb-6 flex items-center gap-2 text-lg font-semibold">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand-600 text-sm text-white">SQ</span>
            ServiceQualityHub
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">One set of SLA numbers for every plant</h1>
          <p className="mt-3 text-slate-600">
            Service catalogue, SLA engine, KPIs, supplier scorecards, problem candidates, improvement register and a
            monthly service review in one click — for the five plants of a fictional machinery manufacturer.
          </p>
          <ul className="mt-6 space-y-2 text-sm text-slate-600">
            <li>• The SLA clock only runs in each service&apos;s support hours, in the plant&apos;s local time.</li>
            <li>• The central IT provider, the plant IT teams and external vendors are measured the same way.</li>
            <li>• &quot;Simulate next day&quot; moves the demo clock so you can watch things happen.</li>
          </ul>
          <p className="mt-6 text-sm">
            <Link href="/how-it-works" className="font-medium text-brand-700 hover:underline">
              How it works (rules, formulas, ITIL practices) →
            </Link>
          </p>
          <div className="mt-6">
            <ApiStatus />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold">Log in with a demo account</h2>
          <p className="mb-4 text-xs text-slate-500">Every demo account uses the password {PASSWORD}.</p>
          <div className="space-y-2">
            {DEMO_USERS.map((u) => (
              <button
                key={u.email}
                disabled={busy}
                onClick={() => signIn(u.email, PASSWORD)}
                className="w-full rounded-lg border border-slate-200 p-3 text-left hover:border-brand-500 hover:bg-brand-50 disabled:opacity-50"
              >
                <span className="block text-sm font-medium">Log in as {u.role}</span>
                <span className="block text-xs text-slate-500">{u.sees}</span>
              </button>
            ))}
          </div>
          <form
            className="mt-6 space-y-2 border-t border-slate-100 pt-4"
            onSubmit={(e) => {
              e.preventDefault();
              signIn(email, password);
            }}
          >
            <p className="text-xs font-medium text-slate-500">Or type an email and password</p>
            <input
              aria-label="Email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="sqm@valdora.example"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <input
              aria-label="Password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              Log in
            </button>
            {error && <p className="text-sm text-red-700">{error}</p>}
          </form>
        </div>
      </div>
    </div>
  );
}
