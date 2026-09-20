# LLM failover: keep working when Gemini's free tier runs out

Gemini's free tier allows about **20 requests a day** on most flash models, so a
single-provider setup stalls the moment it is spent (that is why the Investment
Committee never produced a report). GlassBox now routes around it:

```
agent asks for Gemini ──► Gemini out of quota? ──► next provider that has a key ──► ...
                          (rests for an hour)       (OpenRouter free → Groq → Cerebras → ...)
```

Nothing changes until you add a key. **A provider with no key is simply skipped**,
so enabling one is: put its key in the server's `.env`, restart the backend.

## How it behaves

- The provider an agent asks for is tried first, with that agent's own model list.
- On a quota/rate-limit error the provider **rests** for as long as it told us
  (about an hour for a per-day/credit limit, about 90 s for a per-minute one), so a
  spent quota costs one failed call, not one per agent.
- Failover providers are sent **their own** model names, never Gemini's.
- Every attempt is logged in Admin → Observability (provider, model, status).
  Each agent's result records the provider that actually answered
  (`provider`, and `failed_over_from` when it differs).
- If no failover provider is set up, behaviour is exactly as before.
- Test it any time: **Admin → Observability → "Test failover"**, or
  `POST /api/admin/providers/routing/test`. Status: `GET /api/admin/providers/routing`.

## Providers

Free-tier limits and model names **change often** — check each provider's page.
All of these are optional.

| Provider | Cost | Env var | Get a key |
|---|---|---|---|
| **OpenRouter** — the "omniroute" option: `:free` models plus `openrouter/free`, a meta-model that picks whichever free model is up. Free models are **discovered live**, not hardcoded. | free | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| **Groq** (not xAI's Grok) — very fast; Llama/Qwen-class models | free tier | `GROQ_API_KEY` | https://console.groq.com/keys |
| **Cerebras** — generous free tier; Llama/Qwen | free tier | `CEREBRAS_API_KEY` | https://cloud.cerebras.ai |
| **GitHub Models** — free with a GitHub account, rate-limited | free tier | `GITHUB_MODELS_TOKEN` | https://github.com/marketplace/models |
| **Qwen** (Alibaba DashScope, international) | new-account free quota | `DASHSCOPE_API_KEY` | https://www.alibabacloud.com/help/en/model-studio/get-api-key |
| **DeepSeek** | paid, very cheap (no free tier) | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/api_keys |
| **xAI Grok** | paid | `XAI_API_KEY` | https://console.x.ai |
| **Your own gateway** — OmniRoute, LiteLLM proxy, vLLM, anything OpenAI-compatible | whatever it costs | `LLM_GATEWAY_BASE_URL` (+ optional `LLM_GATEWAY_API_KEY`, `LLM_GATEWAY_MODELS`) | — |
| **Ollama** (local container) | free | `OLLAMA_BASE_URL` | see below |

**Quickest start (2 minutes, free):** create an OpenRouter key, then on the VM:

```bash
cd ~/glassbox
echo 'OPENROUTER_API_KEY=sk-or-...' >> .env
docker compose up -d --no-deps backend
```

then click **Test failover** in Admin → Observability. Add Groq and Cerebras the same
way for more headroom (each has its own daily allowance).

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `LLM_FAILOVER` | `gemini,gateway,openrouter,groq,cerebras,github,qwen,deepseek,xai,ollama` | Order providers are tried after the requested one. Add `claude` to opt into paid Anthropic (`CLAUDE_FAILOVER_MODELS` required). |
| `LLM_FAILOVER_ENABLED` | `1` | `0` switches failover off entirely. |
| `LLM_FAILOVER_USER_RUNS` | `1` | `0` keeps runs started by end users on the requested provider only (see privacy). |
| `LLM_ROUTE_BUDGET_S` | `120` | Stop walking the list after this many seconds. |
| `<NAME>_MODELS` | built-in defaults | Comma-separated model ids for a provider, e.g. `GROQ_MODELS=llama-3.3-70b-versatile`. Names the provider's own model list doesn't offer are dropped automatically. |
| `GEMINI_FAILOVER_MODELS` | `gemini-3.1-flash-lite,gemini-flash-latest,gemini-3.5-flash` | Used when Gemini is a failover target (they carry the highest free daily quota). |
| `OLLAMA_FAILOVER_MODELS` | `qwen2.5:1.5b-instruct` | Model used from the local container. |

## Privacy — read before enabling on user data

A failover provider **sees the prompt**. Free tiers commonly log requests and some
train on them. GlassBox's own prompts are market data and simulated portfolios, but
`/api/me/run-report` can include text an end user typed. If that matters to you,
set `LLM_FAILOVER_USER_RUNS=0`: user-started runs then stay on the provider they
asked for and never leave for a third party.

## Costs

Free OpenRouter models are recorded as exactly $0. Every other provider's cost is
shown as "--" (unknown), never guessed — DeepSeek and xAI bill per token, so set
their keys only if you accept that.

## The local container option (Ollama)

Works with no account and no quota, but the VM is small (about 4 GB RAM, roughly
1.7 GB free): use a 1–1.5 B model and expect it to be slow (CPU only).

```bash
docker compose --profile local-llm up -d ollama
docker compose exec ollama ollama pull qwen2.5:1.5b-instruct
```

It is the last resort in the default order, and only used when it is reachable.

## Troubleshooting

- **"resting" in the routing table** — that provider just hit a quota; it is skipped
  until the timer ends (a per-day limit rests about an hour), then tried again.
- **`API key rejected (HTTP 401)`** — wrong key; the provider rests 6 hours. Fix `.env`, restart.
- **`model not found (HTTP 404)`** — that model id is gone (free models rotate). It is
  remembered for a day and skipped; override with `<NAME>_MODELS`.
- **Every provider failed** — the error lists each provider and why. With no keys set,
  only Gemini is configured, which is the pre-failover behaviour.
