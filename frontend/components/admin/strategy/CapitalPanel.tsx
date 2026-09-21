"use client";

import { useState } from "react";
import type { CapitalRow, StrategyCurves } from "@/lib/types";
import { MultiCurveChart } from "@/components/charts/MultiCurveChart";
import { Section, Th, WrapperToggle, inWrapper, money, pct, plainPct, tone, type Wrapper } from "./shared";

const days = (n: number | null | undefined) => (n === null || n === undefined ? "—" : n >= 365 ? `${(n / 365).toFixed(1)} yr` : `${Math.round(n)} d`);
const shortName = (n: string) => n.replace(" on all symbols", "").replace(" buy & hold", "").replace("Engine in a tax-sheltered account", "Engine (sheltered)").replace("Placebo in a tax-sheltered account", "Placebo (sheltered)");

/** Capital results of the reference strategies, kept apart by account type. Taxable: judged AFTER an
 * estimated tax, wash-sale rule included. Tax-sheltered (IRA / 401k / Roth-style): trading is untaxed, so
 * the pre-tax result is the result. The same strategy can rank differently in each. */
export function CapitalPanel({ rows, curves, tax }: { rows: CapitalRow[]; curves: StrategyCurves; tax: { short_term: number; long_term: number } }) {
  const [wrapper, setWrapper] = useState<Wrapper>("taxable");
  const view = rows.filter((r) => inWrapper(r, wrapper));
  const series = view.filter((r) => curves[r.id]).map((r) => ({ id: r.id, label: shortName(r.name), curve: curves[r.id] }));
  const taxable = wrapper === "taxable";
  const by = (id: string) => rows.find((r) => r.id === id);
  const engine = by("ctl_engine");
  const aware = by("ctl_taxaware");
  const ira = by("ctl_engine_ira");
  const spy = by("ctl_spy");

  return (
    <div className="flex flex-col gap-sp5">
      <WrapperToggle value={wrapper} onChange={setWrapper} />

      <Section
        title="Reference strategies, rebased to 100"
        note="Left of the dashed line is the in-sample backtest; right of it is live paper trading — the only out-of-sample evidence. Curves are before tax; the tax view is in the table."
      >
        <MultiCurveChart series={series} />
      </Section>

      <Section
        title={taxable ? "Taxable account — capital, risk and tax" : "Tax-sheltered account — capital and risk"}
        note={
          taxable
            ? `Estimated tax on realised gains (short-term ${plainPct(tax.short_term)}, long-term ${plainPct(tax.long_term)} assumed, no carry-forward), with the 30-day wash-sale rule applied. Not tax advice. An unrealised gain is not taxed until you sell.`
            : "Inside an IRA / 401k / Roth-style account realised gains are not taxed and the wash-sale rule does not apply, so what matters is the pre-tax result and trading costs. Buy-and-hold and cash owe no tax anywhere, so they stay as the yardstick."
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead>
              <tr>
                <Th>Strategy</Th>
                <Th right>Equity</Th>
                <Th right>Total</Th>
                <Th right>Live</Th>
                <Th right>Worst drop</Th>
                <Th right>Sharpe</Th>
                <Th right>Turnover / yr</Th>
                {taxable ? (
                  <>
                    <Th right>Avg hold</Th>
                    <Th right>Est. tax</Th>
                    <Th right>After tax</Th>
                    <Th right>Tax drag</Th>
                    <Th right>Held back</Th>
                    <Th right>Wash-sale loss</Th>
                  </>
                ) : (
                  <Th right>Costs</Th>
                )}
              </tr>
            </thead>
            <tbody>
              {view.map((r) => (
                <tr key={r.id} className="border-t border-border text-[12px]">
                  <td className="px-sp3 py-sp2 font-semibold text-t1">{r.name}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t1">{money(r.equity)}</td>
                  <td className={`mono px-sp3 py-sp2 text-right font-semibold ${tone(r.total_return)}`}>{pct(r.total_return)}</td>
                  <td className={`mono px-sp3 py-sp2 text-right ${tone(r.live_return)}`}>{r.live_days ? `${pct(r.live_return)} · ${r.live_days}d` : "—"}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-red">{pct(r.max_drawdown)}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t1">{r.sharpe.toFixed(2)}</td>
                  <td className="mono px-sp3 py-sp2 text-right text-t3">{r.turnover.toFixed(2)}×</td>
                  {taxable ? (
                    <>
                      <td className="mono px-sp3 py-sp2 text-right text-t3">{days(r.avg_holding_days)}</td>
                      <td className="mono px-sp3 py-sp2 text-right text-t3">{r.tax_tracked && r.est_tax !== null ? money(r.est_tax) : "—"}</td>
                      <td className={`mono px-sp3 py-sp2 text-right font-semibold ${tone(r.after_tax_return)}`}>{r.tax_tracked ? pct(r.after_tax_return) : "—"}</td>
                      <td className="mono px-sp3 py-sp2 text-right text-red">{r.tax_tracked && r.tax_drag !== null ? pct(-r.tax_drag) : "—"}</td>
                      <td className="mono px-sp3 py-sp2 text-right text-t3" title="Sells the tax-aware engine deferred to avoid realising a short-term gain">{r.deferred_sells ? `${r.deferred_sells}` : "—"}</td>
                      <td className="mono px-sp3 py-sp2 text-right text-t3" title="Losses disallowed because the stock was rebought within 30 days">{r.wash_disallowed ? money(r.wash_disallowed) : "—"}</td>
                    </>
                  ) : (
                    <td className="mono px-sp3 py-sp2 text-right text-t3">{money(r.cost_paid)}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {taxable && rows.some((r) => !r.tax_tracked) && (
          <p className="mt-sp2 text-[11px] text-gold">Some accounts have no tax data yet; run the verified rebuild (python -m app.scripts.run_paper_cycle --rebuild --apply).</p>
        )}

        {taxable && engine && aware && engine.tax_tracked && aware.tax_tracked && (
          <p className="mt-sp3 text-[12px] leading-snug text-t2">
            <b className="text-t1">Tax-aware vs plain engine.</b> Before tax {pct(aware.total_return)} vs {pct(engine.total_return)}; after tax <b className={tone((aware.after_tax_return ?? 0) - (engine.after_tax_return ?? 0))}>{pct(aware.after_tax_return)}</b> vs {pct(engine.after_tax_return)}
            (tax drag {pct(aware.tax_drag === null ? null : -aware.tax_drag)} vs {pct(engine.tax_drag === null ? null : -engine.tax_drag)}). It turned over {aware.turnover.toFixed(1)}× vs {engine.turnover.toFixed(1)}× a year.
            {spy && spy.tax_tracked && <> Simply holding the market: {pct(spy.after_tax_return)}.</>} Parameters were set in advance, not tuned to this history, and this is still a backtest.
          </p>
        )}
        {!taxable && ira && engine && spy && (
          <p className="mt-sp3 text-[12px] leading-snug text-t2">
            <b className="text-t1">Where it should live.</b> The active engine returned {pct(ira.total_return)} in a sheltered account but only {pct(engine.after_tax_return)} after tax in a taxable one; holding the market returns {pct(spy.total_return)} in either.
            Whatever edge the active strategy has is worth most where tax cannot take a share of it.
          </p>
        )}
      </Section>
    </div>
  );
}
