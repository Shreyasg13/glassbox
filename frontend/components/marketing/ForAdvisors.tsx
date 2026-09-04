import { Reveal } from "@/components/Reveal";

const benefits = [
  {
    title: "An evidence trail your clients can see",
    body: "When a client asks \"why does it say that?\", point to the exact API response and the audit that checked it, not a black-box score.",
  },
  {
    title: "Compliance-ready by default",
    body: "Every verification is logged with its source data, its narrative, and its audit result. Export the trail for E&O documentation or a compliance review.",
  },
  {
    title: "Multi-client, white-label ready",
    body: "Run verifications across client portfolios and hand back reports branded for your practice, not ours.",
  },
];

const testimonials = [
  {
    text: "Finally, a platform that shows me where the number came from. My clients ask 'why does it say that?' and I can now point to the exact API response. That's career-defining trust-building.",
    initials: "MD",
    color: "bg-teal-dim text-teal",
    name: "M. Donovan",
    role: "Fee-only RIA · New Jersey",
  },
  {
    text: "The Discrepancy Rate widget changed how my clients think about AI. Instead of 'is this reliable?' they now ask 'what's the error rate this week?' That's a fundamentally different, and better, conversation.",
    initials: "PR",
    color: "bg-gold-dim text-gold",
    name: "P. Ramirez",
    role: "Independent CFP · California",
  },
];

export function ForAdvisors() {
  return (
    <section id="for-advisors" className="scroll-mt-20 border-t border-border px-sp6 py-sp10 md:px-sp10">
      <Reveal>
        <div className="mb-sp2 text-[12px] font-bold uppercase tracking-wide text-t3">For Advisors</div>
        <h2 className="mb-sp8 max-w-[560px] text-[32px] font-extrabold leading-tight tracking-tight text-t1">
          Built for the conversation with your client, not just the score.
        </h2>
      </Reveal>

      <div className="mb-sp8 grid grid-cols-1 gap-sp5 md:grid-cols-3">
        {benefits.map((b, i) => (
          <Reveal key={b.title} delayMs={i * 100}>
            <div className="glass-panel h-full p-sp5 transition-all duration-200 ease-glass hover:-translate-y-1 hover:border-border2 hover:shadow-lg2">
              <h3 className="mb-sp2 text-[14.5px] font-bold text-t1">{b.title}</h3>
              <p className="text-[13px] leading-relaxed text-t2">{b.body}</p>
            </div>
          </Reveal>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-sp5 md:grid-cols-2">
        {testimonials.map((t, i) => (
          <Reveal key={t.name} delayMs={i * 100}>
            <div className="glass-panel-raised h-full p-sp5 transition-all duration-200 ease-glass hover:-translate-y-1 hover:shadow-lg2">
              <div className="mb-sp3 text-[13px] text-gold">★★★★★</div>
              <p className="mb-sp5 text-[13.5px] leading-relaxed text-t1">&ldquo;{t.text}&rdquo;</p>
              <div className="flex items-center gap-sp3">
                <div className={`grid h-[36px] w-[36px] place-items-center rounded-full text-[12px] font-bold ${t.color}`}>
                  {t.initials}
                </div>
                <div>
                  <div className="text-[13px] font-semibold text-t1">{t.name}</div>
                  <div className="text-[11px] text-t3">{t.role}</div>
                </div>
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
