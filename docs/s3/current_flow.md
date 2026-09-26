# Current flow: one ticker, from data sync to a user's screen (T0)

Traced from the real run `2026-09-25:V` (Visa), saved in [committee_output_example.json](committee_output_example.json). File and function
names are exact as of commit `29fbc81`.

## 1. The daily pipeline (VM cron, weekdays 20:35 and 23:45 UTC)

`python -m app.scripts.run_daily_pipeline` -> `pipeline.run` builds the stages in `pipeline.default_stages` and runs them in
`pipeline.STAGE_ORDER`:

| # | Stage | What it does for V | Code |
|---|---|---|---|
| 0 | price sync | Fetches V's daily bars and appends them to the price table; refuses to accept a day with too little coverage | `pipeline.default_sync` -> `scripts/update_daily_data.update_symbol` -> `price_store` |
| 1 | `free_data` | Refreshes SEC fundamentals, 8-K events, Form 4 insider trades, Treasury and BLS macro into a file cache | `free_data.refresh_all` |
| 2 | `committee` | Picks the day's stocks, builds a text context per stock, runs the committee, stores the run | `scripts/run_committee_daily.main` -> `committee_daily.run_daily` |
| 3 | `paper_cycle` | Advances every paper account one day; committee accounts follow the committee's call | `scripts/run_paper_cycle.main` -> `paper_cycle.run_cycle` |
| 4 | `weekly_research` | Fridays: the evidence-gate digest | `research.py` |
| 5 | `snapshot` | Stores what the system BELIEVED that day (signals, risk, committee call) | `snapshots.take` |
| 6 | `mirror` | Copies small disk files into the DB so a rebuilt VM restores them | `artifacts.mirror` |
| 7 | `notifications` | Writes each user's in-app inbox entries | `notifications.generate_daily` |
| 8 | `digest_email` | Emails the ADMIN digest | `digest.run` |
| 9 | `user_digests` | Emails opted-in, confirmed users | `user_digest.run` |

## 2. Inside the committee stage (where the numbers become words)

1. `committee_daily.select_candidates` chooses V ("largest 5-day mover").
2. `committee_daily.build_context` writes a plain-text **context** for V. THIS is where numbers enter the LLM's world: last price,
   RSI, moving-average cross, backtest Sharpe, 1/5/20-day moves, drawdown, risk score, SEC fundamentals, macro line. They are
   formatted into prose, not passed as structured fields, and no snapshot id or source path travels with them.
3. `committee_graph.run_committee_graph` (LangGraph) runs 10 members: 3 deterministic engine members and 7 LLM analysts
   (`_run_analyst`, through `llm_router.complete_routed`, format set by `FORMAT_INSTRUCTIONS`). Each LLM analyst returns a lean
   (BUY/SELL/HOLD), a risk level and a free-text `summary`.
4. `committee_daily.ceo_brief` is DETERMINISTIC: it weights the votes and writes the `ceo.headline`
   ("HOLD - strong consensus (100% of the vote weight); ..."). No LLM writes the headline.
5. `risk.risk_at` is computed BEFORE the committee and fed into the context and the vote. It is not an independent check afterwards.
6. `committee_daily._run_doc` assembles the run document; `db.save_committee_run` stores it (table `committee_runs`);
   `committee_daily._write_report` writes a daily committee report into `report_narratives`.

So the free LLM prose that exists today is the `agents[].summary` text of the seven analysts, plus optional LLM notes in paper reports.

## 3. Every place system-generated text leaves the system (output channels)

| # | Channel | Who can read it | Code | Contains LLM prose? |
|---|---|---|---|---|
| 1 | Report narratives API: **list** | admin | `routers/reports.py` `GET /api/reports/narratives` | depends on report |
| 2 | Report narratives API: **fetch by id** | anyone holding the id (public by design; ids are random UUIDs) | `routers/reports.py` `GET /api/reports/narratives/{id}` | depends on report |
| 3 | `/reports` and `/reports/[id]` pages | public | `frontend/app/(app)/reports/` | depends on report |
| 4 | Daily committee report | via 1-3 | `committee_daily._write_report` | deterministic headlines; analyst text may be quoted |
| 5 | Per-profile paper-trading reports | via 1-3 and the inbox | `paper_cycle._write_reports` | deterministic; optional LLM "analyst note" when `PAPER_LLM_NARRATIVES=1` |
| 6 | Weekly research digest | via 1-3 | `research.py` | deterministic |
| 7 | Admin-triggered orchestration report | via 1-3 | `routers/reports.py` `POST /api/reports/generate` | **yes** |
| 8 | **User-triggered report ("run my report")** | the user | `routers/me.py` `POST /api/me/run-report` -> `orchestration.run_orchestration` | **yes, free-form** |
| 9 | Admin digest email | admin | `digest.py` | no |
| 10 | Per-user digest emails | opted-in users | `user_digest.py` (`render_html`) | no (stance + `ceo.headline`) |
| 11 | In-app inbox | the user | `notifications.py` | no |
| 12 | Portfolio assistant answers | the user | `assistant.py`, `routers/inbox.py` `POST /api/me/ask` | **yes, free-form** |
| 13 | Stance, portfolio and signals APIs and pages | the user | `strategy.stance`, `portfolio_view`, `assistant.signals_on` | no |
| 14 | Track record | the user | `strategy.track_record`, `frontend/app/(app)/track-record` | no |
| 15 | Admin committee "Ask" sandbox | admin | `committee_daily.run_ask` | yes |
| 16 | **Speech** | anyone | `routers/tts.py` `POST /api/tts` | **synthesises ANY text the browser sends** |

Channels 12 (assistant), 10, 11 and 8 were built or found after the architecture diagram and are not named in the plan.

## 4. Things that surprised me

1. **Report fetch-by-id is public by design** (the code says "No auth required per contract" and `AppShell` marks `/reports` "intentionally public"). Ids are random UUIDs, so they cannot be guessed and the list endpoint needs a login. What is missing is an **approved-only check**: once quarantine exists, a quarantined report must still return 404 by id. That is T5/T6 work, not a pre-fix.
2. **`POST /api/tts` speaks arbitrary text.** The plan says speech must use gated text only, but the server cannot tell gated text from
   anything else, because the browser sends the text. It is already rate-limited and budget-capped, so the risk is misuse of voice credits, not data. Making speech gate-only needs a server-side change (speak by content id), not just a flag.
3. **The committee never passes structured numbers.** T3 is bigger than "change the final node": the numbers reach analysts only inside a
   prose context, so `source_snapshot_id` and `source_path` do not exist anywhere yet and T10 must come first.
4. **`research.py` is the evidence gate, not a research module.** The diagram's two `research.py` boxes are one file here.
5. **`snapshots.py` already exists** and means something different: daily records of the system's beliefs. The plan's `snapshots`
   (point-in-time SOURCE data) needs another name, proposed `source_snapshots`.
6. **`risk.py` runs before the committee**, feeding its vote. T4 wants it as an independent check after, so it will run twice.
7. **No migration tool.** Tables come from `metadata.create_all`, which can only add. The plan's "migrations can be rolled back" has no
   mechanism today.
8. **Caddy forwards only `/api/*`, `/auth/*`, `/health`, `/ws/*`.** The plan's `/admin/*` and `/public/*` paths would be served by the
   Next.js frontend, so they must be `/api/admin/*` and `/api/public/*`.
9. **The website already markets features that do not exist.** The Pricing list and the Hero mention an "A6 Auditor confirmation badge" and a
   "Discrepancy Rate dashboard"; `backend/app/models.py` still says the narrated A6 audit trail is "not built". There is also a
   marketing `DiscrepancyBand`. Until S3 lands these claims are ahead of the product.
10. **Some plan content is already done in spirit:** append-only-style scoring only on live days (the paper accounts mark `live_from`),
    a "no LLM backtests" rule (the committee runs only forward), and a weekly evidence gate. The ledger, gate and quarantine are new.
11. **The frontend has no test framework.** CI only type-checks it, so T7's "UI snapshot test" needs a tool added.
12. **Two gunicorn workers share one SQLite file in production.** The ledger's monotonic `seq` under concurrent appends (T11) needs an
    explicit write lock.
