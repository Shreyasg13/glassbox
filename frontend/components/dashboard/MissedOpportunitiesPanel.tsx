"use client";

import { useMemo, useState } from "react";
import { GlassPanel } from "@/components/GlassPanel";
import { JobOutputPanel } from "@/components/admin/JobOutputPanel";
import { useAuth } from "@/lib/auth";
import type { Provider } from "@/lib/types";
import type { Signal } from "@/components/SignalTicker";

export type RecentTrade = { symbol: string; action: "BUY" | "SELL"; shares: number; price: number; date: string };

const STRONG_CONFIDENCE = 70;
const PROVIDERS: Provider[] = ["vllm", "ollama", "gemini", "claude"];

type Candidate = { symbol: string; signal: "BUY" | "SELL"; confidence: number; reason: string };

/**
 * "Missed opportunity" candidates -- the same client-side derivation
 * pattern InsightsAlertsPanel already uses for signal-derived alerts
 * (real live-signals data, no mock rows), cross-referenced here against
 * real recorded trades from /api/portfolio-stats rather than a second,
 * possibly-diverging backend rule. A strong BUY/SELL signal with no
 * matching trade anywhere on record counts as a candidate. When there's
 * no trade history at all yet, every strong signal below qualifies by
 * definition -- shown as an explicit note rather than silently listing
 * rows that look like a verdict on trading discipline.
 */
function deriveCandidates(signals: Signal[], recentTrades: RecentTrade[]): Candidate[] {
  const tradedSymbols = new Set(recentTrades.map((t) => t.symbol));
  const out: Candidate[] = [];
  for (const s of signals) {
    const confidence = typeof s.confidence === "number" ? s.confidence : 0;
    if ((s.signal !== "BUY" && s.signal !== "SELL") || confidence < STRONG_CONFIDENCE) continue;
    if (tradedSymbols.has(s.symbol)) continue;
    out.push({
      symbol: s.symbol,
      signal: s.signal,
      confidence,
      reason: `${s.signal} signal at ${confidence.toFixed(0)}% confidence, no matching trade on record`,
    });
  }
  return out.sort((a, b) => b.confidence - a.confidence).slice(0, 10);
}

export function MissedOpportunitiesPanel({
  signals,
  recentTrades,
  hasTradeHistory,
}: {
  signals: Signal[];
  recentTrades: RecentTrade[];
  hasTradeHistory: boolean;
}) {
  const { role } = useAuth();
  const candidates = useMemo(() => deriveCandidates(signals, recentTrades), [signals, recentTrades]);
  const [provider, setProvider] = useState<Provider>("ollama");
  const [model, setModel] = useState("");
  const [narrative, setNarrative] = useState<string | null>(null);

  return (
    <GlassPanel variant="frost" className="lg:col-span-3">
      <h2 className="mb-sp1 text-[15px] font-bold text-t1">Missed Opportunities</h2>
      <p className="mb-sp4 text-[11.5px] text-t3">
        Strong BUY/SELL signals ({STRONG_CONFIDENCE}%+ confidence) from your live signal feed with no matching trade
        on record.
        {!hasTradeHistory && " No trade history exists yet, so every strong signal below is unacted-on by definition."}
      </p>

      {candidates.length === 0 ? (
        <p className="text-[12px] text-t3">No strong signals are currently unmatched by a recorded trade.</p>
      ) : (
        <div className="mb-sp4 flex flex-col gap-sp2">
          {candidates.map((c) => (
            <div
              key={c.symbol}
              className="flex items-center justify-between rounded-r2 border border-border bg-panel2 px-sp3 py-sp2"
            >
              <span className="text-[12.5px] font-semibold text-t1">{c.symbol}</span>
              <span className={`text-[11px] font-bold ${c.signal === "BUY" ? "text-teal" : "text-red"}`}>
                {c.signal} · {c.confidence.toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {role === "admin" && candidates.length > 0 && (
        <div className="border-t border-border pt-sp4">
          <div className="mb-sp3 flex flex-wrap items-end gap-sp3">
            <label className="flex flex-col gap-sp1 text-[11px] font-semibold text-t3">
              Provider
              <select className="select" value={provider} onChange={(e) => setProvider(e.target.value as Provider)}>
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-sp1 text-[11px] font-semibold text-t3">
              Model
              <input
                className="input"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="e.g. llama3.1:8b"
              />
            </label>
          </div>
          <JobOutputPanel
            startUrl="/api/insights/narrate"
            showInput={false}
            runLabel="Generate AI take"
            buildBody={() => ({ candidates, provider, model })}
            onDone={(result) => setNarrative((result?.narrative as string) ?? null)}
          />
          {narrative && (
            <p className="mt-sp3 border-t border-border pt-sp3 text-[12px] leading-relaxed text-t2">{narrative}</p>
          )}
        </div>
      )}
    </GlassPanel>
  );
}
