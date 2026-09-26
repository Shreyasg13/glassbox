"""User feedback on signals, assistant answers, notifications and the committee itself.

HOW IT IS USED (deliberately advisory): feedback is stored and shown to the admin, with the counts and comments that
would justify a change to the committee (a different agent mix, a clearer explanation, a stock users keep asking about).
It NEVER changes committee prompts, agents or trades automatically: free-text from strangers is an open door for
gaming and prompt injection, and a strategy must clear the live evidence gate before it drives anything (see
docs/ARENA.md). A person reviews it; a change then ships like any other, through a protected pull request.

Bounded and private: per-user daily limit, capped lengths, control characters stripped, one rating per target
(changing your mind updates it instead of double counting). Users only ever read their own feedback.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, insert, select, update

from . import db

TARGET_TYPES = ("signal", "answer", "notification", "committee", "general")
COMMENT_MAX = 1000
DAILY_LIMIT = 30
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,10}([.-][A-Z0-9]{1,3})?$")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_T = db.feedback_table


class FeedbackError(ValueError):
    pass


def record(user: str, target_type: str, target_ref: str = "", rating: int = 0, comment: str = "", symbol: str = "", now: Optional[datetime] = None) -> Dict[str, Any]:
    if target_type not in TARGET_TYPES:
        raise FeedbackError("unknown feedback type")
    if rating not in (-1, 0, 1):
        raise FeedbackError("rating must be -1, 0 or 1")
    comment = _CTRL.sub("", (comment or "")).strip()[:COMMENT_MAX]
    if rating == 0 and not comment:
        raise FeedbackError("add a rating or a comment")
    symbol = (symbol or "").strip().upper()
    if symbol and not _SYMBOL_RE.match(symbol):
        raise FeedbackError("invalid symbol")
    user, ref = user.strip().lower(), (target_ref or "")[:120]
    now = now or datetime.now(timezone.utc)
    with db.engine.begin() as conn:
        existing = conn.execute(select(_T.c.id).where(_T.c.user == user, _T.c.target_type == target_type, _T.c.target_ref == ref, _T.c.target_ref != "")).first()
        if existing:  # same target again: update, don't double count
            conn.execute(update(_T).where(_T.c.id == existing.id).values(rating=rating, comment=comment, created_at=now.isoformat(timespec="seconds")))
            return {"id": existing.id, "updated": True}
        since = (now - timedelta(days=1)).isoformat(timespec="seconds")
        if (conn.execute(select(func.count()).select_from(_T).where(_T.c.user == user, _T.c.created_at >= since)).scalar() or 0) >= DAILY_LIMIT:
            raise FeedbackError("daily feedback limit reached, thank you: please try again tomorrow")
        fid = str(uuid.uuid4())
        conn.execute(insert(_T).values(id=fid, user=user, created_at=now.isoformat(timespec="seconds"), target_type=target_type, target_ref=ref, symbol=symbol, rating=rating, comment=comment))
    return {"id": fid, "updated": False}


def mine(user: str, limit: int = 50) -> List[Dict[str, Any]]:
    with db.engine.connect() as conn:
        rows = conn.execute(select(_T).where(_T.c.user == user.strip().lower()).order_by(_T.c.created_at.desc()).limit(min(max(limit, 1), 200))).fetchall()
    return [{k: r._mapping[k] for k in ("id", "created_at", "target_type", "target_ref", "symbol", "rating", "comment")} for r in rows]


def _since(days: int, now: Optional[datetime]) -> str:
    return ((now or datetime.now(timezone.utc)) - timedelta(days=days)).isoformat(timespec="seconds")


def rows_for_export(days: int = 365, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Admin export. The username is replaced by a short stable hash so a shared dataset doesn't expose accounts."""
    import hashlib

    with db.engine.connect() as conn:
        rows = conn.execute(select(_T).where(_T.c.created_at >= _since(days, now)).order_by(_T.c.created_at.desc())).fetchall()
    return [
        {"created_at": r.created_at, "user": hashlib.sha256(r.user.encode()).hexdigest()[:8], "target_type": r.target_type, "target_ref": r.target_ref, "symbol": r.symbol, "rating": r.rating, "comment": r.comment}
        for r in rows
    ]


def summary(days: int = 90, now: Optional[datetime] = None) -> Dict[str, Any]:
    """What users are telling us, for the admin: helpfulness by type and by stock, plus the newest comments."""
    rows = rows_for_export(days, now)
    with db.engine.connect() as conn:
        users = conn.execute(select(func.count(func.distinct(_T.c.user))).where(_T.c.created_at >= _since(days, now))).scalar() or 0

    def tally(key: str) -> List[Dict[str, Any]]:
        agg: Dict[str, Dict[str, int]] = {}
        for r in rows:
            k = r[key]
            if not k:
                continue
            a = agg.setdefault(k, {"helpful": 0, "unhelpful": 0, "comments": 0})
            a["helpful"] += r["rating"] == 1
            a["unhelpful"] += r["rating"] == -1
            a["comments"] += bool(r["comment"])
        out = [{"key": k, **v, "rated": v["helpful"] + v["unhelpful"], "helpful_rate": (v["helpful"] / (v["helpful"] + v["unhelpful"])) if v["helpful"] + v["unhelpful"] else None} for k, v in agg.items()]
        return sorted(out, key=lambda x: (-(x["rated"] + x["comments"]), x["key"]))

    return {
        "days": days,
        "total": len(rows),
        "users": int(users),
        "helpful": sum(r["rating"] == 1 for r in rows),
        "unhelpful": sum(r["rating"] == -1 for r in rows),
        "by_type": tally("target_type"),
        "by_symbol": tally("symbol")[:15],
        "recent_comments": [r for r in rows if r["comment"]][:30],
        "note": "Advisory only. Feedback never changes the committee automatically; use it to decide what to investigate, then test any change against the live evidence gate.",
    }
