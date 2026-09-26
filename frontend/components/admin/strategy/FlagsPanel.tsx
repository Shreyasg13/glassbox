"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Flag = { key: string; enabled: boolean; default: boolean; description: string; updated_by: string | null; updated_at: string | null };

const GROUPS: { title: string; keys: string[] }[] = [
  { title: "The daily job", keys: ["pipeline.daily"] },
  { title: "What reaches people", keys: ["output.reports", "output.email", "output.speech", "output.assistant", "output.user_reports"] },
];

/** Admin: output kill switches. Every change is written to the audit log with who made it. */
export function FlagsPanel() {
  const { token } = useAuth();
  const qc = useQueryClient();
  const opts = { token: token ?? undefined };
  const [error, setError] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["admin-flags"], queryFn: () => apiFetch<{ flags: Flag[] }>("/api/admin/flags", opts), enabled: !!token, retry: false });
  const set = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) => apiFetch<Flag>(`/api/admin/flags/${key}`, { method: "POST", ...opts, body: JSON.stringify({ enabled }) }),
    onSuccess: () => { setError(null); qc.invalidateQueries({ queryKey: ["admin-flags"] }); },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not change the flag"),
  });

  function toggle(f: Flag) {
    const next = !f.enabled;
    if (!next && !window.confirm(`Turn OFF "${f.key}"?\n\n${f.description}\n\nThis takes effect within a few seconds and is recorded in the audit log.`)) return;
    set.mutate({ key: f.key, enabled: next });
  }

  const byKey = Object.fromEntries((q.data?.flags ?? []).map((f) => [f.key, f]));
  return (
    <div className="flex flex-col gap-sp5">
      <section className="glass-panel p-sp4">
        <h2 className="text-[15px] font-bold text-t1">Kill switches</h2>
        <p className="mt-1 max-w-[80ch] text-[12px] leading-snug text-t3">
          If something is wrong with what GlassBox is saying, switch that channel off here. A change reaches every server within about 5 seconds, needs no deploy,
          and is recorded with your name. Switching a channel off never deletes anything.
        </p>
        {error && <p role="alert" className="mt-sp2 text-[12px] text-red">{error}</p>}
        {q.isPending && <p className="mt-sp2 text-[12px] text-t3">Loading…</p>}
        {q.isError && <p className="mt-sp2 text-[12px] text-red">{q.error instanceof ApiError ? q.error.message : "Could not load the flags."}</p>}
      </section>
      {q.data && GROUPS.map((g) => (
        <section key={g.title} className="glass-panel p-sp4" aria-label={g.title}>
          <h3 className="mb-sp2 text-[13px] font-bold text-t1">{g.title}</h3>
          <ul className="flex flex-col divide-y divide-white/[0.05]">
            {g.keys.map((k) => byKey[k]).filter(Boolean).map((f) => (
              <li key={f.key} className="flex items-start justify-between gap-sp4 py-sp3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-sp2">
                    <code className="mono text-[12px] font-bold text-t1">{f.key}</code>
                    <span className={`rounded-r4 border px-sp2 py-0.5 text-[10px] font-bold uppercase ${f.enabled ? "border-teal/50 text-teal" : "border-red/50 text-red"}`}>{f.enabled ? "on" : "off"}</span>
                    {f.enabled !== f.default && <span className="text-[10.5px] text-gold">changed from default ({f.default ? "on" : "off"})</span>}
                  </div>
                  <p className="mt-1 text-[12px] leading-snug text-t2">{f.description}</p>
                  <p className="mt-0.5 text-[10.5px] text-t3">{f.updated_by ? `last changed by ${f.updated_by} · ${f.updated_at?.replace("T", " ").slice(0, 16)} UTC` : "never changed (using the default)"}</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={f.enabled}
                  aria-label={`${f.key} is ${f.enabled ? "on" : "off"}`}
                  disabled={set.isPending}
                  onClick={() => toggle(f)}
                  className={`relative mt-1 h-[22px] w-[40px] shrink-0 rounded-full transition-colors disabled:opacity-50 ${f.enabled ? "bg-teal" : "bg-raised"}`}
                >
                  <span className={`absolute top-[3px] h-[16px] w-[16px] rounded-full bg-white transition-all ${f.enabled ? "left-[21px]" : "left-[3px]"}`} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
