import { Reveal } from "@/components/Reveal";

const evidenceRows = [
  { label: "Debt / Equity Ratio", value: "1.78", color: "text-teal", source: "FMP API · 2 hr ago" },
  { label: "Altman Z-Score", value: "6.24", color: "text-gold", source: "FMP API · Very Low Risk" },
  { label: "Beta vs S&P 500", value: "1.22", color: "text-t2", source: "Twelve Data · Live" },
];

export function Hero() {
  return (
    <div className="grid grid-cols-1 items-center gap-sp8 px-sp6 py-sp10 md:px-sp10 lg:grid-cols-2 lg:py-sp10">
      <Reveal>
        <div className="mb-sp4 inline-flex items-center gap-sp2 rounded-r4 border border-teal/20 bg-teal-dim px-sp3 py-1 text-[11px] font-semibold text-teal">
          <span className="live-dot" />
          AI Verification · Not AI Advice
        </div>
        <h1 className="mb-sp5 text-[40px] font-extrabold leading-[1.1] tracking-tight text-t1 md:text-[52px]">
          See the math.
          <br />
          <span className="text-teal">Trust the data.</span>
        </h1>
        <p className="mb-sp8 max-w-[500px] text-[17px] leading-[1.7] text-t2">
          Glass Box shows you exactly why every risk score is what it is — the raw institutional
          data, the formula, and an independent audit before you see any number. No black box. No
          hallucinations displayed unchecked.
        </p>
        <div className="mb-sp8 flex flex-wrap gap-sp3">
          <a href="/login" className="btn btn-primary px-sp5 py-sp3 text-[14px]">
            Verify a stock free <span className="opacity-70">→</span>
          </a>
          <a href="#how-it-works" className="btn btn-ghost px-sp5 py-sp3 text-[14px]">
            See how it works
          </a>
        </div>
        <div className="flex flex-wrap gap-sp5 text-[12.5px] text-t2">
          {[
            "No credit card required",
            "5 free verifications daily",
            "Research tool, not advice",
            "E&O insured",
          ].map((p) => (
            <div key={p} className="flex items-center gap-sp2">
              <span className="text-teal">✓</span>
              {p}
            </div>
          ))}
        </div>
      </Reveal>

      <Reveal delayMs={150}>
        <div className="glass-panel-raised overflow-hidden transition-all duration-300 ease-glass hover:-translate-y-1 hover:shadow-lg2">
          <div className="flex items-center justify-between border-b border-border p-sp4">
            <span className="text-[12px] font-semibold text-t2">Live verification — illustrative</span>
            <div className="flex items-center gap-sp2 rounded-r4 bg-raised px-sp3 py-1 text-[11px] font-semibold text-t2">
              <span className="h-[6px] w-[6px] rounded-full bg-teal" />
              A6 Auditor active
            </div>
          </div>

          <div className="flex gap-sp3 border-b border-border p-sp4">
            <input className="input" defaultValue="AAPL" placeholder="Ticker symbol…" readOnly />
            <button className="btn btn-primary shrink-0">Verify →</button>
          </div>

          <div className="p-sp5">
            <div className="mb-sp5 flex items-center gap-sp4">
              <div className="grid h-[64px] w-[64px] shrink-0 place-items-center rounded-full border-2 border-teal/40">
                <div className="text-center">
                  <div className="text-[22px] font-extrabold text-teal">8.4</div>
                  <div className="text-[9px] text-t3">Score</div>
                </div>
              </div>
              <div>
                <div className="text-[15px] font-bold text-t1">Apple Inc. — AAPL</div>
                <div className="mt-sp1 flex items-center gap-sp3 text-[11px] text-t3">
                  <span>NASDAQ · Technology</span>
                  <span className="flex items-center gap-1 rounded-r1 bg-teal-dim px-sp2 py-[2px] text-teal">
                    ✓ A6 Verified · 14:32
                  </span>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-sp2">
              {evidenceRows.map((row) => (
                <div
                  key={row.label}
                  className="flex items-center justify-between rounded-r1 border border-border bg-bg2 px-sp3 py-sp2 transition-colors duration-150 hover:border-border2 hover:bg-panel2"
                >
                  <span className="text-[12.5px] text-t2">{row.label}</span>
                  <div className="text-right">
                    <div className={`mono text-[13px] font-bold ${row.color}`}>{row.value}</div>
                    <div className="text-[10px] text-t3">{row.source}</div>
                  </div>
                </div>
              ))}
              <div className="mt-sp2 rounded-r1 bg-green-dim px-sp3 py-sp2 text-[11.5px] font-semibold text-green">
                ✓ Auditor A6: narrative matches raw API · 0 discrepancies found
              </div>
            </div>
          </div>
        </div>
      </Reveal>
    </div>
  );
}
