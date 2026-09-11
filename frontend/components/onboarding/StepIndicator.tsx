import { STEP_LABELS } from "./types";

export function StepIndicator({ step }: { step: number }) {
  return (
    <div className="mb-sp6">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[15px] font-bold text-t1">Set up Glass Box</span>
        <span className="text-[12px] font-medium text-t3">
          Step {step + 1} of {STEP_LABELS.length}
        </span>
      </div>
      <div className="flex gap-[7px]">
        {STEP_LABELS.map((_, i) => (
          <div
            key={i}
            className={`h-[3.5px] flex-1 rounded-[2px] ${i <= step ? "bg-teal" : "bg-border2"}`}
          />
        ))}
      </div>
      <div className="mt-[7px] flex gap-[7px]">
        {STEP_LABELS.map((label, i) => (
          <div
            key={label}
            className={`flex-1 text-center text-[9px] font-semibold uppercase tracking-wide ${
              i === step ? "text-teal" : i < step ? "text-t2" : "text-t3"
            }`}
          >
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
