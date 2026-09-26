"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch, apiUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Tally = { key: string; helpful: number; unhelpful: number; comments: number; rated: number; helpful_rate: number | null };
type Summary = {
  days: number; total: number; users: number; helpful: number; unhelpful: number; note: string;
  by_type: Tally[]; by_symbol: Tally[];
  recent_comments: { created_at: string; user: string; target_type: string; target_ref: string; symbol: string; rating: number; comment: string }[];
};

const rate = (t: Tally) => (t.helpful_rate == null ? "–" : `${(t.helpful_rate * 100).toFixed(0)}%`);

function TallyTable({ rows, label }: { rows: Tally[]; label: string }) {
  if (!rows.length) return <p className="text-[12px] text-t3">Nothing yet.</p>;
  return (
    <table className="w-full text-left text-[12px]">
      <thead className="text-[10px] uppercase tracking-wide text-t3"><tr><th className="py-1 pr-sp3">{label}</th><th className="pr-sp3">👍</th><th className="pr-sp3">👎</th><th className="pr-sp3">Helpful</th><th>Comments</th></tr></thead>
      <tbody>
        {rows.map((t) => (
          <tr key={t.key} className="border-t border-white/[0.04]">
            <td className="py-1 pr-sp3 font-semibold text-t1">{t.key}</td>
            <td className="mono pr-sp3 text-teal">{t.helpful}</td>
            <td className="mono pr-sp3 text-red">{t.unhelpful}</td>
            <td className="mono pr-sp3">{rate(t)}{t.rated < 5 && t.rated > 0 ? <span className="text-t3"> (n={t.rated})</span> : ""}</td>
            <td className="mono text-t2">{t.comments}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Admin: what users are telling us about signals, answers and the committee. Advisory: nothing here changes the committee. */
export function FeedbackPanel() {
  const { token } = useAuth();
  const [err, setErr] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["admin-feedback"], queryFn: () => apiFetch<Summary>("/api/admin/feedback/summary?days=90", { token: token ?? undefined }), enabled: !!token, retry: false, staleTime: 60_000 });

  async function download() {
    setErr(null);
    try {
      const res = await fetch(apiUrl("/api/admin/feedback/export"), { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const url = URL.createObjectURL(await res.blob());
      Object.assign(document.createElement("a"), { href: url, download: "glassbox-feedback.csv" }).click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Download failed");
    }
  }

  const s = q.data;
  return (
    <div className="flex flex-col gap-sp5">
      <section className="glass-panel p-sp4">
        <div className="flex flex-wrap items-baseline justify-between gap-sp2">
          <h2 className="text-[15px] font-bold text-t1">User feedback (last 90 days)</h2>
          <button type="button" onClick={download} className="rounded-r1 border border-border px-sp3 py-sp1 text-[11px] font-semibold text-t2 hover:bg-bg3">Download CSV</button>
        </div>
        {err && <p className="mt-1 text-[11px] text-red">{err}</p>}
        {q.isPending && <p className="mt-sp2 text-[12px] text-t3">Loading…</p>}
        {q.isError && <p className="mt-sp2 text-[12px] text-red">{q.error instanceof ApiError ? q.error.message : "Could not load feedback."}</p>}
        {s && (
          <>
            <div className="mt-sp3 grid grid-cols-2 gap-sp3 lg:grid-cols-4">
              {[["Responses", s.total], ["People", s.users], ["Helpful", s.helpful], ["Not helpful", s.unhelpful]].map(([k, v]) => (
                <div key={String(k)} className="rounded-r2 border border-border bg-bg2/40 px-sp3 py-sp2">
                  <div className="text-[9.5px] font-bold uppercase tracking-wider text-t3">{k}</div>
                  <div className="mono text-[18px] font-extrabold text-t1">{v}</div>
                </div>
              ))}
            </div>
            <p className="mt-sp2 text-[11px] leading-snug text-t3">{s.note}</p>
          </>
        )}
      </section>
      {s && (
        <div className="grid gap-sp5 lg:grid-cols-2">
          <section className="glass-panel p-sp4"><h3 className="mb-sp2 text-[13px] font-bold text-t1">By what they rated</h3><TallyTable rows={s.by_type} label="Type" /></section>
          <section className="glass-panel p-sp4"><h3 className="mb-sp2 text-[13px] font-bold text-t1">By stock</h3><TallyTable rows={s.by_symbol} label="Stock" /></section>
          <section className="glass-panel p-sp4 lg:col-span-2">
            <h3 className="mb-sp2 text-[13px] font-bold text-t1">Latest comments</h3>
            {s.recent_comments.length === 0 && <p className="text-[12px] text-t3">No comments yet.</p>}
            <ul className="flex flex-col gap-sp2">
              {s.recent_comments.map((c, i) => (
                <li key={i} className="rounded-r2 border border-border bg-bg2/40 px-sp3 py-sp2 text-[12px]">
                  <div className="text-[10.5px] text-t3">{c.created_at.slice(0, 10)} · {c.target_type}{c.symbol ? ` · ${c.symbol}` : ""}{c.rating === 1 ? " · 👍" : c.rating === -1 ? " · 👎" : ""} · user {c.user}</div>
                  <div className="mt-0.5 whitespace-pre-line text-t1">{c.comment}</div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
