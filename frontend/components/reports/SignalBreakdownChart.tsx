"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { GlassPanel } from "@/components/GlassPanel";

type LiveSignalsResponse = {
  summary: {
    buy_signals: number;
    sell_signals: number;
    hold_signals: number;
    avg_confidence: number;
  };
};

// Full literal class names, not interpolated (e.g. `bg-${color}`) --
// Tailwind's JIT scanner only detects complete literal strings in the
// source, so a dynamically-built class name silently produces no CSS
// at all (same fix AgentPerformancePanel's successColor() already
// applies for the identical reason).
const BARS: { key: "buy_signals" | "sell_signals" | "hold_signals"; label: string; barClass: string }[] = [
  { key: "buy_signals", label: "BUY", barClass: "bg-teal" },
  { key: "sell_signals", label: "SELL", barClass: "bg-red" },
  { key: "hold_signals", label: "HOLD", barClass: "bg-t3" },
];

/** Real signal breakdown from /api/live-signals -- the current
 * BUY/SELL/HOLD distribution across the tracked universe, same data
 * source SignalTicker already streams. Same "latest available, not
 * frozen per-report" caveat as PortfolioValueChart. */
export function SignalBreakdownChart() {
  const { data, isLoading } = useQuery({
    queryKey: ["report-chart-signals"],
    queryFn: () => apiFetch<LiveSignalsResponse>("/api/live-signals"),
  });

  if (isLoading) return null;
  if (!data) return null;

  const total = data.summary.buy_signals + data.summary.sell_signals + data.summary.hold_signals || 1;

  return (
    <GlassPanel variant="accent">
      <div className="mb-sp3 flex items-center justify-between">
        <h2 className="text-[14px] font-bold text-t1">Signal Posture</h2>
        <span className="text-[11px] text-t3">avg confidence {data.summary.avg_confidence.toFixed(0)}%</span>
      </div>
      <div className="flex flex-col gap-sp2">
        {BARS.map((bar) => {
          const count = data.summary[bar.key];
          const pct = (count / total) * 100;
          return (
            <div key={bar.key}>
              <div className="mb-1 flex items-center justify-between text-[11.5px]">
                <span className="font-semibold text-t1">{bar.label}</span>
                <span className="mono text-t3">{count}</span>
              </div>
              <div className="h-[6px] w-full overflow-hidden rounded-full bg-panel">
                <div
                  className={`h-full rounded-full ${bar.barClass}`}
                  style={{ width: `${Math.max(2, pct)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </GlassPanel>
  );
}
