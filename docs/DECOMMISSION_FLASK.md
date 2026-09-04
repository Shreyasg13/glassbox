# Decommissioning the legacy Flask dashboard

Short, honest runbook for retiring `backend-source/dashboard/DASHBOARD_PRO.py`
now that the FastAPI + Next.js stack has parity with it.

## What "decommission" means here

**Important caveat up front:** this build never ran Flask live. Per the
original plan, `DASHBOARD_PRO.py` was kept read-only and unused during the
migration -- every FastAPI route in `backend/app/routers/data.py` was
ported by *reading* the Flask route's source in
`backend-source/dashboard/DASHBOARD_PRO.py`, not by running both servers
side by side and diffing live responses. So "decommission" below means
*confirming it's safe to delete/archive*, not documenting an observed
cutover -- there's no live A/B to point to, just a source-level parity
review.

## 1. Parity checklist

Every route Flask served has a FastAPI equivalent, ported field-for-field:

| Flask route (`DASHBOARD_PRO.py`) | FastAPI route |
|---|---|
| `GET /` | dropped -- superseded by the Next.js frontend |
| `GET /api/data` | `GET /api/data` |
| `GET /api/track1/data` | `GET /api/track1/data` |
| `GET /api/track2/data` | `GET /api/track2/data` |
| `GET /api/track1/agents` | `GET /api/track1/agents` |
| `GET /api/track2/agents` | `GET /api/track2/agents` |
| `GET /api/holdings` | `GET /api/holdings` |
| `GET /api/live-signals` | `GET /api/live-signals` (+ push over `/ws/signals`) |
| `GET /api/agent-performance` | `GET /api/agent-performance` |
| `POST /api/monte-carlo` | `POST /api/monte-carlo` (form-encoded params -> query params; see `backend/README.md`) |
| `GET /api/historical-reports` | `GET /api/historical-reports` |
| `GET /api/daily-summary` | `GET /api/daily-summary` |

One pre-existing gap carried over, not introduced by the port: the legacy
dashboard's JS calls `viewReport(filename)` -> `/api/report/${filename}`,
but no such Flask route exists in `DASHBOARD_PRO.py` either. Not ported;
documented as a known gap in the Phase 1 build notes.

FastAPI adds everything Flask never had: JWT auth, the Agent Factory
(`/api/admin/*`), the LLM provider layer, background jobs + WebSocket push
for long-running work, request tracing, rate limiting, and the audit log /
cost-latency dashboard (`/api/admin/audit-log`, `/api/admin/llm-calls`).

## 2. Safe to retire

- `backend-source/dashboard/DASHBOARD_PRO.py`
- Its launchers: `backend-source/START_DASHBOARD.bat`,
  `START_PRO_DASHBOARD.bat`, `DASHBOARD_LAUNCHER.bat`
- `backend-source/committee_dashboard/live_pitch_dashboard.py` and
  `mathematical_proof_lab.py`, if these were only ever reached through
  the Flask dashboard's own routing (verify before deleting -- they
  weren't in scope for this port either way)

These are dashboard *presentation* code -- HTML templates, Flask routing,
Plotly rendering -- fully superseded by the Next.js frontend + FastAPI
gateway.

## 3. Do NOT delete

`app/data_source.py` (the FastAPI data layer) does not import or run any
of the Flask app's Python classes. It reads the same JSON/parquet
*artifacts* those classes produce, directly off disk. So decommissioning
the Flask *process* does not mean decommissioning the *data* it used to
read from:

- `backend-source/reports/` -- `daily_*.json` files, read by
  `/api/data`, `/api/historical-reports`, `/api/daily-summary`, and
  `/reports/generate`'s narration prompt.
- `backend-source/database/` -- `DATABASE_CONFIG.py`, `NOSQL_SCHEMA.py`.
- Whatever `TRADING_STORAGE_PATH` points at (default `D:/TradingStorage`)
  -- `data_parquet/*.parquet` and `training_results/trained_params.json`,
  read by `/api/holdings` and `/api/live-signals`.
- The underlying engine code these artifacts come from
  (`shared_resources/mathematics/vn_core.py`,
  `parallel_tracks/track_1_accelerated/core_3_agents/agents/base_agent.py`,
  `orchestration/daily_parallel_runner.py`) -- whatever process generates
  new reports/training results still needs to keep running; only the
  *Flask dashboard that visualized them* is being retired.

## 4. Actual cutover steps (for a real deployment)

This repo has no live deployment to cut over -- these are the steps for
whenever one exists:

1. Confirm the FastAPI + Next.js stack is running and healthy at its
   target URLs (`/health` on the API, the Next.js home route).
2. Point the reverse proxy / DNS entry that used to route to the Flask
   process at the new stack instead.
3. Stop the Flask process (`DASHBOARD_PRO.py`).
4. Watch logs/error rates for a rollback window before removing the
   Flask launcher scripts from the deploy target.
5. Archive (don't delete) `dashboard/DASHBOARD_PRO.py` and its launchers
   in source control -- they're small, and keeping them costs nothing
   while still being useful as a reference if a parity question comes up
   later.
