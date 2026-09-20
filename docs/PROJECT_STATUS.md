# GlassBox — Project Status & Task Tracker

Living document. Update this whenever a phase completes, a bug is found,
or scope changes — this is the single place to check "where are we" and
"what's next" without re-deriving it from chat history.

**Last updated:** 2026-09-11 (Phase 14 + voice-cache fix)

## Live deployment

| | |
|---|---|
| App | https://glassbox-portfolio-review.duckdns.org |
| API | same domain, path-routed (`/api/*`, `/auth/*`, `/health`, `/ws/*` -- see `deploy/Caddyfile`) |
| Database | Neon Postgres (`console.neon.tech`, org `spring-hill-60129601`, `neondb` / `production` branch) |
| Source | `github.com/Shreyasg13/glassbox` (private, `main` branch) |
| Host | GCP VM `instance-20260902-033025`, project `project-f015cf71-9e01-4a2a-8f5`, zone `us-central1-a` |
| Admin login | username `admin` + the password from `GLASSBOX_ADMIN_PASSWORD_HASH` / `GLASSBOX_ADMIN_PASSWORD` in the VM's `.env`. **No built-in default any more** (see "Security & cost hardening" below) |
| Dev viewer login | none in production. `admin`/`admin` and `user`/`user` exist only locally when `GLASSBOX_ENABLE_DEV_USERS=1` (refused if `GLASSBOX_ENV=production`) |
| Signup | `/signup` — real accounts, bcrypt-hashed, role="viewer" always |

## Phase status

| Phase | What | Status |
|---|---|---|
| 0 | Contract (`openapi.yaml`), design tokens, scaffolding | ✅ Done |
| 1 | FastAPI gateway — all legacy Flask routes ported | ✅ Done |
| 2 | Frontend shell + onboarding flow | ✅ Done |
| 3 | Live WebSocket signal layer | ✅ Done |
| 4 | Agent Factory (CRUD, JWT auth) | ✅ Done |
| 5 | Provider Abstraction Layer + orchestration engine | ✅ Done |
| 6 | Hardening (caching, rate limits, audit log, observability) | ✅ Done |
| — | GCP deployment (Docker Compose + Caddy, no AWS) | ✅ Done, live |
| — | Public marketing landing page + authenticated app shell (matching `GlassBox_Complete_v3.html` / `GlassBox_Reference.html`) | ✅ Done |
| — | UI polish (route transitions, animated stats, scroll-spy) | ✅ Done |
| — | Real trading data synced to VM + daily refresh cron | ✅ Done |
| — | Agent Factory seeded with real committee personas (10 agents, "Investment Committee" orchestration) | ✅ Done |
| 7 | Stock Analysis page + real A6 Audit feed | 📋 Planned — see `docs/PHASE_7_10_AUDIT_KNOWLEDGE_PLAN.md` |
| 8 | Agent-run history / knowledge base foundation | 📋 Planned |
| 9 | External news/market-factor integration | 📋 Planned — blocked on a news API key decision |
| 10 | Admin heuristic/formula panel | 📋 Planned |

## Next wave: platform depth (roadmap, 2026-09-04)

Six workstreams identified from a product-direction discussion, each
verified against the real codebase (not assumed) before being listed
here. Update each row's status as work begins/lands.

| # | What | Current state (verified) | What it needs | Status |
|---|---|---|---|---|
| 1 | **Real agent performance/"journey" stats** -- which agents' signals were actually right, per user, over time | `db.get_agent_performance()` now aggregates real `call_count`/`success_rate`/`avg_duration_ms`/`last_active_at` per agent from the `llm_calls` log, replacing the old hardcoded mock. Deliberately does not claim a trading win-rate -- that needs linking a past signal to its later real outcome, a genuinely separate feature (still not started; see Phase 8 note below). Shown on `/dashboard` via `AgentPerformancePanel` | Real per-user/per-signal profitability tracking is the harder remaining half -- overlaps with **Phase 8** (`PHASE_7_10_AUDIT_KNOWLEDGE_PLAN.md`), read that before extending this further | ✅ Done (call-reliability stats); 📋 signal-profitability tracking still open |
| 2 | **Per-user agent subscription** -- user picks which agents run their reports; only subscribed agents run | New `/api/me/*` router (any logged-in role, not admin-gated): browse agents, save a `subscribed_agent_ids` list on your own `users` row, and `POST /api/me/run-report` runs the real seeded Investment Committee orchestration filtered to just those ids (falls back to the full committee if unset -- same "no preference = default behavior" convention item 4's watchlist uses). Self-service `/agents` page in the nav (checkboxes + a live "Run My Report" job panel, reusing the same job/WS machinery admin runs already use). Known pre-existing gap this inherits, not introduced by it: `/ws/jobs/{id}` has no auth/ownership check at all (relies on the job id being an unguessable UUID) -- true for every job kind already, not something this feature made worse, but worth fixing if job output sensitivity increases | Done for v1. Real per-signal profitability-based auto-subscription (vs. manual picking) would build on item 1's still-open half | ✅ Done |
| 3 | **13F institutional filing data** | **Does not exist anywhere in this codebase** -- confirmed by a full-repo search, zero real matches | SEC EDGAR publishes 13F filings via a free public API (no key needed) -- feasible without a paid data vendor, but is a real new ETL pipeline (quarterly filings, CIK-to-ticker mapping, storage schema) | 📋 Planned, not started |
| 4 | **Simulated test-user cohort** (5 users w/ sessions, for QA/demo) | `app/scripts/seed_demo_users.py` creates 5 real viewer accounts (`demo_growth`/`demo_income`/`demo_index`/`demo_finance`/`demo_diversified`), each with its own watchlist. Required a real feature to actually differentiate them: `/api/holdings` previously returned the identical global 15-symbol universe to every account (no per-user portfolio concept existed at all) -- it now takes an optional auth token (`get_current_user_optional`) and filters + re-normalizes weights to the caller's own watchlist when one is set, falling back to the shared view for anonymous/demo requests and any account with none (every pre-existing signup). Dashboard client-side re-fetches with the token after the server-rendered default paints (same pattern `SignalTicker` already used for live data) | Done | ✅ Done |
| 5 | **Real broker portfolio import** (Robinhood, Schwab, etc.) | The broker-connect icons on the marketing/onboarding UI are illustrative only -- no real OAuth/import wired to any broker. Notably, `Pricing.tsx`'s own copy already promises **"Broker import via SnapTrade"** on the Standard tier -- SnapTrade is a broker-aggregator API built for exactly this (one integration covers many brokers) rather than building Robinhood/Schwab/etc. individually. Robinhood has no official public API at all (unofficial/reverse-engineered access is ToS-risk territory); Schwab has a real developer API but requires app approval | A SnapTrade (or equivalent aggregator) developer account + API key -- external signup, same pattern as DuckDNS/Neon/Google OAuth this session | 📋 Planned, blocked on account creation |
| 6 | **Expose already-built API endpoints with zero UI** | `/api/track1/agents` + `/api/track2/agents` now shown via `TrackComparisonPanel` (labeled illustrative -- these are still the pre-existing static per-track reference constants, not this account's live results). `/api/monte-carlo` now shown via `StressTestPanel`, a real Monte Carlo simulation (numpy random walk seeded from this portfolio's actual historical daily-return distribution, not a canned scenario) with a day-horizon picker and an SVG fan chart of simulated paths. Both on `/dashboard` | Done | ✅ Done |
| 7 | **First-time-visitor onboarding** | Superseded by a bigger, better version: `WelcomeTour.tsx`'s standalone 4-slide product-tour carousel is retired (deleted) in favor of **GlassBox Guide**, a first-party system persona (`lib/glassboxGuide.ts`, `GuideBubble.tsx`) integrated directly into the real setup wizard (Concern → Portfolio → Verify → Alerts) with a Guide intro screen, deterministic per-step/per-selection messages (no LLM -- static UI copy, same reasoning as before), click-to-reveal metric tooltips on Step 3, and a "GlassBox is ready" summary before Dashboard. Onboarding progress now persists across refresh (localStorage -- there was previously *zero* persistence; `complete()` didn't even save anything). The old 4-slide tour is replaced by one small, dismissible `DashboardWelcomeNote` on `/dashboard` only, gated by its own flag so it never re-fires. Guide also appears in My Agents as a system-agent card (opens an info panel, not fake chat) with clearly-disabled "future agent" placeholders (Verify/Risk/Reports). Explicitly **not** an investor-persona imitation -- distinct type/visual role from the Strategy Lens personas (lensData.ts), same teal/verification visual language as the rest of the app. Optional voice reuses the existing ElevenLabs/Kokoro chain (off by default), a real, previously-unused ElevenLabs voice ("River", live-verified) deliberately not one of the 8 lens voices | Done | ✅ Done |
| 8 | **Report charts** -- `/reports/[id]` is LLM-narrated prose only, no risk/signal visualizations | `PortfolioValueChart` (real time series from `/api/data`, an SVG line, no library) + `SignalBreakdownChart` (real BUY/SELL/HOLD counts from `/api/live-signals`) now shown alongside the narrative. Honestly labeled: `DailyReportNarrative` only ever persisted the generated *text*, not the numeric data that went into it (`_build_prompt` discards it after generating), so these show the latest available data as context, not a frozen snapshot locked to that exact report's generation date | Done | ✅ Done |
| 9 | **User/product analytics** -- how people actually use the platform (page views, feature engagement) | Does not exist at all today, confirmed -- distinct from the trading-data graphs already built | Needs a decision on what to track and (if not self-hosted) which analytics provider | 📋 Planned, not scoped yet |
| 10 | **Q&A help chatbot** -- a real conversational agent answering freeform user questions about the platform | Does not exist. Explicitly scoped as separate from item 7's onboarding tour -- this is real ongoing per-query LLM cost, not a one-time static walkthrough | Needs a system prompt, a chat UI, and a cost/scope decision before building (this is a genuine recurring spend, not a one-time feature) | 📋 Planned, not started |

Not on this list because already answered directly, not planned work:
**10 years of price history is real** -- verified live on the VM, AAPL's
own parquet file spans 2016-01-04 to the present (2,523 rows), with RSI/
moving-averages/volatility already computed columns. The gap is 13F
data specifically (row 3), not historical price depth generally.

## Known gaps (disclosed, not oversights)

- **Auth is now real for signup/viewer accounts.** `/auth/signup` +
  `/signup` create genuine bcrypt-hashed accounts in a `users` table
  (`backend/app/auth.py`, `db.py`) — self-serve accounts are always
  role="viewer" (admin is never grantable via signup, by design). The
  original hardcoded `admin`/`admin` was REMOVED (it was a live admin login on the
  public deployment) -- see "Security & cost hardening" below.
  **Google sign-in is real** (`backend/app/oauth_google.py`,
  `routers/oauth.py`) — server-side OAuth 2.0 authorization code flow,
  OAuth accounts keyed on (provider, subject) with no password_hash,
  redirect back to the frontend via a URL fragment so the minted JWT
  never touches a query string or server log. Configured via
  `GOOGLE_OAUTH_CLIENT_ID`/`SECRET`; unset keeps the button returning a
  clean 503 rather than erroring. Microsoft remains honestly disabled —
  same shape of work, just not built yet.
- **Production data now lives in Neon Postgres, not the VM's local
  SQLite file.** `DATABASE_URL` set on the VM; `backend/app/db.py`
  already used plain SQLAlchemy Core with JSON-as-text columns (no
  SQLite-specific SQL), so the swap needed no query changes — just a
  driver (`psycopg`) and a dialect-aware `connect_args`/sslmode branch.
  All 7 tables' existing rows (10 agents, 57 audit-log entries, 6 jobs,
  42 llm_calls, 1 orchestration, 1 user) were copied via
  `app/scripts/migrate_to_postgres.py` and the cutover was verified live
  and definitively — not just by matching row counts, but by writing a
  new user through the live API and confirming it does NOT appear in
  the old SQLite file (which still shows only the pre-migration row),
  proving writes genuinely go to Neon now. The old SQLite file is left
  in place as a frozen pre-cutover snapshot, not an active fallback.
- **Deterministic agents don't call the real engine classes yet.** The
  "Quantitative Strategist (Engine)" etc. agents read the same live-signals
  data those classes would produce, rather than instantiating
  `BaseAgent` subclasses directly (`backend/app/orchestration.py` docstring
  has the full rationale).
- **`committee_vote`'s reduction is a confidence-weighted vote**, not a
  literal call into the source repo's `VnCalculator` — that class computes
  a different tradeoff (info/quality over agent count, not a BUY/SELL/HOLD
  reduction). Still fully deterministic/auditable.
- **Gemini free-tier RPM is very low** on the currently-wired project
  (`gen-lang-client-0725477037` / "Default Gemini Project"). A 7-agent
  parallel committee run reliably 429s most LLM agents even after three
  real bugs were found and fixed (see below) — this is a quota ceiling,
  not a code defect. **Partially addressed**: `AgentConfig.fallback_models`
  now lets a Gemini agent fall through a chain of alternate models when
  its primary is rate-limited (`app/llm_call_logging.py`), pre-filtered by
  a local best-effort quota tracker seeded with the user's own AI Studio
  dashboard numbers (`app/providers/gemini_quota.py`) — the 7 seeded LLM
  agents ship with a 9-model fallback chain. Still no sequential-mode
  orchestration fallback (only per-agent model fallback); that remains
  future work if the fallback chain alone proves insufficient under load.
- **Voice narration (Strategy Lenses, Hero demo, dashboard signal ticker)
  is live and working, now on ElevenLabs as the primary provider**
  (`ELEVENLABS_API_KEY`), with Hugging Face/Kokoro-82M as the fallback.
  This order flipped from an earlier Kokoro-primary version after the
  free HF tier's account-level credit quota was exhausted three times
  across two different keys during real verification (confirmed each
  time via a live `402` — not a code bug). `/api/tts` now takes two
  separate voice ids per call (`elevenlabs_voice_id`, `kokoro_voice_id`)
  since the two providers use entirely different id namespaces — all 8
  Strategy Lens personas were assigned real ElevenLabs voice ids fetched
  live from `GET /v2/voices` with a real key (`lensData.ts`), not
  guessed. `generate_speech()` confirmed live end-to-end (real MP3 bytes
  back from ElevenLabs, 2026-09-04).
- **Mobile/cross-browser audio playback hardened**: `useLensVoice.ts` now
  reuses one persistent `<audio>` element (synchronously primed on the
  first real user click) instead of a fresh `new Audio()` per call — the
  standard fix for mobile Safari/WebKit's autoplay policy, which blocks
  `.play()` unless it's directly attributable to a user gesture and an
  `await fetch(...)` before playback (as this feature's async TTS fetch
  requires) breaks that attribution on a freshly-created element. Applied
  at every real click site (voice toggle, per-row speak buttons, Hero's
  Listen button, Strategy Lenses' card/arrow navigation). Not verified on
  a real iOS device from this environment — the fix follows the
  widely-documented pattern, but hasn't been confirmed hands-on.
- **A6 Audit Activity feed is currently mockup copy**, not a real running
  check — Phase 7 makes it real.
- **Live trading data is point-in-time** until the daily cron job's next
  run (`0 22 * * 1-5` UTC on the VM) — see `docs/DEPLOY_GCP.md` §6b.

## Real bugs found and fixed this session (worth knowing for future debugging)

1. **CORS only ever allowed `localhost:3000`** — blocked every real browser
   login on the deployed site since the first deployment; every `curl`-based
   "verified live" check missed it because curl ignores CORS. Fixed via
   `CORS_ALLOWED_ORIGINS` env var.
2. **Gemini API key leaking into error messages** — found during the Phase 6
   secrets audit, before it ever shipped.
3. **Frontend Dockerfile assumed a `public/` dir existed** — first VM deploy
   failed on it; the directory was empty/never created.
4. **Gemini model name churn** — `gemini-2.0-flash` → `gemini-2.5-flash` (also
   retired) → now on the `gemini-flash-latest` alias to resist future churn.
5. **Gemini "thinking" tokens silently consuming `maxOutputTokens`** — up to
   517 of a 600-token budget spent on invisible reasoning, truncating the
   visible answer mid-sentence. Fixed with `thinkingConfig.thinkingBudget=0`.
6. **Retry-with-backoff getting killed by the outer per-call timeout** — a
   429 retry's own backoff exceeded the 30s timeout wrapping it, converting
   a recoverable error into an unrecoverable one. Fixed by widening the
   timeout budget consistently (provider timeout, launch stagger,
   orchestration limits) instead of just adding a retry in isolation.
7. **Shared circuit-breaker cascading failures** — `get_provider()` caches
   one singleton per provider name, so 3 independent agents' legitimate
   rate-limit failures tripped a breaker that then blocked every *other*
   agent's attempt too. Fixed by raising `failure_threshold` to tolerate a
   burst across multiple agents sharing one instance.

## Phase 11 — Strategy Lenses + Pilot Production landing additions

Sourced from `GlassBox_Pilot_Production.html` (plan/content) and
`GlassBox_Lenses_Interactive.html` (the exact interactive spec — full
persona data, 3D carousel mechanics, animation timings). Landing-page
content, no backend dependency — can be built independently of Phases 7–10.

1. **Strategy Lenses** — 8 investor-archetype cards in a 3D perspective
   carousel: Value (Buffett/Munger), GARP (Lynch), Multi-Strat (Griffin),
   Macro (Dalio), Quant (Simons), Allocation (Englander), Algo (Shaw),
   Reflexive (Soros). Each has a procedurally-generated SVG portrait
   (explicitly NOT a real likeness), a growth/risk bar chart, a typewriter
   "speak" quote in first person, filter chips (All/Value-GARP/Quant/
   Macro/Multi-Strategy), autoplay, drag-to-slide, keyboard nav.
   **The mandatory legal disclaimer** ("original AI archetypes... NOT
   affiliated with, endorsed by, or representing any named investor,"
   portraits "original illustrations, not likenesses") ships with this,
   visibly, not buried in a footer.
2. **"ML Provenance" section** — data/model transparency explainer
   (institutional sources / deterministic core / narrative models / audit
   layer).
3. **Sliding agent/lens marquee banner** under the nav.
4. **5-star score-review feedback widget** — "Was this useful?"

**Status: build in progress.**

### Landing-page addendum ("Plan-correction.MD") progress

A follow-up product-direction doc (referred to in commit messages as
`Plan-correction.MD`) split this into workstreams. Note: that file
itself isn't checked into this repo — confirmed by a full home-directory
search — so its content only survives in commit messages/code comments
right now. If it still exists somewhere, worth adding it under `docs/`
so the rationale doesn't rot into "trust the commit log."

- **Workstream A — Done** (commit `0569bb7`, 2026-09-07): Strategy Lens
  completion tracking (`heardLenses`, tracked against the full persona
  set so filtering can't early-trigger it); a one-time "GlassBox finale"
  voice moment (`GUIDE_LANDING_FINALE_MESSAGE`) that hands off from the
  investor lens voices to the GlassBox system voice (River/am_onyx,
  reused from `GuideBubble`, now exported from `lib/glassboxGuide.ts`
  instead of duplicated); a dedicated `ConversionCTA` section
  (`#glassbox-verify`) between the Lens carousel and the rest of the
  landing page, deliberately not claiming a specific free-signal number
  since backend enforcement didn't exist yet at that point; and a
  floating `AgentLauncher` "Ask GlassBox" shell that never fakes command
  execution for logged-out visitors (every submission gets the same
  honest "create an account" response — no intent parsing behind it).
- **Workstream B/C — Not started**: real intent parsing and real
  verification runs from natural language behind `AgentLauncher` (it's
  still just a shell today).
- **Backend-enforced free-tier entitlements — implemented, tested, and
  committed.** This is what Workstream A's "avoid claiming an unenforced
  quota" note was blocking on: `POST /api/me/verify/{ticker}` and
  `GET /api/me/entitlements` (`backend/app/routers/me.py`) give every
  real (non-dev) account 5 free deterministic signal verifications,
  metered on their own `users` row (`verified_signal_count`), 402 once
  exhausted. Surfaced on the dashboard via a new `VerifySignalPanel`.
  Full backend suite (106 tests, including 8 new ones for this) passes,
  and the frontend type-checks clean — verified 2026-09-07. Not yet
  deployed to the VM, and `ConversionCTA`/`AgentLauncher` copy still
  doesn't reference the real "5 free" number.
- **Onboarding "Choose your agent" step — implemented, tested, and
  committed (2026-09-07).** A new step 0 in `OnboardingFlow.tsx`
  (`StepAgent.tsx`) lets the user pick one of 6 onboarding-only agent
  personas (`agentPersonas.ts` — deliberately separate from the 8
  landing-page Strategy Lens personas and from the real
  `/api/me/agent-subscriptions` feature; purely cosmetic, themes the
  wizard's color/voice/copy). Persistent `AgentHero` sidebar card shows
  the chosen agent with an optional "Hear this agent" voice button.
  **Voice-id caveat**: unlike the 8 Strategy Lens voices and the Guide's
  "River" voice (each fetched live from `GET /v2/voices` with a real
  `ELEVENLABS_API_KEY` and confirmed against this account), the 6 new
  agents' `elevenLabsVoiceId`/`kokoroVoiceId` were assigned with no key
  available in this environment — they're long-stable public
  ElevenLabs premade-catalog ids (Antoni, Arnold, Josh, Rachel, Bella,
  Domi), not fetched/confirmed live this session. Verify with a real key
  next time the VM/key is reachable, same bar the rest of the voice
  work holds itself to.

## Phase 12 — Liquid glass, voice captions, dashboard insights (2026-09-08)

Sourced from a design-exploration prototype the user iterated on
separately (`glassbox-onboarding-upgrade(9).html`, a standalone static
mockup in Downloads — never part of this repo, has no deploy path, and
was never connected to the real app). Three pieces ported into the real
codebase, committed locally (not yet pushed/deployed):

1. **Liquid-glass frosted surface** — `.glass-panel-frost` /
   `.glass-frost-surface` in `globals.css` (real `backdrop-filter`,
   re-themed light/dark via dedicated vars, same pattern as the existing
   `--c-glass-nav-bg`). `GlassPanel` gained a `"frost"` variant.
   AgentHero.tsx already had real frosted glass before this; applied now
   to OnboardingFlow.tsx's four card wrappers (intro screen, sidebar
   Guide card, main wizard card, complete screen), which were flat
   `bg-panel` before. **Not yet applied** to dashboard panels generally —
   only the two new ones below use it; retrofitting existing panels
   (PortfolioOverviewPanel, StressTestPanel, etc.) to `variant="frost"`
   is a follow-up, not done this pass.
2. **Live word-by-word captions on the Guide's voice** —
   `useLensVoice.speak()` takes an optional `onProgress(fraction)`,
   wired to the shared `<audio>` element's real `timeupdate` event
   (genuine playback position, not a guessed timer). `GuideBubble`
   highlights words in sequence, weighted by character length against
   the real elapsed fraction. Does **not** change the deliberate
   "never autoplay" behavior — captions only run inside an already
   explicit `speak()` call from a real click, same as before.
3. **Dashboard: sector-allocation donut + Insights & Alert Signals
   panel** — both real, no new backend endpoint. The donut aggregates
   the same real `holdings[].sector`/`weight` fields
   PortfolioOverviewPanel already tables, re-fetching `/api/holdings`
   client-side with the auth token so it personalizes the same way that
   panel does (a first version of this that only used the server-fetched
   default would have quietly diverged from it for logged-in users with
   a watchlist — caught and fixed before committing). The insights panel
   derives alert-worthy rows from the same live-signals feed
   `SignalTicker` already renders (rsi/ma_cross/volume_ratio/confidence),
   applying standard technical thresholds (RSI 75/25, MA-cross flips,
   ≥1.8x volume, ≥70% confidence) — one insight per symbol, first
   matching rule wins, explicitly labeled as derived from the live
   signal feed and **not** a claim about the real A6 Audit feed (which
   remains its own, still-mockup thing, unaffected by this).

**Verified:** `npm run build` compiles clean (type-check + lint pass,
zero errors). Backend's existing 106 pytest tests still pass (no
backend files touched this pass). Local dev server (frontend :3000 +
backend :8000, backend run against a fresh local SQLite, not Neon)
served both `/onboarding` and `/dashboard` with 200s and no server-side
exceptions logged. **Not verified:** an actual authenticated-browser
visual check (glass blur rendering as intended, caption sync feeling
right against real ElevenLabs audio, donut/insights panel layout) —
every `(app)` route sits behind `AppShell`'s client-only auth `loading`
gate (token lives in `localStorage`, structurally unreachable from a
plain `curl` request, confirmed by reading `lib/auth.tsx`), so this
needs a real logged-in browser session next time one's available in the
environment. Also not done: pushing to `origin`, touching
`docker-compose.yml`/`deploy/Caddyfile`, or deploying to the VM — local
commits on `main` only, by design for this pass.

## Phase 13 — Portfolio growth/stats panels, voice + layout fixes (2026-09-11)

Three commits, pushed to `origin/main` this session (bundled with
Phase 12's own commits — the liquid-glass surface, captions, and the
sector-allocation donut/insights panel — which had been sitting local
since 2026-09-08). Not yet deployed to the VM as of this writing.

1. **`PortfolioGrowthPanel`** — timeframe-toggled (7D/30D/90D/ALL) chart
   over the real `/api/data` series; ranges longer than the on-disk
   sample are disabled and clearly marked rather than silently
   truncated.
2. **`StatsBoard`** — surfaces the already-computed but previously
   unused `/api/daily-summary` risk/return metrics (Sharpe, max
   drawdown, win rate) plus new real P&L/turnover numbers from a new
   `GET /api/portfolio-stats` (`data_source.get_portfolio_stats`): FIFO
   realized-P&L matching and unrealized P&L from live prices, ported
   from `backend-source/DAILY_PNL.py`'s `DailyPnLTracker` rather than
   reimplemented. `has_trade_history` distinguishes a real zero from
   "no trades recorded yet" so an empty `portfolio.json`/`trades.json`
   renders an honest empty state instead of misleading zeros.
3. **`MissedOpportunitiesPanel`** — derives "strong signal, no matching
   trade" candidates client-side (same pattern `InsightsAlertsPanel`
   already uses), with an admin-only "Generate AI take" action hitting
   a new `POST /api/insights/narrate` background job (mirrors
   `reports.py`'s `generate_report` machinery: `complete_with_logging`,
   audit log, WS/poll status) that narrates the candidates it's handed
   rather than re-deriving its own definition server-side.
4. Two bugfixes riding along: `useLensVoice`'s `<audio>` element was
   per-hook-instance, so `GuideBubble` and `AgentHero` (both mounted at
   once in the onboarding sidebar) could genuinely play two voices
   concurrently — moved to module-level shared state so starting
   playback anywhere pauses whatever else was playing. And the
   onboarding sidebar's Guide bubble was clipping text mid-word because
   `min-w-0` was missing through the flex chain in the fixed-220px
   column — added `min-w-0`/`break-words`/`flex-wrap` through it.

**Verified:** `tsc --noEmit` clean, all 106 existing backend pytest
tests still pass, and a live logged-in dashboard screenshot confirmed
every new panel renders against real data with no console errors. This
also stands in for Phase 12's previously-outstanding authenticated-
browser check (donut/insights panel, liquid-glass surface) since
they're on the same dashboard page — captions weren't specifically
re-checked this pass.

## Phase 13b — Onboarding wizard fixes (2026-09-11)

A follow-up bug report against the onboarding wizard (`/onboarding`,
"Step 1 of 5" screen) listed six issues. Checked each against the real
running app (backend :8000 + frontend :3000, logged in as `user`) via
Playwright screenshots before touching anything, since two were
already fixed by Phase 13's `3f30b90`/`c022e17`:

- Guide copilot card clipped / audio button truncated / text
  overflowing the main panel — **already fixed**, no reproduction at
  1400x900 or 400x900.
- Left sidebar cards overlapping the main panel — **already fixed**,
  same screenshots.
- Wizard Back/Continue navigation — **already present**
  (`OnboardingFlow.tsx`'s Cancel/Back + Continue/Finish footer).
- Stepper filled progress + inactive-label contrast — **real, fixed**:
  the current-step segment was only 35%-opacity teal and inactive
  labels used `--c-t4` (`#98a6c0` on white in light theme, barely
  legible) — `StepIndicator.tsx` now fills every segment through the
  current step solid teal and raises inactive labels to `--c-t3`.
- Main panel scroll / Risk meter cut off at the bottom — **real,
  fixed and reproduced first**: at a real 760px-tall viewport the step
  card had no height bound, so the Risk meter and the Back/Continue
  footer ran under the fold with the page's own un-cued scroll as the
  only way to reach them (`scrollHeight` 993 vs `clientHeight` 760).
  `OnboardingFlow.tsx`'s card is now capped at `calc(100vh-180px)`
  with its content independently scrollable and the nav footer pinned
  outside that scroll region — footer always reachable, rest scrolls
  into view.
- Agent carousel/pagination — **real, fixed and reproduced first**: 6
  agent cards don't all fit below ~1000px wide (reproduced at 400px
  and 900px — two of six scrolled out of view with zero affordance
  that more existed). `StepAgent.tsx` gained prev/next paging buttons
  over the existing scroll rail, shown/hidden off the rail's real
  `scrollLeft`/`scrollWidth`.

**Verified:** `tsc --noEmit` clean. Playwright screenshots + scroll-state
checks at 1400x900, 1400x760, and 400x900 confirm no clipping/overlap,
the Risk bar and footer both reachable at the short viewport, and the
paging arrows correctly reveal the two hidden agents with zero console
errors along the way.

## Phase 14 — Aria onboarding revert + dashboard liquid-glass charts (2026-09-11)

Two independent bug reports, both against the live app, addressed in
one pass:

**Onboarding: reverted to a single Aria hero, 4 steps.** The 6-agent
picker step (Allocation/Value/Quant/Macro/Reflexive/GlassBox, built in
an earlier phase) plus the separate "GlassBox Guide" copilot card next
to it were the actual bug the report was describing: one guide persona
shown twice, once generically and once "in character." Cross-checked
against the user's own reference mockup
(`glassbox-onboarding-upgrade(9).html` in Downloads), which has exactly
this shape already. Deleted `StepAgent.tsx`/`AgentHero.tsx`/
`AgentAvatar.tsx`/`agentPersonas.ts` (confirmed nothing outside
onboarding imported them first), added `AriaHero.tsx` as the one
consolidated hero card, trimmed the flow to 4 steps (Concern → Portfolio
→ Verify → Alerts), and renamed `GLASSBOX_GUIDE.name` "GlassBox Guide" →
"Aria" (propagates everywhere via the constant). Footer nav fixed:
Continue is `ml-auto` + `min-w-[170px]`, not full-width, so Back no
longer reads as stranded at the far edge.

**Dashboard: Robinhood-style growth chart + liquid glass everywhere.**
`PortfolioGrowthPanel` now renders a smoothed (Catmull-Rom, still every
real data point) gradient-fill area chart colored by real direction,
with a hover crosshair. `StatsBoard` tiles gained real direction arrows
and ring gauges for Win Rate/Churn Rate (fed from each metric's own
real scalar — no fabricated sparkline history for point-in-time
metrics that don't have any). Every remaining dashboard panel
(`AgentPerformancePanel`, `PortfolioOverviewPanel`, `StressTestPanel`,
`TrackComparisonPanel`, `VerifySignalPanel`) switched from the flat
`accent` variant to `frost`, so the whole dashboard now shares one
consistent glass treatment instead of about half of it.

**Verified:** `tsc --noEmit` and `next build` both clean. Playwright
through the full onboarding flow (1400×900 and 420×900) and a full
dashboard screenshot, logged in as `user` — no console errors beyond
the pre-existing, unrelated data-theme hydration warning. **Not yet
verified:** an actual VM deploy of this phase.

**Found but not fixed (pre-existing, out of scope):**
`StepPortfolio.tsx`'s "Connect portfolio" tab nests an `ExplainTooltip`
button inside a `<button>` — a real nested-interactive-element
hydration warning, unrelated to either change above. Flagging for a
future pass.

## Post-Phase-14 fix — voice narration cache bug (2026-09-11)

User report: navigating onboarding steps didn't stop/refresh narration
correctly -- audio from a previous step kept playing (or replaying)
against the wrong screen. Root cause found by instrumenting real
`/api/tts` calls, not guessed: `useLensVoice.speak()`'s cache was keyed
by `personaId` alone. Aria narrates a different message every step
under that one same id, so after step 1's line was cached, every later
step silently replayed step 1's audio with zero new network requests
-- captions/on-screen text moved on, the sound never did. Fixed by
keying the cache `${personaId}::${text}` and having `stop()` also bump
the request-id guard (covers a fetch still in flight when stop() is
called with nothing new queued). Verified: an instrumented run through
4 real step transitions showed exactly 1 `/api/tts` request before the
fix vs. 4 correct ones after. Deployed.

## New requests to track, not yet scoped (2026-09-11)

Bundled together in one message; none of this is started. Listed here
so it isn't lost, per the user's own ask to track rather than rush it:

- **Aria's avatar** -- currently the same plain checkmark badge used
  for the small nav-icon Guide avatar everywhere else. User wants
  something more expressive/animated ("Pixar-style" character), shared
  via low-res Google Images search-result thumbnails (not usable
  directly as a real asset -- provenance/licensing/resolution all
  wrong for a production app) -- needs a real illustrated/animated
  asset sourced or commissioned properly, not scraped.
- **"Meet the team" entry point** on the home/dashboard screen, tied to
  an animated character, redirecting into the marketing landing page's
  existing Strategy-Lens-carousel flow.
- **Lip-sync / more realistic voice-driven animation** for Aria while
  she's speaking (today: word-by-word text caption highlighting only,
  no visual mouth/face animation).
- **A small HTML or Figma prototype** of the above, for review before
  it's built into the real app -- user's own explicit ask, so this
  should be the actual first deliverable for this bucket, not a full
  implementation.
- **Bigger animated GB logo** on the marketing landing page, placed
  between the "See the data. Invest smarter." tagline and the
  "Live verification / A6 Auditor active" stat panel -- "fun Pixar
  style" animation of the GlassBox mark specifically (separate from
  the Aria-character ask above).
- **Notification panel** -- flagged as entirely missing; not yet
  scoped (which events, where it lives, badge/count behavior all TBD).
- **Mobile compatibility** -- flagged as a "major problem," open on a
  real mobile device rather than a resized desktop browser (Playwright
  viewport tests at 400-420px width across onboarding/dashboard this
  session showed no breakage, so this needs to be characterized on an
  actual phone before it can be diagnosed) -- user marked this as
  priority-before-more-design-work.

## Task list

- [ ] **New, flagged priority:** Characterize the real mobile-compat
      bug (device/browser, which page, what actually happens) before
      attempting a fix -- viewport-resize testing hasn't reproduced
      anything so far, so this needs a real device or its exact repro.
- [ ] **New:** Build a small HTML/Figma prototype for Aria's
      avatar/animation + landing-page "meet the team" flow + bigger
      animated logo placement, for review before real implementation.
- [ ] **New:** Scope and build a notification panel (nothing decided
      yet -- events, placement, badge behavior).
- [x] Deploy Phase 14 to the VM — same `git archive` + `gcloud compute
      scp` convention, this time with the VM's tracked directories
      cleared before extraction (plain tar-over-existing doesn't
      remove files a commit deleted, e.g. the retired agent-picker
      components) so the VM matches the repo exactly. Both containers
      up clean, `/health`, `/onboarding`, and `/dashboard` all 200 on
      the live domain post-deploy.
- [ ] **New:** Fix `StepPortfolio.tsx`'s nested button
      (`ExplainTooltip` inside the "Connect portfolio" tab) — real
      hydration warning, found during Phase 14's verification, not
      part of either change in that phase.
- [x] Retrofit the remaining dashboard panels to `GlassPanel
      variant="frost"` (done in Phase 14).
- [x] Push Phase 12 + 13's commits (done this session).
- [x] Deploy Phase 12/13/13b to the VM — `git archive` tarball
      (deploy convention this repo actually uses; `.env` preserved,
      not overwritten) shipped via `gcloud compute scp`, extracted
      over `~/glassbox`, `docker compose up -d --build`. Both
      containers came up clean (`docker compose ps`/logs show no
      errors) and `https://glassbox-portfolio-review.duckdns.org/health`
      returns `{"status":"ok"}` post-deploy.
- [ ] Deploy the free-tier entitlements/verify-signal feature (committed
      2026-09-07, not yet deployed to the VM), then update
      `ConversionCTA`/`AgentLauncher` copy to reference the real "5 free"
      quota.
- [ ] Decide: build Phase 7 (Stock Analysis + real A6 audit) next?
- [ ] Decide: sequential-mode fallback for LLM committee runs (works around
      the Gemini RPM ceiling without needing a paid tier)?
- [ ] Decide: news API provider for Phase 9, once reached.
- [x] Real user auth (replace hardcoded dev accounts) — done, see "Security & cost hardening".
- [ ] Consider pushing the `glassbox` repo's visibility/CI setup if the
      project moves toward a team rather than solo-dev workflow.

## Security & cost hardening (2026-09-19)

Backend pass aimed at "safe to demo publicly and cheap to run". Everything
below is free/open-source -- no new paid services, no new containers.

**Auth**
- Removed the hardcoded `admin`/`admin` and `user`/`user` logins. Admin is now
  `admin` + a password supplied only via env (`GLASSBOX_ADMIN_PASSWORD_HASH`
  bcrypt, preferred, or `GLASSBOX_ADMIN_PASSWORD` >= 12 chars). Unset = no admin.
  Dev logins exist only with `GLASSBOX_ENABLE_DEV_USERS=1` and never in production.
- `GLASSBOX_ENV=production` (set in docker-compose.yml) makes the backend refuse
  to boot with a missing/default `GLASSBOX_JWT_SECRET`.
- JWT: `python-jose` (open CVEs) replaced by **PyJWT**; algorithm pinned, `exp` +
  `sub` required, malformed role claims are 401 not 500, tokens carry `iat`.
- Passwords: min 10 chars, max 72 bytes (bcrypt truncates silently), common-
  password and password==username rejected. bcrypt runs in a threadpool.
- Login: unknown-user and wrong-password take the same time; per-IP limit plus a
  per-account failed-attempt lockout (20 / 15 min, temporary).

**Rate limiting** -- the old limiter only ever saw Caddy's IP, so all visitors shared
one bucket. The Dockerfile now trusts Caddy's X-Forwarded-For
(`--forwarded-allow-ips`; port 8000 must stay unpublished). Added limits for
/api/tts (cache misses only), /api/monte-carlo, per-user report runs
(6/hour) and verify; the limiter's memory is bounded.

**Cost control** -- /api/tts audio is cached (memory + `/data/tts-cache` on the
existing volume) and concurrent identical requests share one provider call;
ElevenLabs is skipped after `TTS_DAILY_CHAR_BUDGET` chars/day. Provider failures
are now logged (status + error code only) and each response carries an
`X-TTS-Provider: cache|elevenlabs|kokoro` header. `/api/monte-carlo` is bounded
and vectorized (~100x faster).

**Dependencies** -- fastapi 0.115 -> 0.141 (starlette 0.38 -> 1.6), pyarrow, yfinance /
curl_cffi, pydantic, uvicorn upgraded and pinned; `pip-audit` reports no known
vulnerabilities (was ~30). CI (`.github/workflows/backend.yml`) runs tests +
pip-audit; Dependabot watches pip/npm/docker/actions.

**Edge** -- Caddy adds HSTS, nosniff, frame-deny, referrer/permissions policies, a
1 MB body cap, and hides the Server header. CORS methods/headers are allow-listed;
/auth responses are `no-store`; the signals websocket is capped at 300 connections.

**Deliberately NOT done yet** (each needs a decision or a testable environment):
- Content-Security-Policy: needs nonce support in the Next.js frontend first.
- Running the backend container as non-root: needs the `glassbox-db` volume and
  `./trading-storage` bind mount re-owned, and the daily-sync cron re-tested.
- `uvicorn.workers` is deprecated upstream (works in the pinned uvicorn); move to
  the `uvicorn-worker` package before unpinning uvicorn.
- `GET /api/reports/narratives/{id}` is still public (UUID-guarded) -- decide
  whether shared report links are intended.
- Redis-backed rate limits (only needed once there is more than one VM).

## Phase 1 -- paper trading, backtests and the admin master view (2026-09-19)

**Deployed 2026-09-20** (commit 8d74a82): bootstrapped on the VM (27 accounts, live tracking from 2026-09-19) and the daily cron added (`15 22 * * 1-5`, after the data sync). The first live day and the first 11 reports arrive with Monday 2026-09-21's run.

**What exists now.** The quant engine's BUY/SELL/HOLD signals drive simulated
portfolios so the strategy can be measured. Nothing places real orders.

- `app/paper.py` -- the engine (no DB, no network). Orders decided at day D's
  close fill at D+1's close (no look-ahead), 5 bps costs, long-only, no leverage.
  Strategies: `engine_tilt` (target weight = invested x strategic weight x the
  engine's own 1.5x / 1.0x / 0.5x suggested-weight tilt; SELL raises cash),
  `static_rebalanced` (same weights and rebalancing, signals ignored -- each
  profile's benchmark, so alpha = what the signals added), `static_hold`,
  `random_tilt` (a placebo: each symbol acts on ANOTHER symbol's real signal
  history) and `cash`. Days before `live_from` are tagged **backtest**
  (in-sample: the trained params were fitted on this same history); days after
  are **live** (genuine out-of-sample).
- `app/paper_profiles.py` -- the 11-profile cohort (growth, income, index,
  financials, diversified, 60/40, all-weather, quality, momentum, cyclical,
  capital preservation). Every profile gets an account + benchmark **without
  needing a login**; the demo logins (`seed_demo_users`) are optional.
- `app/paper_cycle.py` + `python -m app.scripts.run_paper_cycle` -- the daily
  cycle. `--bootstrap` (once) creates 27 accounts (11 profiles, 11 benchmarks,
  5 controls: SPY, equal-weight, engine-on-all, placebo, cash) and backfills from
  2021-01-04 (includes the 2022 bear market); the daily run replays new days,
  stores the day's signals and writes one report per profile (provider
  `system`) so **Admin -> Reports is no longer empty**. Idempotent.
- Admin: **Admin -> Paper Trading** (leaderboard, equity curve vs benchmark,
  holdings, trades, signal scorecard, "run now"). API: `/api/admin/paper/*`.
- Cron (add after the data sync; see docs/DEPLOY_GCP.md 6b):
  `15 22 * * 1-5 cd ~/glassbox && docker compose exec -T backend python -m app.scripts.run_paper_cycle >> logs/paper_cycle.log 2>&1`

**Gemini reliability (why 40 of 46 LLM calls failed).** 21x 429 (the free tier is
5 req/min and only 20/day on flash models), 14x 404 (invented model ids in the
fallback chain), 4x 503. Now: a 404 is remembered for 24h and never retried;
the fallback chain is narrowed to models the key's own ListModels offers
(fail-open); diagnostics at `GET /api/admin/providers/gemini/models`. The daily
paper cycle does NOT depend on any LLM -- reports are factual templates; an
optional AI note is off unless `PAPER_LLM_NARRATIVES=1`. Free-tier quota itself
is unchanged: LLM agents still get 20 flash calls/day; enable billing to lift it.

**First findings (real data, 2021-01-04 to 2026-09-18, in-sample -- read with care).**
- The SELL signal is counter-productive: prices after a SELL rose *more* than
  average (5-day edge -0.46 pts). BUY has a real edge (+0.78 pts at 5 days, 63% hit rate).
- Engine on all 15 symbols: +133% vs +124% for the placebo, +120% SPY, +213%
  equal-weight buy-and-hold. The engine holds ~20% cash in a bull market.
- Per-profile alpha vs policy benchmark ranges from -7.1% (growth) to +14.5% (quality).
These are the targets for Phase 3 (re-weighting, challenger orchestrations).

**Not built yet:** Phase 2 (richer admin dashboard: attribution, calibration,
drawdown views), Phase 3 (shadow challengers, proposals queue, re-weighting),
per-agent recommendation logging for the LLM committee, per-user paper portfolios
for real customers.

## LLM failover routing (2026-09-20)

Billing is not enabled on the Gemini key, whose free tier is ~20 requests/day on
flash models -- so the Investment Committee could never finish. Requests now fail
over instead of stalling (full guide: docs/FREE_LLM_ROUTING.md).

- `app/providers/openai_compat.py` -- one class for every OpenAI-compatible host:
  OpenRouter (free `:free` models + the `openrouter/free` auto-router, discovered
  live), Groq, Cerebras, GitHub Models, Qwen (DashScope), DeepSeek, xAI Grok and a
  custom `gateway` slot (OmniRoute / LiteLLM / vLLM ...). Errors carry only the
  provider name + HTTP status, never a key, URL, prompt or response body.
- `app/llm_router.py` -- `complete_routed()`: the requested provider first, then a
  failover order; a quota error puts a provider to rest (~1h for a per-day limit)
  so it is not hammered; failover targets get their own model ids; total time
  budget; if nothing else is usable the original error is raised unchanged.
- Wired into agent runs, report/insight narration and the daily paper-report note.
  Agent results record the provider that really answered (`failed_over_from`).
- Admin -> Observability: routing table + "Test failover"; `/api/admin/providers/routing[/test]`.
- **A provider with no key is skipped -- nothing changes until a key is added.**
- Privacy: failover providers see the prompt; `LLM_FAILOVER_USER_RUNS=0` keeps
  end-user runs off third parties.

## CI-built images and pull-based deploys (2026-09-20)

Images are built and tested in GitHub Actions (`.github/workflows/images.yml`), pushed to Google
Artifact Registry with keyless Workload Identity auth, and pulled on the VM by
`deploy/deploy.sh <tag>` (health-checked, auto-rollback). The VM no longer builds anything.
Backend image is now multi-stage (no compiler at runtime). Compose gained healthchecks,
memory limits and log rotation. Guide: docs/DEPLOY_IMAGES.md.
