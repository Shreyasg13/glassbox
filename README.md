# GlassBox Trading Agents

**An open-source, evidence-first multi-agent platform for stock research and paper trading. It is built to show its work, and to tell you when the AI is *not* adding value.**

> **Research and simulation only.** GlassBox places no real orders and holds no money. Nothing here is investment advice.
> Every result is simulated paper trading. Backtest numbers use a fixed 15-symbol universe chosen with hindsight and are
> in-sample; only days after 2026-09-19 are out-of-sample.

Live demo: <https://glassbox-portfolio-review.duckdns.org> · License: [MIT](LICENSE) · Status: early, one maintainer, actively developed.

## What it does

- **Investment Committee.** A LangGraph committee of specialist analyst agents reviews each stock daily, then a synthesis step and a
  risk-check produce a structured BUY / SELL / HOLD with a reason. An optional bull/bear debate exists but is off by default.
- **A plain quant engine underneath.** RSI / moving-average signals and a volatility-based risk signal, so the committee is always
  compared with something simple.
- **Paper trading that keeps score.** Dozens of simulated accounts with the same costs and rules: the engine, the committee, a
  **placebo** (shifted signals), equal-weight hold, SPY, cash, a 200-day trend filter, volatility targeting, and tax-aware
  variants (FIFO lots, wash-sale rule, taxable vs IRA-style sheltered ledgers).
- **Per-user committee-run portfolios.** Each profile has a twin account that follows the committee where it has a call. The
  difference from the engine-only account is exactly what the committee added for that user. Includes a Monte Carlo estimate.
- **A live evidence gate.** A strategy is only called "working" after at least 60 live trading days and a bootstrap confidence
  interval that clears zero, corrected for how many strategies were tried. Until then the scoreboard says **"insufficient"**.
- **Data integrity checks.** Gap detection (a real 8-month hole in the price history once produced fake returns; it was found, fixed and
  documented in [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)), point-in-time handling, and honest handling of missing data.
- **Free public data.** SEC fundamentals, 8-K events and Form 4 insider trades, Treasury and BLS macro (SEC access needs a declared contact).
- **LLM failover.** If a provider's quota runs out, calls route to other providers (OpenRouter, Groq, Cerebras, GitHub Models, Qwen,
  DeepSeek, xAI, any OpenAI-compatible gateway, or local Ollama). See [docs/FREE_LLM_ROUTING.md](docs/FREE_LLM_ROUTING.md).
- **An arena for challengers.** Record another system's daily calls and it is traded and judged under identical rules
  ([docs/ARENA.md](docs/ARENA.md)).
- **Opt-in email digests**, an admin console with per-user views and a validation/inference dataset export.

## How it compares with TradingAgents

[TradingAgents](https://github.com/TauricResearch/TradingAgents) (TauricResearch, Apache-2.0) is the most widely used open-source
multi-agent trading framework, with over 100k GitHub stars at the time of writing. It is the reference point, and this comparison is
meant to be fair. It is based on their public README as of 2026-09-25; things may have changed, so please check theirs.

| | TradingAgents | GlassBox Trading Agents |
|---|---|---|
| Maturity and community | Very large community, research paper, frequent releases, 20k+ forks | Early. One maintainer, a handful of live days |
| Shape | Python package and CLI for running the agent graph on a ticker and date | Full web platform (Next.js + FastAPI): committee, paper accounts, admin console, per-user dashboards |
| Agent roles | Fundamentals, sentiment, news and technical analysts; bull/bear researchers; trader; risk team; portfolio manager | Specialist analysts, synthesis, risk gate; bull/bear debate available but off by default |
| Agent memory | Persistent decision log and memory | No reflection memory yet |
| News and sentiment | Broad (news, social, macro data vendors) | Narrower: SEC filings, insider trades, Treasury and BLS. News/social not yet |
| Model providers | Very broad | Broad, with automatic quota failover |
| Point-in-time data | Yes (since v0.5.0) | Yes, plus gap detection on price history |
| Backtesting | Ticker and date grid | Continuous paper accounts, backtest history plus live out-of-sample days |
| **Baselines and controls** | Not something their README emphasises | Built in: placebo, equal-weight, SPY, cash, trend, vol-target |
| **Is the AI actually adding value?** | Research framework; performance varies by model and period (their own disclaimer) | A live evidence gate that reports "insufficient" until there is enough live data |
| Taxes | Not covered in their README | FIFO lots, wash-sale, taxable vs sheltered accounts, after-tax return |
| Per-user portfolios and reporting | Portfolio-aware runs | Per-user committee-run portfolio, Monte Carlo estimate, digest emails, admin roll-up |
| Symbols | Any ticker | 15 fixed symbols with price history on the server |

**Where GlassBox honestly stands.** The committee is unproven: it has only been live since 2026-09-19 and has no scored calls yet,
so we do not claim it beats the market or beats TradingAgents. The design goal is different: make the comparison measurable.
`docs/ARENA.md` shows how to record TradingAgents' daily calls and trade them beside ours under identical costs and rules, judged by the
same evidence gate, so whichever is better, the data says so.

## Repository layout

```
backend/    FastAPI app: committee (LangGraph), paper trading, risk, data, digests (tests in backend/tests)
frontend/   Next.js app: dashboard, admin console, track record
deploy/     Caddy config and the pull-based deploy script
docs/       Design notes, deployment guides, project status and the arena
```

## Run it

Tests (no market data or API keys needed):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest -q
```

Type-check the frontend: `cd frontend && npm ci && npx tsc --noEmit`.

Running the full app needs price history synced into a `trading-storage/` folder (see `.env.example` and
[docs/DEPLOY_IMAGES.md](docs/DEPLOY_IMAGES.md)) and, for the committee, at least one LLM key. Copy `.env.example` to `.env`, generate
secrets with `python -m app.scripts.gen_secrets --admin`, then use Docker Compose. There is not yet a one-command demo; contributions
that add one are welcome.

## Contributing

Issues and pull requests are welcome. `main` is protected: every change goes through a pull request that must pass CI
(`backend-tests`, `frontend-typecheck`) and be approved by the maintainer. Please read [SECURITY.md](SECURITY.md) before reporting a
vulnerability, and keep claims about performance honest: label backtests as backtests.

## License

[MIT](LICENSE). Not investment advice; use at your own risk.
