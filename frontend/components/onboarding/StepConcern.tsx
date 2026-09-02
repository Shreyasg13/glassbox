import type { ConcernId } from "./types";

const options: { id: ConcernId; icon: string; iconBg: string; title: string; sub: string }[] = [
  {
    id: "ai-verify",
    icon: "🔍",
    iconBg: "rgba(13,204,170,.1)",
    title: "AI recommendations I can't verify",
    sub: "You use AI tools but fear the data behind them is fabricated or wrong",
  },
  {
    id: "influencers",
    icon: "📱",
    iconBg: "rgba(232,160,32,.12)",
    title: "Bad advice from financial influencers",
    sub: "You've seen claims on YouTube or TikTok that turned out to be wrong or misleading",
  },
  {
    id: "volatility",
    icon: "📉",
    iconBg: "rgba(232,68,90,.1)",
    title: "Market volatility I don't understand",
    sub: "When markets move, you can't tell how it affects your specific holdings",
  },
  {
    id: "retirement",
    icon: "⏳",
    iconBg: "rgba(13,184,122,.1)",
    title: "Running out of time before retirement",
    sub: "You need concrete projections, not just portfolio scores",
  },
];

export function StepConcern({
  value,
  onChange,
}: {
  value: ConcernId | null;
  onChange: (id: ConcernId) => void;
}) {
  return (
    <div>
      <div className="mb-1 text-[17px] font-bold text-t1">What&apos;s your biggest investing concern?</div>
      <div className="mb-sp4 text-[13px] text-t3">
        Your answer personalises your alerts, reports, and dashboard layout.
      </div>
      <div className="flex flex-col gap-sp2">
        {options.map((opt) => {
          const selected = value === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => onChange(opt.id)}
              className={`flex items-center gap-sp3 rounded-r2 border p-sp3 text-left transition-colors ${
                selected ? "border-teal bg-teal/[0.04]" : "border-border hover:border-border2"
              }`}
            >
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-r2 text-[16px]"
                style={{ background: opt.iconBg }}
              >
                {opt.icon}
              </div>
              <div className="flex-1">
                <div className="text-[13.5px] font-semibold text-t1">{opt.title}</div>
                <div className="text-[12px] text-t3">{opt.sub}</div>
              </div>
              <div
                className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border text-[11px] ${
                  selected ? "border-teal bg-teal text-bg" : "border-border2 text-transparent"
                }`}
              >
                ✓
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
