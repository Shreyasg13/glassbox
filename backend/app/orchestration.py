"""Agent execution + orchestration modes (Phase 4/5).

Deterministic vs. LLM agents run on genuinely different paths, per the
plan's design guardrail (docs/PERFORMANCE_AND_ORCHESTRATION.md section 3):
quant/deterministic agents never touch an LLM provider, and
`committee_vote` reduces through a deterministic vote, never an LLM
"judge". See `_reduce_committee_vote` for the honest caveat on how that
reduction stands in for the full VnCalculator coordinator.

Note on `data_source.py`: it does not actually import the backend-source
engine's Python classes (`vn_core.VnCalculator`, `base_agent.BaseAgent`)
-- it reads the same JSON/parquet output artifacts those classes produce.
There is no established "add backend-source to sys.path and import the
live class" convention to follow here, so the deterministic agent path
below follows the same convention data_source.py already set: it reuses
`ds.get_live_signals()` rather than instantiating a `BaseAgent` subclass
directly (those require a market-data dict shaped for a specific
strategy, not a freeform admin test-run string).
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Dict, List, Optional

from . import data_source as ds
from . import db
from . import jobs
from . import llm_router
from .models import AgentConfig, OrchestrationConfig


_SYMBOL_RE = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")


def _extract_symbol(text: str) -> str:
    """The ticker a committee input is about. Plain input ("AAPL") is unchanged.
    A richer input (the daily committee prompt) starts its FIRST LINE with the
    ticker followed by context, so the first token of that line that is a
    tracked symbol wins; anything else falls back to the whole stripped text,
    exactly as before, so an unknown symbol still yields the same clear error."""
    raw = text.strip().upper()
    first_line = raw.split("\n", 1)[0]
    for tok in _SYMBOL_RE.findall(first_line):
        if tok in ds.STOCK_INFO:
            return tok
    return raw


async def run_deterministic_agent(agent: AgentConfig, input: str) -> Dict[str, Any]:
    """Deterministic path: treat `input` as a ticker symbol (see _extract_symbol)
    and return that symbol's already-computed quant signal. Never calls an
    LLM provider."""
    symbol = _extract_symbol(input)
    signals = await asyncio.to_thread(ds.get_live_signals)
    match = next((s for s in signals["signals"] if s["symbol"] == symbol), None)
    if match is None:
        known = ", ".join(sorted(ds.STOCK_INFO))
        raise ValueError(f"No deterministic signal for symbol '{symbol}'. Known symbols: {known}")
    return {"agent": agent.name, "type": "deterministic", "symbol": symbol, "signal": match}


async def run_llm_agent(agent: AgentConfig, input: str, job_id: Optional[str], allow_failover: bool = True) -> Dict[str, Any]:
    if not agent.provider or not agent.model:
        raise ValueError(f"LLM agent '{agent.name}' is missing provider/model")
    params = agent.params

    async def _on_token(piece: str) -> None:
        if job_id:
            await jobs.token(job_id, piece)

    async def _on_fallback(candidate: str, reason: str) -> None:
        if job_id:
            await jobs.log(job_id, f"agent '{agent.name}': trying '{candidate}' ({reason})")

    # Routed: if the agent's own provider is out of quota, the run fails over to
    # the next available provider instead of stalling (app/llm_router.py).
    routed = await llm_router.complete_routed(
        agent.provider,
        agent.model,
        input,
        agent_id=agent.id,
        system=agent.system_prompt,
        temperature=params.temperature,
        top_p=params.top_p,
        max_tokens=params.max_tokens,
        on_token=_on_token,
        fallback_models=agent.fallback_models,
        on_fallback=_on_fallback,
        allow_failover=allow_failover,
    )
    out = {"agent": agent.name, "type": "llm", "provider": routed.provider, "model": routed.model, "output": routed.text}
    if routed.provider != agent.provider:
        out["failed_over_from"] = agent.provider  # so the admin can see this answer came from a different provider
    return out


async def run_agent(agent: AgentConfig, input: str, *, job_id: Optional[str] = None, allow_failover: bool = True) -> Dict[str, Any]:
    if job_id:
        await jobs.log(job_id, f"Running agent '{agent.name}' ({agent.type})")
    if agent.type == "deterministic":
        return await run_deterministic_agent(agent, input)
    return await run_llm_agent(agent, input, job_id, allow_failover)


_DECISION_RE = re.compile(r"decision\s*[:\-]\s*[*_`\s]*(BUY|SELL|HOLD)\b", re.I)
_LEAN_TOKEN_RE = re.compile(r"\b(BUY|SELL|HOLD)\b", re.I)


def _lean_from_text(text: str) -> str:
    """An LLM agent's lean. A "Decision: BUY|SELL|HOLD" line (which the daily
    committee prompt demands) wins; otherwise the EARLIEST BUY/SELL/HOLD word in
    the text; otherwise HOLD. The old rule tested "BUY" in the text before "SELL"
    before "HOLD" regardless of position, so "HOLD -- I wouldn't buy here" counted
    as a BUY vote -- a systematic bias toward BUY."""
    m = _DECISION_RE.search(text)
    if m:
        return m.group(1).upper()
    m = _LEAN_TOKEN_RE.search(text)
    return m.group(1).upper() if m else "HOLD"


def _reduce_committee_vote(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deterministic committee reducer -- confidence-weighted majority
    vote, NOT an LLM judge (guardrail in PERFORMANCE_AND_ORCHESTRATION.md).

    This is a pragmatic stand-in for the full VnCalculator coordinator:
    that class computes an information/communication/quality tradeoff
    over the *number* of participating agents, not a BUY/SELL/HOLD
    reduction over their outputs, so wiring it in directly would require
    market-regime state a freeform admin test-run doesn't have. Each
    participating result is mapped to a lean (deterministic agents already
    carry a `signal`+`confidence`; an LLM agent's free text is read for a
    "Decision:" line or its earliest BUY/SELL/HOLD word (see _lean_from_text),
    defaulting to HOLD, weighted at a flat
    50% since free text isn't a calibrated confidence score) and the
    highest-weighted lean wins. Still fully deterministic and auditable.
    """
    votes: Dict[str, float] = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
    tally: List[Dict[str, Any]] = []
    for r in results:
        if r.get("degraded"):
            continue
        if "signal" in r:
            lean = r["signal"]["signal"]
            weight = r["signal"].get("confidence", 50) / 100
        elif "output" in r:
            lean = _lean_from_text(r["output"])
            weight = 0.5
        else:
            continue
        votes[lean] += weight
        tally.append({"agent": r.get("agent"), "lean": lean, "weight": round(weight, 2)})
    decision = max(votes, key=votes.get) if any(votes.values()) else "HOLD"
    return {"decision": decision, "votes": {k: round(v, 2) for k, v in votes.items()}, "tally": tally}


_LLM_LAUNCH_STAGGER_S = 10.0
"""Delay between kicking off consecutive LLM agent calls in a parallel/
committee_vote run. Firing several LLM calls in the same instant reliably
trips free-tier rate limits -- observed live twice: at 0s stagger, 6 of 7
Gemini calls 429'd; a single isolated call succeeds cleanly and quota
recovers within minutes, meaning the free-tier RPM ceiling is much lower
than a small stagger accounts for. 10s keeps 7 agents within a ~70s launch
span (matched by the seed script's agent_timeout_s/run_budget_s) while
actually landing calls in separate rate-limit windows. The gemini provider
also retries transient 429/503 with backoff as a second line of defense,
but avoiding the burst in the first place means fewer calls need it.
Deterministic agents don't hit an external API, so they're launched
immediately with no stagger."""


async def _run_bounded(
    agents: List[AgentConfig], ctx_input: str, agent_timeout_s: float, run_budget_s: float, job_id: Optional[str],
    allow_failover: bool = True,
) -> List[Dict[str, Any]]:
    """Run all agents concurrently (LLM agents staggered slightly to avoid
    a rate-limit-tripping burst); a per-agent timeout and an overall run
    budget each mark the offending agent(s) `degraded` instead of failing
    the whole batch."""

    async def _one(agent: AgentConfig, delay_s: float) -> Dict[str, Any]:
        if delay_s:
            await asyncio.sleep(delay_s)
        try:
            return await asyncio.wait_for(run_agent(agent, ctx_input, job_id=job_id, allow_failover=allow_failover), timeout=agent_timeout_s)
        except Exception as exc:
            if job_id:
                await jobs.log(job_id, f"agent '{agent.name}' failed: {exc}")
            return {"agent": agent.name, "error": str(exc), "degraded": True}

    tasks = {}
    llm_index = 0
    for agent in agents:
        delay = 0.0
        if agent.type == "llm":
            delay = llm_index * _LLM_LAUNCH_STAGGER_S
            llm_index += 1
        tasks[asyncio.create_task(_one(agent, delay))] = agent
    if not tasks:
        return []
    done, pending = await asyncio.wait(tasks.keys(), timeout=run_budget_s)
    results = [t.result() for t in done]
    for t in pending:
        agent = tasks[t]
        t.cancel()
        if job_id:
            await jobs.log(job_id, f"agent '{agent.name}' exceeded run budget; marked degraded")
        results.append({"agent": agent.name, "error": "run budget exceeded", "degraded": True})
    return results


async def run_orchestration(
    orch: OrchestrationConfig, input: Optional[str], *, job_id: Optional[str] = None, allow_failover: bool = True
) -> Dict[str, Any]:
    agent_rows = [(aid, db.get_agent(aid)) for aid in orch.agent_ids]
    missing = [aid for aid, row in agent_rows if row is None]
    agents = [AgentConfig(**row) for _aid, row in agent_rows if row is not None]
    if missing and job_id:
        await jobs.log(job_id, f"Skipping unknown agent ids: {missing}")

    ctx_input = input or ""

    if orch.mode == "sequential":
        results: List[Dict[str, Any]] = []
        start = time.monotonic()
        for agent in agents:
            if time.monotonic() - start > orch.run_budget_s:
                if job_id:
                    await jobs.log(job_id, "Run budget exceeded; stopping sequential run early")
                break
            try:
                r = await asyncio.wait_for(run_agent(agent, ctx_input, job_id=job_id, allow_failover=allow_failover), timeout=orch.agent_timeout_s)
            except Exception as exc:
                r = {"agent": agent.name, "error": str(exc), "degraded": True}
            results.append(r)
            if r.get("output"):
                ctx_input = f"{ctx_input}\n\n[{agent.name}]: {r['output']}"
            elif r.get("signal"):
                ctx_input = f"{ctx_input}\n\n[{agent.name}]: {r['signal']['signal']} ({r['signal']['symbol']})"
        return {"mode": orch.mode, "agents": results}

    if orch.mode == "parallel":
        results = await _run_bounded(agents, ctx_input, orch.agent_timeout_s, orch.run_budget_s, job_id, allow_failover)
        return {"mode": orch.mode, "agents": results}

    if orch.mode == "committee_vote":
        results = await _run_bounded(agents, ctx_input, orch.agent_timeout_s, orch.run_budget_s, job_id, allow_failover)
        vote = _reduce_committee_vote(results)
        return {"mode": orch.mode, "agents": results, "committee_decision": vote}

    raise ValueError(f"Unknown orchestration mode: {orch.mode}")
