import { Reveal } from "@/components/Reveal";
import { CountUpStat } from "./CountUpStat";

const stats = [
  { target: 99.2, decimals: 1, suffix: "%", label: "AI accuracy this week", color: "text-t1" },
  { target: 14, decimals: 0, suffix: "", label: "errors caught by A6", color: "text-green" },
  { target: 0, decimals: 0, suffix: "", label: "errors shown to users", color: "text-t3" },
  { target: 4.8, decimals: 1, suffix: "★", label: "user trust score", color: "text-gold" },
];

export function DiscrepancyBand() {
  return (
    <Reveal>
      <div className="border-y border-border bg-panel px-sp6 py-sp6 md:px-sp10">
        <div className="mx-auto flex max-w-[1100px] flex-wrap items-center justify-between gap-sp6">
          {stats.map((s) => (
            <CountUpStat key={s.label} {...s} />
          ))}
          <a href="#how-it-works" className="text-[12.5px] font-semibold text-teal hover:underline">
            View full audit log →
          </a>
        </div>
      </div>
    </Reveal>
  );
}
