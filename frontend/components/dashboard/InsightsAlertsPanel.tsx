"use client";

import { useMemo, useState } from "react";
import { GlassPanel } from "@/components/GlassPanel";
import type { Signal } from "@/components/SignalTicker";

type Severity = "critical" | "warning" | "info";

type Insight = {
  symbol: string;
  severity: Severity;
  title: string;
  body: string;
};

// live-signals rows carry rsi/ma_cross/volume_ratio (see backend
// app/data_source.py's get_live_signals) but Signal's own type only
// declares the fields SignalTicker itself reads, plus a loose index
// signature for the rest -- narrowed here for real field access.
type LiveSignalRow = Signal & {
  rsi?: number;
  ma_cross?: "BULLISH" | "BEARISH" | "NEUTRAL" | string;
  volume_ratio?: number;
};

const RSI_OVERBOUGHT = 75;
const RSI_OVERSOLD = 25;
const VOLUME_SPIKE = 1.8;
const STRONG_CONFIDENCE = 70;

/**
 * Real insights derived from the same live-signals feed SignalTicker
 * already renders (backend app/data_source.py's get_live_signals) --
 * not a separate alerting system, not mock rows. Thresholds are standard
 * technical bands (RSI 70/30-style overbought/oversold, unusual-volume
 * ratio) applied to real rsi/ma_cross/volume_ratio/confidence values,
 * honestly labeled as derived rather than implied to be a dedicated
 * audit/alert pipeline (the real A6 Audit feed remains mockup copy --
 * see docs/PROJECT_STATUS.md -- this panel makes no claim about that).
 * One insight per symbol at most (first matching rule wins), so the
 * list reflects genuinely notable rows, not padding to a fixed count.
 */
function deriveInsights(signals: Signal[]): Insight[] {
  const out: Insight[] = [];
  for (const raw of signals) {
    const s = raw as LiveSignalRow;
    const confidence = typeof s.confidence === "number" ? s.confidence : 0;
    const rsi = typeof s.rsi === "number" ? s.rsi : null;
    const volumeRatio = typeof s.volume_ratio === "number" ? s.volume_ratio : null;

    if (s.signal === "SELL" && confidence >= STRONG_CONFIDENCE) {
      out.push({
        symbol: s.symbol,
        severity: "critical",
        title: `Strong sell signal on ${s.symbol}`,
        body: `${s.symbol} is showing a SELL signal at ${confidence.toFixed(0)}% confidence${
          rsi !== null ? `, RSI at ${rsi.toFixed(1)}` : ""
        }.`,
      });
    } else if (rsi !== null && (rsi >= RSI_OVERBOUGHT || rsi <= RSI_OVERSOLD)) {
      const overbought = rsi >= RSI_OVERBOUGHT;
      out.push({
        symbol: s.symbol,
        severity: "critical",
        title: `RSI ${overbought ? "overbought" : "oversold"} on ${s.symbol}`,
        body: `RSI is at ${rsi.toFixed(1)}, ${
          overbought ? `above the ${RSI_OVERBOUGHT} overbought band` : `below the ${RSI_OVERSOLD} oversold band`
        }. Current signal: ${s.signal}.`,
      });
    } else if (s.ma_cross === "BEARISH" && s.signal !== "SELL") {
      out.push({
        symbol: s.symbol,
        severity: "warning",
        title: `Bearish MA cross on ${s.symbol}`,
        body: `Moving averages have crossed bearish on ${s.symbol}, though the signal is still ${s.signal}.`,
      });
    } else if (volumeRatio !== null && volumeRatio >= VOLUME_SPIKE) {
      out.push({
        symbol: s.symbol,
        severity: "warning",
        title: `Unusual volume on ${s.symbol}`,
        body: `Volume is running at ${volumeRatio.toFixed(1)}x its moving average on ${s.symbol}.`,
      });
    } else if (s.signal === "BUY" && confidence >= STRONG_CONFIDENCE) {
      out.push({
        symbol: s.symbol,
        severity: "info",
        title: `Strong buy signal on ${s.symbol}`,
        body: `${s.symbol} is showing a BUY signal at ${confidence.toFixed(0)}% confidence.`,
      });
    }
  }

  const rank: Record<Severity, number> = { critical: 0, warning: 1, info: 2 };
  return out.sort((a, b) => rank[a.severity] - rank[b.severity]).slice(0, 8);
}

const severityStyle: Record<Severity, { border: string; iconBg: string; label: string }> = {
  critical: { border: "border-l-red", iconBg: "bg-red-dim", label: "text-red" },
  warning: { border: "border-l-gold", iconBg: "bg-gold-dim", label: "text-gold" },
  info: { border: "border-l-teal", iconBg: "bg-teal-dim", label: "text-teal" },
};

const severityIcon: Record<Severity, string> = {
  critical: "⚡",
  warning: "📉",
  info: "✓",
};

export function InsightsAlertsPanel({ signals }: { signals: Signal[] }) {
  const insights = useMemo(() => deriveInsights(signals), [signals]);
  const [filter, setFilter] = useState<"all" | Severity>("all");
  const [openSymbol, setOpenSymbol] = useState<string | null>(null);

  const visible = filter === "all" ? insights : insights.filter((i) => i.severity === filter);

  return (
    <GlassPanel variant="frost">
      <div className="mb-sp1 flex items-center justify-between">
        <h2 className="text-[15px] font-bold text-t1">Insights &amp; Alert Signals</h2>
      </div>
      <p className="mb-sp4 text-[11.5px] text-t3">
        Derived from your live signal feed -- standard RSI overbought/oversold bands, MA-cross flips, and
        volume-spike thresholds applied to real data, not a separate alerting system.
      </p>

      <div className="mb-sp4 flex gap-sp2">
        {(["all", "critical", "warning", "info"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setFilter(tab)}
            className={`rounded-r4 border px-sp3 py-1 text-[11px] font-bold capitalize transition-colors ${
              filter === tab
                ? tab === "critical"
                  ? "border-red bg-red-dim text-red"
                  : tab === "warning"
                    ? "border-gold bg-gold-dim text-gold"
                    : "border-teal bg-teal-dim text-teal"
                : "border-border2 text-t3 hover:text-t2"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className="text-[12px] text-t3">
          {insights.length === 0
            ? "No monitored holdings are currently crossing an alert threshold."
            : "No insights in this category right now."}
        </p>
      ) : (
        <div className="flex flex-col gap-sp2">
          {visible.map((insight) => {
            const style = severityStyle[insight.severity];
            const open = openSymbol === insight.symbol;
            return (
              <div
                key={insight.symbol + insight.severity}
                className={`cursor-pointer rounded-r2 border border-border border-l-[3px] ${style.border} bg-panel2 px-sp3 py-sp2 transition-colors hover:border-border2`}
                onClick={() => setOpenSymbol(open ? null : insight.symbol)}
              >
                <div className="flex items-center gap-sp2">
                  <span
                    className={`grid h-6 w-6 shrink-0 place-items-center rounded-r1 text-[13px] ${style.iconBg}`}
                  >
                    {severityIcon[insight.severity]}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[12.5px] font-semibold text-t1">
                    {insight.title}
                  </span>
                  <span
                    className={`shrink-0 text-[9px] font-bold uppercase transition-transform ${
                      open ? "rotate-90" : ""
                    }`}
                  >
                    ▸
                  </span>
                </div>
                {open && (
                  <div className="mt-sp2 border-t border-border pt-sp2 text-[11.5px] leading-relaxed text-t2">
                    {insight.body}
                    <div className="mono mt-sp1 text-[10px] text-t4">Source: live signal feed</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </GlassPanel>
  );
}
