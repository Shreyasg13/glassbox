"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { GlassPanel } from "@/components/GlassPanel";

type TrackDataPoint = {
  date: string;
  portfolio_value: number;
  daily_return: number;
  signal?: string;
};

const CHART_W = 560;
const CHART_H = 160;

/**
 * Real portfolio-value time series from /api/data (data_source.py's
 * load_latest_data(), a real daily_*.json report file) -- not a
 * per-report historical snapshot, since DailyReportNarrative only ever
 * persisted the generated text, not the numeric data that went into it
 * (see routers/reports.py's _build_prompt). This shows the latest
 * available series as context alongside the narrative, honestly
 * labeled as such rather than implying it's locked to this exact
 * report's generation date.
 */
export function PortfolioValueChart() {
  const { data, isLoading } = useQuery({
    queryKey: ["report-chart-data"],
    queryFn: () => apiFetch<TrackDataPoint[]>("/api/data"),
  });

  if (isLoading) return null;
  if (!data || data.length < 2) {
    return (
      <GlassPanel>
        <p className="text-[12px] text-t3">Not enough historical data to chart yet.</p>
      </GlassPanel>
    );
  }

  const values = data.map((d) => d.portfolio_value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * CHART_W;
    const y = CHART_H - ((d.portfolio_value - min) / range) * CHART_H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const first = data[0].portfolio_value;
  const last = data[data.length - 1].portfolio_value;
  const totalReturn = ((last - first) / first) * 100;
  const up = totalReturn >= 0;

  return (
    <GlassPanel variant="accent">
      <div className="mb-sp3 flex items-center justify-between">
        <h2 className="text-[14px] font-bold text-t1">Portfolio Value</h2>
        <span className={`mono text-[13px] font-bold ${up ? "text-teal" : "text-red"}`}>
          {up ? "+" : ""}
          {totalReturn.toFixed(2)}%
        </span>
      </div>
      <svg width={CHART_W} height={CHART_H} className="max-w-full" viewBox={`0 0 ${CHART_W} ${CHART_H}`}>
        <polyline
          points={points.join(" ")}
          fill="none"
          className={up ? "stroke-teal" : "stroke-red"}
          strokeWidth={2}
        />
      </svg>
      <div className="mt-sp2 flex justify-between text-[10.5px] text-t3">
        <span>{data[0].date}</span>
        <span>{data[data.length - 1].date}</span>
      </div>
    </GlassPanel>
  );
}
