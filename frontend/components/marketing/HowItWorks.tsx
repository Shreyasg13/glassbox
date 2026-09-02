import { Reveal } from "@/components/Reveal";

const cards = [
  {
    number: "01 — FETCH",
    icon: "⬇",
    iconClass: "bg-teal-dim text-teal",
    title: "Agent A1 pulls institutional data",
    body: "Debt-to-equity, Altman Z-Score, free cash flow, 30 years of history — directly from Financial Modeling Prep's institutional API. Twelve Data provides real-time technicals. No aggregators, no intermediaries.",
    tag: "A1 Data Fetcher · A2 Technical Analyzer · A3 Sentiment Scanner",
    tagClass: "text-teal",
  },
  {
    number: "02 — EXPLAIN",
    icon: "✎",
    iconClass: "bg-gold-dim text-gold",
    title: "Agent A5 translates to plain English",
    body: "A configured narrative agent generates a clear summary from the underlying risk metrics. Every number in the text traces back to its raw data source. Every claim is auditable, not asserted.",
    tag: "A4 Risk Calculator · A5 Narrative Generator",
    tagClass: "text-gold",
  },
  {
    number: "03 — AUDIT",
    icon: "✓",
    iconClass: "bg-green-dim text-green",
    title: "Agent A6 audits before you see it",
    body: "The Auditor cross-checks the narrative against raw API data. If anything doesn't match, it's flagged and corrected before display. You only see verified output — and we publish the error rate publicly, every week.",
    tag: "A6 Auditor · A7 Compliance Monitor",
    tagClass: "text-green",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 px-sp6 py-sp10 md:px-sp10">
      <Reveal>
        <div className="mb-sp2 text-[12px] font-bold uppercase tracking-wide text-t3">
          How Glass Box works
        </div>
        <h2 className="mb-sp8 max-w-[560px] text-[32px] font-extrabold leading-tight tracking-tight text-t1">
          Not AI magic.
          <br />
          AI math — audited.
        </h2>
      </Reveal>
      <div className="grid grid-cols-1 gap-sp5 md:grid-cols-3">
        {cards.map((c, i) => (
          <Reveal key={c.number} delayMs={i * 120}>
            <div className="glass-panel h-full p-sp5">
              <div className="mono mb-sp4 text-[11px] font-bold text-t3">{c.number}</div>
              <div className={`mb-sp4 grid h-[38px] w-[38px] place-items-center rounded-r2 text-[18px] ${c.iconClass}`}>
                {c.icon}
              </div>
              <h3 className="mb-sp2 text-[15.5px] font-bold text-t1">{c.title}</h3>
              <p className="mb-sp4 text-[13px] leading-relaxed text-t2">{c.body}</p>
              <div className={`mono text-[10.5px] font-semibold ${c.tagClass}`}>{c.tag}</div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
