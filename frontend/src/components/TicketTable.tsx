"use client";

import Link from "next/link";
import { PriorityBadge, StatusBadge, TableWrap, Td, Th } from "@/components/ui";
import { formatDateTime, formatMinutes, label } from "@/lib/format";
import type { Ticket } from "@/lib/types";

/** Shows the SLA state that matters most: the live clock for open tickets, the result for finished ones. */
export function SlaCell({ ticket }: { ticket: Ticket }) {
  if (ticket.type === "problem" || ticket.type === "change") return <span className="text-slate-400">–</span>;
  const open = ticket.resolved_at === null;
  const elapsed = open ? ticket.resolution_elapsed_min : ticket.resolution_business_min;
  return (
    <div className="flex flex-col gap-1">
      <StatusBadge status={ticket.resolution_status} />
      <span className="text-xs text-slate-500">
        {formatMinutes(elapsed)} of {formatMinutes(ticket.resolution_target_min)}
      </span>
      {ticket.response_status === "breached" && <span className="text-xs text-red-700">response late</span>}
    </div>
  );
}

export default function TicketTable({ tickets, showProvider = true }: { tickets: Ticket[]; showProvider?: boolean }) {
  if (!tickets.length) return <p className="py-4 text-sm text-slate-400">No tickets.</p>;
  return (
    <TableWrap>
      <thead className="bg-slate-50">
        <tr>
          <Th>Ticket</Th>
          <Th>Priority</Th>
          <Th>Plant</Th>
          <Th>Service</Th>
          {showProvider && <Th>Provider</Th>}
          <Th>Status</Th>
          <Th>Created</Th>
          <Th>Resolution SLA</Th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {tickets.map((t) => (
          <tr key={t.id} className="hover:bg-slate-50" data-testid="ticket-row">
            <Td>
              <Link href={`/tickets/${t.id}`} className="font-medium text-brand-700 hover:underline">
                {t.key}
              </Link>
              <p className="max-w-xs text-xs text-slate-500">{t.title}</p>
              <p className="text-[11px] text-slate-400">{label(t.type)}</p>
            </Td>
            <Td>
              <PriorityBadge priority={t.priority} />
            </Td>
            <Td>{t.plant_code}</Td>
            <Td className="max-w-[12rem]">{t.service_name}</Td>
            {showProvider && <Td className="max-w-[10rem]">{t.provider_name}</Td>}
            <Td>
              {t.status}
              {t.reopen_count > 0 && <p className="text-xs text-amber-700">reopened {t.reopen_count}×</p>}
            </Td>
            <Td className="whitespace-nowrap text-xs">{formatDateTime(t.created_at)}</Td>
            <Td>
              <SlaCell ticket={t} />
            </Td>
          </tr>
        ))}
      </tbody>
    </TableWrap>
  );
}
