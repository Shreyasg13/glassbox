"""Pydantic response/request models for the GlassBox API.

Field names mirror the JSON shapes actually returned by the legacy
Flask dashboard (backend-source/dashboard/DASHBOARD_PRO.py) so the
contract is a faithful port, not a redesign.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Signal = Literal["BUY", "SELL", "HOLD"]


# ---- /api/data, /api/track1/data, /api/track2/data ----

class TrackDataPoint(BaseModel):
    date: str
    portfolio_value: float
    daily_return: float
    positions: Optional[int] = None
    signal: Optional[Signal] = None
    market_return: Optional[float] = None
    agents_active: Optional[int] = None
    vn_score: Optional[float] = None
    track: Optional[str] = None


# ---- /api/track1/agents, /api/track2/agents ----

class TrackAgent(BaseModel):
    name: str
    score: float
    win_rate: float
    decisions: int
    avg_impact: float
    color: str


class TrackAgentsResponse(BaseModel):
    agents: List[TrackAgent]
    vn_score: float
    total_agents: int


# ---- /api/agent-performance ----

class AgentPerformance(BaseModel):
    """Real per-agent call stats, computed from the llm_calls log
    (db.get_agent_performance) -- not a trading win-rate. This system
    doesn't yet link a past BUY/SELL/HOLD signal to its later real-world
    outcome (that's a genuinely separate, harder feature -- see
    docs/PROJECT_STATUS.md's roadmap), so these fields describe agent
    call reliability/volume, which IS real and measured, not signal
    profitability, which isn't measured yet. Earlier field names here
    (score/win_rate/avg_impact) implied the latter while this endpoint
    actually returned a hardcoded mock -- fixed to be honest about what
    it measures now that it's real data."""

    name: str
    call_count: int
    success_rate: float  # 0-100, percent of calls with status "ok"
    avg_duration_ms: Optional[float] = None
    last_active_at: Optional[str] = None


# ---- /api/holdings ----

class Holding(BaseModel):
    symbol: str
    name: str
    sector: str
    weight: float
    signal: Signal
    win_rate: float
    sharpe: float
    test_return: float
    fast_ma: int
    slow_ma: int
    rsi_low: int
    rsi_high: int
    beta: float
    current_price: float
    price_change: float
    current_rsi: float
    volume: int
    data_date: str


class HoldingsSummary(BaseModel):
    total_symbols: int
    avg_win_rate: float
    best_performer: str
    best_return: float
    portfolio_beta: float
    data_source: str
    data_date: str


class HoldingsResponse(BaseModel):
    holdings: List[Holding]
    summary: HoldingsSummary
    sectors: Dict[str, float]


# ---- /api/live-signals & /ws/signals ----

class LiveSignal(BaseModel):
    symbol: str
    name: str
    sector: str
    current_price: float
    signal: Signal
    confidence: float
    rsi: float
    ma_cross: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    volume_ratio: float
    suggested_weight: float
    fast_ma: int
    slow_ma: int
    test_sharpe: float
    win_rate: float
    data_date: str


class LiveSignalsSummary(BaseModel):
    buy_signals: int
    sell_signals: int
    hold_signals: int
    avg_confidence: float
    data_source: str
    last_update: str


class LiveSignalsResponse(BaseModel):
    signals: List[LiveSignal]
    summary: LiveSignalsSummary


# ---- /api/portfolio-stats ----

class TradeRow(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL"]
    shares: float
    price: float
    date: str


class PositionDetail(BaseModel):
    symbol: str
    shares: float
    cost_basis: float
    market_value: float
    unrealized_pnl: float


class PortfolioStats(BaseModel):
    """Real P&L/turnover math ported from backend-source/DAILY_PNL.py's
    DailyPnLTracker (FIFO realized-P&L matching, unrealized P&L from live
    parquet prices) -- not reimplemented from scratch. Reads the same
    portfolio.json/trades.json the legacy script does; both are empty in
    a fresh TRADING_STORAGE_PATH, which `has_trade_history=False` makes
    explicit rather than silently rendering zeros as if trading had
    happened. `churn_rate` is total trade notional (sum of shares*price
    across every trade on record) divided by current total_value -- a
    plain turnover ratio, not time-annualized, since there's no reliable
    period boundary without real trade history to anchor one."""

    cash: float
    positions_value: float
    total_value: float
    initial_capital: float
    total_pnl: float
    total_pnl_pct: float
    realized_pnl: float
    unrealized_pnl: float
    num_positions: int
    num_trades: int
    has_trade_history: bool
    churn_rate: float
    position_details: List[PositionDetail]
    recent_trades: List[TradeRow]
    data_source: str
    as_of: str


# ---- /api/insights/narrate ----

class InsightCandidate(BaseModel):
    """One client-derived "missed opportunity" row, sent up for
    narration -- the frontend owns the detection rule (same pattern
    InsightsAlertsPanel already uses client-side for signal-derived
    alerts), this endpoint only narrates the rows it's handed rather
    than re-deriving its own, possibly-diverging definition."""

    symbol: str
    signal: Signal
    confidence: float
    reason: str


class InsightNarrateRequest(BaseModel):
    candidates: List[InsightCandidate]
    provider: Provider = "ollama"
    model: str


# ---- /api/monte-carlo ----

class MonteCarloResult(BaseModel):
    mean: float
    percentile_5: float
    percentile_95: float
    prob_profit: float
    paths: List[List[float]]
    final_values: List[float]


# ---- /api/historical-reports ----

class HistoricalReport(BaseModel):
    date: str
    file: str
    final_value: float
    return_: float = Field(alias="return")
    sharpe: float
    max_dd: float

    class Config:
        populate_by_name = True


# ---- /api/daily-summary ----

class DailySummary(BaseModel):
    status: str
    current_value: float
    daily_change: float
    vn_score: float
    risk_status: Literal["LOW", "MEDIUM", "HIGH"]
    sharpe: float
    max_dd: float
    win_rate: float
    position_util: float
    alerts: List[str]
    dates: List[str]
    growth_rates: List[float]


# ---- Agent Factory (Phase 4) ----

AgentType = Literal["deterministic", "llm"]
Provider = Literal["vllm", "ollama", "gemini", "claude"]
OrchestrationMode = Literal["sequential", "parallel", "committee_vote"]


class AgentParams(BaseModel):
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 1024
    extra: Dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    id: Optional[str] = None
    name: str
    role: str
    type: AgentType
    provider: Optional[Provider] = None
    model: Optional[str] = None
    fallback_models: List[str] = Field(
        default_factory=list,
        description=(
            "Ordered backup models tried in sequence if `model` is rate-limited/quota-exhausted. "
            "Currently only honored by the gemini provider (its per-tier RPM/TPM/RPD ceilings make "
            "single-model exhaustion routine on a free-tier key); other providers ignore this list."
        ),
    )
    params: AgentParams = Field(default_factory=AgentParams)
    system_prompt: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    enabled: bool = True


class OrchestrationConfig(BaseModel):
    id: Optional[str] = None
    name: str
    mode: OrchestrationMode
    agent_ids: List[str]
    coordinator: str = "vn_engine"
    schedule: Optional[str] = None
    agent_timeout_s: float = Field(30.0, description="Per-agent wall-clock budget for one run")
    run_budget_s: float = Field(120.0, description="Whole-orchestration wall-clock budget")


# ---- Provider health + call logging (Phase 5) ----

class ProviderHealth(BaseModel):
    provider: Provider
    reachable: bool
    detail: Optional[str] = None
    checked_at: str


class LLMCallLog(BaseModel):
    id: str
    agent_id: Optional[str] = None
    provider: Provider
    model: str
    started_at: str
    duration_ms: Optional[int] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    status: Literal["running", "ok", "error", "timeout"]
    error: Optional[str] = None
    estimated_cost_usd: Optional[float] = Field(
        None, description="None when the provider/model has no pricing entry (e.g. self-hosted)"
    )


# ---- Admin audit log (Phase 6) ----

class AuditLogEntry(BaseModel):
    id: str
    actor: str
    action: str = Field(..., description='e.g. "agent.create", "agent.delete", "orchestration.run", "report.generate"')
    resource_type: str = Field(..., description='"agent" | "orchestration" | "report" | "auth"')
    resource_id: Optional[str] = None
    detail: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class PaginatedAuditLog(BaseModel):
    items: List[AuditLogEntry]
    total: int


class PaginatedLLMCalls(BaseModel):
    items: List[LLMCallLog]
    total: int


# ---- Background jobs: agent test-run, orchestration run, report generate ----

JobKind = Literal["agent_test_run", "orchestration_run", "report_generate", "my_agents_run", "insight_narrate"]
JobState = Literal["queued", "running", "done", "error"]


class JobStatus(BaseModel):
    job_id: str
    kind: JobKind
    status: JobState
    created_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ---- /api/me (self-service agent subscriptions + personalized run) ----


class AgentSummary(BaseModel):
    """Safe, public-ish subset of AgentConfig for the self-service agent
    picker -- deliberately excludes system_prompt/provider/model/params,
    which stay admin-only via /api/admin/agents (that GET is gated by
    require_admin at the router level, so a plain viewer can't browse
    them today at all -- this is the non-admin-gated equivalent, minimal
    fields only)."""

    id: str
    name: str
    role: str
    type: AgentType
    enabled: bool


class AgentSubscriptions(BaseModel):
    agent_ids: List[str] = Field(default_factory=list)


# ---- /api/me/entitlements, /api/me/verify/{ticker} ----

class Entitlements(BaseModel):
    """A real, backend-enforced free-tier quota -- not shown anywhere in
    the product until this existed. `remaining` is what the UI should
    gate on; `limit`/`used` are for display ("2 of 5 used")."""

    limit: int
    used: int
    remaining: int


class VerifiedSignalResponse(BaseModel):
    """What a real verification actually returns today: GlassBox's
    deterministic, real-data-driven per-ticker signal (see LiveSignal --
    RSI/moving-average-cross computed from real historical prices, not
    an LLM guess). This is intentionally NOT badged as the fuller
    narrated A6 audit trail (still Phase 7, not built) -- `disclaimer`
    says so explicitly so the free-tier entitlement is never spent on
    something bigger than what it actually delivers."""

    signal: LiveSignal
    verified_at: str
    entitlements: Entitlements
    disclaimer: str = (
        "Deterministic signal from GlassBox's real technical data (RSI, moving-average cross, "
        "historical price/volume). Not yet the full narrated A6 audit trail."
    )


class JobAccepted(BaseModel):
    job_id: str


class AgentTestRunRequest(BaseModel):
    input: str = Field(..., max_length=8000, description="Freeform prompt/context to run the agent against")


class OrchestrationRunRequest(BaseModel):
    input: Optional[str] = Field(default=None, max_length=8000)  # flows into LLM prompts -- bound it


class ReportGenerateRequest(BaseModel):
    date: Optional[str] = Field(None, description="YYYYMMDD; defaults to the latest report on disk")
    provider: Provider = "ollama"
    model: str
    agent_id: Optional[str] = Field(None, description="Reuse an existing agent's system_prompt/params if set")


class DailyReportNarrative(BaseModel):
    id: str
    date: str
    provider: Provider
    model: str
    narrative: str
    created_at: str


# ---- Job WebSocket message envelope (/ws/jobs/{job_id}) ----
#
# All frames share this shape: {"type": ..., "data": {...}}
#   {"type": "log",    "data": {"message": str, "ts": str}}
#   {"type": "token",  "data": {"text": str}}          -- one streamed LLM output chunk
#   {"type": "status", "data": JobStatus}               -- terminal frame; socket closes after
#
# Mirrors the existing /ws/signals envelope convention ({"type", "data"})
# so both dashboards' WS clients share one parsing pattern.


# ---- Auth ----

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Literal["admin", "viewer"]


# Length caps keep a hostile client from making the server hash/log/store
# megabyte-sized "passwords" and usernames. Password's real limit is 72
# BYTES (bcrypt), enforced in auth.py; this is just a coarse outer bound.
class LoginRequest(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)


class SignupRequest(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)
