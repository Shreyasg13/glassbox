"use client";

import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuditLogEntry, LLMCallLog, PaginatedAuditLog, PaginatedLLMCalls } from "@/lib/types";

const PAGE_SIZE = 20;

function Pager({
  offset,
  total,
  onChange,
}: {
  offset: number;
  total: number;
  onChange: (next: number) => void;
}) {
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return (
    <div className="flex items-center justify-between pt-sp3 text-[12px] text-t3">
      <span>
        Page {page} of {pageCount} &middot; {total} total
      </span>
      <div className="flex gap-sp2">
        <button
          className="btn btn-ghost"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - PAGE_SIZE))}
        >
          Prev
        </button>
        <button
          className="btn btn-ghost"
          disabled={offset + PAGE_SIZE >= total}
          onClick={() => onChange(offset + PAGE_SIZE)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

const statusColor: Record<string, string> = {
  ok: "text-teal",
  done: "text-teal",
  running: "text-gold",
  queued: "text-gold",
  error: "text-red",
  timeout: "text-red",
};

function LLMCallsTable() {
  const { token } = useAuth();
  const [offset, setOffset] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["llm-calls", offset],
    queryFn: () =>
      apiFetch<PaginatedLLMCalls>(`/admin/llm-calls?limit=${PAGE_SIZE}&offset=${offset}`, {
        token: token ?? undefined,
      }),
    enabled: !!token,
    placeholderData: keepPreviousData,
  });

  const items: LLMCallLog[] = data?.items ?? [];

  return (
    <div className="glass-panel p-sp5">
      <h2 className="mb-sp4 text-[13px] font-bold uppercase tracking-wide text-t3">LLM Calls</h2>
      {isLoading && !data && <p className="text-[13px] text-t3">Loading…</p>}
      {error && !data && (
        <p className="text-[13px] font-semibold text-red">Failed to load LLM calls.</p>
      )}
      {data && items.length === 0 && <p className="text-[13px] text-t3">No LLM calls logged yet.</p>}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px]">
            <thead>
              <tr className="text-t3">
                <th className="pb-sp2 pr-sp3 font-semibold">Time</th>
                <th className="pb-sp2 pr-sp3 font-semibold">Provider</th>
                <th className="pb-sp2 pr-sp3 font-semibold">Model</th>
                <th className="pb-sp2 pr-sp3 font-semibold">Status</th>
                <th className="pb-sp2 pr-sp3 font-semibold">Duration</th>
                <th className="pb-sp2 pr-sp3 font-semibold">Tokens (in/out)</th>
                <th className="pb-sp2 font-semibold">Cost</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-t border-border">
                  <td className="mono py-sp2 pr-sp3 text-t2">{c.started_at}</td>
                  <td className="py-sp2 pr-sp3 uppercase text-t1">{c.provider}</td>
                  <td className="mono py-sp2 pr-sp3 text-t2">{c.model}</td>
                  <td className={`py-sp2 pr-sp3 font-semibold ${statusColor[c.status] ?? "text-t2"}`}>
                    {c.status}
                  </td>
                  <td className="mono py-sp2 pr-sp3 text-t2">
                    {c.duration_ms != null ? `${c.duration_ms}ms` : "—"}
                  </td>
                  <td className="mono py-sp2 pr-sp3 text-t2">
                    {c.tokens_in ?? "—"} / {c.tokens_out ?? "—"}
                  </td>
                  <td className="mono py-sp2 text-t2">
                    {c.estimated_cost_usd != null ? `$${c.estimated_cost_usd.toFixed(4)}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && <Pager offset={offset} total={data.total} onChange={setOffset} />}
    </div>
  );
}

function AuditLogTable() {
  const { token } = useAuth();
  const [offset, setOffset] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["audit-log", offset],
    queryFn: () =>
      apiFetch<PaginatedAuditLog>(`/admin/audit-log?limit=${PAGE_SIZE}&offset=${offset}`, {
        token: token ?? undefined,
      }),
    enabled: !!token,
    placeholderData: keepPreviousData,
  });

  const items: AuditLogEntry[] = data?.items ?? [];

  return (
    <div className="glass-panel p-sp5">
      <h2 className="mb-sp4 text-[13px] font-bold uppercase tracking-wide text-t3">Audit Log</h2>
      {isLoading && !data && <p className="text-[13px] text-t3">Loading…</p>}
      {error && !data && (
        <p className="text-[13px] font-semibold text-red">Failed to load audit log.</p>
      )}
      {data && items.length === 0 && <p className="text-[13px] text-t3">No admin actions logged yet.</p>}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px]">
            <thead>
              <tr className="text-t3">
                <th className="pb-sp2 pr-sp3 font-semibold">Time</th>
                <th className="pb-sp2 pr-sp3 font-semibold">Actor</th>
                <th className="pb-sp2 pr-sp3 font-semibold">Action</th>
                <th className="pb-sp2 font-semibold">Resource</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="border-t border-border">
                  <td className="mono py-sp2 pr-sp3 text-t2">{e.created_at}</td>
                  <td className="py-sp2 pr-sp3 text-t1">{e.actor}</td>
                  <td className="mono py-sp2 pr-sp3 text-t2">{e.action}</td>
                  <td className="mono py-sp2 text-t2">
                    {e.resource_type}
                    {e.resource_id ? `:${e.resource_id}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && <Pager offset={offset} total={data.total} onChange={setOffset} />}
    </div>
  );
}

export default function ObservabilityPage() {
  return (
    <div className="flex flex-col gap-sp5">
      <h1 className="text-[18px] font-bold text-t1">Observability</h1>
      <LLMCallsTable />
      <AuditLogTable />
    </div>
  );
}
