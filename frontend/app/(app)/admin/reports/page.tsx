"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ReportGenerateForm } from "@/components/admin/ReportGenerateForm";
import type { DailyReportNarrative } from "@/lib/types";

export default function AdminReportsPage() {
  const { token } = useAuth();
  const { data } = useQuery({
    queryKey: ["report-narratives"],
    queryFn: () => apiFetch<DailyReportNarrative[]>("/api/reports/narratives", { token: token ?? undefined }),
    enabled: !!token,
  });

  return (
    <div className="flex flex-col gap-sp5">
      <h1 className="text-[18px] font-bold text-t1">Daily Reports</h1>
      <ReportGenerateForm />

      <div>
        <h2 className="mb-sp3 text-[13px] font-bold uppercase tracking-wide text-t3">History</h2>
        {(data ?? []).length === 0 && <p className="text-[13px] text-t3">No reports generated yet.</p>}
        <div className="flex flex-col gap-sp2">
          {data?.map((r) => (
            <Link
              key={r.id}
              href={`/reports/${r.id}`}
              className="glass-panel flex items-center justify-between p-sp3 hover:border-teal/40"
            >
              <span className="flex flex-col">
                <span className="mono text-[13px] text-t1">{r.date}</span>
                {r.title && <span className="text-[12px] text-t2">{r.title}</span>}
              </span>
              <span className="text-[11px] font-semibold uppercase text-t3">
                {r.provider} · {r.model}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
