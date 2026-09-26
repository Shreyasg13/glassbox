"""LLM-generated narrative with placeholder-only numbers (S3 T3).

The narrative is written by a single LLM call after the committee decision is
saved. Every number in the output MUST be a {{claim:<id>}} placeholder.
Validation ensures no stray digits remain and all claim IDs are known.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import db
from .llm_chat import RoutedChatModel
from .migrated_tables import committee_narratives_table

log = logging.getLogger("glassbox.narrative")


def _iso(dt_or_str: Optional[str | datetime] = None) -> str:
    if dt_or_str is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(dt_or_str, datetime):
        dt = dt_or_str
    else:
        dt = datetime.fromisoformat(dt_or_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def _build_narrative_model() -> RoutedChatModel:
    """Build the RoutedChatModel for narrative generation.

    Provider/model are PINNED from env; failover is OFF.
    """
    provider = os.environ.get("COMMITTEE_NARRATIVE_PROVIDER", "gemini")
    # Default to the same model the committee's debate uses
    model = os.environ.get("COMMITTEE_NARRATIVE_MODEL", os.environ.get("COMMITTEE_DEBATE_MODEL", "gemini-flash-latest"))
    return RoutedChatModel(
        provider=provider,
        model_id=model,
        temperature=0.3,
        max_tokens=800,
        allow_failover=False,  # pinned provider, no failover
    )


NARRATIVE_PROMPT = """You are writing the Investment Committee's daily review narrative for {symbol} on {date}.

Committee decision: {decision}
Action after risk gate: {action}
Risk gate: {gate}
Vote breakdown: {votes}

Analyst rationales:
{rationales}

Structured claims (id | metric | value | unit | period):
{claims_lines}

Write a concise 3-5 sentence narrative explaining the decision. Use ONLY the numbers above.
EVERY number you write MUST be a {{claim:<id>}} placeholder. Do NOT write any raw numbers,
not even years or percentages. If you need to reference a number, use its claim placeholder.
Do not invent facts not in the claims or rationales above.
"""


def _format_claims_for_prompt(claims: List[Dict[str, Any]]) -> str:
    lines = []
    for c in claims:
        val = c["value"]
        if isinstance(val, float):
            # Format for display in prompt (not for rendering)
            if c["unit"] == "pct":
                val_str = f"{val:+.2%}"
            elif c["unit"] == "USD":
                val_str = f"${val:,.2f}"
            elif c["unit"] == "ratio":
                val_str = f"{val:.2f}"
            else:
                val_str = str(val)
        else:
            val_str = str(val)
        lines.append(f"{c['id']} | {c['metric']} | {val_str} | {c['unit']} | {c['period']}")
    return "\n".join(lines)


def _format_rationales(result: Dict[str, Any]) -> str:
    parts = []
    for a in result.get("agents", []):
        if not a.get("ok"):
            continue
        lean = a.get("lean") or a.get("view", {}).get("decision")
        rationale = a.get("view", {}).get("rationale") or a.get("summary") or ""
        if lean and rationale:
            parts.append(f"{a['agent']} ({lean}): {rationale}")
    return "\n".join(parts) if parts else "(none)"


async def write_narrative(run_id: str, decision_doc: Dict[str, Any], claims: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate the narrative via a single LLM call with retry-then-pending logic.

    Returns a dict with keys: narrative, status, attempts, provider_requested,
    model_requested, provider_answered, model_answered, error.
    """
    sym = decision_doc["symbol"]
    d = decision_doc["date"]
    cd = decision_doc.get("committee_decision") or {}
    decision = cd.get("decision")
    action = cd.get("action")
    gate = cd.get("gate")
    votes = cd.get("votes", {})

    claim_ids = {c["id"] for c in claims}
    model = _build_narrative_model()
    model.agent_id = f"narrative-{sym}"

    prompt = NARRATIVE_PROMPT.format(
        symbol=sym,
        date=d,
        decision=decision,
        action=action,
        gate=gate or "none",
        votes=votes,
        rationales=_format_rationales(decision_doc),
        claims_lines=_format_claims_for_prompt(claims),
    )

    provider_requested = os.environ.get("COMMITTEE_NARRATIVE_PROVIDER", "gemini")
    model_requested = os.environ.get("COMMITTEE_NARRATIVE_MODEL", os.environ.get("COMMITTEE_DEBATE_MODEL", "gemini-flash-latest"))

    async def _call_llm(prompt_text: str) -> tuple[str, str, str]:
        """Returns (text, provider_answered, model_answered)."""
        from langchain_core.messages import HumanMessage
        msg = await model.ainvoke([HumanMessage(content=prompt_text)])
        text = msg.content if isinstance(msg.content, str) else str(msg.content)
        meta = msg.response_metadata or {}
        return text, meta.get("provider", ""), meta.get("model", "")

    # First attempt
    text, provider_answered, model_answered = await _call_llm(prompt)
    problems = validate_narrative(text, claim_ids)

    if not problems:
        return {
            "narrative": text,
            "status": "ok",
            "attempts": 1,
            "provider_requested": provider_requested,
            "model_requested": model_requested,
            "provider_answered": provider_answered,
            "model_answered": model_answered,
            "error": None,
        }

    # Retry once with problems appended
    retry_prompt = prompt + "\n\nThe previous answer had these problems:\n" + "\n".join(f"- {p}" for p in problems) + "\n\nRewrite the narrative fixing all problems. Every number MUST be a {{claim:<id>}} placeholder."
    text, provider_answered, model_answered = await _call_llm(retry_prompt)
    problems = validate_narrative(text, claim_ids)

    if not problems:
        return {
            "narrative": text,
            "status": "ok",
            "attempts": 2,
            "provider_requested": provider_requested,
            "model_requested": model_requested,
            "provider_answered": provider_answered,
            "model_answered": model_answered,
            "error": None,
        }

    # Still bad -> pending_review
    return {
        "narrative": text,  # store the bad text for review
        "status": "pending_review",
        "attempts": 2,
        "provider_requested": provider_requested,
        "model_requested": model_requested,
        "provider_answered": provider_answered,
        "model_answered": model_answered,
        "error": "validation failed after retry: " + "; ".join(problems),
    }


def validate_narrative(text: str, claim_ids: set[str]) -> List[str]:
    """Validate that narrative uses ONLY claim placeholders for numbers.

    Returns a list of problem descriptions (empty = ok).
    """
    problems: List[str] = []

    if not text or not text.strip():
        problems.append("narrative is empty")
        return problems

    # Find all {{claim:...}} placeholders
    placeholder_pattern = re.compile(r"\{\{claim:([^}]+)\}\}")
    found_ids = set(placeholder_pattern.findall(text))

    # Check for unknown claim IDs
    unknown = found_ids - claim_ids
    if unknown:
        problems.append(f"unknown claim ids: {', '.join(sorted(unknown))}")

    # Remove all placeholders, then check for any remaining digits
    text_no_placeholders = placeholder_pattern.sub("", text)
    if re.search(r"\d", text_no_placeholders):
        # Find context around digits for better error message
        for m in re.finditer(r"\d", text_no_placeholders):
            start = max(0, m.start() - 20)
            end = min(len(text_no_placeholders), m.end() + 20)
            context = text_no_placeholders[start:end]
            problems.append(f"stray digit found outside placeholders: ...{context}...")
            break  # just report the first one

    return problems


def render(narrative: str, claims: List[Dict[str, Any]]) -> str:
    """Replace {{claim:<id>}} placeholders with formatted values for display (T7)."""
    claim_map = {c["id"]: c for c in claims}

    def format_value(claim: Dict[str, Any]) -> str:
        val = claim["value"]
        unit = claim["unit"]
        if unit == "pct":
            return f"{val:+.2%}"
        elif unit == "USD":
            return f"${val:,.2f}"
        elif unit == "ratio":
            return f"{val:.2f}"
        elif unit == "count":
            return f"{int(val)}"
        else:
            return str(val)

    def repl(match: re.Match) -> str:
        cid = match.group(1)
        claim = claim_map.get(cid)
        if claim is None:
            return f"{{{{claim:{cid}}}}}"
        return format_value(claim)

    return re.sub(r"\{\{claim:([^}]+)\}\}", repl, narrative)