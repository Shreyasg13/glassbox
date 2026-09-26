"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { FeedbackButtons } from "@/components/feedback/FeedbackButtons";

type Item = { id: string; day: string; kind: "signal" | "alert" | "report" | "email"; severity: "info" | "watch" | "attention"; title: string; body: string; link: string; read: boolean; created_at: string };
type Inbox = { items: Item[]; unread: number };

const TABS = [
  { id: "", label: "All" },
  { id: "alert", label: "Alerts" },
  { id: "signal", label: "Daily signals" },
  { id: "report", label: "Reports" },
  { id: "email", label: "Emailed" },
] as const;
const KIND_ICON: Record<Item["kind"], string> = { signal: "◈", alert: "⚡", report: "▤", email: "✉" };
const SEVERITY_TONE: Record<Item["severity"], string> = { attention: "border-gold/50", watch: "border-border2", info: "border-border" };

/** Everything GlassBox has told this user, in one place: daily stance, alerts, paper-trading reports and emailed digests. */
export default function NotificationsPage() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [kind, setKind] = useState<(typeof TABS)[number]["id"]>("");
  const opts = { token: token ?? undefined };
  const q = useQuery({
    queryKey: ["inbox", kind],
    queryFn: () => apiFetch<Inbox>(`/api/me/notifications?limit=100${kind ? `&kind=${kind}` : ""}`, opts),
    enabled: !!token,
    retry: false,
  });
  const read = useMutation({
    mutationFn: (ids: string[] | null) => apiFetch<{ marked: number; unread: number }>("/api/me/notifications/read", { method: "POST", ...opts, body: JSON.stringify({ ids }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["inbox"] });
      qc.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  return (
    <div className="flex flex-col gap-sp4">
      <header className="flex flex-wrap items-end justify-between gap-sp3">
        <div>
          <h1 className="text-[22px] font-extrabold tracking-tight text-t1">Inbox</h1>
          <p className="mt-1 max-w-[70ch] text-[12px] text-t3">Your daily stance, alerts on your stocks, paper-trading reports and the digests we emailed you. Simulated research, not investment advice.</p>
        </div>
        <div className="flex items-center gap-sp3">
          <Link href="/ask" className="btn btn-ghost text-[12px]">Ask the assistant</Link>
          <button type="button" onClick={() => read.mutate(null)} disabled={!q.data?.unread || read.isPending} className="btn btn-ghost text-[12px] disabled:opacity-50">
            Mark all read{q.data?.unread ? ` (${q.data.unread})` : ""}
          </button>
        </div>
      </header>

      <div className="flex flex-wrap gap-1" role="tablist" aria-label="Filter">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={kind === t.id} onClick={() => setKind(t.id)} className={`rounded-r1 border px-sp3 py-1 text-[12px] ${kind === t.id ? "border-teal/60 bg-teal-dim text-teal" : "border-border text-t3"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {q.isPending && <p className="text-[12px] text-t3">Loading…</p>}
      {q.isError && <p className="text-[12px] text-red">{q.error instanceof ApiError ? q.error.message : "Could not load your inbox."}</p>}
      {q.data && q.data.items.length === 0 && (
        <div className="glass-panel p-sp5 text-[13px] text-t2">
          Nothing here yet. After each trading day&rsquo;s review, GlassBox posts your stance, any alerts on your stocks and your paper-trading report here.
        </div>
      )}
      <ul className="flex flex-col gap-sp3">
        {q.data?.items.map((n) => (
          <li key={n.id} className={`glass-panel border-l-2 p-sp4 ${SEVERITY_TONE[n.severity]} ${n.read ? "opacity-80" : ""}`}>
            <div className="flex flex-wrap items-start justify-between gap-sp2">
              <div className="flex min-w-0 items-start gap-sp2">
                <span aria-hidden className="mt-0.5 text-[14px] text-t3">{KIND_ICON[n.kind]}</span>
                <div className="min-w-0">
                  <div className={`text-[13.5px] ${n.read ? "font-medium text-t2" : "font-bold text-t1"}`}>
                    {!n.read && <span className="mr-1.5 inline-block h-[7px] w-[7px] rounded-full bg-teal align-middle" aria-label="unread" />}
                    {n.title}
                  </div>
                  <div className="mt-0.5 text-[10.5px] text-t3">{n.day} · {n.kind}</div>
                </div>
              </div>
              <div className="flex items-center gap-sp2">
                {n.link && (
                  <Link href={n.link} onClick={() => !n.read && read.mutate([n.id])} className="btn btn-ghost text-[11px]">Open</Link>
                )}
                {!n.read && <button type="button" onClick={() => read.mutate([n.id])} className="text-[11px] text-t3 underline decoration-dotted hover:text-t1">mark read</button>}
              </div>
            </div>
            {n.body && <p className="mt-sp2 whitespace-pre-line text-[12px] leading-relaxed text-t2">{n.body}</p>}
            <div className="mt-sp2"><FeedbackButtons type="notification" refId={n.id} label="Useful?" /></div>
          </li>
        ))}
      </ul>
    </div>
  );
}
