"use client";

import { useState } from "react";
import type { RiskRow, StrategyDecision } from "@/lib/types";
import { AgentInspector } from "./AgentInspector";
import { LeanChip, RiskChip, Section, VoteBar, leanTone } from "./shared";

const labelTone = (l: string | undefined) => (l === "strong consensus" ? "text-teal" : l === "majority" ? "text-t1" : "text-gold");

/** One symbol, one glance: the committee's call, how firmly it agreed, whether the engine
 * trio and the analyst panel saw it the same way, and what the risk check did. */
export function DecisionCard({ d, defaultOpen = false }: { d: StrategyDecision; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const ceo = d.ceo;
  const call = d.action ?? d.decision;
  return (
    <div className="rounded-r3 border border-border bg-bg2/40 p-sp4">
      <div className="flex flex-wrap items-center gap-x-sp3 gap-y-sp2">
        <span className="text-[16px] font-extrabold text-t1">{d.symbol}</span>
        <span className="mono text-[11px] text-t3">
          {d.date} · ${d.price?.toFixed(2)}
        </span>
        <span className="ml-auto flex flex-wrap items-center gap-sp2">
          <span className="text-[10px] font-bold uppercase tracking-wide text-t3">engine</span>
          <LeanChip lean={d.engine_signal} small />
          <span className="text-[10px] font-bold uppercase tracking-wide text-t3">committee call</span>
          <span className={`text-[18px] font-extrabold ${leanTone(call)}`}>{call ?? "failed"}</span>
        </span>
      </div>

      {ceo ? (
        <p className="mt-sp2 text-[12px] leading-snug text-t2">
          <span className={`font-semibold ${labelTone(ceo.label)}`}>{ceo.label}</span> · {ceo.headline}
        </p>
      ) : (
        <p className="mt-sp2 text-[12px] text-red">{d.error ?? "No decision was reached."}</p>
      )}

      <div className="mt-sp3 grid gap-sp4 md:grid-cols-[1.2fr_1fr_1fr]">
        <div>
          <VoteBar votes={d.votes} />
          <p className="mt-1 text-[10px] text-t3">Confidence-weighted vote, never an AI judge. {d.answered}/{d.total} answered{!d.quorum_ok && " · LOW QUORUM, not acted on"}.</p>
        </div>
        <div className="text-[11px] text-t2">
          <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-t3">Engine trio vs analyst panel</div>
          {ceo && ceo.engine_trio && ceo.analyst_panel ? (
            <div className="flex items-center gap-sp2">
              <LeanChip lean={ceo.engine_trio} small />
              <span className={ceo.trio_panel_agree ? "text-teal" : "text-gold"}>{ceo.trio_panel_agree ? "agree" : "disagree"}</span>
              <LeanChip lean={ceo.analyst_panel} small />
            </div>
          ) : (
            <span className="text-t3">—</span>
          )}
          {ceo && ceo.dissenters.length > 0 && <p className="mt-1 text-[10px] text-t3">Dissent: {ceo.dissenters.join(", ")}</p>}
        </div>
        <div className="text-[11px] text-t2">
          <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-t3">Risk check</div>
          <RiskChip level={d.risk?.level} score={d.risk?.score} />
          {d.gate && <p className="mt-1 text-[10px] text-gold">{d.gate}</p>}
          {d.analyst_risk && (
            <p className="mt-1 text-[10px] text-t3">
              Analysts rated it: {d.analyst_risk.LOW} low · {d.analyst_risk.MEDIUM} medium · {d.analyst_risk.HIGH} high
            </p>
          )}
        </div>
      </div>

      <button type="button" className="mt-sp3 text-[11px] font-semibold uppercase tracking-wide text-teal hover:underline" onClick={() => setOpen(!open)}>
        {open ? "Hide the committee" : "Inspect all 10 agents"}
      </button>
      {open && (
        <div className="mt-sp3 border-t border-border pt-sp3">
          <AgentInspector d={d} />
        </div>
      )}
    </div>
  );
}

export function RiskTable({ rows }: { rows: RiskRow[] }) {
  if (!rows.length) return <p className="text-[12px] text-t3">Not enough price history to rate risk yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-[12px]">
        <thead>
          <tr className="text-left text-[10px] font-bold uppercase tracking-wide text-t3">
            <th className="px-sp3 py-sp2">Symbol</th>
            <th className="px-sp3 py-sp2">Risk</th>
            <th className="px-sp3 py-sp2">Volatility (vs own history)</th>
            <th className="px-sp3 py-sp2 text-right">From 1-yr high</th>
            <th className="px-sp3 py-sp2">Trend</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol} className="border-t border-border">
              <td className="px-sp3 py-sp2 font-semibold text-t1">{r.symbol}</td>
              <td className="px-sp3 py-sp2">
                <RiskChip level={r.level} score={r.score} />
              </td>
              <td className="mono px-sp3 py-sp2 text-t2">
                {(r.vol * 100).toFixed(0)}% <span className="text-t3">· {Math.round(r.vol_pct)}th pct</span>
              </td>
              <td className="mono px-sp3 py-sp2 text-right text-red">{(r.drawdown * 100).toFixed(1)}%</td>
              <td className={`px-sp3 py-sp2 ${r.below_ma200 ? "text-red" : "text-teal"}`}>{r.below_ma200 ? "below 200-day" : "above 200-day"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CeoView({ decisions, latestDate, risk, history }: { decisions: StrategyDecision[]; latestDate: string | null; risk: RiskRow[]; history: { date: string; symbol: string; decision: string | null; action: string | null; engine_signal: string; consensus: string | null }[] }) {
  return (
    <div className="flex flex-col gap-sp5">
      <Section
        title={`Committee decisions${latestDate ? ` — ${latestDate}` : ""}`}
        note="What the committee recommended, how strongly it agreed, and where its two halves disagreed. The call is the vote after the risk check; the vote itself is always kept."
      >
        {decisions.length === 0 ? (
          <p className="text-[12px] text-t3">No reviews yet. The committee runs on weekdays at 22:15 UTC, or use the Ask console.</p>
        ) : (
          <div className="flex flex-col gap-sp3">
            {decisions.map((d, i) => (
              <DecisionCard key={d.id} d={d} defaultOpen={i === 0} />
            ))}
          </div>
        )}
      </Section>

      <Section title="Risk today" note="Rule-based regime read, no fitted parameters. It says how rough it is likely to be, not which way.">
        <RiskTable rows={risk} />
      </Section>

      {history.length > 0 && (
        <Section title="Recent history" note="The last reviews, newest first. Agreement with the engine is the cheapest sign the committee is adding nothing.">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-[12px]">
              <tbody>
                {history.slice(0, 20).map((h) => (
                  <tr key={`${h.date}:${h.symbol}`} className="border-t border-border first:border-t-0">
                    <td className="mono px-sp3 py-sp1 text-t3">{h.date}</td>
                    <td className="px-sp3 py-sp1 font-semibold text-t1">{h.symbol}</td>
                    <td className="px-sp3 py-sp1"><LeanChip lean={h.engine_signal} small /> <span className="text-[10px] text-t3">engine</span></td>
                    <td className="px-sp3 py-sp1"><LeanChip lean={h.action ?? h.decision} small /> <span className="text-[10px] text-t3">committee</span></td>
                    <td className="px-sp3 py-sp1 text-t3">{h.consensus ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </div>
  );
}
