import { Reveal } from "@/components/Reveal";

const items = [
  {
    icon: "🏛",
    title: "Institutional sources",
    body: "FMP + Twelve Data: the same feeds funds pay for, never scraped aggregators.",
    tag: "30 yrs history",
  },
  {
    icon: "🧮",
    title: "Deterministic core",
    body: "Risk math (Altman Z, D/E, beta) is formula-based and reproducible, no model guesswork on the numbers.",
    tag: "auditable",
  },
  {
    icon: "🧠",
    title: "Narrative models",
    body: "LLMs explain, they don't decide. Trained to summarize the metrics, constrained to cite every claim.",
    tag: "Qwen · Llama · cloud",
  },
  {
    icon: "🛡",
    title: "Audit layer",
    body: "A6 checks every narrative against raw data. Weekly error rate published, nothing hidden.",
    tag: "0 shown to users",
  },
];

export function MLProvenance() {
  return (
    <section id="ml-provenance" className="scroll-mt-20 border-t border-border px-sp6 py-sp10 md:px-sp10">
      <Reveal>
        <div className="mx-auto max-w-[640px] text-center">
          <div className="mb-sp2 text-[12px] font-bold uppercase tracking-wide text-t3">
            Trusted Data · Trained Models
          </div>
          <h2 className="mb-sp2 text-[32px] font-extrabold leading-tight tracking-tight text-t1">
            What the models learned, and from where
          </h2>
          <p className="text-[15px] text-t2">
            Transparency isn&apos;t only about the audit. It&apos;s about what went in. Here&apos;s the provenance
            behind every score.
          </p>
        </div>
      </Reveal>

      <div className="mt-sp8 grid grid-cols-1 gap-sp5 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((it, i) => (
          <Reveal key={it.title} delayMs={i * 100}>
            <div className="glass-panel h-full p-sp5 transition-all duration-200 ease-glass hover:-translate-y-1 hover:border-border2 hover:shadow-lg2">
              <div className="mb-sp3 text-[26px]">{it.icon}</div>
              <h3 className="mb-sp2 text-[14.5px] font-bold text-t1">{it.title}</h3>
              <p className="mb-sp4 text-[12.5px] leading-relaxed text-t2">{it.body}</p>
              <div className="mono inline-block rounded-r1 bg-raised px-sp2 py-1 text-[10px] font-semibold text-t3">
                {it.tag}
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
