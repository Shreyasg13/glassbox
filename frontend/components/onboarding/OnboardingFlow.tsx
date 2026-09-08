"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { StepIndicator } from "./StepIndicator";
import { StepAgent } from "./StepAgent";
import { StepConcern } from "./StepConcern";
import { StepPortfolio } from "./StepPortfolio";
import { StepVerify } from "./StepVerify";
import { StepAlerts } from "./StepAlerts";
import { GuideAvatar, GuideBubble } from "./GuideBubble";
import { AgentHero } from "./AgentHero";
import { AgentAvatar } from "./AgentAvatar";
import { DEFAULT_AGENT_ID, getAgentPersona } from "./agentPersonas";
import { initialOnboardingState, type OnboardingState } from "./types";
import {
  GLASSBOX_GUIDE,
  GUIDE_INTRO_MESSAGE,
  GUIDE_STEP_MESSAGES,
  GUIDE_CONCERN_ACK,
  GUIDE_ALERTS_RECOMMENDATION,
  GUIDE_COMPLETE_MESSAGE,
  guidePortfolioMessage,
  onboardingStateKey,
  onboardingCompleteKey,
} from "@/lib/glassboxGuide";

const LAST_STEP = 4;

type Persisted = { step: number; state: OnboardingState };

export function OnboardingFlow() {
  const router = useRouter();
  const { username, loading: authLoading } = useAuth();
  // -1 = the Guide intro screen, 0-4 = the real steps.
  const [step, setStep] = useState(-1);
  const [state, setState] = useState<OnboardingState>(initialOnboardingState);
  const [hydrated, setHydrated] = useState(false);
  // Live preview while browsing the deck on step 0 -- not committed into
  // persisted state until that step's Continue click (see the footer
  // button below), so cancelling out of onboarding never leaves a
  // half-chosen agentId behind.
  const [previewAgentId, setPreviewAgentId] = useState(DEFAULT_AGENT_ID);
  const effectiveAgentId = state.agentId ?? (step === 0 ? previewAgentId : DEFAULT_AGENT_ID);

  // Resume in-progress onboarding on refresh -- the only source of
  // truth for this (there's no backend onboarding endpoint at all yet;
  // see complete()'s TODO below), so this isn't competing with
  // anything, just filling a real gap. Keyed per-username (real bug
  // fixed: this used to be one global key shared by every account on
  // the browser) -- waits for authLoading to clear first so it doesn't
  // read the wrong (un-scoped/"anon") bucket on a hard page reload
  // before AuthProvider's own hydration has run.
  useEffect(() => {
    if (authLoading) return;
    try {
      const raw = localStorage.getItem(onboardingStateKey(username));
      if (raw) {
        const parsed = JSON.parse(raw) as Persisted;
        setStep(parsed.step);
        setState(parsed.state);
      }
    } catch {
      // malformed/inaccessible storage -- start fresh from the intro
    }
    setHydrated(true);
  }, [authLoading, username]);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(onboardingStateKey(username), JSON.stringify({ step, state }));
    } catch {
      // best-effort -- a refresh mid-flow just restarts in that case
    }
  }, [hydrated, username, step, state]);

  function patch(next: Partial<OnboardingState>) {
    setState((prev) => ({ ...prev, ...next }));
  }

  async function complete() {
    // TODO: POST `state` to /api/onboarding once the FastAPI gateway exposes it.
    try {
      localStorage.setItem(onboardingCompleteKey(username), "1");
      localStorage.removeItem(onboardingStateKey(username));
    } catch {
      // best-effort
    }
    router.push("/dashboard");
  }

  if (step === LAST_STEP + 1) {
    const agent = getAgentPersona(state.agentId);
    return (
      <div className="mx-auto flex max-w-[440px] flex-col items-center gap-sp5 rounded-r4 border border-border2 bg-panel p-sp8 text-center shadow-lg2">
        <div
          className="grid place-items-center rounded-full border-2 p-1"
          style={{ borderColor: agent.color }}
        >
          <AgentAvatar face={agent.face} color={agent.color} size={56} showCheck />
        </div>
        <div className="text-[16px] font-extrabold text-t1">{agent.name} is active</div>
        <GuideBubble message={GUIDE_COMPLETE_MESSAGE} compact />
        <div className="grid w-full grid-cols-1 gap-sp2 rounded-r2 border border-border bg-bg2 p-sp4 text-[12.5px] text-t2 sm:grid-cols-3">
          <div>
            <div className="mono text-[18px] font-extrabold text-teal">{state.tickers.length}</div>
            <div className="text-[10.5px] uppercase tracking-wide text-t3">Holdings monitored</div>
          </div>
          <div>
            <div className="mono text-[18px] font-extrabold text-teal">
              {Object.values(state.alertTypes).filter(Boolean).length}
            </div>
            <div className="text-[10.5px] uppercase tracking-wide text-t3">Alert types active</div>
          </div>
          <div>
            <div className="mono text-[18px] font-extrabold text-teal">On</div>
            <div className="text-[10.5px] uppercase tracking-wide text-t3">Verification enabled</div>
          </div>
        </div>
        <button type="button" onClick={complete} className="btn btn-primary px-sp6 py-sp3">
          Open Dashboard →
        </button>
      </div>
    );
  }

  if (step === -1) {
    return (
      <div className="mx-auto flex max-w-[440px] flex-col items-center gap-sp5 rounded-r4 border border-border2 bg-panel p-sp8 text-center shadow-lg2">
        <GuideAvatar size={56} />
        <div>
          <div className="mb-1 text-[13px] font-extrabold uppercase tracking-wide text-teal">
            {GLASSBOX_GUIDE.name}
          </div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-t3">
            {GLASSBOX_GUIDE.role}
          </div>
        </div>
        <p className="text-[14px] leading-relaxed text-t2">&ldquo;{GUIDE_INTRO_MESSAGE}&rdquo;</p>
        <button
          type="button"
          onClick={() => setStep(0)}
          className="btn btn-primary px-sp6 py-sp3"
        >
          Get Started →
        </button>
      </div>
    );
  }

  function handleContinue() {
    if (step === 0) {
      patch({ agentId: previewAgentId });
      setStep(1);
      return;
    }
    setStep(step + 1);
  }

  return (
    <div className="mx-auto grid max-w-[880px] grid-cols-1 gap-sp5 lg:grid-cols-[220px_1fr]">
      <div className="hidden lg:block">
        <div className="sticky top-sp5">
          <AgentHero agentId={effectiveAgentId} />
          <div className="rounded-r3 border border-border bg-panel p-sp4">
            <GuideBubble key={step} message={GUIDE_STEP_MESSAGES[step as 0 | 1 | 2 | 3 | 4]} />
            {step === 1 && state.concern && (
              <p className="mt-sp3 border-t border-border pt-sp3 text-[12px] text-teal">
                {GUIDE_CONCERN_ACK[state.concern]}
              </p>
            )}
            {step === 2 && (
              <p className="mt-sp3 border-t border-border pt-sp3 text-[12px] text-teal">
                {guidePortfolioMessage(state.tickers.length)}
              </p>
            )}
            {step === 4 && (
              <p className="mt-sp3 border-t border-border pt-sp3 text-[12px] text-t3">
                {GUIDE_ALERTS_RECOMMENDATION}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-r4 border border-border2 bg-panel shadow-lg2">
        {/* Compact Guide message for tablet/mobile -- stacked above the
            form, never side-by-side (spec: no side-by-side below desktop). */}
        <div className="border-b border-border p-sp4 lg:hidden">
          <AgentHero agentId={effectiveAgentId} />
          <GuideBubble key={step} message={GUIDE_STEP_MESSAGES[step as 0 | 1 | 2 | 3 | 4]} compact />
        </div>

        <div className="p-sp6 pb-0">
          <StepIndicator step={step} />
        </div>

        <div className="px-sp6 py-sp4">
          {step === 0 && <StepAgent selectedId={previewAgentId} onSelect={setPreviewAgentId} />}
          {step === 1 && (
            <StepConcern value={state.concern} onChange={(concern) => patch({ concern })} />
          )}
          {step === 2 && (
            <StepPortfolio tickers={state.tickers} onTickersChange={(tickers) => patch({ tickers })} />
          )}
          {step === 3 && <StepVerify tickers={state.tickers} />}
          {step === 4 && <StepAlerts state={state} onChange={patch} />}
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
            onClick={handleContinue}
            className="rounded-r2 bg-teal px-sp5 py-sp2 text-[14px] font-bold text-bg shadow-teal transition-transform hover:-translate-y-px hover:bg-teal2"
          >
            {step === 0 ? "Continue with this agent →" : step === LAST_STEP ? "Finish →" : "Continue →"}
          </button>
        </div>
      </div>
    </div>
  );
}
