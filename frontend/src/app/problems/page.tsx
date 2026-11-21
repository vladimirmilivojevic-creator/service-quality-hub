"use client";

import Link from "next/link";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import { Button, Card, ErrorMessage, Loading, PageTitle, StatusBadge, TableWrap, Td, Th } from "@/components/ui";
import { canEdit, useAuth } from "@/lib/auth";
import { formatDate, formatDateTime } from "@/lib/format";
import { useApi, useApiMutation, useMeta } from "@/lib/hooks";
import type { Candidate, Ticket, TicketDetail } from "@/lib/types";

type Problem = Ticket & { incident_count: number };

export default function ProblemsPage() {
  return (
    <AppShell>
      <Problems />
    </AppShell>
  );
}

function CandidateCard({ candidate }: { candidate: Candidate }) {
  const { user } = useAuth();
  const create = useApiMutation<{ incident_ids: number[]; title: string }, TicketDetail>("POST", "/problems");
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-4" data-testid="candidate">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {candidate.count} × &ldquo;{candidate.category}&rdquo; – {candidate.service_name}
          </p>
          <p className="text-xs text-slate-500">
            {candidate.plant_name} · first {formatDateTime(candidate.first_seen)} · last{" "}
            {formatDateTime(candidate.last_seen)}
          </p>
        </div>
        {canEdit(user, candidate.plant_id) && (
          <Button
            variant="primary"
            disabled={create.isPending}
            data-testid="create-problem"
            onClick={() =>
              create.mutate({ incident_ids: candidate.incidents.map((i) => i.id), title: candidate.suggested_title })
            }
          >
            Create problem
          </Button>
        )}
      </div>
      <ul className="mt-3 space-y-1 text-sm">
        {candidate.incidents.map((i) => (
          <li key={i.id}>
            <Link href={`/tickets/${i.id}`} className="text-brand-700 hover:underline">
              {i.key}
            </Link>{" "}
            {i.title} <span className="text-xs text-slate-400">({formatDate(i.created_at)})</span>
          </li>
        ))}
      </ul>
      <ErrorMessage error={create.error} />
    </div>
  );
}

function ProblemEditor({ problem, onClose }: { problem: Problem; onClose: () => void }) {
  const update = useApiMutation<Record<string, string>, TicketDetail>("PATCH", `/problems/${problem.id}`);
  const [form, setForm] = useState({
    problem_status: problem.problem_status ?? "investigating",
    root_cause: problem.root_cause ?? "",
    workaround: problem.workaround ?? "",
  });
  return (
    <form
      className="mt-3 grid gap-2 rounded-lg bg-slate-50 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        update.mutate(form, { onSuccess: onClose });
      }}
    >
      <label className="text-xs font-medium text-slate-500">
        Status
        <select
          value={form.problem_status}
          onChange={(e) => setForm({ ...form, problem_status: e.target.value })}
          className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="investigating">Investigating</option>
          <option value="known_error">Known error (root cause or workaround documented)</option>
          <option value="resolved">Resolved (root cause removed)</option>
        </select>
      </label>
      <label className="text-xs font-medium text-slate-500">
        Root cause
        <textarea
          rows={2}
          value={form.root_cause}
          onChange={(e) => setForm({ ...form, root_cause: e.target.value })}
          className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        />
      </label>
      <label className="text-xs font-medium text-slate-500">
        Workaround
        <textarea
          rows={2}
          value={form.workaround}
          onChange={(e) => setForm({ ...form, workaround: e.target.value })}
          className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
        />
      </label>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={update.isPending}>
          Save
        </Button>
        <Button type="button" onClick={onClose}>
          Cancel
        </Button>
      </div>
      <ErrorMessage error={update.error} />
    </form>
  );
}

function Problems() {
  const { user } = useAuth();
  const meta = useMeta();
  const candidates = useApi<Candidate[]>("/problems/candidates");
  const problems = useApi<Problem[]>("/problems");
  const [editing, setEditing] = useState<number | null>(null);
  const rule = meta.data?.problem_rule;

  return (
    <>
      <PageTitle
        title="Problems"
        subtitle={
          rule
            ? `Problem candidate rule: at least ${rule.min_incidents} incidents with the same plant, service and category within ${rule.window_days} days that are not linked to a problem yet. One problem record finds the root cause once, instead of fixing the same symptom again and again.`
            : undefined
        }
      />
      <Card title="Problem candidates (recurring incidents)">
        <ErrorMessage error={candidates.error} />
        {!candidates.data ? (
          <Loading />
        ) : candidates.data.length === 0 ? (
          <p className="text-sm text-slate-500">No recurring incidents right now.</p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {candidates.data.map((c) => (
              <CandidateCard key={`${c.plant_id}-${c.service_id}-${c.category}`} candidate={c} />
            ))}
          </div>
        )}
      </Card>
      <Card className="mt-6" title="Problem records">
        {!problems.data ? (
          <Loading />
        ) : (
          <TableWrap>
            <thead className="bg-slate-50">
              <tr>
                <Th>Problem</Th>
                <Th>Plant</Th>
                <Th>Status</Th>
                <Th>Incidents</Th>
                <Th>Root cause / workaround</Th>
                <Th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100" data-testid="problem-table">
              {problems.data.map((p) => (
                <tr key={p.id}>
                  <Td className="max-w-xs">
                    <Link href={`/tickets/${p.id}`} className="font-medium text-brand-700 hover:underline">
                      {p.key}
                    </Link>
                    <p className="text-sm">{p.title}</p>
                    <p className="text-xs text-slate-400">
                      {p.service_name} · opened {formatDate(p.created_at)}
                    </p>
                  </Td>
                  <Td>{p.plant_code}</Td>
                  <Td>
                    <StatusBadge status={p.problem_status} />
                  </Td>
                  <Td>{p.incident_count}</Td>
                  <Td className="max-w-md text-xs">
                    <p>
                      <span className="text-slate-500">Root cause:</span> {p.root_cause ?? "not known yet"}
                    </p>
                    <p>
                      <span className="text-slate-500">Workaround:</span> {p.workaround ?? "–"}
                    </p>
                    {editing === p.id && <ProblemEditor problem={p} onClose={() => setEditing(null)} />}
                  </Td>
                  <Td>
                    {canEdit(user, p.plant_id) && editing !== p.id && (
                      <Button onClick={() => setEditing(p.id)}>Edit</Button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </TableWrap>
        )}
      </Card>
    </>
  );
}
