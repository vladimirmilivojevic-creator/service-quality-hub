"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import TicketTable from "@/components/TicketTable";
import { Button, Card, ErrorMessage, Loading, PageTitle, PriorityBadge, StatusBadge } from "@/components/ui";
import { canEdit, useAuth } from "@/lib/auth";
import { formatDateTime, formatMinutes, label } from "@/lib/format";
import { useApi, useApiMutation } from "@/lib/hooks";
import type { Ticket, TicketDetail } from "@/lib/types";

export default function TicketPage() {
  return (
    <AppShell>
      <TicketView />
    </AppShell>
  );
}

const NEXT_STATUSES: Record<string, string[]> = {
  New: ["In progress", "Pending", "Resolved"],
  "In progress": ["Pending", "Resolved"],
  Pending: ["In progress", "Resolved"],
  Resolved: ["Closed", "In progress"],
  Closed: ["In progress"],
};

function Step({
  title,
  time,
  note,
  done,
  tz,
}: {
  title: string;
  time: string | null;
  note?: string;
  done: boolean;
  tz: string;
}) {
  return (
    <li className="relative pl-6">
      <span
        className={`absolute left-0 top-1.5 h-3 w-3 rounded-full ${done ? "bg-brand-600" : "border-2 border-slate-300 bg-white"}`}
      />
      <p className="text-sm font-medium">{title}</p>
      <p className="text-xs text-slate-500">{time ? formatDateTime(time, tz) : "not yet"}</p>
      {note && <p className="text-xs text-slate-500">{note}</p>}
    </li>
  );
}

function SlaBox({ title, ticket, kind }: { title: string; ticket: TicketDetail; kind: "response" | "resolution" }) {
  const target = kind === "response" ? ticket.response_target_min : ticket.resolution_target_min;
  const measured = kind === "response" ? ticket.response_business_min : ticket.resolution_business_min;
  const elapsed = kind === "response" ? ticket.response_elapsed_min : ticket.resolution_elapsed_min;
  const status = kind === "response" ? ticket.response_status : ticket.resolution_status;
  const due = kind === "response" ? ticket.response_due_at : ticket.resolution_due_at;
  const used = measured ?? elapsed;
  const share = target && used !== null ? Math.min(100, Math.round((used / target) * 100)) : 0;
  const bar = status === "breached" ? "bg-red-500" : status === "at_risk" ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="rounded-lg border border-slate-200 p-4" data-testid={`sla-${kind}`}>
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-medium">{title}</p>
        <StatusBadge status={status} />
      </div>
      <p className="text-2xl font-semibold">{formatMinutes(used)}</p>
      <p className="text-xs text-slate-500">of {formatMinutes(target)} target (support hours only)</p>
      <div className="mt-2 h-2 w-full rounded bg-slate-100">
        <div className={`h-2 rounded ${bar}`} style={{ width: `${share}%` }} />
      </div>
      {due && (
        <p className="mt-2 text-xs text-slate-500">Due {formatDateTime(due, ticket.plant_timezone)} (plant time)</p>
      )}
    </div>
  );
}

function LinkedTicket({ title, ticket }: { title: string; ticket: Ticket }) {
  return (
    <p className="text-sm">
      {title}:{" "}
      <Link href={`/tickets/${ticket.id}`} className="font-medium text-brand-700 hover:underline">
        {ticket.key} – {ticket.title}
      </Link>
    </p>
  );
}

function TicketView() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const ticket = useApi<TicketDetail>(`/tickets/${id}`);
  const update = useApiMutation<{ status: string }, TicketDetail>("PATCH", `/tickets/${id}`);

  if (ticket.error) return <ErrorMessage error={ticket.error} />;
  if (!ticket.data) return <Loading />;
  const t = ticket.data;
  const hasSla = t.type === "incident" || t.type === "request";
  const editable = hasSla && canEdit(user, t.plant_id);

  return (
    <>
      <PageTitle
        title={`${t.key} · ${t.title}`}
        subtitle={
          <>
            {label(t.type)} · {t.plant_code} · {t.service_name} · provider {t.provider_name}
            {t.external_key && t.source === "jsm_import" ? " · imported from Jira Service Management" : ""}
          </>
        }
        actions={
          editable &&
          NEXT_STATUSES[t.status]?.map((status) => (
            <Button
              key={status}
              onClick={() => update.mutate({ status })}
              disabled={update.isPending}
              data-testid={`set-${status}`}
            >
              {status === "In progress" && (t.status === "Resolved" || t.status === "Closed")
                ? "Reopen"
                : `Set ${status}`}
            </Button>
          ))
        }
      />
      <ErrorMessage error={update.error} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Ticket">
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <dt className="text-slate-500">Status</dt>
            <dd>{t.status}</dd>
            <dt className="text-slate-500">Priority</dt>
            <dd>
              <PriorityBadge priority={t.priority} />
              {t.impact && (
                <span className="ml-2 text-xs text-slate-500">
                  impact {t.impact} × urgency {t.urgency}
                </span>
              )}
            </dd>
            <dt className="text-slate-500">Category</dt>
            <dd>{t.category}</dd>
            <dt className="text-slate-500">Support hours</dt>
            <dd>{t.support_hours_label}</dd>
            <dt className="text-slate-500">Plant time zone</dt>
            <dd>{t.plant_timezone}</dd>
            <dt className="text-slate-500">Paused (pending)</dt>
            <dd>{formatMinutes(t.paused_minutes)}</dd>
            <dt className="text-slate-500">Reopened</dt>
            <dd>{t.reopen_count}×</dd>
            <dt className="text-slate-500">Source</dt>
            <dd>{t.source}</dd>
          </dl>
          {t.source_sla_note && (
            <p className="mt-3 text-xs text-slate-500">JSM&apos;s own SLA fields (reference): {t.source_sla_note}</p>
          )}
          <div className="mt-4 space-y-1">
            {t.problem && <LinkedTicket title="Problem" ticket={t.problem} />}
            {t.caused_by_change && <LinkedTicket title="Caused by change" ticket={t.caused_by_change} />}
          </div>
        </Card>
        <Card title="Timeline" info="All times are shown in the plant's local time.">
          <ol className="space-y-4 border-l border-slate-200 pl-2">
            <Step title="Created" time={t.created_at} done tz={t.plant_timezone} />
            {hasSla && (
              <Step
                title="First response"
                time={t.first_response_at}
                done={!!t.first_response_at}
                tz={t.plant_timezone}
              />
            )}
            {t.type === "change" && (
              <Step
                title="Planned window"
                time={t.planned_start}
                note={`until ${formatDateTime(t.planned_end, t.plant_timezone)} · outcome: ${label(t.outcome)}`}
                done={!!t.outcome}
                tz={t.plant_timezone}
              />
            )}
            {t.pending_since && (
              <Step title="Waiting for the user since" time={t.pending_since} done tz={t.plant_timezone} />
            )}
            <Step title="Resolved" time={t.resolved_at} done={!!t.resolved_at} tz={t.plant_timezone} />
            <Step title="Closed" time={t.closed_at} done={!!t.closed_at} tz={t.plant_timezone} />
          </ol>
        </Card>
        {hasSla ? (
          <div className="space-y-4">
            <SlaBox title="Response SLA" ticket={t} kind="response" />
            <SlaBox title="Resolution SLA" ticket={t} kind="resolution" />
          </div>
        ) : (
          <Card title={t.type === "problem" ? "Problem record" : "Change record"}>
            {t.type === "problem" ? (
              <div className="space-y-2 text-sm">
                <p>
                  Status: <StatusBadge status={t.problem_status} />
                </p>
                <p>
                  <span className="text-slate-500">Root cause:</span> {t.root_cause ?? "not known yet"}
                </p>
                <p>
                  <span className="text-slate-500">Workaround:</span> {t.workaround ?? "–"}
                </p>
                <Link href="/problems" className="text-brand-700 hover:underline">
                  Edit on the Problems page →
                </Link>
              </div>
            ) : (
              <div className="space-y-2 text-sm">
                <p>Type: {t.change_type}</p>
                <p>
                  Outcome: <StatusBadge status={t.outcome} />
                </p>
              </div>
            )}
          </Card>
        )}
      </div>
      {t.linked.length > 0 && (
        <Card className="mt-6" title={t.type === "problem" ? "Linked incidents" : "Incidents caused by this change"}>
          <TicketTable tickets={t.linked} />
        </Card>
      )}
    </>
  );
}
