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
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "positive" | "negative" | "neutral";
}) {
  const toneClass = tone === "positive" ? "text-teal" : tone === "negative" ? "text-red" : "text-t1";
  return (
    <div className="rounded-r2 border border-border bg-panel2 px-sp3 py-sp3">
      <div className="flex items-center text-[10.5px] font-semibold uppercase tracking-wide text-t3">
        {label}
        {hint && <GuideHint label={label} explanation={hint} />}
      </div>
      <div className={`mono mt-1 text-[17px] font-bold ${toneClass}`}>{value}</div>
    </div>
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
          hint="Percentage of days in the recorded series with a positive return."
        />
        <StatTile
          label="Total P&L"
          value={stats ? `${stats.total_pnl >= 0 ? "+" : ""}$${stats.total_pnl.toFixed(2)}` : "--"}
          tone={stats ? (stats.total_pnl >= 0 ? "positive" : "negative") : "neutral"}
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
          hint="Total trade notional (sum of shares x price across every recorded trade) divided by current total portfolio value -- a plain turnover ratio."
        />
      </div>
    </GlassPanel>
  );
}
