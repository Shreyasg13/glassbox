"use client";

// Sliding badge banner -- ported from docs/design-reference/GlassBox_Pilot_Production.html
// (ABAND + LEGBAND arrays). Content duplicated once so the CSS animation
// (translateX(-50%), see .marquee-track in app/globals.css) loops seamlessly.

const AGENT_BADGES = [
  { code: "A1", name: "Data Fetcher", spec: "institutional API", color: "teal" },
  { code: "A2", name: "Technical Analyzer", spec: "real-time technicals", color: "blue" },
  { code: "A3", name: "Sentiment Scanner", spec: "news & social", color: "purple" },
  { code: "A4", name: "Risk Calculator", spec: "Altman Z · D/E · beta", color: "gold" },
  { code: "A5", name: "Narrative Generator", spec: "plain-English explain", color: "cyan" },
  { code: "A6", name: "Auditor", spec: "cross-checks every claim", color: "green" },
  { code: "A7", name: "Compliance Monitor", spec: "logs the evidence trail", color: "red" },
] as const;

const LENS_BADGES = [
  { code: "V", name: "Value Lens", spec: "Buffett & Munger", color: "gold" },
  { code: "G", name: "GARP Lens", spec: "Peter Lynch", color: "green" },
  { code: "Q", name: "Quant Lens", spec: "Simons · Shaw", color: "cyan" },
  { code: "M", name: "Macro Lens", spec: "Dalio · Soros", color: "purple" },
  { code: "X", name: "Multi-Strat Lens", spec: "Griffin · Englander", color: "teal" },
] as const;

const BADGES = [...AGENT_BADGES, ...LENS_BADGES];

export function AgentMarquee() {
  return (
    <div className="overflow-hidden border-b border-border bg-bg1/60 py-sp3">
      <div className="marquee-track flex w-max gap-sp3">
        {[...BADGES, ...BADGES].map((b, i) => (
          <span
            key={`${b.code}-${i}`}
            className="mono flex shrink-0 items-center gap-sp2 whitespace-nowrap rounded-r4 border px-sp3 py-1 text-[11px] font-semibold"
            style={{ borderColor: `var(--c-${b.color})`, background: `var(--c-${b.color}-dim)`, color: `var(--c-${b.color})` }}
          >
            <span className="font-extrabold">{b.code}</span>
            <span className="text-t1">{b.name}</span>
            <span className="text-t3">· {b.spec}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
