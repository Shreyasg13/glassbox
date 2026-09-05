import type { ConcernId } from "@/components/onboarding/types";

/**
 * GlassBox Guide -- a first-party system persona, distinct from the
 * investor-archetype Strategy Lenses (lensData.ts). Deliberately NOT
 * folded into LensPersona's type: that shape is investor-specific
 * (inspiredName/firm/track-record/growth/risk sliders, a procedurally
 * drawn portrait) and forcing a system agent into it would mean
 * fabricating meaningless values for fields that don't apply. This is
 * a small, purpose-built config instead, reusing the same *visual
 * language* (the --c-{accent} token system, the same badge/card
 * patterns) rather than the same TypeScript shape.
 *
 * Accent is "teal" deliberately -- the app's own primary/brand color
 * (nav, primary buttons, verification checkmarks), not one persona's
 * exclusive accent, which fits: the Guide represents GlassBox itself,
 * not one investment philosophy among several.
 */
export const GLASSBOX_GUIDE = {
  id: "glassbox-guide",
  name: "GlassBox Guide",
  role: "Verification Copilot",
  accent: "teal",
  description:
    "Your guide to understanding what GlassBox verifies, why it matters, and what is monitoring your portfolio.",
} as const;

export const GUIDE_INTRO_MESSAGE =
  "I'll help you set up GlassBox around what matters to you. About 2 minutes.";

export const GUIDE_STEP_MESSAGES: Record<0 | 1 | 2 | 3, string> = {
  0: "First, tell me what you want GlassBox to watch most closely. I'll use this to prioritize your dashboard, reports, and alerts.",
  1: "Now give me the holdings you want GlassBox to monitor. Connect a supported portfolio source or enter tickers manually.",
  2: "Here's your first GlassBox verification. Instead of asking you to trust an AI-generated score, GlassBox exposes the data behind it and independently checks the result.",
  3: "Last step. Tell me when something is important enough to get your attention.",
};

/** Deterministic (no LLM) contextual acknowledgement per concern
 * selection -- see OnboardingFlow.tsx's step 0. */
export const GUIDE_CONCERN_ACK: Record<ConcernId, string> = {
  "ai-verify": "Got it. I'll prioritize evidence-backed verification and make the underlying data easier to inspect.",
  influencers: "I'll help separate claims from evidence and surface where the underlying data disagrees.",
  volatility: "I'll focus on explaining which market changes actually affect your holdings and why.",
  retirement: "I'll prioritize portfolio risk, concentration, and changes that could affect your longer-term plan.",
};

/** Deterministic (no LLM) glossary for unfamiliar verification metrics
 * -- see StepVerify's EvidenceRow tooltips. */
export const GUIDE_METRIC_EXPLANATIONS: Record<string, string> = {
  "Debt / Equity Ratio": "Shows how much debt the company uses relative to shareholder equity.",
  "Altman Z-Score": "A financial-health indicator commonly used to estimate bankruptcy risk.",
  "Beta vs S&P 500": "Measures how strongly the stock has historically moved relative to the broader market.",
  "A6 Verified": "GlassBox independently checked the generated analysis against the underlying evidence.",
  "Evidence Chain": "Shows where the numbers came from so the result can be inspected rather than blindly trusted.",
  // Dashboard/reports terms -- same deterministic-glossary pattern,
  // reused via GuideHint (GuideBubble.tsx) rather than duplicated copy.
  "Portfolio Beta": "How strongly your combined holdings have historically moved relative to the broader market, weighted by position size.",
  "Win Rate": "The percentage of a backtest's historical trades that were profitable. A track-record statistic, not a prediction.",
  "Agent Success Rate": "The percentage of this agent's calls that completed without error -- a reliability measure, not a trading win-rate. GlassBox doesn't yet link a past signal to its later real-world outcome.",
  "Monte Carlo Simulation": "A real random-walk simulation seeded from this portfolio's own historical daily-return distribution -- not a canned scenario.",
  "Percentile Band": "The 5th-to-95th percentile range across all simulated outcomes: a plausible spread, not a forecast of what will happen.",
  "Prob. of Profit": "The share of simulated paths that ended above today's value, based purely on historical volatility.",
};

export function guidePortfolioMessage(holdingCount: number): string {
  if (holdingCount === 0) {
    return "Add a holding above (connect a broker or enter a ticker) and I'll show you what GlassBox verification looks like.";
  }
  return `I found ${holdingCount} holding${holdingCount === 1 ? "" : "s"}. Next I'll show you what GlassBox verification looks like using one of them.`;
}

export const GUIDE_ALERTS_RECOMMENDATION =
  "For a new account, Crisis Alerts and Portfolio Score Changes are a good starting point. You can change these settings anytime.";

export const GUIDE_ALERTS_CONFIRM = "Looks good. You can change this anytime.";

export const GUIDE_COMPLETE_MESSAGE =
  "You're ready. GlassBox will monitor your selected holdings and surface changes that are worth investigating.";

export const GUIDE_DASHBOARD_WELCOME =
  "You're in. This dashboard summarizes what GlassBox is monitoring. You can inspect or configure the automation behind your analysis under My Agents.";

// localStorage keys -- same convention as useLensVoice.ts's shared
// voice-enabled flag and the old WelcomeTour's tour-seen flag.
export const ONBOARDING_STATE_KEY = "glassbox_onboarding_state";
export const ONBOARDING_COMPLETE_KEY = "glassbox_onboarding_complete";
export const DASHBOARD_WELCOME_SEEN_KEY = "glassbox_dashboard_welcome_seen";

/**
 * Where to send the browser right after a successful login/signup/OAuth
 * callback. First login (onboarding never completed) goes straight into
 * the GlassBox Guide-led wizard -- the whole point of this feature is
 * that it's the first thing a new user sees, not something they have to
 * discover via a separate /choose menu. A returning user who already
 * completed onboarding keeps the existing /choose landing (sample data
 * vs. redo setup) -- that behavior predates this feature and isn't part
 * of the bug this fixes.
 */
export function postLoginRedirect(): "/onboarding" | "/choose" {
  try {
    return localStorage.getItem(ONBOARDING_COMPLETE_KEY) === "1" ? "/choose" : "/onboarding";
  } catch {
    return "/choose";
  }
}
