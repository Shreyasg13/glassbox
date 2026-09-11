"use client";

import { useMemo, useState } from "react";
import { GlassPanel } from "@/components/GlassPanel";

export type GrowthPoint = {
  date: string;
  portfolio_value: number;
  daily_return: number;
};

const CHART_W = 640;
const CHART_H = 180;

type TimeframeKey = "7D" | "30D" | "90D" | "ALL";
const TIMEFRAMES: { key: TimeframeKey; days: number | null }[] = [
  { key: "7D", days: 7 },
  { key: "30D", days: 30 },
  { key: "90D", days: 90 },
  { key: "ALL", days: null },
];

/**
 * Real portfolio-value series from /api/data (same data_source.py's
 * load_latest_data() PortfolioValueChart already charts inside report
 * pages) -- this is the dashboard-level view, with a timeframe toggle
 * added on top since that's real data slicing, not a new data source.
 * Timeframes longer than what's actually on disk are shown disabled
 * rather than silently clamped, so a 5-day sample doesn't quietly
 * masquerade as a real 90-day view.
 */
export function PortfolioGrowthPanel({ initialData }: { initialData: GrowthPoint[] }) {
  const spanDays = initialData.length;
  const [timeframe, setTimeframe] = useState<TimeframeKey>(spanDays >= 30 ? "30D" : "ALL");

  const sliced = useMemo(() => {
    const tf = TIMEFRAMES.find((t) => t.key === timeframe);
    if (!tf || tf.days === null) return initialData;
    return initialData.slice(-tf.days);
  }, [initialData, timeframe]);

  if (initialData.length < 2) {
    return (
      <GlassPanel variant="accent" className="lg:col-span-2">
        <h2 className="mb-sp2 text-[14px] font-bold text-t1">Portfolio Growth</h2>
        <p className="text-[12px] text-t3">
          Not enough historical data to chart yet ({initialData.length} day
          {initialData.length === 1 ? "" : "s"} on record).
        </p>
      </GlassPanel>
    );
  }

  const values = sliced.map((d) => d.portfolio_value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = sliced.map((d, i) => {
    const x = sliced.length > 1 ? (i / (sliced.length - 1)) * CHART_W : 0;
    const y = CHART_H - ((d.portfolio_value - min) / range) * CHART_H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const first = sliced[0].portfolio_value;
  const last = sliced[sliced.length - 1].portfolio_value;
  const periodReturn = ((last - first) / first) * 100;
  const up = periodReturn >= 0;

  return (
    <GlassPanel variant="accent" className="lg:col-span-2">
      <div className="mb-sp3 flex flex-wrap items-center justify-between gap-sp2">
        <h2 className="text-[14px] font-bold text-t1">Portfolio Growth</h2>
        <span className={`mono text-[13px] font-bold ${up ? "text-teal" : "text-red"}`}>
          {up ? "+" : ""}
          {periodReturn.toFixed(2)}%
        </span>
      </div>

      <div className="mb-sp3 flex gap-sp1">
        {TIMEFRAMES.map((tf) => {
          const available = tf.days === null || spanDays >= 2;
          const disabled = tf.days !== null && spanDays < tf.days;
          return (
            <button
              key={tf.key}
              type="button"
              disabled={!available}
              title={disabled ? `Only ${spanDays} day${spanDays === 1 ? "" : "s"} of history on record` : undefined}
              onClick={() => setTimeframe(tf.key)}
              className={`rounded-r4 border px-sp2 py-0.5 text-[11px] font-bold transition-colors ${
                timeframe === tf.key
                  ? "border-teal bg-teal-dim text-teal"
                  : disabled
                    ? "cursor-not-allowed border-border2 text-t4 opacity-50"
                    : "border-border2 text-t3 hover:text-t2"
              }`}
            >
              {tf.key}
              {disabled ? " *" : ""}
            </button>
          );
        })}
      </div>
      {spanDays < 90 && (
        <p className="mb-sp2 text-[10.5px] text-t4">* Disabled ranges exceed the {spanDays}-day sample on disk.</p>
      )}

      <svg width={CHART_W} height={CHART_H} className="max-w-full" viewBox={`0 0 ${CHART_W} ${CHART_H}`}>
        <polyline
          points={points.join(" ")}
          fill="none"
          className={up ? "stroke-teal" : "stroke-red"}
          strokeWidth={2}
        />
      </svg>
      <div className="mt-sp2 flex justify-between text-[10.5px] text-t3">
        <span>{sliced[0].date}</span>
        <span>{sliced[sliced.length - 1].date}</span>
      </div>
    </GlassPanel>
  );
}
