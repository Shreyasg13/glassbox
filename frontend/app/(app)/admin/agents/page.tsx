"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AgentConfig } from "@/lib/types";

export default function AgentsListPage() {
  const { token } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["agents"],
    queryFn: () => apiFetch<AgentConfig[]>("/api/admin/agents", { token: token ?? undefined }),
    enabled: !!token,
  });

  return (
    <div className="flex flex-col gap-sp5">
      <div className="flex items-center justify-between">
        <h1 className="text-[18px] font-bold text-t1">Agents</h1>
        <Link href="/admin/agents/new" className="btn btn-primary">
          New Agent
        </Link>
      </div>

      {isLoading && <p className="text-[13px] text-t3">Loading…</p>}
      {error && <p className="text-[13px] font-semibold text-red">Failed to load agents.</p>}

      {data && data.length === 0 && (
        <p className="text-[13px] text-t3">No agents yet. Create one to get started.</p>
      )}

      <div className="grid grid-cols-1 gap-sp3 md:grid-cols-2 lg:grid-cols-3">
        {data?.map((a) => (
          <Link key={a.id} href={`/admin/agents/${a.id}`} className="glass-panel p-sp4 hover:border-teal/40">
            <div className="mb-sp2 flex items-center justify-between">
              <span className="text-[14px] font-bold text-t1">{a.name}</span>
              <span
                className={`h-[7px] w-[7px] rounded-full ${a.enabled ? "bg-teal" : "bg-t4"}`}
                title={a.enabled ? "enabled" : "disabled"}
              />
            </div>
            <p className="text-[12px] text-t3">{a.role}</p>
            <div className="mt-sp3 flex items-center gap-sp2 text-[11px] font-semibold uppercase text-t3">
              <span className="rounded-r1 border border-border px-sp2 py-[2px]">{a.type}</span>
              {a.type === "llm" && a.provider && (
                <span className="rounded-r1 border border-border px-sp2 py-[2px]">{a.provider}</span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
