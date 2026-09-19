"use client";

import { useId, useMemo, useState } from "react";
import type { CurvePoint } from "@/lib/types";

const W = 720;
const H = 240;
const PAD = { l: 8, r: 8, t: 12, b: 20 };

type Props = {
  curve: CurvePoint[];
  benchmark?: CurvePoint[];
  startCash: number;
  label: string;
  benchmarkLabel?: string;
};

const money = (n: number) => `$${Math.round(n).toLocaleString()}`;

/** Equity curve of an account against its benchmark, on a shared scale. The
 * dashed vertical line marks where "backtest" (in-sample replay) ends and "live"
 * (real out-of-sample paper trading) begins. Plain SVG like the dashboard's
 * other charts -- no chart library. */
export function EquityCurveChart({ curve, benchmark = [], startCash, label, benchmarkLabel = "Benchmark" }: Props) {
  const gid = useId();
  const [hover, setHover] = useState<number | null>(null);

  const geo = useMemo(() => {
    if (curve.length < 2) return null;
    const byDate = new Map(benchmark.map((p) => [p[0], p[1]]));
    const bench = curve.map((p) => byDate.get(p[0]) ?? null);
    const all = [...curve.map((p) => p[1]), ...(bench.filter((v) => v !== null) as number[])];
    const lo = Math.min(...all, startCash);
    const hi = Math.max(...all, startCash);
    const span = hi - lo || 1;
    const x = (i: number) => PAD.l + (i / (curve.length - 1)) * (W - PAD.l - PAD.r);
    const y = (v: number) => PAD.t + (1 - (v - lo) / span) * (H - PAD.t - PAD.b);
    const line = (vals: (number | null)[]) => {
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
    const firstLive = curve.findIndex((p) => p[2] === "live");
    return {
      x,
      y,
      bench,
      acct: line(curve.map((p) => p[1])),
      benchPath: line(bench),
      baseline: y(startCash),
      firstLive,
      up: curve[curve.length - 1][1] >= startCash,
    };
  }, [curve, benchmark, startCash]);

  if (!geo) return <p className="py-sp6 text-center text-[13px] text-t3">Not enough history to chart yet.</p>;

  const idx = hover ?? curve.length - 1;
  const pt = curve[idx];
  const color = geo.up ? "var(--c-teal)" : "var(--c-red)";

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const rel = (e.clientX - r.left) / r.width;
    setHover(Math.max(0, Math.min(curve.length - 1, Math.round(rel * (curve.length - 1)))));
  }

  return (
    <div>
      <div className="mb-sp2 flex flex-wrap items-baseline gap-x-sp5 gap-y-1 text-[12px]">
        <span className="mono text-t3">{pt[0]}</span>
        <span className="mono font-semibold text-t1" style={{ color }}>
          {label} {money(pt[1])}
        </span>
        {geo.bench[idx] !== null && (
          <span className="mono text-t3">
            {benchmarkLabel} {money(geo.bench[idx] as number)}
          </span>
        )}
        <span className="text-[10px] font-semibold uppercase tracking-wide text-t3">{pt[2] === "live" ? "live · out-of-sample" : "backtest · in-sample"}</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Equity curve for ${label}${benchmark.length ? ` against ${benchmarkLabel}` : ""}`}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.18} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <line x1={PAD.l} x2={W - PAD.r} y1={geo.baseline} y2={geo.baseline} stroke="var(--c-border2)" strokeDasharray="3 4" />
        <path d={`${geo.acct} L${geo.x(curve.length - 1)},${H - PAD.b} L${geo.x(0)},${H - PAD.b} Z`} fill={`url(#${gid})`} stroke="none" />
        {geo.benchPath && <path d={geo.benchPath} fill="none" stroke="var(--c-t3, #8a94a6)" strokeWidth={1.5} strokeDasharray="5 4" />}
        <path d={geo.acct} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {geo.firstLive > 0 && (
          <g>
            <line x1={geo.x(geo.firstLive)} x2={geo.x(geo.firstLive)} y1={PAD.t} y2={H - PAD.b} stroke="var(--c-gold, #e0b34a)" strokeDasharray="4 3" />
            <text x={geo.x(geo.firstLive) + 5} y={PAD.t + 10} fontSize={10} fill="var(--c-gold, #e0b34a)">
              live
            </text>
          </g>
        )}
        <line x1={geo.x(idx)} x2={geo.x(idx)} y1={PAD.t} y2={H - PAD.b} stroke="var(--c-border2)" />
        <circle cx={geo.x(idx)} cy={geo.y(pt[1])} r={4} fill={color} stroke="var(--c-panel)" strokeWidth={2} />
        <text x={PAD.l} y={H - 5} fontSize={10} fill="var(--c-t3, #8a94a6)">
          {curve[0][0]}
        </text>
        <text x={W - PAD.r} y={H - 5} fontSize={10} textAnchor="end" fill="var(--c-t3, #8a94a6)">
          {curve[curve.length - 1][0]}
        </text>
      </svg>
    </div>
  );
}
