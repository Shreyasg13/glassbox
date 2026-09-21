"use client";

import type { CapitalRow, StrategyCurves } from "@/lib/types";
import { MultiCurveChart } from "@/components/charts/MultiCurveChart";
import { Section, Th, money, pct, plainPct, tone } from "./shared";

const days = (n: number | null | undefined) => (n === null || n === undefined ? "—" : n >= 365 ? `${(n / 365).toFixed(1)} yr` : `${Math.round(n)} d`);

/** Capital results of the reference strategies -- pre-tax and after an ESTIMATED tax -- so the
 * cost of trading actively is visible next to what it earned. Buy-and-hold pays nothing until it
 * sells; every rebalance by the engine can realise a taxable gain. */
export function CapitalPanel({ rows, curves, tax }: { rows: CapitalRow[]; curves: StrategyCurves; tax: { short_term: number; long_term: number } }) {
  const series = rows.filter((r) => curves[r.id]).map((r) => ({ id: r.id, label: r.name.replace(" on all symbols", "").replace(" buy & hold", ""), curve: curves[r.id] }));
  const engine = rows.find((r) => r.id === "ctl_engine");
  const hold = rows.find((r) => r.id === "ctl_spy");
  return (
    <div className="flex flex-col gap-sp5">
      <Section title="Reference strategies, rebased to 100" note="Every strategy starts with the same idea of $100k. Left of the dashed line is the in-sample backtest; right of it is live paper trading — the only out-of-sample evidence.">
        <MultiCurveChart series={series} />
      </Section>

      <Section
        title="Capital, risk and tax"
        note={`Tax is an estimate on realised gains only (short-term ${plainPct(tax.short_term)}, long-term ${plainPct(tax.long_term)} assumed, no carry-forward) — not tax advice. An unrealised gain is not taxed until you sell.`}
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px]">
            <thead>
              <tr>
                <Th>Strategy</Th>
                <Th right>Equity</Th>
                <Th right>Total</Th>
                <Th right>Live</Th>
                <Th right>Worst drop</Th>
                <Th right>Sharpe</Th>
                <Th right>Turnover / yr</Th>
                <Th right>Avg hold</Th>
                <Th right>Est. tax</Th>
                <Th right>After tax</Th>
                <Th right>Tax drag</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-border text-[12px]">
                  <td className="px-sp3 py-sp2 font-semibold text-t1">{r.name}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t1">{money(r.equity)}</td>
                  <td className={`mono px-sp3 py-sp2 text-right font-semibold ${tone(r.total_return)}`}>{pct(r.total_return)}</td>
                  <td className={`mono px-sp3 py-sp2 text-right ${tone(r.live_return)}`}>{r.live_days ? `${pct(r.live_return)} · ${r.live_days}d` : "—"}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-red">{pct(r.max_drawdown)}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t1">{r.sharpe.toFixed(2)}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t3">{r.turnover.toFixed(2)}×</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t3">{days(r.avg_holding_days)}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t3">{r.tax_tracked && r.est_tax !== null ? money(r.est_tax) : "—"}</td>
                  <td className={`mono px-sp3 py-sp2 text-right font-semibold ${tone(r.after_tax_return)}`}>{r.tax_tracked ? pct(r.after_tax_return) : "—"}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-red">{r.tax_tracked && r.tax_drag !== null ? pct(-r.tax_drag) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.some((r) => !r.tax_tracked) && (
          <p className="mt-sp2 text-[11px] text-gold">Tax columns show “—” for accounts created before tax tracking; run the verified rebuild (python -m app.scripts.run_paper_cycle --rebuild --apply) to fill them in without changing any history.</p>
        )}
        {engine && hold && engine.tax_tracked && hold.tax_tracked && (
          <p className="mt-sp3 text-[12px] text-t2">
            Reading it: the signal engine returned {pct(engine.total_return)} before tax and {pct(engine.after_tax_return)} after, versus {pct(hold.total_return)} / {pct(hold.after_tax_return)} for holding the market.
            An active strategy has to beat buy-and-hold by more than its tax drag ({pct(engine.tax_drag === null ? null : -engine.tax_drag)}) before it is worth running with real money.
          </p>
        )}
      </Section>
    </div>
  );
}
