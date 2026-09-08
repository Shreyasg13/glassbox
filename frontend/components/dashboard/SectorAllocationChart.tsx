"use client";

import { useEffect, useMemo, useState } from "react";
import { GlassPanel } from "@/components/GlassPanel";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Holding, HoldingsData } from "./PortfolioOverviewPanel";

const SIZE = 132;
const STROKE = 18;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

// One fixed color per sector name rather than a randomized palette, so a
// sector reads the same color across a refresh/re-render. Falls back to
// a neutral gray for any sector not in this list (the real universe here
// is 15 seeded symbols across a known set of sectors, but this must not
// silently break if that set grows).
const SECTOR_COLORS: Record<string, string> = {
  Technology: "#0dccaa",
  Semiconductors: "#4d7aff",
  Financials: "#e8a020",
  "Consumer Discretionary": "#a46bff",
  "Consumer Staples": "#22d3ee",
  Healthcare: "#e8445a",
  Energy: "#0db87a",
  Industrials: "#9aaccc",
  "Communication Services": "#b45309",
  Automotive: "#dc2626",
  "Real Estate": "#7c3aed",
  Utilities: "#6b7a99",
};
const FALLBACK_COLOR = "#5c7090";

type Slice = { sector: string; weight: number; color: string };

/**
 * Real sector allocation, aggregated client-side from the same
 * `holdings[].sector` / `holdings[].weight` fields PortfolioOverviewPanel
 * already renders as a table -- no new backend endpoint, no mock data.
 * Hand-rolled SVG (stacked <circle> arcs via stroke-dasharray), matching
 * the no-charting-library convention already established by
 * PortfolioValueChart/SignalBreakdownChart/StressTestPanel's fan chart.
 *
 * Re-fetches /api/holdings client-side with the auth token, same as
 * PortfolioOverviewPanel -- without this it would keep showing the
 * server-fetched shared/global holdings forever, diverging from that
 * panel once a logged-in user's personalized watchlist loads there.
 */
export function SectorAllocationChart({ initialHoldings }: { initialHoldings: Holding[] }) {
  const { token } = useAuth();
  const [holdings, setHoldings] = useState<Holding[]>(initialHoldings);
  const [hovered, setHovered] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    apiFetch<HoldingsData>("/api/holdings", { token })
      .then((personalized) => {
        if (!cancelled) setHoldings(personalized.holdings);
      })
      .catch(() => {
        // keep showing the server-fetched default on failure
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const slices = useMemo<Slice[]>(() => {
    const bySector = new Map<string, number>();
    for (const h of holdings) {
      bySector.set(h.sector, (bySector.get(h.sector) ?? 0) + h.weight);
    }
    return Array.from(bySector.entries())
      .map(([sector, weight]) => ({ sector, weight, color: SECTOR_COLORS[sector] ?? FALLBACK_COLOR }))
      .sort((a, b) => b.weight - a.weight);
  }, [holdings]);

  if (slices.length === 0) {
    return (
      <GlassPanel variant="frost">
        <h2 className="mb-sp2 text-[14px] font-bold text-t1">Sector Allocation</h2>
        <p className="text-[12px] text-t3">No holdings data available right now.</p>
      </GlassPanel>
    );
  }

  const total = slices.reduce((s, x) => s + x.weight, 0);
  let cumulative = 0;
  const arcs = slices.map((s) => {
    const fraction = total > 0 ? s.weight / total : 0;
    const dash = fraction * CIRCUMFERENCE;
    const rotate = (cumulative / total) * 360 - 90;
    cumulative += s.weight;
    return { ...s, dash, gap: CIRCUMFERENCE - dash, rotate };
  });

  return (
    <GlassPanel variant="frost">
      <div className="mb-sp4 flex items-baseline justify-between">
        <h2 className="text-[14px] font-bold text-t1">Sector Allocation</h2>
        <span className="text-[10.5px] text-t3">by portfolio weight</span>
      </div>
      <div className="flex items-center gap-sp4">
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="shrink-0">
          {arcs.map((a) => (
            <circle
              key={a.sector}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke={a.color}
              strokeWidth={STROKE}
              strokeDasharray={`${a.dash.toFixed(1)} ${a.gap.toFixed(1)}`}
              transform={`rotate(${a.rotate.toFixed(2)} ${SIZE / 2} ${SIZE / 2})`}
              style={{
                transition: "opacity .15s ease",
                opacity: hovered === null || hovered === a.sector ? 1 : 0.3,
              }}
              onMouseEnter={() => setHovered(a.sector)}
              onMouseLeave={() => setHovered(null)}
            />
          ))}
          <text
            x={SIZE / 2}
            y={SIZE / 2 - 3}
            textAnchor="middle"
            fontSize={19}
            fontWeight={800}
            className="mono fill-t1"
          >
            {slices.length}
          </text>
          <text x={SIZE / 2} y={SIZE / 2 + 13} textAnchor="middle" fontSize={8.5} className="fill-t3">
            SECTORS
          </text>
        </svg>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          {arcs.map((a) => (
            <div
              key={a.sector}
              onMouseEnter={() => setHovered(a.sector)}
              onMouseLeave={() => setHovered(null)}
              className="flex items-center gap-sp2 rounded-r1 px-sp1 py-0.5 text-[11px] transition-colors hover:bg-raised"
            >
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: a.color }} />
              <span className="flex-1 truncate text-t2">{a.sector}</span>
              <span className="mono shrink-0 font-bold text-t1">{a.weight.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    </GlassPanel>
  );
}
