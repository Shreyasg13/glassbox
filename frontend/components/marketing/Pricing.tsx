import { Reveal } from "@/components/Reveal";

/* GlassBox is a free, non-commercial research preview: no paid plans, no payments, no trials.
 * The earlier Standard ($20) and Advisor ($150) cards were marketing only (there was never a payment backend) and are
 * removed so the site does not present itself as a paid product. Keep it this way unless the owner decides otherwise
 * after legal review. The export keeps its old name so the landing page import does not change. */
const features = [
  { on: true, label: "5 stock verifications per account" },
  { on: true, label: "Full Evidence Path · raw data visible" },
  { on: true, label: "Daily committee research and paper-trading track record" },
  { on: false, label: "A6 Auditor confirmation badge (coming soon)" },
  { on: false, label: "Discrepancy Rate dashboard (coming soon)" },
];

export function Pricing() {
  return (
    <section id="access" className="scroll-mt-20 border-t border-border bg-bg1 px-sp6 py-sp10 md:px-sp10">
      <Reveal>
        <div className="mb-sp2 text-[12px] font-bold uppercase tracking-wide text-t3">Free access</div>
        <h2 className="mb-sp2 text-[32px] font-extrabold leading-tight tracking-tight text-t1">
          A free research preview.
        </h2>
        <p className="mb-sp8 max-w-[60ch] text-[15px] text-t2">
          GlassBox is a non-commercial research project. There are no paid plans, no payments and no trials. Everything
          here is simulated research, not investment advice.
        </p>
      </Reveal>

      <Reveal>
        <div className="glass-panel-accent flex max-w-[460px] flex-col border-teal/30 p-sp5">
          <div className="mb-sp2 text-[13px] font-bold text-teal">Research preview</div>
          <div className="mb-sp1 text-[38px] font-extrabold leading-none text-t1">Free</div>
          <div className="mb-sp4 text-[11.5px] text-t3">no credit card · no payment details collected</div>
          <hr className="mb-sp4 border-border" />
          <div className="mb-sp6 flex flex-col gap-sp2">
            {features.map((f) => (
              <div key={f.label} className="flex items-start gap-sp2 text-[12.5px]">
                <span className={f.on ? "text-teal" : "text-t4"}>{f.on ? "✓" : "—"}</span>
                <span className={f.on ? "text-t1" : "text-t4"}>{f.label}</span>
              </div>
            ))}
          </div>
          <a href="/login" className="btn btn-primary justify-center">
            Start free
          </a>
        </div>
      </Reveal>
    </section>
  );
}
