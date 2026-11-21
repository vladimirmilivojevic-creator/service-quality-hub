"use client";

import Link from "next/link";
import { FictionBanner } from "@/components/AppShell";
import { Card, ErrorMessage, Loading, RagBadge, TableWrap, Td, Th } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { formatDateTime, formatMinutes } from "@/lib/format";
import { useMeta } from "@/lib/hooks";

const ITIL_MAP = [
  ["Service catalogue & portfolio (pipeline / live / retired)", "Service catalogue management, portfolio management"],
  ["SLA targets per priority, support hours, OLA and contract targets", "Service level management"],
  ["Incidents with priority = impact × urgency and a live SLA clock", "Incident management"],
  ["Service requests (accounts, devices, restores)", "Service request management"],
  ["Problem candidates, problem records, known errors", "Problem management"],
  ["Changes (standard / normal / emergency) and change success rate", "Change enablement"],
  [
    "Supplier scorecards for the central provider, plant IT teams and vendors",
    "Supplier management, relationship management",
  ],
  ["KPI dashboard, plant comparison and trends", "Measurement and reporting"],
  ["Improvement (CSI) register with owners, due dates and KPI targets", "Continual improvement"],
  ["Monthly service review report", "Service level management, continual improvement"],
  ["Jira Service Management CSV import", "Service desk (tool integration), measurement and reporting"],
];

const REVIEW_AGENDA = [
  "Summary – 3 to 5 points a manager reads first",
  "KPIs against targets, with RAG and a six-month trend",
  "Plants side by side",
  "Supplier scorecards",
  "Top 10 SLA breaches",
  "P1 / major incidents",
  "Problems and problem candidates",
  "Changes: success rate and the ones that failed",
  "Improvement register: open, done, overdue",
  "Actions for next month",
];

export default function HowItWorksPage() {
  const meta = useMeta();
  const { user } = useAuth();
  const m = meta.data;

  return (
    <div className="min-h-screen">
      <FictionBanner />
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-sm text-white">SQ</span>
            ServiceQualityHub
          </Link>
          <Link href={user ? "/" : "/login"} className="text-sm font-medium text-brand-700 hover:underline">
            {user ? "Back to the dashboard →" : "Open the demo →"}
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-5xl space-y-6 px-4 py-8">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">How it works</h1>
          <p className="mt-2 max-w-3xl text-slate-600">
            ServiceQualityHub keeps one service catalogue, one SLA engine and one set of KPIs for the five plants of a
            fictional machinery manufacturer. The central IT provider, every plant&apos;s IT team and external vendors
            are measured the same way, so the numbers are comparable. Everything below is in plain English.
          </p>
        </div>
        <ErrorMessage error={meta.error} />
        {!m ? (
          <Loading text="Loading the rules from the API (the free server may need up to a minute to wake up)…" />
        ) : (
          <>
            <Card title="1. The SLA clock">
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                <li>
                  The clock <strong>only runs during the service&apos;s support hours</strong>, in the{" "}
                  <strong>plant&apos;s local time</strong> (Austria, Germany, France, Brazil).
                </li>
                <li>
                  It <strong>stops while we wait for the user</strong> (status &ldquo;Pending&rdquo;).
                </li>
                <li>
                  <strong>Response</strong> = time from creation to the first action by IT. <strong>Resolution</strong>{" "}
                  = time from creation to &ldquo;Resolved&rdquo;, minus the pending time.
                </li>
                <li>
                  The SLA target is <strong>frozen on the ticket when it is created</strong>. If a target changes later,
                  old tickets keep theirs, so past reports never change.
                </li>
                <li>
                  An open ticket is <RagBadge rag="green">on track</RagBadge> below {Math.round(m.at_risk_share * 100)}{" "}
                  % of the target, <RagBadge rag="amber">at risk</RagBadge> from {Math.round(m.at_risk_share * 100)} %
                  to 100 %, and <RagBadge rag="red">breached</RagBadge> above 100 %. A finished ticket exactly on target
                  counts as met.
                </li>
              </ul>
              <p className="mt-4 text-xs font-semibold uppercase text-slate-500">Support-hour calendars</p>
              <ul className="mt-1 text-sm text-slate-700">
                {m.calendars.map((c) => (
                  <li key={c.code}>• {c.label}</li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate-500">
                Public holidays are not part of this version. Demo clock now: {formatDateTime(m.demo_now)} (Vienna).
              </p>
            </Card>

            <Card title="2. Priority = impact × urgency, and the default SLA policy">
              <div className="grid gap-6 md:grid-cols-2">
                <TableWrap>
                  <thead className="bg-slate-50">
                    <tr>
                      <Th>Impact ↓ / Urgency →</Th>
                      <Th>High</Th>
                      <Th>Medium</Th>
                      <Th>Low</Th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100" data-testid="priority-matrix">
                    {["high", "medium", "low"].map((impact) => (
                      <tr key={impact}>
                        <Td className="font-medium capitalize">{impact}</Td>
                        {["high", "medium", "low"].map((urgency) => (
                          <Td key={urgency}>
                            P{m.priority_matrix.find((c) => c.impact === impact && c.urgency === urgency)?.priority}
                          </Td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </TableWrap>
                <TableWrap>
                  <thead className="bg-slate-50">
                    <tr>
                      <Th>Priority</Th>
                      <Th>First response</Th>
                      <Th>Resolution</Th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {m.priorities.map((p) => (
                      <tr key={p.priority}>
                        <Td>
                          <span className="font-medium">{p.label}</span>
                          <span className="block text-xs text-slate-500">{p.example}</span>
                        </Td>
                        <Td>{formatMinutes(p.response_min)}</Td>
                        <Td>{formatMinutes(p.resolution_min)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </TableWrap>
              </div>
              <p className="mt-3 text-sm text-slate-600">
                Services can have exceptions: MES stops production lines, so its P1 target is 10 min response and 2 h
                resolution. Service requests use P3 or P4.
              </p>
            </Card>

            <Card title="3. KPIs, formulas and targets">
              <TableWrap>
                <thead className="bg-slate-50">
                  <tr>
                    <Th>KPI</Th>
                    <Th>What it means</Th>
                    <Th>Formula</Th>
                    <Th>Target (green / amber / red)</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100" data-testid="kpi-formulas">
                  {m.kpis.map((k) => (
                    <tr key={k.key}>
                      <Td className="font-medium">{k.name}</Td>
                      <Td className="text-xs">{k.definition}</Td>
                      <Td className="font-mono text-xs">{k.formula}</Td>
                      <Td className="text-xs">{k.target_text}</Td>
                    </tr>
                  ))}
                </tbody>
              </TableWrap>
              <p className="mt-3 text-sm text-slate-600">
                Colours: <RagBadge rag="green">green</RagBadge> on target · <RagBadge rag="amber">amber</RagBadge> close
                to the target, watch it · <RagBadge rag="red">red</RagBadge> target missed, act. A value exactly on a
                boundary gets the better colour.
              </p>
            </Card>

            <div className="grid gap-6 md:grid-cols-2">
              <Card title="4. Supplier scorecards">
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                  <li>
                    <strong>OLA</strong> (operational level agreement): internal providers – the central IT provider and
                    each plant&apos;s IT team.
                  </li>
                  <li>
                    <strong>Contract</strong>: external vendors (WAN carrier, managed print, scanners).
                  </li>
                  <li>
                    Green at or above the agreed target, amber up to {m.supplier_amber_band} points below, red further
                    below.
                  </li>
                  <li>
                    Trend ▲▼ compares with the previous month; the top 3 services with breaches show where to look.
                  </li>
                </ul>
              </Card>
              <Card title="5. Problem candidates">
                <p className="text-sm text-slate-700">
                  At least <strong>{m.problem_rule.min_incidents} incidents</strong> with the same plant, service and
                  category within <strong>{m.problem_rule.window_days} days</strong> that are not linked to a problem
                  yet. One click creates a problem record and links the incidents. A problem becomes a{" "}
                  <em>known error</em> when a workaround is documented, and is <em>resolved</em> when the root cause is
                  removed.
                </p>
              </Card>
            </div>

            <Card title="6. Monthly service review (one click)">
              <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
                {REVIEW_AGENDA.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ol>
              <p className="mt-2 text-sm text-slate-600">Export: Print / Save as PDF (A4) and Excel (.xlsx).</p>
            </Card>

            <Card title="7. Feature → ITIL 4 practice">
              <TableWrap>
                <thead className="bg-slate-50">
                  <tr>
                    <Th>Feature in ServiceQualityHub</Th>
                    <Th>ITIL 4 practice</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100" data-testid="itil-map">
                  {ITIL_MAP.map(([feature, practice]) => (
                    <tr key={feature}>
                      <Td>{feature}</Td>
                      <Td className="text-slate-600">{practice}</Td>
                    </tr>
                  ))}
                </tbody>
              </TableWrap>
            </Card>

            <Card title="8. About the demo data">
              <p className="text-sm text-slate-700">
                Valdora Machinery Group, its five plants (Innfeld, Salzbach, Illerau, Rhinval, Vale Verde), its people
                and its suppliers are invented. About six months of tickets are generated with a fixed random seed, with
                six built-in stories: a WAN carrier below its contract in Vale Verde, recurring MES terminal freezes in
                Innfeld, label-printer repairs that got faster after spare printers were put on site, a failed
                Friday-evening ERP release, old requests at Illerau and frequent reopens at Rhinval. &ldquo;Simulate
                next day&rdquo; moves the demo clock one day forward; &ldquo;Reset demo&rdquo; (Service Quality Manager)
                returns to the start.
              </p>
            </Card>
          </>
        )}
      </main>
    </div>
  );
}
