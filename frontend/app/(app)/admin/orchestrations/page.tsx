"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { OrchestrationConfig } from "@/lib/types";

export default function OrchestrationsListPage() {
  const { token } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["orchestrations"],
    queryFn: () => apiFetch<OrchestrationConfig[]>("/admin/orchestrations", { token: token ?? undefined }),
    enabled: !!token,
  });

  return (
    <div className="flex flex-col gap-sp5">
      <div className="flex items-center justify-between">
        <h1 className="text-[18px] font-bold text-t1">Orchestrations</h1>
        <Link href="/admin/orchestrations/new" className="btn btn-primary">
          New Orchestration
        </Link>
      </div>

      {isLoading && <p className="text-[13px] text-t3">Loading…</p>}
      {error && <p className="text-[13px] font-semibold text-red">Failed to load orchestrations.</p>}
      {data && data.length === 0 && (
        <p className="text-[13px] text-t3">No orchestrations yet — create one to get started.</p>
      )}

      <div className="grid grid-cols-1 gap-sp3 md:grid-cols-2 lg:grid-cols-3">
        {data?.map((o) => (
          <Link
            key={o.id}
            href={`/admin/orchestrations/${o.id}`}
            className="glass-panel p-sp4 hover:border-teal/40"
          >
            <span className="text-[14px] font-bold text-t1">{o.name}</span>
            <p className="mt-sp2 text-[12px] text-t3">
              {o.mode} · {o.agent_ids.length} agent{o.agent_ids.length === 1 ? "" : "s"}
            </p>
            {o.schedule && <p className="mono mt-sp1 text-[11px] text-t3">{o.schedule}</p>}
          </Link>
        ))}
      </div>
    </div>
  );
}
