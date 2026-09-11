import { GlassPanel } from "@/components/GlassPanel";
import { GuideHint } from "@/components/onboarding/GuideBubble";

export type DailySummaryData = {
  sharpe: number;
  max_dd: number;
  win_rate: number;
  risk_status: "LOW" | "MEDIUM" | "HIGH";
};

export type PortfolioStatsData = {
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  realized_pnl: number;
  unrealized_pnl: number;
  churn_rate: number;
  num_trades: number;
  has_trade_history: boolean;
};

function StatTile({
  label,
  value,
  hint,
  tone = "neutral",
  gauge,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "positive" | "negative" | "neutral";
  // 0..1 -- only ever set from a real single scalar already on the tile
  // (e.g. churn rate itself), never a fabricated multi-point series. A
  // ring is an honest way to graph one real number; a sparkline would
  // imply history that doesn't exist for these metrics.
  gauge?: number;
}) {
  const toneClass = tone === "positive" ? "text-teal" : tone === "negative" ? "text-red" : "text-t1";
  const arrow = tone === "positive" ? "▲" : tone === "negative" ? "▼" : null;
  const ringColor = tone === "negative" ? "var(--c-red)" : "var(--c-teal)";
  return (
    <div
      className="relative overflow-hidden rounded-r2 border border-border2 px-sp3 py-sp3"
      style={{
        background: "linear-gradient(165deg, rgba(255,255,255,.05), rgba(255,255,255,.01))",
        backdropFilter: "blur(6px)",
        WebkitBackdropFilter: "blur(6px)",
      }}
    >
      <div className="flex items-center justify-between gap-sp2">
        <div className="flex items-center text-[10.5px] font-semibold uppercase tracking-wide text-t3">
          {label}
          {hint && <GuideHint label={label} explanation={hint} />}
        </div>
        {gauge !== undefined && <GaugeRing fraction={gauge} color={ringColor} />}
      </div>
      <div className={`mono mt-1 flex items-baseline gap-1 text-[17px] font-bold ${toneClass}`}>
        {arrow && <span className="text-[11px]">{arrow}</span>}
        {value}
      </div>
    </div>
  );
}

/** Small ring gauge for a single real 0..1 fraction -- filled arc length
 * proportional to the value, nothing interpolated or fabricated. */
function GaugeRing({ fraction, color }: { fraction: number; color: string }) {
  const clamped = Math.max(0, Math.min(1, fraction));
  const r = 12;
  const c = 2 * Math.PI * r;
  return (
    <svg width={28} height={28} viewBox="0 0 28 28" className="shrink-0" aria-hidden="true">
      <circle cx={14} cy={14} r={r} fill="none" stroke="var(--c-border2)" strokeWidth={3} />
      <circle
        cx={14}
        cy={14}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={3}
        strokeLinecap="round"
        strokeDasharray={`${c * clamped} ${c}`}
        transform="rotate(-90 14 14)"
      />
    </svg>
  );
}

/**
 * Real risk/return + P&L/turnover stats in one board: sharpe/max_dd/win_rate
 * come from /api/daily-summary (data_source.py's get_daily_summary, ported
 * from the legacy dashboard's own formulas -- already computed, just never
 * surfaced on the main dashboard before). total_pnl/realized/unrealized/
 * churn_rate come from /api/portfolio-stats (DAILY_PNL.py's FIFO P&L
 * matching, see that endpoint's docstring). Churn/P&L tiles show an
 * explicit "no trade history yet" note instead of a bare 0% when
 * has_trade_history is false, since a real zero and "nothing recorded"
 * are different facts and collapsing them would be misleading.
 */
export function StatsBoard({ summary, stats }: { summary: DailySummaryData | null; stats: PortfolioStatsData | null }) {
  return (
    <GlassPanel variant="frost" className="lg:col-span-3">
      <h2 className="mb-sp1 text-[15px] font-bold text-t1">Stats Board</h2>
      <p className="mb-sp4 text-[11.5px] text-t3">
        Risk/return metrics from the latest daily report series, plus real P&amp;L and turnover from your recorded
        trades.
      </p>

      <div className="grid grid-cols-2 gap-sp3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile
          label="Sharpe"
          value={summary ? summary.sharpe.toFixed(2) : "--"}
          hint="Risk-adjusted return: average daily return divided by its volatility, annualized. Higher is better."
        />
        <StatTile
          label="Max Drawdown"
          value={summary ? `${summary.max_dd.toFixed(1)}%` : "--"}
          tone={summary && summary.max_dd > 15 ? "negative" : "neutral"}
          hint="The largest peak-to-trough decline in portfolio value over the recorded series."
        />
        <StatTile
          label="Win Rate"
          value={summary ? `${summary.win_rate.toFixed(1)}%` : "--"}
          gauge={summary ? summary.win_rate / 100 : undefined}
          tone={summary && summary.win_rate >= 50 ? "positive" : "neutral"}
          hint="Percentage of days in the recorded series with a positive return."
        />
        <StatTile
          label="Total P&L"
          value={stats ? `${stats.total_pnl >= 0 ? "+" : ""}$${stats.total_pnl.toFixed(2)}` : "--"}
          tone={stats ? (stats.total_pnl > 0 ? "positive" : stats.total_pnl < 0 ? "negative" : "neutral") : "neutral"}
          hint="Current total value minus initial capital -- cash plus the live market value of open positions."
        />
        <StatTile
          label="Realized / Unrealized"
          value={stats ? `$${stats.realized_pnl.toFixed(0)} / $${stats.unrealized_pnl.toFixed(0)}` : "--"}
          hint="Realized: locked-in profit from closed (FIFO-matched) trades. Unrealized: paper gain/loss on open positions at current prices."
        />
        <StatTile
          label="Churn Rate"
          value={stats ? (stats.has_trade_history ? `${(stats.churn_rate * 100).toFixed(1)}%` : "No trades yet") : "--"}
          gauge={stats?.has_trade_history ? stats.churn_rate : undefined}
          hint="Total trade notional (sum of shares x price across every recorded trade) divided by current total portfolio value -- a plain turnover ratio."
        />
      </div>
    </GlassPanel>
  );
}
