import { Reveal } from "@/components/Reveal";

const tiers = [
  {
    name: "Free",
    color: "text-t1",
    price: "0",
    priceColor: "text-t1",
    period: "forever · no credit card needed",
    features: [
      { on: true, label: "5 stock verifications per account" },
      { on: true, label: "Full Evidence Path · raw data visible" },
      { on: true, label: "A6 Auditor confirmation badge" },
      { on: true, label: "Discrepancy Rate dashboard" },
      { on: false, label: "Portfolio Glass Box Score" },
      { on: false, label: "Crisis Alerts" },
    ],
    cta: "Start Free",
    ctaClass: "btn-ghost",
    popular: false,
  },
  {
    name: "Standard",
    color: "text-teal",
    price: "20",
    priceColor: "text-teal",
    period: "per month · cancel anytime",
    features: [
      { on: true, label: "200 verifications per month" },
      { on: true, label: "Portfolio Glass Box Score" },
      { on: true, label: "Crisis Alerts · real-time" },
      { on: true, label: "Stress Test · historical crisis simulator" },
      { on: true, label: "Weekly Discrepancy Report email" },
      { on: true, label: "Broker import via SnapTrade" },
    ],
    cta: "Start Standard →",
    ctaClass: "btn-primary",
    popular: true,
  },
  {
    name: "Advisor",
    color: "text-gold",
    price: "150",
    priceColor: "text-gold",
    period: "per month · for independent advisors",
    features: [
      { on: true, label: "Unlimited verifications" },
      { on: true, label: "White-label Client Reports PDF" },
      { on: true, label: "API access for custom integrations" },
      { on: true, label: "Multi-client portfolio management" },
      { on: true, label: "Compliance audit log export" },
      { on: true, label: "30-day free trial · no risk" },
    ],
    cta: "Start 30-day Trial",
    ctaClass: "btn-ghost",
    popular: false,
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="scroll-mt-20 border-t border-border bg-bg1 px-sp6 py-sp10 md:px-sp10">
      <Reveal>
        <div className="mb-sp2 text-[12px] font-bold uppercase tracking-wide text-t3">Pricing</div>
        <h2 className="mb-sp2 text-[32px] font-extrabold leading-tight tracking-tight text-t1">
          Start free. Upgrade when you trust us.
        </h2>
        <p className="mb-sp8 text-[15px] text-t2">No dark patterns. All prices visible. Cancel anytime.</p>
      </Reveal>

      <div className="grid grid-cols-1 gap-sp5 md:grid-cols-3">
        {tiers.map((t, i) => (
          <Reveal key={t.name} delayMs={i * 100}>
            <div
              className={`relative flex h-full flex-col p-sp5 transition-all duration-200 ease-glass hover:-translate-y-1 ${
                t.popular
                  ? "glass-panel-accent border-teal/30 hover:shadow-lg2"
                  : "glass-panel hover:border-border2 hover:shadow-lg2"
              }`}
            >
              {t.popular && (
                <div className="absolute -top-3 left-sp5 rounded-r4 bg-teal px-sp3 py-1 text-[10px] font-bold uppercase text-bg">
                  Most Popular
                </div>
              )}
              <div className={`mb-sp2 text-[13px] font-bold ${t.color}`}>{t.name}</div>
              <div className="mb-sp1 flex items-baseline gap-sp1">
                <span className={`text-[18px] font-bold ${t.priceColor}`}>$</span>
                <span className={`text-[38px] font-extrabold leading-none ${t.priceColor}`}>{t.price}</span>
              </div>
              <div className="mb-sp4 text-[11.5px] text-t3">{t.period}</div>
              <hr className="mb-sp4 border-border" />
              <div className="mb-sp6 flex flex-1 flex-col gap-sp2">
                {t.features.map((f) => (
                  <div key={f.label} className="flex items-start gap-sp2 text-[12.5px]">
                    <span className={f.on ? "text-teal" : "text-t4"}>{f.on ? "✓" : "—"}</span>
                    <span className={f.on ? "text-t1" : "text-t4"}>{f.label}</span>
                  </div>
                ))}
              </div>
              <a href="/login" className={`btn ${t.ctaClass} justify-center`}>
                {t.cta}
              </a>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
