# GlassBox — Phases 7–10: Stock Analysis, Audit Trail, Knowledge Base, External Intelligence

Continuation of the phased build plan (Phases 0–6 already shipped and live).
This covers four requested pieces, each scoped honestly against what
actually exists in the codebase today versus what's genuinely new
infrastructure — no phase here assumes a subsystem exists that doesn't.

## What exists today (the honest baseline)

- Per-symbol **latest** signal/price data (`/api/live-signals`, `/api/holdings`) —
  no historical time series exposed via API yet, even though the underlying
  parquet files have ~5 years of history per symbol.
- `llm_calls` table logs provider/model/duration/tokens/cost per call, but
  **not** the actual output text in a queryable way, and deterministic
  signals aren't persisted historically at all — only the latest snapshot.
- No "A6 Auditor" cross-check exists — the marketing page's audit-activity
  feed (NVDA verified, TSLA correction, etc.) is mockup copy, not a real
  running feature. Building it for real means: given an LLM agent's
  narrative, extract its numeric claims and diff them against the actual
  signal/holdings data, then log the result.
- No external news/market-factor source is wired in anywhere.
- Recharts is already a frontend dependency (unused so far) — the charting
  library for all of this is already in place.

## Phase 7 — Stock Analysis page + a real A6 Audit feed

**User-facing** (per the access-control decision below), no new
infrastructure beyond one new backend endpoint and a persistence table.

- Backend: `GET /api/stocks/{symbol}/history?range=1y` — reads the existing
  per-symbol parquet's full OHLCV+indicator series (already computed by
  the daily-sync cron job) and returns it for charting, instead of only
  ever exposing the latest row.
- Backend: a real audit step. When an LLM agent produces a narrative
  (test-run, orchestration run, or `/reports/generate`), run a lightweight
  post-check: extract numeric claims from the text (regex/simple parse for
  patterns like "D/E of X", "RSI at Y"), compare each against the actual
  signal/holdings values for that symbol, and log a row to a new
  `audit_events` table (`symbol, claim, actual_value, stated_value, status:
  "verified"|"corrected"|"flagged", agent_name, created_at`). This is what
  makes "0 discrepancies" or "flagged, corrected before display" a real,
  computed fact instead of scripted mockup text.
- Backend: `GET /api/stocks/{symbol}/audit-log` — public, paginated, feeds
  the frontend feed component.
- Frontend: `app/(marketing-or-app)/stocks/[symbol]/page.tsx` — price/RSI/MA
  charts (Recharts) + the audit-activity feed, styled per the reference
  mockup's "Stock Analysis" screen.
- **Exit:** a real stock page where every audit-feed entry is the output of
  an actual check that ran against actual data, not a static list.

## Phase 8 — Signal/agent-output history (the foundation for "RAG")

**Backend-only infrastructure.** This is a database/pipeline phase, not a
page — it's what Phase 9's news integration and any future "why did this
drift" question need to exist first.

- New `agent_run_history` table: every agent run's full input/output
  persisted (not just `llm_calls`' metadata) — `agent_id, symbol, input,
  output, signal_snapshot (JSON), created_at`.
- A retrieval function: given a symbol (+ optional date range), pull the
  most relevant past runs. **Start simple** — recency + symbol match, no
  embeddings — and treat a full vector-embedding pipeline (a real "RAG"
  system in the strict sense) as an explicit **Phase 8b** upgrade only if
  the simple version proves insufficient; it needs an embedding model and
  a vector store, real added infrastructure this plan doesn't assume yet.
- Wire this retrieval into `run_llm_agent()` (`orchestration.py`) as
  optional extra context: "here's what this committee said about this
  stock over the last N runs."
- **Exit:** agents can reference their own past reasoning on a symbol;
  the audit feed can show trend ("A6 has verified AAPL 12 times this
  month, 1 correction").

## Phase 9 — External news / market-factor integration

**Needs a decision from you before any code**, same as the Gemini key
earlier: no external news API is wired in today, and I won't fabricate
what one would return. Options, cheapest first:
- A free-tier news API (NewsAPI.org, Alpha Vantage's News Sentiment
  endpoint, or similar) — needs a key, same flow as the Gemini key.
- Skip real news and instead have agents reason only from price/technical
  drift + their own history (Phase 8) — real but narrower "why" answers.

Once a source is picked: a fetch+summarize step (reuses the existing
Provider Abstraction Layer to summarize raw articles) feeds into the
`GlobalMacro`/`BehavioralCoach` agent prompts as grounding context, and
audit-feed entries can cite it ("Crisis Alert fired — TSLA D/E increased
12%, related news: ...").

## Phase 10 — Admin heuristic/formula panel

**Admin-only** (per the access decision below). A page showing the actual
math behind a signal — the RSI/MA formulas, the deterministic committee's
confidence-weighted vote calculation — as interactive charts an admin can
study and (eventually) tune parameters against. Builds on Phase 7's
charting work; no new backend infrastructure beyond exposing the formula
inputs/intermediate values that already exist inside `data_source.py`'s
calculations.

## Access control (your question, answered)

| Section | Access |
|---|---|
| Stock Analysis page + A6 Audit feed (Phase 7) | **Public/user-facing** — it's the product's core trust pitch ("see the math," published error rate) |
| Signal history retrieval (Phase 8) | Backend-only, no direct UI |
| News/external intelligence (Phase 9) | Feeds into agent output shown to users; the raw admin config (which source, keys) stays admin-only |
| Heuristic/formula panel (Phase 10) | **Admin-only** — the tuning knobs, not the verified result |

## Suggested order

7 → 8 → 10 → 9, in that order: Phase 7 ships something real and visible
fastest with zero new infra risk; Phase 8 is the foundation Phase 9
actually needs to be more than "news pasted into a prompt"; Phase 10 is
independent and can slot in anytime; Phase 9 waits last since it's the
one genuinely blocked on you picking and provisioning a news API key.
