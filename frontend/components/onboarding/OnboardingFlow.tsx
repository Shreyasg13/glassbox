"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useLensVoice } from "@/lib/useLensVoice";
import { StepIndicator } from "./StepIndicator";
import { StepConcern } from "./StepConcern";
import { StepPortfolio } from "./StepPortfolio";
import { StepVerify } from "./StepVerify";
import { StepAlerts } from "./StepAlerts";
import { GuideAvatar, GuideBubble } from "./GuideBubble";
import { AriaHero } from "./AriaHero";
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

// Four real steps -- Your concern, Portfolio, First verify, Alerts. The
// agent-pick step that used to sit at index 0 is retired: it was a second,
// confusing identity alongside Aria (the actual, single guide persona),
// not a feature anyone's flow depended on downstream (OnboardingState's
// old agentId was cosmetic-only, never read outside this file).
const LAST_STEP = 3;

type Persisted = { step: number; state: OnboardingState };

export function OnboardingFlow() {
  const router = useRouter();
  const { username, loading: authLoading } = useAuth();
  // Onboarding is the one flow where the Guide's voice is on by default
  // and speaks each step automatically (spec: "live onboarding assistant
  // with voice, clear steps"), unlike the rest of the app where voice
  // stays click-only. `enabled` is the same shared, localStorage-persisted
  // flag used by the Lenses/Hero/dashboard ticker (useLensVoice.ts) --
  // turning it on here also turns it on there, which is intentional (one
  // voice preference, not a hidden onboarding-only shadow flag). The
  // actual enable+prime happens inside the "Get Started" button's onClick
  // below, synchronously, because it must be a real user gesture for
  // mobile Safari's autoplay policy to ever allow the audio that follows.
  const voice = useLensVoice();
  // -1 = the Guide intro screen, 0-3 = the real steps.
  const [step, setStep] = useState(-1);
  const [state, setState] = useState<OnboardingState>(initialOnboardingState);
  const [hydrated, setHydrated] = useState(false);

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
    return (
      <div className="mx-auto flex max-w-[440px] flex-col items-center gap-sp5 rounded-r4 glass-frost-surface p-sp8 text-center">
        <GuideAvatar size={56} />
        <div className="text-[16px] font-extrabold text-t1">You&apos;re all set</div>
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
      <div className="mx-auto flex max-w-[440px] flex-col items-center gap-sp5 rounded-r4 glass-frost-surface p-sp8 text-center">
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
          onClick={() => {
            // Real, synchronous click -- the one moment this session gets
            // to unlock autoplay for everything that follows.
            voice.primeAudio();
            if (!voice.enabled) voice.toggle();
            setStep(0);
          }}
          className="btn btn-primary px-sp6 py-sp3"
        >
          Get Started →
        </button>
      </div>
    );
  }

  const stepMessage = GUIDE_STEP_MESSAGES[step as 0 | 1 | 2 | 3];

  return (
    <div className="mx-auto grid max-w-[880px] grid-cols-1 gap-sp5 lg:grid-cols-[220px_1fr]">
      <div className="hidden lg:block">
        <div className="sticky top-sp5">
          <AriaHero key={step} message={stepMessage} autoSpeak />
          {step === 0 && state.concern && (
            <p className="-mt-sp2 mb-sp4 rounded-r3 border border-teal/[0.18] bg-teal/[0.05] p-sp3 text-[12px] text-teal">
              {GUIDE_CONCERN_ACK[state.concern]}
            </p>
          )}
          {step === 1 && (
            <p className="-mt-sp2 mb-sp4 rounded-r3 border border-teal/[0.18] bg-teal/[0.05] p-sp3 text-[12px] text-teal">
              {guidePortfolioMessage(state.tickers.length)}
            </p>
          )}
          {step === 3 && (
            <p className="-mt-sp2 mb-sp4 rounded-r3 border border-border bg-bg2 p-sp3 text-[12px] text-t3">
              {GUIDE_ALERTS_RECOMMENDATION}
            </p>
          )}
        </div>
      </div>

      <div className="flex max-h-[calc(100vh-180px)] flex-col rounded-r4 glass-frost-surface">
        {/* Compact Guide message for tablet/mobile -- stacked above the
            form, never side-by-side (spec: no side-by-side below desktop). */}
        <div className="shrink-0 border-b border-border p-sp4 lg:hidden">
          <AriaHero key={step} message={stepMessage} compact />
        </div>

        <div className="shrink-0 p-sp6 pb-0">
          <StepIndicator step={step} />
        </div>

        {/* Bounded + independently scrollable, so a tall step always
            stays reachable via a visible scrollbar instead of running
            under the viewport fold with no cue -- and the Back/Continue
            footer below never gets pushed off-screen with it. */}
        <div className="min-h-0 flex-1 overflow-y-auto px-sp6 py-sp4">
          {step === 0 && (
            <StepConcern value={state.concern} onChange={(concern) => patch({ concern })} />
          )}
          {step === 1 && (
            <StepPortfolio tickers={state.tickers} onTickersChange={(tickers) => patch({ tickers })} />
          )}
          {step === 2 && <StepVerify tickers={state.tickers} />}
          {step === 3 && <StepAlerts state={state} onChange={patch} />}
        </div>

        <div className="flex shrink-0 items-center gap-sp3 border-t border-border px-sp6 py-sp4">
          <button
            type="button"
            onClick={() => (step === 0 ? router.push("/dashboard") : setStep(step - 1))}
            className="text-[12.5px] font-medium text-t3 hover:text-t2"
          >
            {step === 0 ? "Cancel" : "Back"}
          </button>
          {/* Pinned to the right with a fixed floor width, not flex:1 --
              a full-width Continue button left Back visually stranded at
              the far edge with no relationship to it. */}
          <button
            type="button"
            onClick={() => setStep(step + 1)}
            className="ml-auto min-w-[170px] rounded-r2 bg-teal px-sp5 py-sp2 text-[14px] font-bold text-bg shadow-teal transition-transform hover:-translate-y-px hover:bg-teal2"
          >
            {step === LAST_STEP ? "Finish →" : "Continue →"}
          </button>
        </div>
      </div>
    </div>
  );
}
