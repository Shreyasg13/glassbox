import { Reveal } from "@/components/Reveal";

const stats = [
  { num: "99.2%", label: "AI accuracy this week", color: "text-t1" },
  { num: "14", label: "errors caught by A6", color: "text-green" },
  { num: "0", label: "errors shown to users", color: "text-t3" },
  { num: "4.8★", label: "user trust score", color: "text-gold" },
];

export function DiscrepancyBand() {
  return (
    <Reveal>
      <div className="border-y border-border bg-panel px-sp6 py-sp6 md:px-sp10">
        <div className="mx-auto flex max-w-[1100px] flex-wrap items-center justify-between gap-sp6">
          {stats.map((s) => (
            <div key={s.label}>
              <div className={`mono text-[24px] font-extrabold ${s.color}`}>{s.num}</div>
              <div className="text-[11.5px] text-t3">{s.label}</div>
            </div>
          ))}
          <a href="#how-it-works" className="text-[12.5px] font-semibold text-teal hover:underline">
            View full audit log →
          </a>
        </div>
      </div>
    </Reveal>
  );
}
