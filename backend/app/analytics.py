"""First-party, cookie-free visit analytics: who is finding GlassBox, from where, and whether they sign up.

PRIVACY BY DESIGN (so no consent banner is needed and nothing personal can leak):
  * No cookies, no local storage, no fingerprinting, no third-party scripts.
  * The IP address is NEVER stored. It is only mixed into a hash that also contains a per-day secret
    salt, so `visitor` can count unique people WITHIN a day but cannot follow anyone across days.
    Consequence: multi-day "visitors" are really *visitor-days* (someone who comes on 3 days counts 3).
  * Do-Not-Track / Global-Privacy-Control requests are not recorded at all.
  * Only page paths, a normalised referrer / utm tag and a coarse device class are kept; ids inside
    paths are masked; rows are pruned after RETENTION_DAYS.
  * Bots, crawlers, link-preview fetchers and monitors are not counted; /admin, /api etc. are never counted.

NEVER FATAL: a recording problem must not affect the visitor, so callers swallow errors.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import delete, distinct, func, insert, select

from . import db
from .auth import SECRET_KEY

log = logging.getLogger("glassbox.analytics")

RETENTION_DAYS = 180
MAX_PATH = 200
MAX_TAG = 60
MAX_ROWS_PER_DAY_PER_WORKER = 50_000  # a flood guard on top of the per-IP rate limit
SKIP_PREFIXES = ("/admin", "/api", "/auth", "/_next", "/ws", "/oauth")
_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|headless|lighthouse|pagespeed|curl|wget|python-requests|httpx|aiohttp|monitor|uptime|"
    r"preview|facebookexternalhit|embedly|whatsapp|telegram|discord|scrapy|axios|go-http|java/|postman|okhttp",
    re.I,
)
_ID_SEG = re.compile(r"^(?:[0-9a-f]{8,}|[0-9a-f]{8}-[0-9a-f-]{20,}|\d{4,})$", re.I)
_TAG_OK = re.compile(r"[^a-z0-9._-]+")
_SOURCE_BY_HOST = (  # (host suffix, label)
    ("linkedin.com", "linkedin"), ("lnkd.in", "linkedin"), ("github.com", "github"), ("t.co", "x"), ("twitter.com", "x"), ("x.com", "x"),
    ("news.ycombinator.com", "hackernews"), ("reddit.com", "reddit"), ("youtube.com", "youtube"), ("youtu.be", "youtube"),
    ("bing.com", "bing"), ("duckduckgo.com", "duckduckgo"), ("facebook.com", "facebook"), ("medium.com", "medium"), ("dev.to", "devto"),
)

_day_counts: Dict[str, int] = {}


# ------------------------------------------------------------------ helpers --


def _own_hosts() -> set:
    from .digest import LIVE_SITE

    return {urlparse(LIVE_SITE).hostname or "", "localhost", "127.0.0.1"}


def clean_tag(raw: Optional[str]) -> str:
    """A short lowercase label safe to store and display (utm values come from anyone's URL)."""
    return _TAG_OK.sub("-", (raw or "").strip().lower())[:MAX_TAG].strip("-")


def normalize_path(raw: str) -> Optional[str]:
    """The path only (no query/fragment), ids masked, or None if this page must not be counted."""
    if not raw or any(ord(c) < 32 for c in raw):
        return None
    path = urlparse(raw).path or "/"
    if not path.startswith("/"):
        return None
    path = path[:MAX_PATH]
    if len(path) > 1:
        path = path.rstrip("/")
    if any(path == p or path.startswith(p + "/") for p in SKIP_PREFIXES):
        return None
    if path == "/":
        return "/"
    return "/" + "/".join(":id" if _ID_SEG.match(seg) else seg for seg in path.split("/") if seg)


def normalize_source(referrer: Optional[str], utm_source: Optional[str]) -> str:
    """An explicit utm_source wins; otherwise the referrer's site mapped to a friendly label; otherwise 'direct'."""
    tag = clean_tag(utm_source)
    if tag:
        return tag
    try:
        host = (urlparse(referrer or "").hostname or "").lower().removeprefix("www.")
    except ValueError:
        return "direct"
    if not host or host in _own_hosts():
        return "direct"
    for suffix, label in _SOURCE_BY_HOST:
        if host == suffix or host.endswith("." + suffix):
            return label
    if host.startswith("google."):
        return "google"
    return host[:MAX_TAG]


def device_class(ua: str) -> str:
    if re.search(r"ipad|tablet", ua, re.I):
        return "tablet"
    return "mobile" if re.search(r"mobi|android|iphone", ua, re.I) else "desktop"


def visitor_id(ip: str, ua: str, day: str) -> str:
    """Unique within `day` only: the salt changes daily and is derived from the server secret."""
    salt = hmac.new(SECRET_KEY.encode(), f"analytics|{day}".encode(), hashlib.sha256).digest()
    return hashlib.sha256(salt + f"{ip}|{ua}".encode()).hexdigest()[:16]


# ---------------------------------------------------------------- recording --


def record_hit(
    path: str,
    referrer: str = "",
    utm_source: str = "",
    utm_medium: str = "",
    utm_campaign: str = "",
    *,
    ip: str,
    ua: str,
    dnt: bool = False,
    now: Optional[datetime] = None,
) -> bool:
    """Stores one page view. Returns whether it was recorded (False = filtered out on purpose)."""
    if dnt or not ua or _BOT_RE.search(ua):
        return False
    clean = normalize_path(path)
    if clean is None:
        return False
    now = now or datetime.now(timezone.utc)
    day = now.strftime("%Y-%m-%d")
    if _day_counts.get(day, 0) >= MAX_ROWS_PER_DAY_PER_WORKER:
        return False
    if day not in _day_counts and len(_day_counts) > 3:
        _day_counts.clear()  # only today matters; don't let old days pile up
    _day_counts[day] = _day_counts.get(day, 0) + 1
    row = {
        "day": day,
        "ts": now.isoformat(timespec="seconds"),
        "path": clean,
        "visitor": visitor_id(ip, ua, day),
        "source": normalize_source(referrer, utm_source) or "direct",
        "medium": clean_tag(utm_medium),
        "campaign": clean_tag(utm_campaign),
        "device": device_class(ua),
    }
    with db.engine.begin() as conn:
        conn.execute(insert(db.page_views_table).values(**row))
    if random.random() < 0.002:  # housekeeping now and then, not on every hit
        prune(now)
    return True


def prune(now: Optional[datetime] = None) -> int:
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    with db.engine.begin() as conn:
        return conn.execute(delete(db.page_views_table).where(db.page_views_table.c.day < cutoff)).rowcount


# ------------------------------------------------------------------ summary --

_T = db.page_views_table
_VD = distinct(_T.c.visitor + _T.c.day)  # one visitor on one day


def _rows(conn, stmt) -> List[Any]:
    return conn.execute(stmt).fetchall()


def summary(days: int = 30, users: Optional[List[Dict[str, Any]]] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    first = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    in_range = _T.c.day >= first
    with db.engine.connect() as conn:
        daily = {r.day: (r.uv, r.pv) for r in _rows(conn, select(_T.c.day, func.count(distinct(_T.c.visitor)).label("uv"), func.count().label("pv")).where(in_range).group_by(_T.c.day))}
        pages = _rows(conn, select(_T.c.path, func.count(_VD).label("v"), func.count().label("pv")).where(in_range).group_by(_T.c.path).order_by(func.count(_VD).desc(), func.count().desc()).limit(15))
        # Attribution is FIRST TOUCH per visitor-day: the referrer / utm tag only exists on the landing page view, so later
        # pages of the same visit (which arrive with no referrer) must not turn a LinkedIn visitor into a "direct" one.
        first_ids = select(func.min(_T.c.id)).where(in_range).group_by(_T.c.visitor, _T.c.day)
        landing = _T.c.id.in_(first_ids)
        sources = _rows(conn, select(_T.c.source, func.count().label("v")).where(landing).group_by(_T.c.source).order_by(func.count().desc()).limit(15))
        campaigns = _rows(conn, select(_T.c.source, _T.c.medium, _T.c.campaign, func.count().label("v")).where(landing, _T.c.campaign != "").group_by(_T.c.source, _T.c.medium, _T.c.campaign).order_by(func.count().desc()).limit(15))
        devices = _rows(conn, select(_T.c.device, func.count().label("v")).where(landing).group_by(_T.c.device).order_by(func.count().desc()))
        live = conn.execute(select(func.count(distinct(_T.c.visitor))).where(_T.c.day == today, _T.c.ts >= (now - timedelta(minutes=30)).isoformat(timespec="seconds"))).scalar() or 0

        def stage(*paths: str) -> int:
            return conn.execute(select(func.count(_VD)).where(in_range, _T.c.path.in_(paths))).scalar() or 0

        total_vd = conn.execute(select(func.count(_VD)).where(in_range)).scalar() or 0
        funnel = [
            {"step": "Visited the site", "visitors": total_vd},
            {"step": "Opened login or sign-up", "visitors": stage("/login", "/signup")},
            {"step": "Reached the app", "visitors": stage("/dashboard", "/onboarding", "/choose")},
        ]
    series = []
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        uv, pv = daily.get(d, (0, 0))
        series.append({"day": d, "visitors": uv, "pageviews": pv})
    signups = [(u.get("created_at") or "")[:10] for u in (users or []) if u.get("role") != "admin"]
    signups_in = [d for d in signups if first <= d <= today]
    by_day: Dict[str, int] = {}
    for d in signups_in:
        by_day[d] = by_day.get(d, 0) + 1
    for row in series:
        row["signups"] = by_day.get(row["day"], 0)
    funnel.append({"step": "Signed up", "visitors": len(signups_in)})
    tot_pv = sum(r["pageviews"] for r in series)
    return {
        "days": days,
        "as_of": now.isoformat(timespec="seconds"),
        "live_now": int(live),
        "today": {"visitors": daily.get(today, (0, 0))[0], "pageviews": daily.get(today, (0, 0))[1]},
        "totals": {"visitor_days": total_vd, "pageviews": tot_pv, "signups": len(signups_in), "signup_rate": (len(signups_in) / total_vd) if total_vd else None},
        "series": series,
        "pages": [{"path": r.path, "visitors": r.v, "pageviews": r.pv} for r in pages],
        "sources": [{"source": r.source, "visitors": r.v} for r in sources],
        "campaigns": [{"source": r.source, "medium": r.medium, "campaign": r.campaign, "visitors": r.v} for r in campaigns],
        "devices": [{"device": r.device, "visitors": r.v} for r in devices],
        "funnel": funnel,
        "note": (
            "Privacy-first: no cookies and no IP addresses are stored, and the visitor hash resets every day, so 'visitors' here are "
            "visitor-days (someone who returns on 3 days counts 3). Bots and Do-Not-Track visits are excluded, so real traffic can be a little higher."
        ),
    }
