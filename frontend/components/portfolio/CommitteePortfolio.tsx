"use client";

import { useMemo, useState } from "react";

export type Money = {
  id: string;
  name: string;
  initial: number;
  final: number;
  profit: number;
  return: number | null;
  live_profit: number | null;
  live_return: number | null;
  since: string | null;
  as_of: string | null;
};
type Horizon = { days: number; p5: number; p25: number; p50: number; p75: number; p95: number; prob_above_current: number; prob_above_initial: number; prob_loss_10pct: number };
export type MonteCarlo = {
  method: string;
  simulations: number;
  based_on_days: number;
  horizons: Horizon[];
  fan: { start: number; days: number[]; p5: number[]; p50: number[]; p95: number[] };
} | null;
type SymbolRow = {
  symbol: string;
  policy_weight: number;
  current_weight: number;
  value: number;
  engine_signal: string;
  engine_confidence: number;
  committee_action: string | null;
  committee_date: string | null;
  committee_fresh: boolean;
  headline: string | null;
  consensus: string | null;
  disagrees: boolean;
  pnl: number;
  engine_pnl: number;
};
type Decision = { date: string; symbol: string; engine_signal: string | null; decision: string | null; action: string | null; consensus: string | null; headline: string | null; gated: boolean; answered: number | null; total: number | null };
type Trade = { date: string; symbol: string; side: string; shares: number; price: number; reason: string; by_committee: boolean };
type AgentRow = { agent: string; ranked?: boolean; hit_rate?: number | null; mean_edge?: number | null; directional_calls?: number; agree_with_final?: number | null };
export type PortfolioView = {
  label: string;
  is_model_portfolio: boolean;
  simulated: boolean;
  watchlist: string[];
  risk_level: string | null;
  live_from: string | null;
  live_days: number;
  committee: Money;
  engine: Money;
  benchmark: Money;
  committee_added: { dollars: number; points: number | null; note: string };
  curves: { dates: string[]; live_from: string | null; committee: (number | null)[]; engine: (number | null)[]; benchmark: (number | null)[] };
  symbols: SymbolRow[];
  decisions: Decision[];
  trades: Trade[];
  monte_carlo: { committee: MonteCarlo; engine: MonteCarlo };
  agents: { reviews: number; agents: AgentRow[]; note?: string | null };
};

const usd = (v: number | null | undefined) => (v == null ? "n/a" : `${v < 0 ? "-" : ""}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`);
const signedUsd = (v: number) => `${v >= 0 ? "+" : "-"}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const pct = (v: number | null | undefined, d = 1) => (v == null ? "n/a" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`);
const tone = (v: number | null | undefined) => (v == null || v === 0 ? "text-t2" : v > 0 ? "text-teal" : "text-red");

const W = 640;
const H = 220;
const PAD = 12;

function Stat({ label, value, sub, cls = "text-t1" }: { label: string; value: string; sub?: string; cls?: string }) {
  return (
    <div className="rounded-r2 border border-border bg-bg2/40 px-sp3 py-sp3">
      <div className="text-[9.5px] font-bold uppercase tracking-wider text-t3">{label}</div>
      <div className={`mono mt-1 text-[18px] font-extrabold ${cls}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-t3">{sub}</div>}
    </div>
  );
}

function GrowthChart({ v }: { v: PortfolioView }) {
  const [liveOnly, setLiveOnly] = useState(false);
  const c = v.curves;
  const liveIdx = c.live_from ? c.dates.indexOf(c.live_from) : -1;
  const from = liveOnly && liveIdx > 0 ? liveIdx - 1 : 0;
  const series = useMemo(
    () =>
      [
        { key: "benchmark", label: "Policy benchmark (just hold your plan)", cls: "stroke-t3", vals: c.benchmark.slice(from) },
        { key: "engine", label: "Engine only", cls: "stroke-gold", vals: c.engine.slice(from) },
        { key: "committee", label: "Run by the committee", cls: "stroke-teal", vals: c.committee.slice(from) },
      ] as const,
    [c, from],
  );
  const dates = c.dates.slice(from);
  const all = series.flatMap((s) => s.vals.filter((x): x is number => x != null));
  if (dates.length < 2 || all.length < 2) return <p className="text-[12px] text-t3">Not enough history to chart yet.</p>;
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const x = (i: number) => PAD + (i / (dates.length - 1)) * (W - 2 * PAD);
  const y = (val: number) => H - PAD - ((val - lo) / (hi - lo || 1)) * (H - 2 * PAD);
  const path = (vals: (number | null)[]) => vals.map((val, i) => (val == null ? "" : `${i === 0 || vals[i - 1] == null ? "M" : "L"}${x(i).toFixed(1)},${y(val).toFixed(1)}`)).join(" ");
  const liveX = liveIdx >= from && liveIdx >= 0 ? x(liveIdx - from) : null;
  return (
    <div>
      <div className="mb-sp2 flex flex-wrap items-center justify-between gap-sp2">
        <div className="flex flex-wrap gap-sp3 text-[10.5px] text-t3">
          {[...series].reverse().map((s) => (
            <span key={s.key} className="flex items-center gap-1">
              <svg width="14" height="6" aria-hidden><line x1="0" y1="3" x2="14" y2="3" className={s.cls} strokeWidth="2" /></svg>
              {s.label}
            </span>
          ))}
        </div>
        {liveIdx > 0 && (
          <div className="flex gap-1" role="group" aria-label="Chart range">
            {[["All history", false], ["Live only", true]].map(([label, val]) => (
              <button key={String(label)} type="button" onClick={() => setLiveOnly(val as boolean)} aria-pressed={liveOnly === val} className={`rounded-r1 border px-sp2 py-0.5 text-[10.5px] ${liveOnly === val ? "border-teal/60 bg-teal-dim text-teal" : "border-border text-t3"}`}>
                {label as string}
              </button>
            ))}
          </div>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Portfolio value from ${dates[0]} to ${dates[dates.length - 1]}`}>
        {liveX != null && (
          <>
            <line x1={liveX} x2={liveX} y1={PAD} y2={H - PAD} className="stroke-border" strokeDasharray="3 3" />
            <text x={liveX + 4} y={PAD + 8} className="fill-t3" fontSize="9">committee live →</text>
          </>
        )}
        {series.map((s) => (
          <path key={s.key} d={path(s.vals as (number | null)[])} fill="none" className={s.cls} strokeWidth={s.key === "committee" ? 2.2 : 1.5} strokeLinejoin="round" />
        ))}
        <text x={PAD} y={H - 2} className="fill-t3" fontSize="9">{dates[0]}</text>
        <text x={W - PAD} y={H - 2} textAnchor="end" className="fill-t3" fontSize="9">{dates[dates.length - 1]}</text>
        <text x={W - PAD} y={PAD + 8} textAnchor="end" className="fill-t3" fontSize="9">{usd(hi)}</text>
        <text x={W - PAD} y={H - PAD - 2} textAnchor="end" className="fill-t3" fontSize="9">{usd(lo)}</text>
      </svg>
    </div>
  );
}

function Fan({ mc, label }: { mc: NonNullable<MonteCarlo>; label: string }) {
  const f = mc.fan;
  const lo = Math.min(...f.p5, f.start);
  const hi = Math.max(...f.p95, f.start);
  const maxDay = f.days[f.days.length - 1];
  const x = (d: number) => PAD + (d / maxDay) * (W - 2 * PAD);
  const y = (val: number) => H - PAD - ((val - lo) / (hi - lo || 1)) * (H - 2 * PAD);
  const band = `M${x(0)},${y(f.start)} ${f.days.map((d, i) => `L${x(d).toFixed(1)},${y(f.p95[i]).toFixed(1)}`).join(" ")} ${[...f.days].reverse().map((d, i) => `L${x(d).toFixed(1)},${y(f.p5[f.days.length - 1 - i]).toFixed(1)}`).join(" ")} Z`;
  const mid = `M${x(0)},${y(f.start)} ${f.days.map((d, i) => `L${x(d).toFixed(1)},${y(f.p50[i]).toFixed(1)}`).join(" ")}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${label}: range of simulated outcomes over the next ${maxDay} trading days`}>
      <path d={band} fill="currentColor" fillOpacity={0.15} className="text-teal" />
      <path d={mid} fill="none" className="stroke-teal" strokeWidth="2" />
      <line x1={PAD} x2={W - PAD} y1={y(f.start)} y2={y(f.start)} className="stroke-border" strokeDasharray="3 3" />
      <text x={PAD} y={H - 2} className="fill-t3" fontSize="9">today {usd(f.start)}</text>
      <text x={W - PAD} y={H - 2} textAnchor="end" className="fill-t3" fontSize="9">+{maxDay} trading days</text>
      <text x={W - PAD} y={PAD + 8} textAnchor="end" className="fill-t3" fontSize="9">95th {usd(f.p95[f.p95.length - 1])}</text>
      <text x={W - PAD} y={H - PAD - 2} textAnchor="end" className="fill-t3" fontSize="9">5th {usd(f.p5[f.p5.length - 1])}</text>
    </svg>
  );
}

const horizonLabel = (d: number) => (d <= 21 ? "1 month" : d <= 63 ? "3 months" : "1 year");

function MonteCarloBlock({ v }: { v: PortfolioView }) {
  const mc = v.monte_carlo.committee;
  const eng = v.monte_carlo.engine;
  if (!mc) return <p className="text-[12px] text-t3">Not enough history yet for a Monte Carlo estimate (needs about 60 trading days).</p>;
  return (
    <div>
      <Fan mc={mc} label="Committee-run portfolio" />
      <div className="mt-sp3 overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-[12px]">
          <thead className="text-[10px] uppercase tracking-wide text-t3">
            <tr><th className="py-1 pr-sp3">Horizon</th><th className="pr-sp3">Poor case (5%)</th><th className="pr-sp3">Middle</th><th className="pr-sp3">Good case (95%)</th><th className="pr-sp3">Chance above today</th><th>Chance above start</th></tr>
          </thead>
          <tbody>
            {mc.horizons.map((h) => (
              <tr key={h.days} className="border-t border-white/[0.04]">
                <td className="py-1 pr-sp3 font-semibold text-t1">{horizonLabel(h.days)}</td>
                <td className="mono pr-sp3 text-red">{usd(h.p5)}</td>
                <td className="mono pr-sp3 text-t1">{usd(h.p50)}</td>
                <td className="mono pr-sp3 text-teal">{usd(h.p95)}</td>
                <td className="mono pr-sp3">{(h.prob_above_current * 100).toFixed(0)}%</td>
                <td className="mono">{(h.prob_above_initial * 100).toFixed(0)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {eng && (
        <p className="mt-sp2 text-[11px] text-t3">
          Engine-only for comparison, 1 year middle case: <span className="mono text-t2">{usd(eng.horizons[eng.horizons.length - 1].p50)}</span> vs committee-run{" "}
          <span className="mono text-t2">{usd(mc.horizons[mc.horizons.length - 1].p50)}</span>.
          {v.live_days < 30 && " The two are nearly identical because the committee has only been trading for a few days."}
        </p>
      )}
      <p className="mt-sp2 text-[10.5px] leading-snug text-t3">
        An estimate, not a forecast: {mc.simulations.toLocaleString()} random futures built by reshuffling this portfolio&rsquo;s own {mc.based_on_days.toLocaleString()} past daily results.
        It can&rsquo;t see regime changes, and most of that history is a backtest.
      </p>
    </div>
  );
}

function Chip({ text, cls }: { text: string | null; cls?: string }) {
  if (!text) return <span className="text-t3">–</span>;
  const c = cls ?? (text === "BUY" ? "text-teal" : text === "SELL" ? "text-red" : "text-t2");
  return <span className={`text-[11px] font-bold ${c}`}>{text}</span>;
}

export function CommitteePortfolio({ v, compact = false }: { v: PortfolioView; compact?: boolean }) {
  const c = v.committee;
  return (
    <div className="flex flex-col gap-sp4">
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-sp2">
          <h3 className="text-[14px] font-bold text-t1">{v.label}</h3>
          <span className="text-[10.5px] text-t3">
            {v.watchlist.join(" · ")}
            {v.risk_level ? ` · ${v.risk_level} risk` : ""} · simulated paper trading, not real money
          </span>
        </div>
        {v.is_model_portfolio && <p className="mt-1 text-[11px] text-gold">You have no personal paper portfolio yet, so this is GlassBox&rsquo;s shared model portfolio over every tracked stock.</p>}
      </div>

      <div className="grid grid-cols-2 gap-sp3 lg:grid-cols-4">
        <Stat label="Started with" value={usd(c.initial)} sub={c.since ? `since ${c.since}` : undefined} />
        <Stat label="Now" value={usd(c.final)} sub={c.as_of ? `as of ${c.as_of}` : undefined} />
        <Stat label="Profit" value={`${signedUsd(c.profit)}`} sub={pct(c.return)} cls={tone(c.profit)} />
        <Stat
          label="Committee added"
          value={signedUsd(v.committee_added.dollars)}
          sub={v.committee_added.points != null ? `${v.committee_added.points >= 0 ? "+" : ""}${(v.committee_added.points * 100).toFixed(2)} pts vs engine only` : undefined}
          cls={tone(v.committee_added.dollars)}
        />
      </div>
      <p className="-mt-sp2 text-[11px] leading-snug text-t3">
        {v.committee_added.note}{" "}
        {v.live_days > 0 ? `Live (out-of-sample) since ${v.live_from}: ${v.live_days} trading day${v.live_days === 1 ? "" : "s"}, ${pct(c.live_return, 2)}.` : "Everything shown is backtest so far."} Before the committee started, its line matches the engine&rsquo;s by construction.
      </p>

      <section aria-label="Portfolio growth">
        <h4 className="mb-sp2 text-[12px] font-bold text-t1">Growth: committee-run vs engine-only vs your plan</h4>
        <GrowthChart v={v} />
        <div className="mt-sp2 grid grid-cols-3 gap-sp2 text-[11px] text-t3">
          <span>Committee-run <b className={tone(v.committee.return)}>{pct(v.committee.return)}</b></span>
          <span>Engine only <b className={tone(v.engine.return)}>{pct(v.engine.return)}</b></span>
          <span>Plan (benchmark) <b className={tone(v.benchmark.return)}>{pct(v.benchmark.return)}</b></span>
        </div>
      </section>

      <section aria-label="Monte Carlo estimate">
        <h4 className="mb-sp2 text-[12px] font-bold text-t1">Where it could go: Monte Carlo estimate</h4>
        <MonteCarloBlock v={v} />
      </section>

      <section aria-label="Where the money and the calls are">
        <h4 className="mb-sp2 text-[12px] font-bold text-t1">By stock: how the money is spread and why</h4>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-[12px]">
            <thead className="text-[10px] uppercase tracking-wide text-t3">
              <tr><th className="py-1 pr-sp3">Stock</th><th className="pr-sp3">Plan</th><th className="pr-sp3">Holding</th><th className="pr-sp3">Engine</th><th className="pr-sp3">Committee</th><th className="pr-sp3">Profit</th><th>Why</th></tr>
            </thead>
            <tbody>
              {v.symbols.map((s) => (
                <tr key={s.symbol} className="border-t border-white/[0.04] align-top">
                  <td className="py-1.5 pr-sp3 font-extrabold text-t1">{s.symbol}</td>
                  <td className="mono pr-sp3">{(s.policy_weight * 100).toFixed(0)}%</td>
                  <td className="mono pr-sp3">{(s.current_weight * 100).toFixed(0)}%<span className="text-t3"> {usd(s.value)}</span></td>
                  <td className="pr-sp3"><Chip text={s.engine_signal} /></td>
                  <td className="pr-sp3">
                    <Chip text={s.committee_action} />
                    {s.committee_action && (s.disagrees ? <span className="ml-1 text-[10px] text-gold">overruled engine</span> : null)}
                    {s.committee_action && !s.committee_fresh && <span className="ml-1 text-[10px] text-t3">({s.committee_date}, older)</span>}
                  </td>
                  <td className={`mono pr-sp3 ${tone(s.pnl)}`}>{signedUsd(s.pnl)}</td>
                  <td className="text-[11px] leading-snug text-t2">{s.headline ?? (s.committee_action ? s.consensus : "No committee review on this stock yet")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {!compact && (
        <>
          <section aria-label="Agent progress">
            <h4 className="mb-sp2 text-[12px] font-bold text-t1">How the committee&rsquo;s agents are doing on these stocks</h4>
            {v.agents.agents.some((a) => a.ranked) ? (
              <ul className="grid gap-sp2 sm:grid-cols-2">
                {v.agents.agents.filter((a) => a.ranked).map((a) => (
                  <li key={a.agent} className="rounded-r2 border border-border bg-bg2/40 px-sp3 py-sp2 text-[12px]">
                    <b className="text-t1">{a.agent}</b>{" "}
                    <span className="text-t3">hit rate {a.hit_rate != null ? `${(a.hit_rate * 100).toFixed(0)}%` : "n/a"} · edge {pct(a.mean_edge ?? null)} · {a.directional_calls ?? 0} scored calls</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[12px] text-t3">{v.agents.note ?? "Not enough scored calls yet."} ({v.agents.reviews} review{v.agents.reviews === 1 ? "" : "s"} on these stocks so far.)</p>
            )}
          </section>

          <section aria-label="Recent committee decisions">
            <h4 className="mb-sp2 text-[12px] font-bold text-t1">Recent committee decisions and trades</h4>
            <div className="grid gap-sp4 lg:grid-cols-2">
              <ul className="flex flex-col gap-sp2">
                {v.decisions.length === 0 && <li className="text-[12px] text-t3">No reviews of these stocks yet.</li>}
                {v.decisions.slice(0, 10).map((d) => (
                  <li key={`${d.date}${d.symbol}`} className="rounded-r2 border border-border bg-bg2/40 px-sp3 py-sp2 text-[12px]">
                    <span className="mono text-t3">{d.date}</span> <b className="text-t1">{d.symbol}</b> engine <Chip text={d.engine_signal} /> → committee <Chip text={d.action ?? d.decision} />
                    {d.gated && <span className="ml-1 text-[10px] text-gold">risk-gated</span>}
                    {d.headline && <div className="mt-0.5 text-[11px] text-t2">{d.headline}</div>}
                    <div className="text-[10px] text-t3">{d.consensus ?? "no consensus"} · {d.answered}/{d.total} agents answered</div>
                  </li>
                ))}
              </ul>
              <ul className="flex flex-col gap-sp2">
                {v.trades.length === 0 && <li className="text-[12px] text-t3">No trades yet.</li>}
                {v.trades.slice(0, 10).map((t, i) => (
                  <li key={`${t.date}${t.symbol}${i}`} className="rounded-r2 border border-border bg-bg2/40 px-sp3 py-sp2 text-[12px]">
                    <span className="mono text-t3">{t.date}</span> <Chip text={t.side} cls={t.side === "BUY" ? "text-teal" : "text-red"} /> {t.shares} <b className="text-t1">{t.symbol}</b> @ {t.price}
                    <div className="text-[11px] text-t2">{t.reason}{t.by_committee ? " · committee-driven" : ""}</div>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
