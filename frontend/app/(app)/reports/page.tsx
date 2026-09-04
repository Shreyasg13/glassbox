"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { GlassPanel } from "@/components/GlassPanel";
import type { DailyReportNarrative } from "@/lib/types";

export default function ReportsPage() {
  const { token, role } = useAuth();
  const isAdmin = !!token && role === "admin";

  const { data } = useQuery({
    queryKey: ["report-narratives"],
    queryFn: () => apiFetch<DailyReportNarrative[]>("/api/reports/narratives", { token: token ?? undefined }),
    enabled: isAdmin,
  });

  return (
    <div className="flex flex-col gap-sp5">
      <h1 className="text-[18px] font-bold text-t1">Daily Reports</h1>

      {!isAdmin && (
        <GlassPanel>
          <p className="text-[13px] text-t3">Sign in as admin to generate and browse daily reports.</p>
        </GlassPanel>
      )}

      {isAdmin && (data ?? []).length === 0 && (
        <p className="text-[13px] text-t3">No reports generated yet.</p>
      )}

      {isAdmin && (
        <div className="flex flex-col gap-sp2">
          {data?.map((r) => (
            <Link
              key={r.id}
              href={`/reports/${r.id}`}
              className="glass-panel flex items-center justify-between p-sp3 hover:border-teal/40"
            >
              <span className="mono text-[13px] text-t1">{r.date}</span>
              <span className="text-[11px] font-semibold uppercase text-t3">
                {r.provider} · {r.model}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
