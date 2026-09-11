"use client";

import { useCallback, useState } from "react";
import { GlassPanel } from "@/components/GlassPanel";
import { GuideHint } from "@/components/onboarding/GuideBubble";
import { GUIDE_METRIC_EXPLANATIONS } from "@/lib/glassboxGuide";
import { apiFetch, ApiError } from "@/lib/api";

type MonteCarloResult = {
  mean: number;
  percentile_5: number;
  percentile_95: number;
  prob_profit: number;
  paths: number[][];
  final_values: number[];
};

const DAY_OPTIONS = [7, 14, 30, 90];
const CHART_W = 560;
const CHART_H = 140;
const MAX_PATHS_DRAWN = 40;

/** Real Monte Carlo simulation (backend/app/data_source.py's run_monte_carlo) --
 * a normal-distribution random walk seeded from this portfolio's own real
 * historical daily returns, not a canned demo number. Matches the "Stress
 * Test · historical crisis simulator" feature Pricing.tsx already promises. */
export function StressTestPanel() {
  const [days, setDays] = useState(7);
  const [result, setResult] = useState<MonteCarloResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (selectedDays: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<MonteCarloResult>(
        `/api/monte-carlo?days=${selectedDays}&simulations=500&confidence=0.95`,
        { method: "POST" }
      );
      setResult(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  }, []);

  function pathsToSvg(paths: number[][]): { d: string; className: string }[] {
    const shown = paths.slice(0, MAX_PATHS_DRAWN);
    const allValues = shown.flat();
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const range = max - min || 1;

    return shown.map((path) => {
      const points = path.map((v, i) => {
        const x = (i / (path.length - 1)) * CHART_W;
        const y = CHART_H - ((v - min) / range) * CHART_H;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      });
      const endsUp = path[path.length - 1] >= path[0];
      return { d: `M${points.join("L")}`, className: endsUp ? "stroke-teal/25" : "stroke-red/25" };
    });
  }

  return (
    <GlassPanel variant="frost">
      <div className="mb-sp1 flex items-center justify-between">
        <h2 className="text-[15px] font-bold text-t1">Stress Test</h2>
        <span className="text-[10.5px] text-t3">Monte Carlo · real historical returns</span>
      </div>
      <p className="mb-sp4 text-[11.5px] text-t3">
        500 simulated paths from this portfolio&apos;s own historical daily-return distribution,
        not a canned scenario.
      </p>

      <div className="mb-sp4 flex flex-wrap items-center gap-sp2">
        {DAY_OPTIONS.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => {
              setDays(d);
              run(d);
            }}
            disabled={loading}
            className={`btn text-[12px] ${days === d && result ? "btn-primary" : "btn-ghost"}`}
          >
            {d}d
          </button>
        ))}
        {loading && <span className="text-[12px] text-t3">Simulating…</span>}
      </div>

      {error && <p className="text-[12px] font-semibold text-red">{error}</p>}

      {result && (
        <>
          <div className="mb-sp4 overflow-x-auto">
            <svg width={CHART_W} height={CHART_H} className="max-w-full">
              {pathsToSvg(result.paths).map((p, i) => (
                <path key={i} d={p.d} fill="none" className={p.className} strokeWidth={1} />
              ))}
            </svg>
          </div>

          <div className="grid grid-cols-2 gap-sp4 sm:grid-cols-4">
            <div>
              <div className="mono text-[16px] font-extrabold text-t1">${result.mean.toFixed(0)}</div>
              <div className="text-[10.5px] uppercase tracking-wide text-t3">Mean outcome</div>
            </div>
            <div>
              <div className="mono text-[16px] font-extrabold text-red">${result.percentile_5.toFixed(0)}</div>
              <div className="text-[10.5px] uppercase tracking-wide text-t3">
                5th percentile
                <GuideHint label="Percentile Band" explanation={GUIDE_METRIC_EXPLANATIONS["Percentile Band"]} />
              </div>
            </div>
            <div>
              <div className="mono text-[16px] font-extrabold text-teal">${result.percentile_95.toFixed(0)}</div>
              <div className="text-[10.5px] uppercase tracking-wide text-t3">95th percentile</div>
            </div>
            <div>
              <div className="mono text-[16px] font-extrabold text-gold">{result.prob_profit.toFixed(0)}%</div>
              <div className="text-[10.5px] uppercase tracking-wide text-t3">
                Prob. of profit
                <GuideHint label="Prob. of Profit" explanation={GUIDE_METRIC_EXPLANATIONS["Prob. of Profit"]} />
              </div>
            </div>
          </div>
        </>
      )}

      {!result && !loading && !error && (
        <p className="text-[12px] text-t3">Pick a horizon above to run the simulation.</p>
      )}
    </GlassPanel>
  );
}
