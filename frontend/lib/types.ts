// Mirrors backend/app/models.py exactly (Phase 4/5 section). Keep in sync.

export type AgentType = "deterministic" | "llm";
export type Provider =
  | "vllm"
  | "ollama"
  | "gemini"
  | "claude"
  // OpenAI-compatible failover providers (see backend/app/llm_router.py)
  | "openrouter"
  | "groq"
  | "cerebras"
  | "github"
  | "qwen"
  | "deepseek"
  | "xai"
  | "gateway";
export type OrchestrationMode = "sequential" | "parallel" | "committee_vote";
export type Role = "admin" | "viewer";

export type AgentParams = {
  temperature: number;
  top_p: number;
  max_tokens: number;
  extra: Record<string, unknown>;
};

export type AgentConfig = {
  id?: string;
  name: string;
  role: string;
  type: AgentType;
  provider?: Provider | null;
  model?: string | null;
  fallback_models: string[];
  params: AgentParams;
  system_prompt?: string | null;
  tools: string[];
  enabled: boolean;
};

export type OrchestrationConfig = {
  id?: string;
  name: string;
  mode: OrchestrationMode;
  agent_ids: string[];
  coordinator: string;
  schedule?: string | null;
  agent_timeout_s: number;
  run_budget_s: number;
};

export type ProviderHealth = {
  provider: Provider;
  reachable: boolean;
  detail?: string | null;
  checked_at: string;
};

export type JobKind = "agent_test_run" | "orchestration_run" | "report_generate" | "my_agents_run" | "insight_narrate";
export type JobState = "queued" | "running" | "done" | "error";

export type JobStatus = {
  job_id: string;
  kind: JobKind;
  status: JobState;
  created_at: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
};

export type LLMCallLog = {
  id: string;
  agent_id?: string | null;
  provider: Provider;
  model: string;
  started_at: string;
  duration_ms?: number | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  status: "running" | "ok" | "error" | "timeout";
  error?: string | null;
  estimated_cost_usd?: number | null;
};

export type PaginatedLLMCalls = { items: LLMCallLog[]; total: number };

export type AuditLogEntry = {
  id: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  detail: Record<string, unknown>;
  created_at: string;
};

export type PaginatedAuditLog = { items: AuditLogEntry[]; total: number };

export type DailyReportNarrative = {
  id: string;
  date: string;
  provider: Provider | "system"; // "system" = written by the paper-trading engine, not an LLM
  model: string;
  narrative: string;
  created_at: string;
  title?: string | null;
  profile?: string | null;
};

export const DEFAULT_AGENT_PARAMS: AgentParams = {
  temperature: 0.7,
  top_p: 1.0,
  max_tokens: 1024,
  extra: {},
};

export function emptyAgent(): AgentConfig {
  return {
    name: "",
    role: "",
    type: "deterministic",
    provider: null,
    model: null,
    fallback_models: [],
    params: { ...DEFAULT_AGENT_PARAMS },
    system_prompt: "",
    tools: [],
    enabled: true,
  };
}

export function emptyOrchestration(): OrchestrationConfig {
  return {
    name: "",
    mode: "sequential",
    agent_ids: [],
    coordinator: "vn_engine",
    schedule: "",
    agent_timeout_s: 30.0,
    run_budget_s: 120.0,
  };
}

// ---- Paper trading (admin master view) ----

export type PaperAccountKind = "profile" | "benchmark" | "control";
export type CurveMode = "backtest" | "live";
export type CurvePoint = [string, number, CurveMode];

export type PaperAccountSummary = {
  id: string;
  name: string;
  kind: PaperAccountKind;
  strategy: string;
  username: string | null;
  risk_level: string | null;
  profile: { archetype?: string; horizon_years?: number };
  equity: number;
  total_return: number;
  cagr: number | null;
  live_return: number | null;
  max_drawdown: number;
  sharpe: number;
  volatility: number;
  trade_count: number;
  cost_paid: number;
  turnover: number;
  days: number;
  live_days: number;
  inception: string | null;
  last_date: string | null;
  cash_weight: number;
  benchmark_id: string | null;
  benchmark_return?: number;
  alpha: number | null;
  live_alpha: number | null;
};

export type PaperOverview = {
  initialised: boolean;
  meta: { live_from: string; start: string; last_date: string | null; last_run?: string } | null;
  accounts: PaperAccountSummary[];
};

export type PaperTrade = { date: string; symbol: string; side: "BUY" | "SELL"; shares: number; price: number; cost: number; reason: string };

export type PaperAccountDetail = {
  summary: PaperAccountSummary;
  weights: Record<string, number>;
  invested: number;
  note: string;
  holdings: Record<string, { shares: number; price: number; value: number; weight: number }>;
  cash: number;
  curve: CurvePoint[];
  benchmark_curve: CurvePoint[];
  recent_trades: PaperTrade[];
};

export type SignalStat = { n: number; mean_return: number | null; hit_rate: number | null };
export type PaperScorecard = {
  horizons: number[];
  signals: Record<"BUY" | "SELL" | "HOLD" | "ALL", Record<string, SignalStat>>;
  edge_vs_average: Record<"BUY" | "SELL", Record<string, number | null>>;
  in_sample: boolean;
  as_of: string | null;
};

export type PaperRunResult = {
  bootstrapped: boolean;
  latest_data_date: string;
  live_from: string;
  accounts: number;
  new_live_days: string[];
  reports_written: number;
};

// ---- LLM routing / failover (admin) ----

export type RoutingProvider = {
  provider: string;
  label: string;
  tier: "free" | "freemium" | "paid" | "custom" | "local" | string;
  configured: boolean;
  not_configured_reason: string;
  in_failover_order: boolean;
  cooling_down_s: number;
  cooldown_reason: string;
  last: { ok: boolean; at: string; detail: string } | null;
  get_a_key: string;
};

export type RoutingStatus = { enabled: boolean; order: string[]; budget_s: number; user_runs_may_fail_over: boolean; providers: RoutingProvider[] };

export type RoutingTestResult = { ok: boolean; answered_by: string; model: string; failed_over: boolean; reply: string; skipped_or_failed: { provider: string; result: string }[] };
