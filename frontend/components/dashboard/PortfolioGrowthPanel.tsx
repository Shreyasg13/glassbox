"use client";

import { useId, useMemo, useState } from "react";
import { GlassPanel } from "@/components/GlassPanel";

export type GrowthPoint = {
  date: string;
  portfolio_value: number;
  daily_return: number;
};

const CHART_W = 640;
const CHART_H = 200;
const PAD_Y = 10; // keeps the smoothed curve's peaks from touching the frame

type TimeframeKey = "7D" | "30D" | "90D" | "ALL";
const TIMEFRAMES: { key: TimeframeKey; days: number | null }[] = [
  { key: "7D", days: 7 },
  { key: "30D", days: 30 },
  { key: "90D", days: 90 },
  { key: "ALL", days: null },
];

/** Catmull-Rom -> cubic Bezier smoothing through the real data points --
 * no resampling or fabricated intermediate values, just a smooth curve
 * that actually passes through every real (x,y), the same way Robinhood/
 * most price charts render a daily series without it looking like a
 * jagged EKG. */
function smoothPath(pts: { x: number; y: number }[]): string {
  if (pts.length < 2) return "";
  if (pts.length === 2) return `M ${pts[0].x},${pts[0].y} L ${pts[1].x},${pts[1].y}`;
  let d = `M ${pts[0].x},${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }
  return d;
}

/**
 * Real portfolio-value series from /api/data (same data_source.py's
 * load_latest_data() PortfolioValueChart already charts inside report
 * pages) -- this is the dashboard-level view, with a timeframe toggle
 * added on top since that's real data slicing, not a new data source.
 * Timeframes longer than what's actually on disk are shown disabled
 * rather than silently clamped, so a 5-day sample doesn't quietly
 * masquerade as a real 90-day view.
 *
 * Visual style: smoothed area chart with a gradient fill under the
 * curve, colored by the real direction of the period's return -- same
 * idiom as Robinhood/most brokerage price charts. Still every real
 * (date, value) point, nothing resampled or invented; only the curve
 * between them is smoothed.
 */
export function PortfolioGrowthPanel({ initialData }: { initialData: GrowthPoint[] }) {
  const gradientId = useId();
  const spanDays = initialData.length;
  const [timeframe, setTimeframe] = useState<TimeframeKey>(spanDays >= 30 ? "30D" : "ALL");
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const sliced = useMemo(() => {
    const tf = TIMEFRAMES.find((t) => t.key === timeframe);
    if (!tf || tf.days === null) return initialData;
    return initialData.slice(-tf.days);
  }, [initialData, timeframe]);

  if (initialData.length < 2) {
    return (
      <GlassPanel variant="frost" className="lg:col-span-2">
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

  const coords = sliced.map((d, i) => {
    const x = sliced.length > 1 ? (i / (sliced.length - 1)) * CHART_W : 0;
    const y = PAD_Y + (CHART_H - 2 * PAD_Y) * (1 - (d.portfolio_value - min) / range);
    return { x, y };
  });

  const first = sliced[0].portfolio_value;
  const last = sliced[sliced.length - 1].portfolio_value;
  const periodReturn = ((last - first) / first) * 100;
  const up = periodReturn >= 0;
  const lineColor = up ? "var(--c-teal)" : "var(--c-red)";

  const linePath = smoothPath(coords);
  const areaPath = `${linePath} L ${coords[coords.length - 1].x.toFixed(1)},${CHART_H} L ${coords[0].x.toFixed(1)},${CHART_H} Z`;

  const hovered = hoverIdx !== null ? sliced[hoverIdx] : null;
  const hoveredCoord = hoverIdx !== null ? coords[hoverIdx] : null;

  function handleMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    const idx = Math.round(frac * (sliced.length - 1));
    setHoverIdx(Math.min(sliced.length - 1, Math.max(0, idx)));
  }

  return (
    <GlassPanel variant="frost" className="lg:col-span-2">
      <div className="mb-sp1 flex flex-wrap items-start justify-between gap-sp2">
        <div>
          <h2 className="text-[14px] font-bold text-t1">Portfolio Growth</h2>
          <div className="mono mt-1 text-[22px] font-extrabold text-t1">
            ${(hovered ? hovered.portfolio_value : last).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </div>
        <div className="text-right">
          <span
            className={`mono inline-flex items-center gap-1 rounded-r4 px-sp2 py-0.5 text-[12.5px] font-bold ${
              up ? "bg-teal-dim text-teal" : "bg-red-dim text-red"
            }`}
          >
            {up ? "▲" : "▼"} {up ? "+" : ""}
            {periodReturn.toFixed(2)}%
          </span>
          <div className="mt-1 text-[10.5px] text-t4">{hovered ? hovered.date : `${timeframe} change`}</div>
        </div>
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

      <svg
        width={CHART_W}
        height={CHART_H}
        className="max-w-full cursor-crosshair"
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIdx(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity={0.32} />
            <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
        <path d={linePath} fill="none" stroke={lineColor} strokeWidth={2.25} strokeLinejoin="round" strokeLinecap="round" />
        {hoveredCoord && (
          <g>
            <line
              x1={hoveredCoord.x}
              y1={0}
              x2={hoveredCoord.x}
              y2={CHART_H}
              stroke="var(--c-border2)"
              strokeWidth={1}
              strokeDasharray="3 3"
            />
            <circle cx={hoveredCoord.x} cy={hoveredCoord.y} r={4} fill={lineColor} stroke="var(--c-panel)" strokeWidth={2} />
          </g>
        )}
      </svg>
      <div className="mt-sp2 flex justify-between text-[10.5px] text-t3">
        <span>{sliced[0].date}</span>
        <span>{sliced[sliced.length - 1].date}</span>
      </div>
    </GlassPanel>
  );
}
