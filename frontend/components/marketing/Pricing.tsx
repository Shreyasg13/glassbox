import { Reveal } from "@/components/Reveal";
import { CoffeeButton } from "@/components/support/CoffeeButton";
import { supportUrl } from "@/lib/support";

const free = [
  { on: true, label: "5 free stock verifications per account" },
  { on: true, label: "Full Evidence Path · raw data visible" },
  { on: true, label: "A6 Auditor confirmation badge" },
  { on: true, label: "Discrepancy Rate dashboard" },
  { on: true, label: "Your portfolio, run by the committee, with growth and Monte Carlo estimate" },
  { on: true, label: "Daily email digest of your stocks (opt-in)" },
];

// Not built yet: shown greyed out with no buy button, so nobody pays for or expects them today.
const soon = [
  {
    name: "Standard",
    price: "20",
    features: ["More verifications per month", "Real-time crisis alerts", "Broker import via SnapTrade"],
  },
  {
    name: "Advisor",
    price: "150",
    features: ["Unlimited verifications", "White-label client reports PDF", "API access and multi-client portfolios"],
  },
];

export function Pricing() {
  const hasCoffee = supportUrl() !== null;
  return (
    <section id="pricing" className="scroll-mt-20 border-t border-border bg-bg1 px-sp6 py-sp10 md:px-sp10">
      <Reveal>
        <div className="mb-sp2 text-[12px] font-bold uppercase tracking-wide text-t3">Free &amp; supported by you</div>
        <h2 className="mb-sp2 text-[32px] font-extrabold leading-tight tracking-tight text-t1">Free to use. Coffee if it helps.</h2>
        <p className="mb-sp8 max-w-[70ch] text-[15px] text-t2">
          Every feature is free for everyone: no card, no paywall, no trial that turns into a charge. Running it isn&rsquo;t free though: the domain, hosting, security, infrastructure, market data and AI model usage all cost money.
          Donations are what pay for that, and they&rsquo;re how GlassBox stays freely available to all. Giving is optional and doesn&rsquo;t unlock anything.
        </p>
      </Reveal>

      <div className="grid grid-cols-1 gap-sp5 md:grid-cols-2">
        <Reveal>
          <div className="glass-panel flex h-full flex-col p-sp5">
            <div className="mb-sp2 text-[13px] font-bold text-t1">Free</div>
            <div className="mb-sp1 flex items-baseline gap-sp1">
              <span className="text-[18px] font-bold text-t1">$</span>
              <span className="text-[38px] font-extrabold leading-none text-t1">0</span>
            </div>
            <div className="mb-sp4 text-[11.5px] text-t3">forever · no credit card needed</div>
            <hr className="mb-sp4 border-border" />
            <div className="mb-sp6 flex flex-1 flex-col gap-sp2">
              {free.map((f) => (
                <div key={f.label} className="flex items-start gap-sp2 text-[12.5px]">
                  <span className="text-teal">✓</span>
                  <span className="text-t1">{f.label}</span>
                </div>
              ))}
            </div>
            <a href="/login" className="btn btn-primary justify-center">
              Start Free
            </a>
          </div>
        </Reveal>

        <Reveal delayMs={100}>
          <div className="glass-panel-accent flex h-full flex-col border-teal/30 p-sp5">
            <div className="mb-sp2 text-[13px] font-bold text-teal">Support GlassBox</div>
            <div className="mb-sp1 text-[38px] font-extrabold leading-none text-teal">☕</div>
            <div className="mb-sp4 text-[11.5px] text-t3">one-off, any amount · paid on Buy Me a Coffee</div>
            <hr className="mb-sp4 border-border" />
            <div className="mb-sp6 flex flex-1 flex-col gap-sp2 text-[12.5px] text-t1">
              <p>Donated money is used for the domain, hosting, security and new infrastructure (servers, storage, market data), and for the AI model costs behind the committee and agents.</p>
              <p>That&rsquo;s how every functionality stays freely available to everyone, not just those who can pay.</p>
              <p className="text-t2">You pay on buymeacoffee.com. GlassBox never sees or stores a card number.</p>
              <p className="text-t2">A donation doesn&rsquo;t change your account or limits.</p>
            </div>
            {hasCoffee ? <CoffeeButton /> : <span className="btn btn-ghost cursor-default justify-center opacity-60">Coffee link coming soon</span>}
          </div>
        </Reveal>
      </div>

      <Reveal>
        <div className="mb-sp3 mt-sp8 text-[12px] font-bold uppercase tracking-wide text-t3">Planned, not available yet</div>
        <div className="grid grid-cols-1 gap-sp5 md:grid-cols-2">
          {soon.map((t) => (
            <div key={t.name} className="glass-panel relative p-sp5 opacity-60" aria-label={`${t.name}, coming soon`}>
              <span className="absolute right-sp4 top-sp4 rounded-r4 border border-border px-sp2 py-0.5 text-[10px] font-bold uppercase text-t3">Coming soon</span>
              <div className="text-[13px] font-bold text-t2">{t.name}</div>
              <div className="mb-sp3 text-[12px] text-t3">Planned at ${t.price}/month · nothing to buy today</div>
              <ul className="flex flex-col gap-1 text-[12px] text-t3">
                {t.features.map((f) => (
                  <li key={f}>— {f}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
