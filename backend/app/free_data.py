"""Free, commercially-safe public data for the committee and the UI.

Only sources that are public and free to use in a product:

  * SEC EDGAR (data.sec.gov / www.sec.gov) -- company fundamentals from XBRL filings, the filing feed
    (8-K events, 10-K / 10-Q dates), and Form 4 insider open-market transactions. No key; the SEC's
    fair-access policy requires a User-Agent that names a contact (set SEC_USER_AGENT, e.g. "GlassBox
    research you@yourdomain.com") and at most 10 requests a second.
  * US Treasury daily par yield curve, and the BLS public API (unemployment rate, CPI) -- US government data.

There is no free, commercially-safe media/news or social-sentiment feed (scraped news sites and most
"free tier" news APIs are not licensed for use in a product), so this deliberately does not try to
approximate one. Form 4 insider buying/selling is the closest genuinely free, genuinely legal substitute:
it is a well-established sentiment-adjacent signal (an executive's own money, not commentary about the
stock) from the same EDGAR source already used for fundamentals and 8-Ks.

Design rules:
  * REFRESH is separate from USE. A daily job (app/scripts/refresh_free_data.py) fetches and writes a small
    JSON cache; the committee and the UI only ever READ the cache, so a review never waits on, or fails
    because of, a third-party website, and the same date always renders the same prompt.
  * POINT IN TIME. Every figure is computed "as of" a date from what had been FILED by then (restated
    values that were filed later are ignored), so nothing here can leak the future into a backtest.
  * Missing is fine. Funds (SPY, QQQ, GLD ...) have no company filings, banks report different line items,
    a source can be down or unconfigured: every function returns None / [] for what it cannot say and the
    prompt simply omits that line. Status per source is recorded so the admin can see what is and is not live.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from .data_source import TRADING_STORAGE_PATH

log = logging.getLogger("glassbox.free_data")

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
TREASURY_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)
BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/{series}"
BLS_SERIES = {"unemployment": "LNS14000000", "cpi": "CUUR0000SA0"}

SEC_MIN_INTERVAL_S = 0.12  # ~8 requests a second, under the SEC's 10/s ceiling
TICKER_MAP_TTL_DAYS = 30
FUNDAMENTALS_TTL_DAYS = 3
BLS_LAG_DAYS = {"unemployment": 12, "cpi": 20}  # days after a month ends before its figure is public (jobs report ~1 week, CPI ~2 weeks, plus margin)

FORM4_INDEX_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik:010d}&type=4&dateb=&owner=include&count=20&output=atom"
INSIDER_LOOKBACK_DAYS = 30  # how far back "recent insider activity" looks in a prompt/UI line
INSIDER_KEEP_DAYS = 180  # how long a transaction stays in the cache before being pruned
INSIDER_NEW_PER_RUN = 8  # cap on newly-discovered filings fetched (2 requests each) in one refresh, per company
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
# Only these transaction codes are a discretionary open-market decision. Grants (A), option exercises (M),
# tax-withholding sales (F) and gifts (G) are routine compensation mechanics, not a buy/sell view -- every
# insider-sentiment tracker excludes them for the same reason.
OPEN_MARKET_CODES = {"P": "purchase", "S": "sale"}

# XBRL "us-gaap" tags, most specific first. Flow concepts are annual (10-K) values; instant ones are year-end balances.
CONCEPTS: Dict[str, List[str]] = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_income": ["OperatingIncomeLoss"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "op_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "liabilities": ["Liabilities"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
}
INSTANT = {"equity", "liabilities", "long_term_debt"}
UNITS = {"USD", "USD/shares"}
ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT"}

# 8-K item numbers -> plain English; the ones worth a second look are flagged.
ITEM_TEXT = {
    "1.01": "entered a material agreement", "1.02": "terminated a material agreement", "1.03": "bankruptcy or receivership",
    "2.01": "completed an acquisition or disposal", "2.02": "reported quarterly results", "2.03": "took on a direct financial obligation",
    "2.04": "triggered acceleration of an obligation", "2.05": "announced exit or restructuring costs", "2.06": "recorded a material impairment",
    "3.01": "received a delisting notice", "3.02": "sold unregistered securities", "4.01": "changed its auditor",
    "4.02": "said prior financial statements should not be relied on", "5.01": "changed control", "5.02": "changed directors or senior officers",
    "5.07": "held a shareholder vote", "7.01": "made a regulation-FD disclosure", "8.01": "reported another event",
}
ITEM_FLAGGED = {"1.02", "1.03", "2.04", "2.05", "2.06", "3.01", "4.01", "4.02", "5.01", "5.02"}
ITEM_IGNORED = {"9.01"}  # exhibits only


# ------------------------------------------------------------------ paths / status --


def data_dir() -> Path:
    d = Path(os.environ.get("FREE_DATA_DIR") or (TRADING_STORAGE_PATH / "free_data"))
    return d


def _read(name: str) -> Optional[Any]:
    try:
        return json.loads((data_dir() / name).read_text(encoding="utf8"))
    except (OSError, ValueError):
        return None


def _write(name: str, obj: Any) -> None:
    path = data_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, separators=(",", ":")), encoding="utf8")
    os.replace(tmp, path)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fresh(obj: Optional[Dict[str, Any]], ttl_days: float) -> bool:
    try:
        return obj is not None and (_now() - datetime.fromisoformat(obj["fetched_at"])) < timedelta(days=ttl_days)
    except (KeyError, ValueError):
        return False


def read_status() -> Dict[str, Any]:
    return _read("status.json") or {}


def _set_status(status: Dict[str, Any], source: str, ok: bool, detail: str, count: int = 0) -> None:
    status[source] = {"ok": ok, "detail": detail, "count": count, "at": _now().isoformat()}


# -------------------------------------------------------------------------- fetching --


def sec_user_agent() -> Optional[str]:
    """The SEC requires a declared contact. Never guess one: without SEC_USER_AGENT the SEC part stays off."""
    ua = (os.environ.get("SEC_USER_AGENT") or "").strip()
    return ua if "@" in ua else None


class Fetcher:
    """Polite JSON/text GET with a minimum interval between calls and a few retries on 429 / 5xx."""

    def __init__(self, headers: Optional[Dict[str, str]] = None, min_interval: float = 0.0, transport: Optional[httpx.BaseTransport] = None, sleep: Callable[[float], None] = time.sleep):
        self.http = httpx.Client(headers=headers or {}, timeout=30.0, transport=transport, follow_redirects=True)
        self.min_interval, self._sleep, self._last = min_interval, sleep, 0.0

    def get(self, url: str, attempts: int = 3) -> httpx.Response:
        last_exc: Optional[Exception] = None
        for i in range(attempts):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.http.get(url)
                if r.status_code in (429, 500, 502, 503, 504):
                    last_exc = httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                    self._sleep(1.5 * (i + 1))
                    continue
                r.raise_for_status()
                return r
            except httpx.TransportError as exc:
                last_exc = exc
                self._sleep(1.5 * (i + 1))
        raise last_exc or RuntimeError("request failed")

    def json(self, url: str) -> Any:
        return self.get(url).json()


# --------------------------------------------------------------- SEC: extraction (pure) --


def _days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _annual_rows(rows: List[Dict[str, Any]], instant: bool, keep_years: int = 9) -> List[Dict[str, Any]]:
    """Fiscal-year rows from 10-K filings, every filed version kept (a later restatement is a NEW version with a
    later `filed` date, which is exactly what makes as-of lookups honest)."""
    out = []
    for r in rows:
        if r.get("form") not in ANNUAL_FORMS or r.get("fp") != "FY" or "end" not in r or "filed" not in r or r.get("val") is None:
            continue
        if not instant:
            if "start" not in r or not 330 <= _days_between(r["start"], r["end"]) <= 400:
                continue
        out.append({"end": r["end"], "start": r.get("start"), "val": r["val"], "filed": r["filed"]})
    ends = sorted({r["end"] for r in out})[-keep_years:]
    return sorted((r for r in out if r["end"] in ends), key=lambda r: (r["end"], r["filed"]))


def extract_concepts(facts: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Compact per-concept annual series out of a companyfacts document (which can be several MB)."""
    gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    out: Dict[str, Dict[str, Any]] = {}
    for name, tags in CONCEPTS.items():
        best: Optional[Dict[str, Any]] = None
        for tag in tags:
            for unit, rows in ((gaap.get(tag) or {}).get("units") or {}).items():
                if unit not in UNITS:
                    continue
                series = _annual_rows(rows, name in INSTANT)
                if series and (best is None or series[-1]["end"] > best["series"][-1]["end"]):
                    best = {"tag": tag, "unit": unit, "series": series}
        if best:
            out[name] = best
    return out


_FILINGS_KEEP = 80


def extract_filings(sub: Dict[str, Any]) -> List[Dict[str, Any]]:
    rec = ((sub.get("filings") or {}).get("recent")) or {}
    forms, dates, items = rec.get("form") or [], rec.get("filingDate") or [], rec.get("items") or []
    out = []
    for i, (form, filed) in enumerate(zip(forms, dates)):
        raw = items[i] if i < len(items) else ""
        out.append({"form": form, "filed": filed, "items": [x.strip() for x in str(raw).split(",") if x.strip()]})
    return out[:_FILINGS_KEEP]


# ------------------------------------------------------------ SEC: point-in-time reads --


def _known(series: List[Dict[str, Any]], as_of: str) -> List[Tuple[str, float, str]]:
    """(end, value, filed) for each fiscal year end, using the LATEST version filed on or before `as_of`."""
    best: Dict[str, Dict[str, Any]] = {}
    for r in series:
        if r["filed"] <= as_of and (r["end"] not in best or r["filed"] >= best[r["end"]]["filed"]):
            best[r["end"]] = r
    return [(e, best[e]["val"], best[e]["filed"]) for e in sorted(best)]


def _prior(known: List[Tuple[str, float, str]]) -> Optional[Tuple[str, float, str]]:
    """The year-earlier entry for the latest one (fiscal year ends drift by a few days)."""
    if len(known) < 2:
        return None
    for e, v, f in reversed(known[:-1]):
        if 330 <= _days_between(e, known[-1][0]) <= 400:
            return (e, v, f)
    return None


def fundamentals_from_concepts(concepts: Dict[str, Dict[str, Any]], as_of: str, price: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Latest FULL fiscal year that had been filed by `as_of`: growth, margins, returns, leverage, cash flow, P/E.
    Anything the filer does not report under a standard tag is simply absent."""
    known = {k: _known(v["series"], as_of) for k, v in concepts.items()}
    known = {k: v for k, v in known.items() if v}
    if not known:
        return None
    rev = known.get("revenue")
    anchor = (rev or next(iter(known.values())))[-1]
    fy_end, filed = anchor[0], anchor[2]

    def latest(name: str) -> Optional[float]:
        k = known.get(name)
        return k[-1][1] if k else None

    def at(name: str) -> Optional[float]:  # the value for the SAME fiscal year as the anchor
        for e, v, _f in reversed(known.get(name, [])):
            if abs(_days_between(e, fy_end)) <= 20:
                return v
        return None

    out: Dict[str, Any] = {"fiscal_year_end": fy_end, "filed": filed, "age_days": _days_between(filed, as_of)}
    r_now, r_prev = at("revenue"), None
    if rev:
        p = _prior(rev)
        r_prev = p[1] if p else None
    ni, oi, eq, lia, ltd, ocf, capex, eps = (at(n) for n in ("net_income", "operating_income", "equity", "liabilities", "long_term_debt", "op_cash_flow", "capex", "eps"))
    if r_now and r_prev and r_prev > 0:
        out["revenue_growth"] = r_now / r_prev - 1
    if r_now and r_now > 0:
        if ni is not None:
            out["net_margin"] = ni / r_now
        if oi is not None:
            out["operating_margin"] = oi / r_now
        if ocf is not None and capex is not None:
            out["fcf_margin"] = (ocf - abs(capex)) / r_now
    if ni is not None and eq and eq > 0:
        out["roe"] = ni / eq
    if eq and eq > 0:
        if ltd is not None:
            out["debt_to_equity"] = ltd / eq
        elif lia is not None:
            out["liabilities_to_equity"] = lia / eq
    if eps is not None:
        out["eps"] = eps
        if price and eps > 0:
            out["pe"] = price / eps
    return out if len(out) > 3 else None


def fundamentals_line(f: Optional[Dict[str, Any]], price: Optional[float] = None) -> Optional[str]:
    if not f:
        return None
    bits = []
    if "revenue_growth" in f:
        bits.append(f"revenue {f['revenue_growth']:+.1%} year on year")
    if "net_margin" in f:
        bits.append(f"net margin {f['net_margin']:.1%}")
    if "operating_margin" in f:
        bits.append(f"operating margin {f['operating_margin']:.1%}")
    if "roe" in f:
        bits.append(f"return on equity {f['roe']:.0%}")
    if "fcf_margin" in f:
        bits.append(f"free-cash-flow margin {f['fcf_margin']:.1%}")
    if "debt_to_equity" in f:
        bits.append(f"long-term debt {f['debt_to_equity']:.2f}x equity")
    elif "liabilities_to_equity" in f:
        bits.append(f"liabilities {f['liabilities_to_equity']:.1f}x equity")
    if "pe" in f:
        bits.append(f"P/E {f['pe']:.1f} on last fiscal year's earnings")
    if not bits:
        return None
    return f"Fundamentals (fiscal year to {f['fiscal_year_end']}, filed {f['filed']}): " + ", ".join(bits) + "."


def events_from_filings(filings: List[Dict[str, Any]], as_of: str, days: int = 30) -> List[Dict[str, Any]]:
    lo = (date.fromisoformat(as_of) - timedelta(days=days)).isoformat()
    out = []
    for f in filings:
        if not (lo <= f["filed"] <= as_of):
            continue
        if f["form"] == "8-K":
            items = [i for i in f["items"] if i not in ITEM_IGNORED]
            if not items:
                continue
            what = "; ".join(ITEM_TEXT.get(i, f"item {i}") for i in items)
            out.append({"filed": f["filed"], "form": "8-K", "items": items, "text": what, "flag": any(i in ITEM_FLAGGED for i in items)})
        elif f["form"] in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
            out.append({"filed": f["filed"], "form": f["form"], "items": [], "text": "quarterly or annual report filed", "flag": False})
    return sorted(out, key=lambda e: e["filed"], reverse=True)


def events_line(events: List[Dict[str, Any]]) -> Optional[str]:
    if not events:
        return None
    parts = [f"{e['form']} {e['filed']} ({e['text']}){' [worth a look]' if e['flag'] else ''}" for e in events[:4]]
    return "Recent SEC filings (last 30 days): " + "; ".join(parts) + "."


# ------------------------------------------------------------------ macro (pure parts) --


def parse_treasury_csv(text: str) -> List[Dict[str, Any]]:
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            m, d_, y = r["Date"].split("/")
            iso = f"{int(y):04d}-{int(m):02d}-{int(d_):02d}"
            row = {"date": iso}
            for label, key in (("3 Mo", "y3m"), ("2 Yr", "y2"), ("10 Yr", "y10")):
                if r.get(label) not in (None, ""):
                    row[key] = float(r[label])
            if len(row) > 1:
                rows.append(row)
        except (KeyError, ValueError):
            continue
    return sorted(rows, key=lambda r: r["date"])


def parse_bls(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        data = payload["Results"]["series"][0]["data"]
    except (KeyError, IndexError, TypeError):
        return []
    out = []
    for d_ in data:
        p = str(d_.get("period", ""))
        if re.fullmatch(r"M(0[1-9]|1[0-2])", p) and d_.get("value") not in (None, "", "-"):
            try:
                out.append({"month": f"{int(d_['year']):04d}-{p[1:]}", "value": float(d_["value"])})
            except (ValueError, KeyError):
                continue
    return sorted(out, key=lambda r: r["month"])


def _shift_month(month: str, delta: int) -> str:
    idx = int(month[:4]) * 12 + (int(month[5:7]) - 1) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _released(month: str, as_of: str, lag_days: int) -> bool:
    y, m = int(month[:4]), int(month[5:7])
    end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
    return end + timedelta(days=lag_days) <= date.fromisoformat(as_of)


def macro_from_cache(cache: Optional[Dict[str, Any]], as_of: str) -> Optional[Dict[str, Any]]:
    if not cache:
        return None
    out: Dict[str, Any] = {}
    tre = [r for r in cache.get("treasury", []) if r["date"] <= as_of]
    if tre:
        now = tre[-1]
        old = next((r for r in reversed(tre) if _days_between(r["date"], now["date"]) >= 90), None)
        out["treasury_date"] = now["date"]
        for k in ("y3m", "y2", "y10"):
            if k in now:
                out[k] = now[k]
        if "y10" in now and "y2" in now:
            out["curve_10y_2y"] = now["y10"] - now["y2"]
        if old and "y10" in now and "y10" in old:
            out["y10_change_3m"] = now["y10"] - old["y10"]
    for name in ("unemployment", "cpi"):
        rows = {r["month"]: r["value"] for r in (cache.get("bls") or {}).get(name, []) if _released(r["month"], as_of, BLS_LAG_DAYS[name])}
        if not rows:
            continue
        month = max(rows)
        if name == "unemployment":
            out["unemployment"], out["unemployment_month"] = rows[month], month
            if _shift_month(month, -6) in rows:
                out["unemployment_6m_ago"] = rows[_shift_month(month, -6)]
        else:
            year_ago = rows.get(_shift_month(month, -12))
            if year_ago:
                out["cpi_yoy"], out["cpi_month"] = rows[month] / year_ago - 1, month
    return out or None


def macro_line(m: Optional[Dict[str, Any]]) -> Optional[str]:
    if not m:
        return None
    bits = []
    if "y10" in m:
        chg = f" ({m['y10_change_3m']:+.2f} pts over 3 months)" if "y10_change_3m" in m else ""
        bits.append(f"10-year Treasury {m['y10']:.2f}%{chg}")
    if "curve_10y_2y" in m:
        c = m["curve_10y_2y"]
        bits.append(f"yield curve (10y minus 2y) {c:+.2f} pts ({'inverted' if c < 0 else 'normal'})")
    if "unemployment" in m:
        prev = f", was {m['unemployment_6m_ago']:.1f}% six months earlier" if "unemployment_6m_ago" in m else ""
        bits.append(f"unemployment {m['unemployment']:.1f}% ({m['unemployment_month']}{prev})")
    if "cpi_yoy" in m:
        bits.append(f"consumer prices {m['cpi_yoy']:+.1%} year on year ({m['cpi_month']})")
    return ("Macro backdrop: " + "; ".join(bits) + ".") if bits else None


# ------------------------------------------------------------------- cache readers --


def fundamentals_as_of(sym: str, as_of: str, price: Optional[float] = None) -> Optional[Dict[str, Any]]:
    c = _read(f"fundamentals/{sym}.json")
    return fundamentals_from_concepts(c["concepts"], as_of, price) if c and c.get("concepts") else None


def events_as_of(sym: str, as_of: str, days: int = 30) -> List[Dict[str, Any]]:
    c = _read(f"filings/{sym}.json")
    return events_from_filings(c["filings"], as_of, days) if c and c.get("filings") else []


def macro_as_of(as_of: str) -> Optional[Dict[str, Any]]:
    return macro_from_cache(_read("macro.json"), as_of)


def context_lines(sym: str, as_of: str, price: Optional[float] = None) -> List[str]:
    """Extra prompt lines for one symbol on one date, from the cache only. Never raises, never touches the network."""
    lines: List[Optional[str]] = []
    try:
        lines.append(fundamentals_line(fundamentals_as_of(sym, as_of, price)))
        lines.append(events_line(events_as_of(sym, as_of)))
        lines.append(insider_line(insider_events_as_of(sym, as_of)))
        lines.append(macro_line(macro_as_of(as_of)))
    except Exception:  # noqa: BLE001 -- extra context must never break a review
        log.warning("free-data context unavailable for %s", sym)
    return [ln for ln in lines if ln]


def snapshot(symbols: List[str], as_of: str, prices: Dict[str, Optional[float]]) -> Dict[str, Any]:
    """Everything the admin's data panel shows."""
    rows = []
    for s in symbols:
        f = fundamentals_as_of(s, as_of, prices.get(s))
        ev = events_as_of(s, as_of)
        rows.append({"symbol": s, "fundamentals": f, "events": ev[:5], "insiders": insider_events_as_of(s, as_of)[:5]})
    return {"as_of": as_of, "rows": rows, "macro": macro_as_of(as_of), "macro_line": macro_line(macro_as_of(as_of)), "status": read_status(), "sec_configured": sec_user_agent() is not None}


# ---------------------------------------------------------------------------- refresh --


def _refresh_treasury(http: Fetcher, status: Dict[str, Any], today: date) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for year in (today.year - 1, today.year):
        rows += parse_treasury_csv(http.get(TREASURY_URL.format(year=year)).text)
    if not rows:
        raise ValueError("no yield-curve rows parsed")
    return rows


def refresh_macro(http: Optional[Fetcher] = None, today: Optional[date] = None) -> Dict[str, Any]:
    http = http or Fetcher()
    today = today or _now().date()
    status = read_status()
    cache = _read("macro.json") or {"treasury": [], "bls": {}}
    try:
        cache["treasury"] = _refresh_treasury(http, status, today)
        _set_status(status, "treasury", True, f"through {cache['treasury'][-1]['date']}", len(cache["treasury"]))
    except Exception as exc:  # noqa: BLE001 -- each source fails on its own
        _set_status(status, "treasury", False, f"{type(exc).__name__}: {exc}"[:200])
    for name, series in BLS_SERIES.items():
        try:
            rows = parse_bls(http.json(BLS_URL.format(series=series)))
            if not rows:
                raise ValueError("no rows parsed")
            cache.setdefault("bls", {})[name] = rows
            _set_status(status, f"bls_{name}", True, f"through {rows[-1]['month']}", len(rows))
        except Exception as exc:  # noqa: BLE001
            _set_status(status, f"bls_{name}", False, f"{type(exc).__name__}: {exc}"[:200])
    cache["fetched_at"] = _now().isoformat()
    _write("macro.json", cache)
    _write("status.json", status)
    return status


def refresh_sec(symbols: List[str], sec: Optional[Fetcher] = None, force: bool = False) -> Dict[str, Any]:
    status = read_status()
    ua = sec_user_agent()
    if sec is None:
        if not ua:
            _set_status(status, "sec", False, "not configured: set SEC_USER_AGENT to a string with a contact email (SEC fair-access policy)")
            _write("status.json", status)
            return status
        sec = Fetcher({"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, SEC_MIN_INTERVAL_S)
    tmap = _read("sec_tickers.json")
    try:
        if not _fresh(tmap, TICKER_MAP_TTL_DAYS) or force:
            raw = sec.json(SEC_TICKERS_URL)
            tmap = {"fetched_at": _now().isoformat(), "map": {v["ticker"].upper(): int(v["cik_str"]) for v in raw.values()}}
            _write("sec_tickers.json", tmap)
    except Exception as exc:  # noqa: BLE001
        _set_status(status, "sec", False, f"ticker map: {type(exc).__name__}: {exc}"[:200])
        _write("status.json", status)
        return status
    ciks = tmap["map"]
    ok, skipped, no_facts, failed = 0, [], [], []
    for s in symbols:
        cik = ciks.get(s.upper().replace(".", "-")) or ciks.get(s.upper())
        if not cik:
            skipped.append(s)  # not in the ticker map at all: a fund or other non-filer
            continue
        # Company facts (XBRL) and submissions are two independent endpoints: a trust/fund can have a real
        # CIK and file 8-Ks (submissions) while having no XBRL financial concepts (companyfacts 404s). One
        # missing does not mean the other should be thrown away.
        try:
            cached = _read(f"fundamentals/{s}.json")
            if force or not _fresh(cached, FUNDAMENTALS_TTL_DAYS):
                concepts = extract_concepts(sec.json(SEC_FACTS_URL.format(cik=cik)))
                _write(f"fundamentals/{s}.json", {"cik": cik, "fetched_at": _now().isoformat(), "concepts": concepts})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                no_facts.append(s)  # a real filer with no XBRL facts (e.g. a fund/trust) -- not an error
            else:
                failed.append(f"{s}: {type(exc).__name__}")
                continue
        except Exception as exc:  # noqa: BLE001 -- one company failing must not stop the rest
            failed.append(f"{s}: {type(exc).__name__}")
            continue
        try:
            _write(f"filings/{s}.json", {"cik": cik, "fetched_at": _now().isoformat(), "filings": extract_filings(sec.json(SEC_SUBMISSIONS_URL.format(cik=cik)))})
            ok += 1
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{s}: {type(exc).__name__}")
    detail = (
        f"{ok} companies refreshed"
        + (f"; no filings for {', '.join(skipped)} (funds)" if skipped else "")
        + (f"; no XBRL facts for {', '.join(no_facts)} (fund/trust)" if no_facts else "")
        + (f"; FAILED {', '.join(failed)}" if failed else "")
    )
    _set_status(status, "sec", not failed and ok > 0, detail, ok)
    _write("status.json", status)
    return status


# ------------------------------------------------------ SEC: Form 4 insider transactions --


def _num(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _form4_filings(sec: Fetcher, cik: int) -> List[Dict[str, str]]:
    """Recent Form 4 filings for this issuer's CIK: accession number, filed date, and the filing's own
    directory (where its primary XML document lives)."""
    root = ET.fromstring(sec.get(FORM4_INDEX_URL.format(cik=cik)).text)
    out = []
    for entry in root.findall("a:entry", _ATOM_NS):
        content = entry.find("a:content", _ATOM_NS)
        if content is None:
            continue
        acc = content.findtext("a:accession-number", namespaces=_ATOM_NS)
        filed = content.findtext("a:filing-date", namespaces=_ATOM_NS)
        href = content.findtext("a:filing-href", namespaces=_ATOM_NS)
        if acc and filed and href:
            out.append({"accession": acc, "filed": filed, "dir": href.rsplit("/", 1)[0]})
    return out


def _form4_transactions(sec: Fetcher, dir_url: str) -> List[Dict[str, Any]]:
    """Open-market (non-derivative) BUY/SELL lines out of one Form 4's primary XML document. The
    document's filename varies by filer agent (`form4.xml`, `wk-form4_....xml`, ...), so it is found
    from the filing's own directory listing rather than guessed."""
    items = (sec.json(f"{dir_url}/index.json").get("directory") or {}).get("item") or []
    doc = next((i["name"] for i in items if i["name"].endswith(".xml") and i.get("size")), None)
    if not doc:
        return []
    root = ET.fromstring(sec.get(f"{dir_url}/{doc}").text)
    owner = (root.findtext("reportingOwner/reportingOwnerId/rptOwnerName") or "").strip()
    out = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = t.findtext("transactionCoding/transactionCode")
        if code not in OPEN_MARKET_CODES:
            continue
        d = t.findtext("transactionDate/value")
        shares = _num(t.findtext("transactionAmounts/transactionShares/value"))
        if not d or shares is None:
            continue
        price = _num(t.findtext("transactionAmounts/transactionPricePerShare/value"))
        out.append({"date": d, "owner": owner, "code": code, "side": OPEN_MARKET_CODES[code], "shares": shares, "value": (shares * price) if price else None})
    return out


def refresh_insiders(symbols: List[str], sec: Optional[Fetcher] = None, force: bool = False) -> Dict[str, Any]:
    """Form 4 open-market insider buys/sells, cached incrementally: each run only fetches filings not
    already seen (`cache["seen"]`), so a quiet company costs one ATOM request, not a re-parse of its
    whole history. See the module docstring for why this exists in place of a news/sentiment feed."""
    status = read_status()
    ua = sec_user_agent()
    if sec is None:
        if not ua:
            _set_status(status, "insiders", False, "not configured: set SEC_USER_AGENT (SEC fair-access policy)")
            _write("status.json", status)
            return status
        sec = Fetcher({"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, SEC_MIN_INTERVAL_S)
    tmap = _read("sec_tickers.json")
    try:
        if not _fresh(tmap, TICKER_MAP_TTL_DAYS) or force:
            raw = sec.json(SEC_TICKERS_URL)
            tmap = {"fetched_at": _now().isoformat(), "map": {v["ticker"].upper(): int(v["cik_str"]) for v in raw.values()}}
            _write("sec_tickers.json", tmap)
    except Exception as exc:  # noqa: BLE001
        _set_status(status, "insiders", False, f"ticker map: {type(exc).__name__}: {exc}"[:200])
        _write("status.json", status)
        return status
    ciks = tmap["map"]
    ok, no_cik, failed = 0, [], []
    for s in symbols:
        cik = ciks.get(s.upper().replace(".", "-")) or ciks.get(s.upper())
        if not cik:
            no_cik.append(s)  # funds and other non-filers: same set refresh_sec skips, for the same reason
            continue
        cache = _read(f"insiders/{s}.json") or {"seen": [], "transactions": []}
        try:
            filings = _form4_filings(sec, cik)
        except Exception as exc:  # noqa: BLE001 -- one company failing must not stop the rest
            failed.append(f"{s}: {type(exc).__name__}")
            continue
        new = [f for f in filings if f["accession"] not in cache["seen"]][:INSIDER_NEW_PER_RUN]
        for f in new:
            try:
                cache["transactions"] += _form4_transactions(sec, f["dir"])
            except Exception as exc:  # noqa: BLE001 -- one filing failing must not lose what is already cached
                log.warning("Form 4 %s (%s) failed: %s", f["accession"], s, exc)
            cache["seen"].append(f["accession"])  # mark seen even on failure/no BUY-SELL: never re-parsed
        cutoff = (_now().date() - timedelta(days=INSIDER_KEEP_DAYS)).isoformat()
        cache["transactions"] = [t for t in cache["transactions"] if t["date"] >= cutoff]
        cache["seen"] = cache["seen"][-500:]
        cache["fetched_at"] = _now().isoformat()
        _write(f"insiders/{s}.json", cache)
        ok += 1
    detail = f"{ok} companies checked" + (f"; no CIK for {', '.join(no_cik)}" if no_cik else "") + (f"; FAILED {', '.join(failed)}" if failed else "")
    _set_status(status, "insiders", not failed and ok > 0, detail, ok)
    _write("status.json", status)
    return status


def insider_events_as_of(sym: str, as_of: str, lookback_days: int = INSIDER_LOOKBACK_DAYS) -> List[Dict[str, Any]]:
    """Open-market Form 4 transactions filed on or before `as_of`, within the lookback window -- point
    in time, like every other free_data read."""
    cache = _read(f"insiders/{sym}.json")
    if not cache:
        return []
    cutoff = (date.fromisoformat(as_of) - timedelta(days=lookback_days)).isoformat()
    return sorted((t for t in cache.get("transactions", []) if cutoff <= t["date"] <= as_of), key=lambda t: t["date"], reverse=True)


def _insider_side(rows: List[Dict[str, Any]], singular: str, plural: str) -> str:
    n = len(rows)
    val = sum(r["value"] for r in rows if r.get("value"))
    owners = len({r["owner"] for r in rows if r.get("owner")})
    bit = f"{n} {singular if n == 1 else plural}"
    if val:
        bit += f" (~${val:,.0f})"
    if owners:
        bit += f" by {owners} insider{'s' if owners != 1 else ''}"
    return bit


def insider_line(events: List[Dict[str, Any]]) -> Optional[str]:
    if not events:
        return None
    buys = [e for e in events if e["side"] == "purchase"]
    sells = [e for e in events if e["side"] == "sale"]
    parts = [p for p in (_insider_side(buys, "purchase", "purchases") if buys else None, _insider_side(sells, "sale", "sales") if sells else None) if p]
    return f"Insider activity (Form 4 open-market, last {INSIDER_LOOKBACK_DAYS} days): " + "; ".join(parts) + "."


def refresh_all(symbols: List[str], force: bool = False) -> Dict[str, Any]:
    refresh_macro()
    refresh_sec(symbols, force=force)
    return refresh_insiders(symbols, force=force)
