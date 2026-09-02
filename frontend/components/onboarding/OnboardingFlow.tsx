"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { StepIndicator } from "./StepIndicator";
import { StepConcern } from "./StepConcern";
import { StepPortfolio } from "./StepPortfolio";
import { StepVerify } from "./StepVerify";
import { StepAlerts } from "./StepAlerts";
import { initialOnboardingState, type OnboardingState } from "./types";

const LAST_STEP = 3;

export function OnboardingFlow() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [state, setState] = useState<OnboardingState>(initialOnboardingState);

  function patch(next: Partial<OnboardingState>) {
    setState((prev) => ({ ...prev, ...next }));
  }

  async function complete() {
    // TODO: POST `state` to /api/onboarding once the FastAPI gateway exposes it.
    router.push("/dashboard");
  }

  return (
    <div className="mx-auto max-w-[640px] rounded-r4 border border-border2 bg-panel shadow-lg2">
      <div className="p-sp6 pb-0">
        <StepIndicator step={step} />
      </div>

      <div className="px-sp6 py-sp4">
        {step === 0 && (
          <StepConcern value={state.concern} onChange={(concern) => patch({ concern })} />
        )}
        {step === 1 && (
          <StepPortfolio
            connectedBroker={state.connectedBroker}
            onConnectBroker={(connectedBroker) => patch({ connectedBroker })}
            tickers={state.tickers}
            onTickersChange={(tickers) => patch({ tickers })}
          />
        )}
        {step === 2 && <StepVerify tickers={state.tickers} />}
        {step === 3 && <StepAlerts state={state} onChange={patch} />}
      </div>

      <div className="flex items-center justify-between border-t border-border px-sp6 py-sp4">
        <button
          type="button"
          onClick={() => (step === 0 ? router.push("/dashboard") : setStep(step - 1))}
          className="text-[12.5px] font-medium text-t3 hover:text-t2"
        >
          {step === 0 ? "Cancel" : "Back"}
        </button>
        <button
          type="button"
          onClick={() => (step === LAST_STEP ? complete() : setStep(step + 1))}
          className="rounded-r2 bg-teal px-sp5 py-sp2 text-[14px] font-bold text-bg shadow-teal transition-transform hover:-translate-y-px hover:bg-teal2"
        >
          {step === LAST_STEP ? "Go to my Dashboard →" : "Continue →"}
        </button>
      </div>
    </div>
  );
}
