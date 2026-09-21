import type { Lean, RiskLevel } from "@/lib/types";

export const pct = (n: number | null | undefined, digits = 1) => (n === null || n === undefined ? "—" : `${n >= 0 ? "+" : ""}${(n * 100).toFixed(digits)}%`);
export const plainPct = (n: number | null | undefined, digits = 0) => (n === null || n === undefined ? "—" : `${(n * 100).toFixed(digits)}%`);
export const money = (n: number) => `$${Math.round(n).toLocaleString()}`;
export const tone = (n: number | null | undefined) => (n === null || n === undefined ? "text-t3" : n >= 0 ? "text-teal" : "text-red");

export const leanTone = (l: string | null | undefined) => (l === "BUY" ? "text-teal" : l === "SELL" ? "text-red" : l === "HOLD" ? "text-t2" : "text-t3");
const leanBg = (l: string | null | undefined) => (l === "BUY" ? "bg-teal-dim text-teal" : l === "SELL" ? "bg-red-dim text-red" : "bg-bg3 text-t2");
const riskBg = (r: string | null | undefined) => (r === "HIGH" ? "bg-red-dim text-red" : r === "LOW" ? "bg-green-dim text-green" : "bg-gold-dim text-gold");

export function LeanChip({ lean, small }: { lean: Lean | string | null | undefined; small?: boolean }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-r1 px-2 py-[1px] font-bold ${small ? "text-[10px]" : "text-[11px]"} ${leanBg(lean)}`}>{lean ?? "—"}</span>
  );
}

export function RiskChip({ level, score }: { level: RiskLevel | string | null | undefined; score?: number }) {
  if (!level) return <span className="text-[10px] text-t3">risk n/a</span>;
  return (
    <span className={`inline-block whitespace-nowrap rounded-r1 px-2 py-[1px] text-[10px] font-bold ${riskBg(level)}`}>
      {level} risk{score !== undefined ? ` · ${Math.round(score)}` : ""}
    </span>
  );
}

export function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return <th className={`px-sp3 py-sp2 text-[10px] font-bold uppercase tracking-wide text-t3 ${right ? "text-right" : "text-left"}`}>{children}</th>;
}

/** A BUY / HOLD / SELL vote split as one horizontal bar. */
export function VoteBar({ votes }: { votes: { BUY: number; SELL: number; HOLD: number } | null }) {
  if (!votes) return null;
  const total = votes.BUY + votes.SELL + votes.HOLD || 1;
  const seg = (k: "BUY" | "HOLD" | "SELL", color: string) => (
    <div style={{ width: `${(votes[k] / total) * 100}%` }} className={color} title={`${k} ${votes[k].toFixed(1)}`} />
  );
  return (
    <div>
      <div className="flex h-[8px] w-full overflow-hidden rounded-full bg-bg3">
        {seg("BUY", "bg-teal")}
        {seg("HOLD", "bg-t3")}
        {seg("SELL", "bg-red")}
      </div>
      <div className="mono mt-1 flex justify-between text-[10px] text-t3">
        <span className="text-teal">BUY {votes.BUY.toFixed(1)}</span>
        <span>HOLD {votes.HOLD.toFixed(1)}</span>
        <span className="text-red">SELL {votes.SELL.toFixed(1)}</span>
      </div>
    </div>
  );
}

export function Section({ title, note, children, right }: { title: string; note?: React.ReactNode; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="glass-panel p-sp4">
      <div className="mb-sp3 flex flex-wrap items-start justify-between gap-sp3">
        <div>
          <h2 className="text-[13px] font-bold uppercase tracking-wide text-t3">{title}</h2>
          {note && <p className="mt-1 max-w-[80ch] text-[11px] text-t3">{note}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

export type Wrapper = "taxable" | "sheltered";

/** Which account wrapper a strategy row belongs to. Passive references (buy-and-hold, cash) owe no
 * tax in either wrapper, so they appear in both views as the yardstick. */
export const inWrapper = (r: { tax_status?: string; strategy: string }, w: Wrapper) =>
  w === "taxable" ? r.tax_status !== "sheltered" : r.tax_status === "sheltered" || r.strategy === "static_hold" || r.strategy === "cash";

const WRAPPERS: { id: Wrapper; label: string; hint: string }[] = [
  { id: "taxable", label: "Taxable account", hint: "brokerage — tax on realised gains" },
  { id: "sheltered", label: "Tax-sheltered account", hint: "IRA · 401k · Roth — no tax on trading" },
];

/** Keeps the two ledgers apart: the same strategy is judged after tax in a taxable account and
 * before tax in a sheltered one, and the answer can differ. */
export function WrapperToggle({ value, onChange }: { value: Wrapper; onChange: (w: Wrapper) => void }) {
  return (
    <div className="inline-flex flex-wrap gap-sp2" role="tablist" aria-label="Account type">
      {WRAPPERS.map((w) => (
        <button
          key={w.id}
          type="button"
          role="tab"
          aria-selected={value === w.id}
          onClick={() => onChange(w.id)}
          className={`rounded-r2 border px-sp3 py-sp2 text-left ${value === w.id ? "border-teal/60 bg-teal-dim" : "border-border bg-bg2/40 hover:bg-bg3"}`}
        >
          <div className={`text-[12px] font-bold ${value === w.id ? "text-teal" : "text-t1"}`}>{w.label}</div>
          <div className="text-[10px] text-t3">{w.hint}</div>
        </button>
      ))}
    </div>
  );
}
