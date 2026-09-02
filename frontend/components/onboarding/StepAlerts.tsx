import type { OnboardingState } from "./types";
import { thresholdLabel } from "./types";

const alertTypeMeta = [
  { key: "crisis" as const, icon: "⚡", bg: "rgba(232,68,90,.1)", title: "Crisis Alerts", sub: "When risk factors breach thresholds" },
  { key: "weeklyReport" as const, icon: "📊", bg: "rgba(13,204,170,.1)", title: "Weekly Discrepancy Report", sub: "AI accuracy summary every Monday" },
  { key: "scoreChanges" as const, icon: "📈", bg: "rgba(77,122,255,.1)", title: "Portfolio Score Changes", sub: "Alert when your score moves ±0.5" },
  { key: "marketEvents" as const, icon: "🌐", bg: "rgba(136,146,176,.08)", title: "Market Events", sub: "Macro events that may affect holdings" },
];

const deliveryOptions = ["✉ Email", "🔔 In-app", "📱 SMS", "💬 Slack"];
const frequencies: { id: OnboardingState["frequency"]; label: string }[] = [
  { id: "realtime", label: "Real-time" },
  { id: "daily", label: "Daily digest" },
  { id: "weekly", label: "Weekly only" },
];

export function StepAlerts({
  state,
  onChange,
}: {
  state: OnboardingState;
  onChange: (next: Partial<OnboardingState>) => void;
}) {
  function toggleAlertType(key: keyof OnboardingState["alertTypes"]) {
    onChange({ alertTypes: { ...state.alertTypes, [key]: !state.alertTypes[key] } });
  }

  function toggleDelivery(label: string) {
    const name = label.replace(/^\S+\s/, "");
    const on = state.delivery.includes(name);
    onChange({ delivery: on ? state.delivery.filter((d) => d !== name) : [...state.delivery, name] });
  }

  return (
    <div>
      <div className="mb-1 text-[17px] font-bold text-t1">How should Glass Box alert you?</div>
      <div className="mb-sp5 text-[13px] text-t3">
        Configure delivery and frequency. Change these anytime in Settings.
      </div>

      <div className="mb-sp4 rounded-r2 border border-border bg-bg2 p-sp4">
        <div className="mb-sp3 text-[9.5px] font-bold uppercase tracking-wider text-t3">
          Alert types
        </div>
        {alertTypeMeta.map((a, i) => (
          <div
            key={a.key}
            className={`flex items-center justify-between py-sp2 ${
              i < alertTypeMeta.length - 1 ? "border-b border-white/[0.04]" : ""
            }`}
          >
            <div className="flex items-center gap-sp3">
              <div
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-r1 text-[13px]"
                style={{ background: a.bg }}
              >
                {a.icon}
              </div>
              <div>
                <div className="text-[13px] font-semibold text-t1">{a.title}</div>
                <div className="text-[11.5px] text-t3">{a.sub}</div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => toggleAlertType(a.key)}
              className={`h-5 w-9 rounded-full transition-colors ${
                state.alertTypes[a.key] ? "bg-teal" : "bg-raised"
              }`}
            >
              <span
                className={`block h-4 w-4 translate-x-0.5 rounded-full bg-white transition-transform ${
                  state.alertTypes[a.key] ? "translate-x-[18px]" : "translate-x-0.5"
                }`}
              />
            </button>
          </div>
        ))}
      </div>

      <div className="mb-2 text-[9.5px] font-bold uppercase tracking-wider text-t3">
        Delivery method
      </div>
      <div className="mb-sp4 flex flex-wrap gap-sp2">
        {deliveryOptions.map((label) => {
          const name = label.replace(/^\S+\s/, "");
          const selected = state.delivery.includes(name);
          return (
            <button
              key={label}
              type="button"
              onClick={() => toggleDelivery(label)}
              className={`rounded-r1 border px-sp3 py-sp2 text-[12.5px] font-semibold transition-colors ${
                selected ? "border-teal bg-teal/[0.06] text-teal" : "border-border bg-bg2 text-t3"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      <div className="mb-2 text-[9.5px] font-bold uppercase tracking-wider text-t3">
        Alert frequency
      </div>
      <div className="mb-sp4 flex gap-sp2">
        {frequencies.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => onChange({ frequency: f.id })}
            className={`rounded-r1 border px-sp3 py-sp2 text-[12.5px] font-semibold transition-colors ${
              state.frequency === f.id
                ? "border-teal bg-teal/[0.06] text-teal"
                : "border-border bg-bg2 text-t3"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="mb-2 text-[9.5px] font-bold uppercase tracking-wider text-t3">
        Crisis sensitivity threshold
      </div>
      <div className="mb-sp4 rounded-r2 border border-border bg-bg2 p-sp3">
        <div className="mb-sp2 flex justify-between">
          <span className="text-[12.5px] text-t2">Trigger alert when score changes by</span>
          <span className="mono text-[13px] font-bold text-teal">{thresholdLabel(state.threshold)}</span>
        </div>
        <input
          type="range"
          min={1}
          max={5}
          step={1}
          value={state.threshold}
          onChange={(e) => onChange({ threshold: Number(e.target.value) })}
          className="w-full accent-teal"
        />
        <div className="mt-1 flex justify-between text-[10.5px] text-t4">
          <span>Sensitive (±0.5)</span>
          <span>Relaxed (±2.5)</span>
        </div>
      </div>

      <div className="flex items-center gap-sp3 rounded-r2 border border-teal/[0.18] bg-teal/[0.06] px-sp3 py-sp3">
        <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full bg-teal text-[12px] font-black text-bg">
          ✓
        </div>
        <div>
          <div className="text-[12.5px] font-bold text-teal">Ready to go</div>
          <div className="text-[11.5px] text-t3">
            {Object.values(state.alertTypes).filter(Boolean).length} alerts active ·{" "}
            {state.delivery.join(" + ") || "No delivery selected"} ·{" "}
            {frequencies.find((f) => f.id === state.frequency)?.label} · Threshold{" "}
            {thresholdLabel(state.threshold)}
          </div>
        </div>
      </div>
    </div>
  );
}
