export type ConcernId = "ai-verify" | "influencers" | "volatility" | "retirement";

export type OnboardingState = {
  // Which onboarding-agent persona is guiding this wizard -- see
  // agentPersonas.ts. Cosmetic only (recolors the wizard + frames the
  // verification step's copy); not linked to real agent subscriptions
  // (/api/me/agent-subscriptions is a separate, unrelated concept).
  agentId: string | null;
  concern: ConcernId | null;
  tickers: string[];
  alertTypes: {
    crisis: boolean;
    weeklyReport: boolean;
    scoreChanges: boolean;
    marketEvents: boolean;
  };
  delivery: string[];
  frequency: "realtime" | "daily" | "weekly";
  threshold: number; // 1..5, mapped to ±0.5 .. ±2.5
};

export const initialOnboardingState: OnboardingState = {
  agentId: null,
  concern: null,
  tickers: ["AAPL", "MSFT", "NVDA", "TSLA"],
  alertTypes: {
    crisis: true,
    weeklyReport: true,
    scoreChanges: true,
    marketEvents: false,
  },
  delivery: ["Email", "In-app"],
  frequency: "realtime",
  threshold: 1,
};

export const STEP_LABELS = ["Your agent", "Your concern", "Portfolio", "First verify", "Alerts"] as const;

export function thresholdLabel(step: number): string {
  const value = 0.5 + (step - 1) * 0.5;
  return `±${value.toFixed(1)}`;
}
