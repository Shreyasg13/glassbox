# GlassBox — Performance & Orchestration Addendum

Adds concrete rules for backend throughput, frontend smoothness, and AI-agent
orchestration on top of the base architecture in the project plan. Every
phase's implementation should satisfy these, not treat them as later polish.

## 1. Backend (FastAPI) — fast by construction

- **Never block the event loop.** All I/O (file reads of `reports/*.json`,
  DB queries, LLM calls, subprocess calls into the existing engine) must be
  `async` or run via `run_in_threadpool` / `asyncio.to_thread`. A slow report
  read must never stall `/ws/signals` for other connected clients.
- **Cache hot reads.** `/api/live-signals`, `/api/holdings`, `/api/agent-performance`
  are polled/streamed constantly — wrap them with a short in-process TTL cache
  (1-3s) keyed by source file mtime, so N clients don't cause N redundant disk
  reads. Use `cachetools.TTLCache` or a tiny hand-rolled version; no need for
  Redis until multi-instance deployment (Phase 6).
- **WebSocket fan-out, not per-client polling loops.** `/ws/signals` should have
  a single background task that reads the source once per tick and broadcasts
  to all connected sockets (`ConnectionManager.broadcast`), not one polling
  loop per client.
- **LLM calls are background tasks, always.** `/reports/generate` and any
  admin "test run" panel action must return immediately with a job id, run the
  provider call in a background task, and stream progress/result over
  `/ws/reports/{job_id}` or SSE. No request handler ever awaits an LLM call
  directly — this is the #1 way a slow Gemini/Claude round-trip would freeze
  the API for unrelated dashboard traffic.
- **Timeouts + circuit breaker per provider.** Every `LLMProvider.complete()`
  call gets a hard timeout (default 30s, configurable per agent) and a
  per-provider failure counter; after N consecutive failures, short-circuit
  to a cached/fallback response and surface provider health in the admin
  dashboard rather than hanging requests.
- **Pagination on anything unbounded.** `/api/historical-reports` and future
  audit-log endpoints take `limit`/`cursor`, never return the whole table.
- **Uvicorn with `--workers` + `uvloop`** in production (Phase 6); single
  worker + `--reload` in dev is fine through Phase 1-4.

## 2. Frontend (Next.js) — smooth by construction

- **RSC shell, client islands only where live.** Nav, static pages, and
  initial data for charts render server-side (RSC/SSR) so first paint has
  real content, not a skeleton. Only `SignalTicker`, `AgentCards`, and chart
  components that need live updates are `"use client"`.
- **TanStack Query tuned per data class**, not one global default:
  - Live-ish (`agent-performance`, `holdings`): `staleTime: 3_000`,
    `refetchInterval` only as a fallback if WS is disconnected.
  - Slow-moving (`historical-reports`, `settings`): `staleTime: 5 * 60_000`.
  - Prefetch on the server for the initial page load (`queryClient.prefetchQuery`
    in the RSC, hydrate into the client) so the client never shows a loading
    spinner for data the server already had.
- **WebSocket hook is a single shared connection** (`useSignalSocket` context
  provider), not one socket per component — multiple widgets subscribe to the
  same message stream instead of opening N sockets.
- **Auto-reconnect with backoff + optimistic "stale" indicator** — on
  disconnect, show the last-known values dimmed/labeled "reconnecting" rather
  than blanking the UI, and fall back to REST polling until the socket
  recovers.
- **Charts are lazy-loaded (`next/dynamic`, `ssr:false`) and memoized** — recharts
  re-renders are the most common source of jank in a ticking dashboard; wrap
  series components in `React.memo` and only pass in the diffed slice of new
  data, not the whole growing array, where the API allows windowing.
- **Route-level code splitting is automatic under App Router** — just avoid
  importing the admin Agent Factory bundle (sliders, JSON/system-prompt
  editors) from the public dashboard route.

## 3. AI agent orchestration — well-conducted, not just "callable"

- **Deterministic vs. LLM agents run on different paths.** The V(n) /
  quant agents (`base_agent.py` subclasses) execute synchronously in-process
  as today — they're fast and auditable, and Phase 4-5 must not silently
  route them through an LLM provider. Only admin-created "analyst" agents and
  report narration go through the Provider Abstraction Layer.
- **Orchestration modes map to concrete async patterns:**
  - `sequential` → agents run in order, each sees prior agents' output in its
    prompt/context (for LLM agents) or its input state (for deterministic
    ones). Implemented as a plain `for` loop with `await`.
  - `parallel` → `asyncio.gather(*[run_agent(a) for a in agents], return_exceptions=True)`;
    one agent's failure/timeout must not kill the others — collect and report
    partial results.
  - `committee_vote` → run agents in parallel (as above), then reduce through
    the existing `vn_engine` coordinator, never through an LLM "judge" — keeps
    the final signal deterministic and auditable per the plan's design
    guardrail.
- **Per-agent budget, not just per-call timeout.** An orchestration run
  (e.g. daily pre-market) has a wall-clock budget; if a parallel agent blows
  its individual timeout it's marked `degraded` and excluded from the vote
  rather than stalling the whole run.
- **Everything the LLM touches is logged with cost/latency/token counts**
  per call (provider, model, ms, tokens_in/out, estimated cost) into an
  `llm_calls` table, surfaced in the admin dashboard (Phase 6 observability
  requirement) — this is what lets an admin actually compare
  Ollama-local vs. Gemini-cloud for a given agent instead of guessing.
- **Streaming where the UI benefits.** Report narration and any long LLM
  completion streams token-by-token over the job's WS/SSE channel so the
  admin "test run" panel and the daily-report viewer feel live instead of
  spinner-then-dump.

## 4. Where this plugs into the phased plan

- Phase 1 (FastAPI gateway): apply the caching + async rules to every ported
  route from day one.
- Phase 3 (WS layer): build the single-broadcast `ConnectionManager` and the
  shared-socket frontend hook as specified above, not per-widget sockets.
- Phase 4 (Agent Factory): orchestration engine implements the three modes
  exactly as described in §3, with per-agent timeout/budget fields in the
  `Orchestration` schema (`agent_timeout_s`, `run_budget_s`).
- Phase 5 (Providers): every adapter (`VLLMProvider`, `OllamaProvider`,
  `GeminiProvider`, `ClaudeProvider`) implements the same timeout/circuit-breaker
  wrapper in a shared base class — no provider gets to skip it.
- Phase 6 (Hardening): promote the in-process TTL cache to Redis if running
  multi-instance, turn on `uvloop`/multi-worker Uvicorn, and wire the
  `llm_calls` cost/latency table into the admin observability dashboard.
