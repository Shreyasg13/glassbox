"""Seeds the Agent Factory with the real investment-committee personas.

Run via: python -m app.scripts.seed_agents

Sourced directly from backend-source/parallel_tracks/ -- not generic
placeholder content:
- 3 deterministic agents mirror the Track-1 core_3_agents roles, the only
  3 roles with a real, fairly complete deterministic Python implementation
  in the source repo (quantitative.py, risk_manager.py, value_investor.py).
- 7 LLM "persona twin" agents mirror the full Track-2 7-agent committee
  (backend-source/parallel_tracks/track_2_full_system/agents/*.py); their
  system prompts are written directly from those files' docstrings.
- One "Investment Committee" orchestration (committee_vote) ties all 10
  together, coordinated through vn_engine per the project's own guardrail
  that a committee's final call stays deterministic, never an LLM judge.

Honesty note baked into the 3 deterministic agents' system_prompt: the
orchestration engine's deterministic path (see app/orchestration.py's
module docstring) does not currently instantiate these BaseAgent
subclasses -- it filters the same live-signals data those classes would
produce. That's disclosed in-product, not just in this comment, so an
admin reading the Agent Factory sees the real state of the wiring.

Idempotent: checks existing agent/orchestration names before creating, so
running this twice creates nothing new.
"""
from __future__ import annotations

import logging
import sys

from app import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_agents")

_ENGINE_NOTE = (
    " Note: currently reads the same live-signals data this role's logic "
    "would produce, rather than invoking the source engine class directly "
    "-- full class wiring is a follow-up."
)

DETERMINISTIC_AGENTS = [
    {
        "name": "Quantitative Strategist (Engine)",
        "role": "Technical analysis — RSI, MACD, EMA, momentum/mean-reversion signals, multi-timeframe analysis",
        "type": "deterministic",
        "provider": None,
        "model": None,
        "system_prompt": "Deterministic technical-analysis engine." + _ENGINE_NOTE,
        "tools": ["deterministic-engine"],
        "enabled": True,
    },
    {
        "name": "Risk Manager (Engine)",
        "role": "Portfolio protection — Value at Risk, drawdown monitoring, Kelly-criterion position sizing, risk-adjusted signals",
        "type": "deterministic",
        "provider": None,
        "model": None,
        "system_prompt": "Deterministic risk-management engine." + _ENGINE_NOTE,
        "tools": ["deterministic-engine"],
        "enabled": True,
    },
    {
        "name": "Value Investor (Engine)",
        "role": "Fundamental analysis and final synthesis — P/E, P/B, ROE, DCF, quality/value scoring, combines all agents into one recommendation",
        "type": "deterministic",
        "provider": None,
        "model": None,
        "system_prompt": "Deterministic fundamental-analysis and synthesis engine." + _ENGINE_NOTE,
        "tools": ["deterministic-engine"],
        "enabled": True,
    },
]

_LLM_PARAMS = {"temperature": 0.4, "top_p": 0.9, "max_tokens": 600, "extra": {}}

LLM_AGENTS = [
    {
        "name": "Quantitative Strategist",
        "role": "Technical analysis specialist",
        "system_prompt": (
            "You are the Quantitative Strategist on an investment committee. Your job is "
            "technical analysis: exponential moving averages, RSI, MACD, momentum and "
            "mean-reversion signals, multi-timeframe analysis, and pattern identification. "
            "Give a technical read on the stock under discussion — trend direction, "
            "momentum, and any signal divergence — in plain, direct language. State your "
            "confidence and what would change your view."
        ),
    },
    {
        "name": "Risk Manager",
        "role": "Portfolio protection specialist",
        "system_prompt": (
            "You are the Risk Manager on an investment committee. Your job is portfolio "
            "protection: Value at Risk, drawdown monitoring, volatility assessment, beta, "
            "Sharpe ratio, and position sizing (Kelly criterion). For the stock under "
            "discussion, assess the risk profile and recommend a maximum position size. "
            "Flag anything that should give the committee pause."
        ),
    },
    {
        "name": "Value Investor",
        "role": "Fundamental analysis and synthesis specialist",
        "system_prompt": (
            "You are the Value Investor on an investment committee, and the committee's "
            "synthesis voice — you weigh every other agent's input alongside fundamentals "
            "(P/E, P/B, ROE, debt-to-equity, free cash flow, DCF) to reach a final "
            "recommendation. For the stock under discussion, give your fundamental read, "
            "then state the committee's final call: BUY, SELL, or HOLD, and why."
        ),
    },
    {
        "name": "Behavioral Coach",
        "role": "Market psychology specialist",
        "system_prompt": (
            "You are the Behavioral Coach on an investment committee. Your job is market "
            "psychology: detecting sentiment extremes, crowded trades, fear/greed cycles, "
            "and behavioral biases — both in the market and in the committee's own "
            "reasoning. For the stock under discussion, flag any sentiment or "
            "crowd-behavior risk, and note if the committee itself is at risk of a "
            "behavioral bias (recency, anchoring, herding)."
        ),
    },
    {
        "name": "Global Macro",
        "role": "Top-down economic analysis specialist",
        "system_prompt": (
            "You are the Global Macro specialist on an investment committee. Your job is "
            "top-down economic context: interest rates, central bank policy, currency "
            "moves, geopolitical risk, and economic regime shifts. For the stock under "
            "discussion, note any macro tailwinds or headwinds relevant to its sector and "
            "geography."
        ),
    },
    {
        "name": "Technological Innovator",
        "role": "Technology and disruption specialist",
        "system_prompt": (
            "You are the Technological Innovator on an investment committee. Your job is "
            "assessing disruption risk and innovation-driven opportunity: emerging "
            "technology trends, competitive tech positioning, and adoption cycles. For the "
            "stock under discussion, assess its technological moat or vulnerability to "
            "disruption."
        ),
    },
    {
        "name": "Personal Context",
        "role": "Investor-context and personalization specialist",
        "system_prompt": (
            "You are the Personal Context specialist on an investment committee. Your job "
            "is translating the committee's analysis into what it means for a specific "
            "investor's goals, constraints, tax situation, and risk tolerance. Given the "
            "committee's discussion of the stock, note portfolio-fit considerations a real "
            "investor should weigh — position sizing relative to their goals, tax "
            "implications, liquidity needs."
        ),
    },
]

ORCHESTRATION_NAME = "Investment Committee"


def _seed_agents() -> dict[str, str]:
    """Returns {agent_name: agent_id} for every agent that exists after this call
    (both newly created and pre-existing), so the orchestration can reference all
    of them regardless of which run created which."""
    existing_by_name = {a["name"]: a["id"] for a in db.list_agents()}
    ids: dict[str, str] = {}

    for spec in DETERMINISTIC_AGENTS:
        name = spec["name"]
        if name in existing_by_name:
            log.info("[agent] %r already exists, skipping", name)
            ids[name] = existing_by_name[name]
            continue
        created = db.create_agent(
            {
                "name": spec["name"],
                "role": spec["role"],
                "type": spec["type"],
                "provider": spec["provider"],
                "model": spec["model"],
                "params": {"temperature": 0.7, "top_p": 1.0, "max_tokens": 1024, "extra": {}},
                "system_prompt": spec["system_prompt"],
                "tools": spec["tools"],
                "enabled": spec["enabled"],
            }
        )
        log.info("[agent] created deterministic %r (id=%s)", name, created["id"])
        ids[name] = created["id"]

    for spec in LLM_AGENTS:
        name = spec["name"]
        if name in existing_by_name:
            log.info("[agent] %r already exists, skipping", name)
            ids[name] = existing_by_name[name]
            continue
        created = db.create_agent(
            {
                "name": spec["name"],
                "role": spec["role"],
                "type": "llm",
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "params": _LLM_PARAMS,
                "system_prompt": spec["system_prompt"],
                "tools": [],
                "enabled": True,
            }
        )
        log.info("[agent] created llm %r (id=%s)", name, created["id"])
        ids[name] = created["id"]

    return ids


def _seed_orchestration(agent_ids_by_name: dict[str, str]) -> None:
    existing_by_name = {o["name"]: o["id"] for o in db.list_orchestrations()}
    if ORCHESTRATION_NAME in existing_by_name:
        log.info("[orchestration] %r already exists, skipping", ORCHESTRATION_NAME)
        return

    all_names = [a["name"] for a in DETERMINISTIC_AGENTS] + [a["name"] for a in LLM_AGENTS]
    agent_ids = [agent_ids_by_name[name] for name in all_names]

    created = db.create_orchestration(
        {
            "name": ORCHESTRATION_NAME,
            "mode": "committee_vote",
            "agent_ids": agent_ids,
            "coordinator": "vn_engine",
            "schedule": None,
            "agent_timeout_s": 30.0,
            "run_budget_s": 180.0,
        }
    )
    log.info(
        "[orchestration] created %r (id=%s) with %d agents",
        ORCHESTRATION_NAME,
        created["id"],
        len(agent_ids),
    )


def main() -> int:
    agent_ids_by_name = _seed_agents()
    _seed_orchestration(agent_ids_by_name)
    log.info(
        "Done. %d agents, %d orchestrations in DB.",
        len(db.list_agents()),
        len(db.list_orchestrations()),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
