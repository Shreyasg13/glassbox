# GlassBox backend (FastAPI)

FastAPI gateway that ports the read routes from the legacy Flask
dashboard (`backend-source/dashboard/DASHBOARD_PRO.py`) and adds
JWT auth, a WebSocket signal feed, and admin CRUD for the Agent
Factory (Phase 4). It does not reimplement any trading/agent math --
`app/data_source.py` reads the same JSON/parquet artifacts the legacy
dashboard read.

## Run

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000/docs for the interactive OpenAPI UI.

## Data sources

Two env vars control where data is read from (both have working
defaults so the API runs out of the box against the sample data
already committed to the source repo):

- `BACKEND_SOURCE_PATH` -- path to the cloned `multi-agent-trading-system`
  repo, used for `reports/daily_*.json`. Default: `../backend-source`
  (i.e. `glassbox/backend-source` alongside this `backend/` folder).
- `TRADING_STORAGE_PATH` -- path to the live data store the legacy
  code hardcoded as `D:/TradingStorage` (parquet price files, trained
  model params, per-track performance JSON). Default: `D:/TradingStorage`.
  When this path doesn't exist, endpoints fall back to the same
  generated/defaulted values `DASHBOARD_PRO.py` used (this matches
  the legacy behavior -- it isn't new fallback logic).

`pandas`/`pyarrow` are only imported lazily, inside
`data_source._load_parquet_row`, so they're not required unless
`TRADING_STORAGE_PATH/data_parquet/*.parquet` actually exists. Install
them (`pip install pandas pyarrow`) once real price data is wired up.

## Auth

`POST /auth/login` with `{"username": "admin", "password": "admin"}`
returns a JWT. Send it as `Authorization: Bearer <token>` to reach any
`/admin/*` route. **This dev login is a placeholder** -- see the
`TODO(real-auth)` markers in `app/auth.py`; it must be replaced with a
real user store before Phase 6 launch.

## Admin storage

`/admin/agents`, `/admin/orchestrations`, `/admin/jobs`, LLM call logs,
and report narratives are all backed by SQLite (`app/glassbox.db`, via
SQLAlchemy Core) as a placeholder persistence layer -- swapping to the
project's real Postgres config is a later phase (change `DATABASE_URL`
in `app/db.py`).

## Provider Abstraction Layer (Phase 5)

`app/providers/` implements one `LLMProvider` interface with four
adapters (`ollama.py`, `vllm.py`, `gemini.py`, `claude.py`), all wrapped
by `BaseProvider`'s shared timeout + circuit-breaker logic
(`app/providers/base.py`) -- see `docs/PERFORMANCE_AND_ORCHESTRATION.md`
sections 1/3 for why. `app/providers/factory.get_provider(name)` resolves
an agent's configured `provider` string to a live instance.

Env vars (all optional -- an unset/unreachable provider just reports
`reachable: false` from `/admin/providers/health`, it doesn't crash
anything):

- `OLLAMA_BASE_URL` -- default `http://localhost:11434`
- `VLLM_BASE_URL` -- default `http://localhost:8001` (OpenAI-compatible `/v1/chat/completions`)
- `GEMINI_API_KEY` -- Gemini REST API key (raw `httpx` client, no SDK dependency)
- `ANTHROPIC_API_KEY` -- used by the official `anthropic` async SDK

Run the provider test suite (mocked HTTP, no real credentials needed):

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Background jobs (agent test-run, orchestration run, report generate)

Per the perf doc, nothing that touches an LLM is ever awaited inline in
a request handler -- these three endpoints all return `{"job_id": ...}`
immediately (202) and do the real work in `asyncio.create_task`:

```bash
TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Create an LLM agent, then test-run it
AGENT_ID=$(curl -s -X POST localhost:8000/admin/agents -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Macro Analyst","role":"analyst","type":"llm","provider":"ollama","model":"llama3"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

JOB_ID=$(curl -s -X POST localhost:8000/admin/agents/$AGENT_ID/test-run -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"input":"AAPL"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# Poll (fallback) or connect to ws://localhost:8000/ws/jobs/$JOB_ID for live log/token/status frames
curl -s localhost:8000/admin/jobs/$JOB_ID -H "Authorization: Bearer $TOKEN"

# Provider health (always 200; unreachable/unconfigured is a normal result)
curl -s localhost:8000/admin/providers/health -H "Authorization: Bearer $TOKEN"

# Generate a narrated daily report
curl -s -X POST localhost:8000/reports/generate -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"provider":"ollama","model":"llama3"}'
```

Verified on this machine (no Ollama/vLLM running, no cloud API keys set):
health-check correctly reports all four providers `reachable: false`
with a clear `detail`; a deterministic agent test-run against `"AAPL"`
returns a real signal from the live quant engine; an LLM agent test-run
and `/reports/generate` both fail cleanly with `status: "error"` and a
readable message over `/ws/jobs/{id}`, with no server-side exception or
hang; a `committee_vote` orchestration mixing one deterministic and one
(unreachable) LLM agent correctly marks the LLM agent `degraded` and
still produces a decision from the surviving agent.

## Endpoint inventory (parity with DASHBOARD_PRO.py)

| Method | Path | Ported from |
|---|---|---|
| GET | `/api/data` | `/api/data` |
| GET | `/api/track1/data` | `/api/track1/data` |
| GET | `/api/track2/data` | `/api/track2/data` |
| GET | `/api/track1/agents` | `/api/track1/agents` |
| GET | `/api/track2/agents` | `/api/track2/agents` |
| GET | `/api/agent-performance` | `/api/agent-performance` |
| GET | `/api/holdings` | `/api/holdings` |
| GET | `/api/live-signals` | `/api/live-signals` |
| POST | `/api/monte-carlo` | `/api/monte-carlo` (now JSON/query params, not form-encoded) |
| GET | `/api/historical-reports` | `/api/historical-reports` |
| GET | `/api/daily-summary` | `/api/daily-summary` |
| WS | `/ws/signals` | new -- pushes the `/api/live-signals` payload every 3s |
| POST | `/auth/login` | new |
| * | `/admin/agents`, `/admin/orchestrations` | new (Phase 4) |

Not ported: the Flask `/` route (renders the whole legacy HTML
dashboard -- superseded by the Next.js frontend) and a `/api/report/<filename>`
endpoint that the legacy dashboard's own JS calls (`viewReport()`) but
that was never implemented server-side in `DASHBOARD_PRO.py` -- that
was already a dead reference in the source and isn't part of this
contract.
