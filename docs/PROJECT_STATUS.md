# GlassBox — Project Status & Task Tracker

Living document. Update this whenever a phase completes, a bug is found,
or scope changes — this is the single place to check "where are we" and
"what's next" without re-deriving it from chat history.

**Last updated:** 2026-09-04

## Live deployment

| | |
|---|---|
| App | https://glassbox-portfolio-review.duckdns.org |
| API | same domain, path-routed (`/api/*`, `/auth/*`, `/health`, `/ws/*` -- see `deploy/Caddyfile`) |
| Database | Neon Postgres (`console.neon.tech`, org `spring-hill-60129601`, `neondb` / `production` branch) |
| Source | `github.com/Shreyasg13/glassbox` (private, `main` branch) |
| Host | GCP VM `instance-20260902-033025`, project `project-f015cf71-9e01-4a2a-8f5`, zone `us-central1-a` |
| Admin login | `admin` / `admin` (still hardcoded — real signup exists now, but self-serve accounts can never be admin) |
| Dev viewer login | `user` / `user` (still hardcoded, unchanged) |
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
here. None started yet -- this is the prioritization list, not a
progress log. Update each row's status as work begins/lands.

| # | What | Current state (verified) | What it needs | Status |
|---|---|---|---|---|
| 1 | **Real agent performance/"journey" stats** -- which agents' signals were actually right, per user, over time | `/api/agent-performance` exists but returns `ds.AGENT_PERFORMANCE`, a **hardcoded 3-agent mock** (`data_source.py`) -- not derived from any real data. The real signal (agent calls, cost, latency, outcomes) already exists in `llm_calls`/`audit_log` (Neon) via Phase 6's observability work | Overlaps directly with **Phase 8** (`PHASE_7_10_AUDIT_KNOWLEDGE_PLAN.md`) -- read that plan before starting this so the two don't diverge | 📋 Planned |
| 2 | **Per-user agent subscription** -- user picks which agents run their reports; only subscribed agents run | Does not exist. Every orchestration currently runs its full fixed agent list for everyone | New `user_agent_subscriptions` table/column, an admin+user-facing UI, and an `orchestration.py` filter respecting it | 📋 Planned |
| 3 | **13F institutional filing data** | **Does not exist anywhere in this codebase** -- confirmed by a full-repo search, zero real matches | SEC EDGAR publishes 13F filings via a free public API (no key needed) -- feasible without a paid data vendor, but is a real new ETL pipeline (quarterly filings, CIK-to-ticker mapping, storage schema) | 📋 Planned, not started |
| 4 | **Simulated test-user cohort** (5 users w/ sessions, for QA/demo) | Does not exist. `/auth/signup` can create real accounts, but nothing seeds a cohort with distinct portfolios/agent activity to observe | A seed script (`app/scripts/`, same pattern as `seed_agents.py`) creating 5 accounts + distinct holdings, so dashboard/agent behavior can be eyeballed per simulated user | 📋 Planned |
| 5 | **Real broker portfolio import** (Robinhood, Schwab, etc.) | The broker-connect icons on the marketing/onboarding UI are illustrative only -- no real OAuth/import wired to any broker. Notably, `Pricing.tsx`'s own copy already promises **"Broker import via SnapTrade"** on the Standard tier -- SnapTrade is a broker-aggregator API built for exactly this (one integration covers many brokers) rather than building Robinhood/Schwab/etc. individually. Robinhood has no official public API at all (unofficial/reverse-engineered access is ToS-risk territory); Schwab has a real developer API but requires app approval | A SnapTrade (or equivalent aggregator) developer account + API key -- external signup, same pattern as DuckDNS/Neon/Google OAuth this session | 📋 Planned, blocked on account creation |
| 6 | **Expose already-built API endpoints with zero UI** | `/api/track1/agents`, `/api/track2/agents`, `/api/monte-carlo` all exist, work, and have **no frontend consumer anywhere** (confirmed: zero matches in `frontend/`) | Smallest, cheapest item on this list -- just UI work against endpoints that already exist and work | 📋 Planned, quick win |

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
  original `admin`/`admin` hardcoded dev account is kept unconditionally
  (every deployment doc points people at it) rather than replaced.
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

## Task list

- [ ] Decide: build Phase 7 (Stock Analysis + real A6 audit) next?
- [ ] Decide: sequential-mode fallback for LLM committee runs (works around
      the Gemini RPM ceiling without needing a paid tier)?
- [ ] Decide: news API provider for Phase 9, once reached.
- [ ] Real user auth (replace hardcoded dev accounts) — no phase assigned yet,
      raise if this becomes a priority before a public launch.
- [ ] Consider pushing the `glassbox` repo's visibility/CI setup if the
      project moves toward a team rather than solo-dev workflow.
