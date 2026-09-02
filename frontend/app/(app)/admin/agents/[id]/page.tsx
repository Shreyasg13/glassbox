"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AgentForm } from "@/components/admin/AgentForm";
import type { AgentConfig } from "@/lib/types";

export default function EditAgentPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();

  const { data, isLoading, error } = useQuery({
    queryKey: ["agents", id],
    queryFn: () => apiFetch<AgentConfig>(`/admin/agents/${id}`, { token: token ?? undefined }),
    enabled: !!token && !!id,
  });

  if (isLoading) return <p className="text-[13px] text-t3">Loading…</p>;
  if (error || !data) return <p className="text-[13px] font-semibold text-red">Agent not found.</p>;

  return (
    <div className="flex flex-col gap-sp5">
      <h1 className="text-[18px] font-bold text-t1">{data.name}</h1>
      <AgentForm initial={data} />
    </div>
  );
}
