import { Reveal } from "@/components/Reveal";

const posts = [
  {
    title: "Why we publish our own error rate",
    excerpt:
      "Every AI research tool makes mistakes. Most hide them. Here's why showing ours, every week, is the point.",
  },
  {
    title: "How Agent A6 audits Agent A5",
    excerpt:
      "A walkthrough of the verification step that runs before any narrative reaches your screen — and what happens when it disagrees.",
  },
  {
    title: "Reading a Debt/Equity ratio without the jargon",
    excerpt: "The raw metrics behind a risk score, explained the way we'd explain them to a client.",
  },
];

export function Blog() {
  return (
    <section id="blog" className="scroll-mt-20 border-t border-border px-sp6 py-sp10 md:px-sp10">
      <Reveal>
        <div className="mb-sp2 text-[12px] font-bold uppercase tracking-wide text-t3">From the desk</div>
        <h2 className="mb-sp8 max-w-[560px] text-[32px] font-extrabold leading-tight tracking-tight text-t1">
          Notes on transparency.
        </h2>
      </Reveal>
      <div className="grid grid-cols-1 gap-sp5 md:grid-cols-3">
        {posts.map((p, i) => (
          <Reveal key={p.title} delayMs={i * 100}>
            <div className="glass-panel h-full p-sp5">
              <h3 className="mb-sp2 text-[14.5px] font-bold text-t1">{p.title}</h3>
              <p className="text-[13px] leading-relaxed text-t2">{p.excerpt}</p>
              <div className="mt-sp4 text-[11.5px] font-semibold text-t3">Coming soon</div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
