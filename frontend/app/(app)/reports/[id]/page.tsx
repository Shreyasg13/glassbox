"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { GlassPanel } from "@/components/GlassPanel";
import type { DailyReportNarrative } from "@/lib/types";

export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();

  // No auth required per contract — /reports/narratives/{id} is public.
  const { data, isLoading, error } = useQuery({
    queryKey: ["report-narrative", id],
    queryFn: () => apiFetch<DailyReportNarrative>(`/reports/narratives/${id}`),
    enabled: !!id,
  });

  if (isLoading) return <p className="text-[13px] text-t3">Loading…</p>;
  if (error || !data) return <p className="text-[13px] font-semibold text-red">Report not found.</p>;

  return (
    <div className="flex flex-col gap-sp5">
      <div className="flex items-center justify-between">
        <h1 className="mono text-[18px] font-bold text-t1">{data.date}</h1>
        <span className="text-[11px] font-semibold uppercase text-t3">
          {data.provider} · {data.model}
        </span>
      </div>
      <GlassPanel variant="raised">
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-t1">{data.narrative}</p>
      </GlassPanel>
    </div>
  );
}
