import { GlassPanel } from "@/components/GlassPanel";

export type Holding = {
  symbol: string;
  name: string;
  sector: string;
  weight: number;
  signal: "BUY" | "SELL" | "HOLD" | string;
  win_rate: number;
  current_price: number;
  price_change: number;
};

export type HoldingsSummary = {
  total_symbols: number;
  avg_win_rate: number;
  best_performer: string;
  best_return: number;
  portfolio_beta: number;
  data_source: string;
  data_date: string;
};

export type HoldingsData = {
  holdings: Holding[];
  summary: HoldingsSummary;
};

const signalColor: Record<string, string> = {
  BUY: "text-teal",
  SELL: "text-red",
  HOLD: "text-t3",
};

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className={`mono text-[20px] font-extrabold ${color ?? "text-t1"}`}>{value}</div>
      <div className="text-[10.5px] uppercase tracking-wide text-t3">{label}</div>
    </div>
  );
}

export function PortfolioOverviewPanel({ data }: { data: HoldingsData | null }) {
  if (!data || data.holdings.length === 0) {
    return (
      <GlassPanel variant="accent" className="lg:col-span-2">
        <h1 className="mb-sp2 text-[20px] font-extrabold text-t1">Portfolio Overview</h1>
        <p className="text-[13px] text-t3">No holdings data available right now.</p>
      </GlassPanel>
    );
  }

  const { holdings, summary } = data;

  return (
    <GlassPanel variant="accent" className="lg:col-span-2">
      <div className="mb-sp5 flex items-center justify-between">
        <h1 className="text-[20px] font-extrabold text-t1">Portfolio Overview</h1>
        <span className="text-[10.5px] text-t3">
          {summary.data_source} · {summary.data_date}
        </span>
      </div>

      <div className="mb-sp5 grid grid-cols-2 gap-sp4 sm:grid-cols-4">
        <Stat label="Holdings" value={String(summary.total_symbols)} />
        <Stat label="Avg Win Rate" value={`${summary.avg_win_rate.toFixed(0)}%`} color="text-teal" />
        <Stat label="Best Performer" value={summary.best_performer} color="text-gold" />
        <Stat label="Portfolio Beta" value={summary.portfolio_beta.toFixed(2)} />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-[12px]">
          <thead>
            <tr className="text-t3">
              <th className="pb-sp2 pr-sp3 font-semibold">Symbol</th>
              <th className="pb-sp2 pr-sp3 font-semibold">Signal</th>
              <th className="pb-sp2 pr-sp3 font-semibold">Weight</th>
              <th className="pb-sp2 pr-sp3 font-semibold">Win Rate</th>
              <th className="pb-sp2 font-semibold">Price</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <tr key={h.symbol} className="border-t border-border">
                <td className="mono py-sp2 pr-sp3 font-bold text-t1">{h.symbol}</td>
                <td className={`py-sp2 pr-sp3 font-semibold ${signalColor[h.signal] ?? "text-t2"}`}>
                  {h.signal}
                </td>
                <td className="mono py-sp2 pr-sp3 text-t2">{(h.weight * 100).toFixed(1)}%</td>
                <td className="mono py-sp2 pr-sp3 text-t2">{h.win_rate.toFixed(0)}%</td>
                <td className="mono py-sp2 text-t2">
                  ${h.current_price.toFixed(2)}
                  <span className={h.price_change >= 0 ? "ml-sp2 text-teal" : "ml-sp2 text-red"}>
                    {h.price_change >= 0 ? "+" : ""}
                    {h.price_change.toFixed(2)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassPanel>
  );
}
