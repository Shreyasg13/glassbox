"use client";

import { useState } from "react";

type Metric = {
  ticker: string;
  name: string;
  score: number;
  risk: "Low" | "Moderate";
  de: number;
  zscore: number;
  beta: number;
  price: string;
  change: string;
};

// Mock evidence data matching the source onboarding mockup (obSwitchTicker payloads).
// Replace with a real call to /api/holdings/:ticker/verify once the backend is wired.
const mockMetrics: Record<string, Metric> = {
  AAPL: { ticker: "AAPL", name: "Apple Inc.", score: 8.4, risk: "Low", de: 1.78, zscore: 6.24, beta: 1.22, price: "$182.40", change: "+2.1%" },
  MSFT: { ticker: "MSFT", name: "Microsoft Corp.", score: 9.1, risk: "Low", de: 0.62, zscore: 8.12, beta: 0.95, price: "$415.20", change: "+1.4%" },
  NVDA: { ticker: "NVDA", name: "NVIDIA Corp.", score: 8.7, risk: "Low", de: 0.44, zscore: 7.66, beta: 1.78, price: "$901.44", change: "+3.2%" },
  TSLA: { ticker: "TSLA", name: "Tesla Inc.", score: 5.8, risk: "Moderate", de: 3.21, zscore: 2.88, beta: 2.1, price: "$218.90", change: "-1.8%" },
};

export function StepVerify({ tickers }: { tickers: string[] }) {
  const available = tickers.filter((t) => mockMetrics[t]);
  const list = available.length > 0 ? available : ["AAPL"];
  const [active, setActive] = useState(list[0]);
  const m = mockMetrics[active] ?? mockMetrics.AAPL;
  const isRisk = m.risk === "Moderate";

  return (
    <div>
      <div className="mb-1 text-[17px] font-bold text-t1">Your first Glass Box verification</div>
      <div className="mb-sp4 text-[13px] text-t3">
        See Glass Box work on your top holding. Every number is backed by institutional data and
        confirmed by Auditor A6.
      </div>

      <div className="mb-sp4 flex flex-wrap gap-sp2">
        {list.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setActive(t)}
            className={`mono rounded-r4 border px-sp3 py-1 text-[12px] font-bold ${
              active === t
                ? "border-teal bg-teal/[0.06] text-teal"
                : "border-border bg-bg2 text-t3 hover:border-border2"
            }`}
          >
            {t}
            {mockMetrics[t]?.risk === "Moderate" ? " ⚠" : ""}
          </button>
        ))}
      </div>

      <div className="rounded-r2 border border-border bg-bg2 p-sp4">
        <div className="mb-sp4 flex items-center gap-sp4">
          <div
            className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-full border-[3px]"
            style={{
              borderColor: isRisk ? "var(--c-gold)" : "var(--c-teal)",
              background: isRisk ? "rgba(232,160,32,.05)" : "rgba(13,204,170,.04)",
            }}
          >
            <div
              className="text-[24px] font-black leading-none"
              style={{ color: isRisk ? "var(--c-gold)" : "var(--c-teal)" }}
            >
              {m.score}
            </div>
            <div className="mt-0.5 text-[8px] font-semibold uppercase tracking-wide text-t3">
              Score
            </div>
          </div>
          <div className="flex-1">
            <div className="mb-1 text-[15px] font-extrabold text-t1">
              {m.name} · {m.ticker}
            </div>
            <div className="flex flex-wrap items-center gap-sp2">
              <span className="text-[12px] text-t3">NASDAQ · Technology</span>
              <span className="flex items-center gap-1 rounded-r2 border border-teal/15 px-2 py-0.5 text-[11px] text-teal">
                ✓ A6 Verified
              </span>
              <span
                className={`rounded-r4 px-2 py-0.5 text-[11px] font-semibold ${
                  isRisk ? "bg-gold-dim text-gold" : "bg-green-dim text-green"
                }`}
              >
                {m.risk} Risk
              </span>
            </div>
          </div>
          <div className="text-right">
            <div className="mono text-[16px] font-bold text-t1">{m.price}</div>
            <div className={`text-[12px] font-semibold ${m.change.startsWith("-") ? "text-red" : "text-green"}`}>
              {m.change}
            </div>
          </div>
        </div>

        <div className="mb-sp3 flex flex-col gap-sp2">
          <EvidenceRow label="Debt / Equity Ratio" source="FMP API · 2hr ago" value={m.de} color="var(--c-teal)" tag="Low" />
          <EvidenceRow label="Altman Z-Score" source="FMP · Calculated · Safe Zone >2.99" value={m.zscore} color="var(--c-gold)" tag="Very Low" />
          <EvidenceRow label="Beta vs S&P 500" source="Twelve Data · Live" value={m.beta} color="var(--c-t2)" tag="Moderate" />
        </div>

        <div className="flex items-center gap-sp2 rounded-r1 border border-teal/15 bg-teal/[0.05] px-sp3 py-sp2 text-[12px] font-medium text-teal">
          ✓ A6 Auditor: narrative matches raw API · 0 discrepancies · Evidence chain intact
        </div>
      </div>
      <div className="mt-sp3 text-center text-[11.5px] text-t3">
        Switch tickers above to explore your other holdings
      </div>
    </div>
  );
}

function EvidenceRow({
  label,
  source,
  value,
  color,
  tag,
}: {
  label: string;
  source: string;
  value: number;
  color: string;
  tag: string;
}) {
  return (
    <div
      className="flex items-center gap-sp3 rounded-r1 border border-border bg-panel px-sp3 py-sp2"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <div className="flex-1">
        <div className="text-[10.5px] font-bold uppercase tracking-wide text-t3">{label}</div>
        <div className="text-[10px] text-t4">{source}</div>
      </div>
      <div className="mono text-[16px] font-bold" style={{ color }}>
        {value}
      </div>
      <span className="rounded-r4 bg-teal-dim px-2 py-0.5 text-[9px] font-semibold text-teal">
        {tag}
      </span>
    </div>
  );
}
