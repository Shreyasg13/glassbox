"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { OrchestrationForm } from "@/components/admin/OrchestrationForm";
import type { OrchestrationConfig } from "@/lib/types";

export default function EditOrchestrationPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();

  const { data, isLoading, error } = useQuery({
    queryKey: ["orchestrations", id],
    queryFn: () =>
      apiFetch<OrchestrationConfig>(`/api/admin/orchestrations/${id}`, { token: token ?? undefined }),
    enabled: !!token && !!id,
  });

  if (isLoading) return <p className="text-[13px] text-t3">Loading…</p>;
  if (error || !data) return <p className="text-[13px] font-semibold text-red">Orchestration not found.</p>;

  return (
    <div className="flex flex-col gap-sp5">
      <h1 className="text-[18px] font-bold text-t1">{data.name}</h1>
      <OrchestrationForm initial={data} />
    </div>
  );
}
