"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { StrategyOverview } from "@/lib/types";
import { AccuracyPanel } from "@/components/admin/strategy/AccuracyPanel";
import { AskConsole } from "@/components/admin/strategy/AskConsole";
import { CapitalPanel } from "@/components/admin/strategy/CapitalPanel";
import { CeoView } from "@/components/admin/strategy/CeoView";

const TABS = [
  { id: "ceo", label: "CEO view", hint: "today's calls" },
  { id: "ask", label: "Ask the committee", hint: "prompt console" },
  { id: "accuracy", label: "Is it working?", hint: "accuracy & leaderboard" },
  { id: "capital", label: "Capital & tax", hint: "results" },
] as const;
type Tab = (typeof TABS)[number]["id"];

/** One page to answer: what did the committee decide, is each signal actually delivering,
 * which agent is worth trusting, and what does it earn after cost and tax? */
export default function StrategyPage() {
  const { token, role } = useAuth();
  const [tab, setTab] = useState<Tab>("ceo");
  const q = useQuery({
    queryKey: ["strategy-overview"],
    queryFn: () => apiFetch<StrategyOverview>("/api/admin/strategy/overview", { token: token ?? undefined }),
    enabled: !!token && role === "admin",
    refetchInterval: 60_000,
    retry: false,
  });

  if (role !== "admin") return <p className="py-sp10 text-center text-[13px] text-t3">This page is for administrators.</p>;

  return (
    <div className="flex flex-col gap-sp5">
      <header>
        <h1 className="text-[22px] font-extrabold tracking-tight text-t1">Strategy</h1>
        <p className="mt-1 max-w-[80ch] text-[12px] text-t3">
          A long-horizon, tax-aware research system: daily closes, weekly-scale decisions, no intraday trading. Everything here is simulated paper trading — research, not investment advice.
          {q.data?.data_date && <span className="mono"> · data through {q.data.data_date}</span>}
        </p>
      </header>

      <nav className="flex flex-wrap gap-sp2" aria-label="Strategy sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            aria-current={tab === t.id}
            className={`rounded-r2 border px-sp4 py-sp2 text-left ${tab === t.id ? "border-teal/60 bg-teal-dim" : "border-border bg-bg2/40 hover:bg-bg3"}`}
          >
            <div className={`text-[12px] font-bold ${tab === t.id ? "text-teal" : "text-t1"}`}>{t.label}</div>
            <div className="text-[10px] text-t3">{t.hint}</div>
          </button>
        ))}
      </nav>

      {tab === "accuracy" ? (
        <AccuracyPanel />
      ) : q.isPending ? (
        <p className="py-sp6 text-center text-[13px] text-t3">Loading…</p>
      ) : q.isError ? (
        <p className="py-sp6 text-center text-[13px] text-red">{q.error instanceof ApiError ? q.error.message : "Could not load the strategy view"}</p>
      ) : tab === "ceo" ? (
        <CeoView decisions={q.data.decisions} latestDate={q.data.latest_review_date} risk={q.data.risk_today} history={q.data.history} />
      ) : tab === "ask" ? (
        <AskConsole symbols={q.data.risk_today.map((r) => r.symbol).sort()} />
      ) : (
        <CapitalPanel rows={q.data.capital} curves={q.data.curves} tax={q.data.tax_assumptions} />
      )}
    </div>
  );
}
