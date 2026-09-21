"use client";

import { useMemo, useState } from "react";
import type { CurvePoint } from "@/lib/types";

const W = 720;
const H = 260;
const PAD = { l: 8, r: 8, t: 12, b: 20 };
// ten distinguishable hues: the strategy set is larger than the theme palette, and two lines sharing a colour cannot be told apart
const COLORS = ["var(--c-teal)", "var(--c-blue)", "var(--c-gold)", "var(--c-red)", "var(--c-purple)", "var(--c-cyan)", "var(--c-green)", "#e879a8", "var(--c-t2)", "var(--c-t3)"];

export type Series = { id: string; label: string; curve: CurvePoint[] };

/** Several equity curves on one scale, each rebased to 100 at its own first point so strategies
 * with different starting cash compare fairly. The dashed line marks where the in-sample backtest
 * ends and genuine out-of-sample "live" trading begins. Plain SVG, no chart library. */
export function MultiCurveChart({ series, height = H }: { series: Series[]; height?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const [off, setOff] = useState<Set<string>>(new Set());

  const geo = useMemo(() => {
    const usable = series.filter((s) => s.curve.length > 1);
    if (!usable.length) return null;
    const dates = usable.reduce((a, b) => (b.curve.length > a.curve.length ? b : a)).curve.map((p) => p[0]);
    const rebased = usable.map((s) => {
      const base = s.curve[0][1] || 1;
      const byDate = new Map(s.curve.map((p) => [p[0], (p[1] / base) * 100]));
      return { id: s.id, label: s.label, vals: dates.map((d) => byDate.get(d) ?? null) };
    });
    const visible = rebased.filter((s) => !off.has(s.id));
    const all = visible.flatMap((s) => s.vals.filter((v): v is number => v !== null));
    const lo = Math.min(...all, 100);
    const hi = Math.max(...all, 100);
    const span = hi - lo || 1;
    const x = (i: number) => PAD.l + (i / (dates.length - 1)) * (W - PAD.l - PAD.r);
    const y = (v: number) => PAD.t + (1 - (v - lo) / span) * (height - PAD.t - PAD.b);
    const path = (vals: (number | null)[]) => {
      let d = "";
      let pen = false;
      vals.forEach((v, i) => {
        if (v === null) {
          pen = false;
          return;
        }
        d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
        pen = true;
      });
      return d;
    };
    const live = usable[0].curve.find((p) => p[2] === "live")?.[0];
    const firstLive = live ? dates.indexOf(live) : -1;
    return { dates, rebased, path, x, y, firstLive, base: y(100) };
  }, [series, off, height]);

  if (!geo) return <p className="py-sp6 text-center text-[13px] text-t3">Not enough history to chart yet.</p>;
  const idx = hover ?? geo.dates.length - 1;

  return (
    <div>
      <div className="mb-sp2 flex flex-wrap items-baseline gap-x-sp4 gap-y-1 text-[12px]">
        <span className="mono text-t3">{geo.dates[idx]}</span>
        {geo.rebased.map((s, i) => {
          const v = s.vals[idx];
          return (
            <button
              key={s.id}
              type="button"
              onClick={() =>
                setOff((prev) => {
                  const n = new Set(prev);
                  if (n.has(s.id)) n.delete(s.id);
                  else n.add(s.id);
                  return n;
                })
              }
              className={`mono inline-flex items-center gap-1 ${off.has(s.id) ? "opacity-40" : ""}`}
              title="Click to show or hide"
            >
              <span className="inline-block h-[8px] w-[8px] rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
              <span className="text-t2">{s.label}</span>
              <span className="text-t1">{v === null ? "—" : v.toFixed(1)}</span>
            </button>
          );
        })}
      </div>
      <svg
        viewBox={`0 0 ${W} ${height}`}
        className="w-full"
        role="img"
        aria-label="Strategy equity curves rebased to 100"
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setHover(Math.max(0, Math.min(geo.dates.length - 1, Math.round(((e.clientX - r.left) / r.width) * (geo.dates.length - 1)))));
        }}
        onMouseLeave={() => setHover(null)}
      >
        <line x1={PAD.l} x2={W - PAD.r} y1={geo.base} y2={geo.base} stroke="var(--c-border)" strokeDasharray="3 4" />
        {geo.firstLive > 0 && (
          <g>
            <line x1={geo.x(geo.firstLive)} x2={geo.x(geo.firstLive)} y1={PAD.t} y2={height - PAD.b} stroke="var(--c-t3)" strokeDasharray="4 3" />
            {/* keep the label inside the plot when the live stretch is at the far right */}
            <text x={geo.x(geo.firstLive) + (geo.firstLive > geo.dates.length * 0.85 ? -4 : 4)} textAnchor={geo.firstLive > geo.dates.length * 0.85 ? "end" : "start"} y={PAD.t + 9} fontSize="9" fill="var(--c-t3)">
              {geo.firstLive > geo.dates.length * 0.85 ? "← backtest | live →" : "live →"}
            </text>
          </g>
        )}
        {geo.rebased.map((s, i) => !off.has(s.id) && <path key={s.id} d={geo.path(s.vals)} fill="none" stroke={COLORS[i % COLORS.length]} strokeWidth={1.6} />)}
        <line x1={geo.x(idx)} x2={geo.x(idx)} y1={PAD.t} y2={height - PAD.b} stroke="var(--c-t3)" strokeOpacity={0.4} />
      </svg>
    </div>
  );
}
