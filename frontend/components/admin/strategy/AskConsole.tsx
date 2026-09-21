"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AskSummary, StrategyDecision } from "@/lib/types";
import { DecisionCard } from "./CeoView";
import { LeanChip, Section } from "./shared";

const MAX_Q = 500;

/** A prompt console for the committee: pick a symbol, optionally put a question to the chair,
 * and read every agent's answer. It is a sandbox -- the result is never saved as a decision and
 * never feeds the paper account or the scorecards. Each ask costs about seven model calls. */
export function AskConsole({ symbols }: { symbols: string[] }) {
  const { token } = useAuth();
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState(symbols[0] ?? "");
  const [question, setQuestion] = useState("");
  const [askId, setAskId] = useState<string | null>(null);
  const opts = { token: token ?? undefined };

  const recent = useQuery({
    queryKey: ["committee-asks"],
    queryFn: () => apiFetch<AskSummary[]>("/api/admin/committee/asks?limit=8", opts),
    enabled: !!token,
    refetchInterval: 20_000,
  });
  const current = useQuery({
    queryKey: ["committee-ask", askId],
    queryFn: () => apiFetch<StrategyDecision & { status: string }>(`/api/admin/committee/asks/${encodeURIComponent(askId ?? "")}`, opts),
    enabled: !!token && !!askId,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 4_000 : false),
  });
  const send = useMutation({
    mutationFn: () => apiFetch<{ id: string }>("/api/admin/committee/ask", { method: "POST", ...opts, body: JSON.stringify({ symbol: symbol || symbols[0], question }) }),
    onSuccess: (r) => {
      setAskId(r.id);
      qc.invalidateQueries({ queryKey: ["committee-asks"] });
    },
  });
  const err = (e: unknown) => (e instanceof ApiError ? e.message : "failed");
  const doc = current.data;
  const running = send.isPending || doc?.status === "running";

  return (
    <div className="flex flex-col gap-sp5">
      <Section
        title="Ask the committee"
        note="Runs the full committee (3 engine agents + 7 analysts) on today's data for one symbol and shows every answer, the exact prompt and each raw reply. A run takes about a minute."
      >
        <div className="grid gap-sp3 md:grid-cols-[160px_1fr_auto] md:items-end">
          <label className="text-[10px] font-bold uppercase tracking-wide text-t3">
            Symbol
            <select className="input mt-1 w-full" value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {symbols.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="text-[10px] font-bold uppercase tracking-wide text-t3">
            Question for the chair (optional)
            <input
              className="input mt-1 w-full"
              maxLength={MAX_Q}
              placeholder="e.g. Is the volume spike a reason to trim, or noise?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
          </label>
          <button type="button" className="btn btn-primary" disabled={!symbols.length || running} onClick={() => send.mutate()}>
            {running ? "Asking…" : "Ask"}
          </button>
        </div>
        {send.isError && <p className="mt-sp2 text-[12px] text-red">{err(send.error)}</p>}
        <p className="mt-sp2 text-[10px] text-t3">Sandbox only: never saved as a committee decision. One question at a time.</p>
      </Section>

      {doc && (
        <Section title={`Answer — ${doc.symbol}`} note={doc.question ? `Question: ${doc.question}` : undefined}>
          {doc.status === "running" && <p className="text-[12px] text-t2">The committee is deliberating… analysts answer one by one over about a minute.</p>}
          {doc.status === "error" && <p className="text-[12px] text-red">{doc.error}</p>}
          {doc.status === "done" && <DecisionCard d={doc} defaultOpen />}
        </Section>
      )}

      {(recent.data?.length ?? 0) > 0 && (
        <Section title="Recent questions">
          <ul className="flex flex-col">
            {recent.data!.map((a) => (
              <li key={a.id} className="border-t border-border first:border-t-0">
                <button type="button" className="flex w-full flex-wrap items-center gap-sp3 px-sp3 py-sp2 text-left text-[12px] hover:bg-teal-dim/40" onClick={() => setAskId(a.id)}>
                  <span className="font-semibold text-t1">{a.symbol}</span>
                  <span className="min-w-0 flex-1 truncate text-t2">{a.question || "(no question — a plain review)"}</span>
                  {a.status === "done" ? <LeanChip lean={a.action ?? a.decision} small /> : <span className="text-[10px] text-t3">{a.status}</span>}
                  <span className="mono text-[10px] text-t3">{a.created_at.slice(0, 16).replace("T", " ")}</span>
                </button>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
