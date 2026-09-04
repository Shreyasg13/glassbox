// Mirrors backend/app/models.py exactly (Phase 4/5 section). Keep in sync.

export type AgentType = "deterministic" | "llm";
export type Provider = "vllm" | "ollama" | "gemini" | "claude";
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

export type JobKind = "agent_test_run" | "orchestration_run" | "report_generate" | "my_agents_run";
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
  provider: Provider;
  model: string;
  narrative: string;
  created_at: string;
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
