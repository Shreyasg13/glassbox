"""S3 T2: the honest "before" number. How far are today's committee outputs from their own source data?

Read-only: audits the committee runs ALREADY STORED, with no new model calls (an LLM asked to make calls on past dates is
forbidden by the plan, and unnecessary here: every run stores the exact context the analysts were given and what they wrote).

    python -m app.scripts.baseline_discrepancy --csv baseline.csv --json summary.json
    python -m app.scripts.baseline_discrepancy --from-json summary.json --markdown docs/s3/baseline.md

Three parts, reported separately because they answer different questions:

  A. CONTEXT FIDELITY. The numbers the committee is told (price, moves, distance from highs, RSI, engine signal, risk regime, volatility,
     macro line) are recomputed INDEPENDENTLY from the raw price rows and compared. Everything that cannot be recomputed here (backtest
     Sharpe, win rate, correlations, volatility percentile) is counted as "not independently checked", never as passed.
  B. HEADLINE. The deterministic CEO headline's "N% of the vote weight" must equal the stored consensus.
  C. LLM PROSE. Every number an AI analyst wrote must be traceable to the context that analyst was given (matching after rounding and
     ignoring sign). A number that is not is "unsupported": either invented or derived by arithmetic. This is the number S3's A6 gate
     exists to drive down.

Limits, stated so the number is not over-read: small whole numbers (10 or less) and years are treated as wording, not claims; the
per-analyst "reflection" note some analysts receive is not stored, so a number quoted from it would be counted unsupported.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

_DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
_NUM = re.compile(r"(?<![\w.])([-+]?)\$?(\d(?:[\d,]*\d)?)(\.\d+)?(?:st|nd|rd|th)?(%|x)?")  # commas only BETWEEN digits, so "227," is 227
REL_TOL = 0.005  # a claim within 0.5% of a source figure counts as the same figure


@dataclass(frozen=True)
class Num:
    value: float
    decimals: int
    text: str
    pct: bool

    @property
    def wording(self) -> bool:
        """Whole numbers up to 10 and years read as words ("7 analysts", "2026"), not as data claims."""
        return (not self.pct and self.decimals == 0 and (abs(self.value) <= 10 or 1900 <= abs(self.value) <= 2100))


def numbers(text: str) -> List[Num]:
    out = []
    for m in _NUM.finditer(_DATE.sub(" ", text or "")):
        sign, whole, frac, unit = m.groups()
        try:
            v = float(whole.replace(",", "") + (frac or ""))
        except ValueError:
            continue
        out.append(Num(-v if sign == "-" else v, len((frac or ".")[1:]), m.group(0), unit == "%"))
    return out


def same_figure(x: Num, c: Num) -> bool:
    """True if `x` is the source figure `c`, allowing for rounding, a dropped sign ("1.2% below" vs "-1.2%") and formatting."""
    ax, ac = abs(x.value), abs(c.value)
    d = min(x.decimals, c.decimals)
    if abs(round(ax, d) - round(ac, d)) < 1e-9:
        return True
    return ac != 0 and abs(ax - ac) / ac <= REL_TOL


def unsupported(prose: str, context: str) -> List[Num]:
    """Numbers in `prose` (claims only) that no figure in `context` accounts for."""
    ctx = numbers(context)
    return [n for n in numbers(prose) if not n.wording and not any(same_figure(n, c) for c in ctx)]


# ------------------------------------------------------------------ part A --


def _text_status(claimed: Optional[str], expected: str) -> str:
    """A label the context does not contain at all is 'not_found' (the older context format), not a wrong value."""
    return "not_found" if claimed is None else ("verified" if claimed == expected else "mismatch")


def _f(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text)
    return float(m.group(1).replace(",", "")) if m else None


def context_checks(run: Dict[str, Any], book, risk_at, macro_line_for) -> List[Dict[str, Any]]:
    """[{check, claimed, expected, status}] for one run. Independent recomputation from the raw closes."""
    sym, d, ctx = run["symbol"], run["date"], run.get("context") or ""
    rows: List[Dict[str, Any]] = []

    def add(check: str, claimed: Optional[float], expected: Optional[float], tol: float) -> None:
        if claimed is None or expected is None:
            rows.append({"check": check, "claimed": claimed, "expected": expected, "status": "not_found" if claimed is None else "not_recomputable"})
            return
        gap = abs(claimed - expected)
        rows.append({"check": check, "claimed": claimed, "expected": round(expected, 6), "gap": round(gap, 6), "tol": tol, "status": "verified" if gap <= tol + 1e-9 else "mismatch"})

    dates = book._sorted_dates.get(sym) or []
    if d not in book.close.get(sym, {}):
        return [{"check": "run date in price data", "claimed": d, "expected": None, "status": "mismatch"}]
    i = dates.index(d)
    closes = [book.close[sym][x] for x in dates[: i + 1]]
    px = closes[-1]

    def ret(n: int) -> Optional[float]:
        return px / closes[-1 - n] - 1 if len(closes) > n else None

    add("last price", _f(r"Last price (\d[\d,]*(?:\.\d+)?)", ctx), px, 0.005)
    for n in (1, 5, 20):
        claimed = _f(rf"{n}-day ([+-]\d+(?:\.\d+)?)%", ctx)
        add(f"{n}-day move %", claimed, None if ret(n) is None else ret(n) * 100, 0.05)
    win60 = closes[-60:]
    add("distance from 60-day high %", _f(r"([+-]\d+(?:\.\d+)?)% from its 60-day high", ctx), (px / max(win60) - 1) * 100, 0.05)
    win252 = closes[-252:]
    add("distance from 252-day high %", _f(r"([+-]\d+(?:\.\d+)?)% from its 252-day high", ctx), (px / max(win252) - 1) * 100, 0.05)
    rets = [b / a - 1 for a, b in zip(closes[-21:], closes[-20:])]
    if len(rets) > 2:
        mean = sum(rets) / len(rets)
        vol = (sum((x - mean) ** 2 for x in rets) / max(len(rets) - 1, 1)) ** 0.5 * math.sqrt(252)
        add("20-day volatility %", _f(r"20-day volatility (\d+(?:\.\d+)?)%", ctx), vol * 100, 0.5)
    sig = (book.signal.get(sym, {}) or {}).get(d)
    if sig:
        add("RSI", _f(r"RSI (\d+(?:\.\d+)?)", ctx), float(sig[2]), 0.05)
        add("engine confidence %", _f(r"confidence (\d+(?:\.\d+)?)%", ctx), float(sig[1]), 0.5)
        m = re.search(r"Quant engine signal: (BUY|SELL|HOLD)", ctx)
        rows.append({"check": "engine signal", "claimed": m.group(1) if m else None, "expected": sig[0], "status": _text_status(m.group(1) if m else None, sig[0])})
    if len(closes) >= 200:
        above = px > sum(closes[-200:]) / 200
        m = re.search(r"price (above|below) its 200-day average", ctx)
        if m:
            rows.append({"check": "above/below 200-day average", "claimed": m.group(1), "expected": "above" if above else "below", "status": _text_status(m.group(1), "above" if above else "below")})
    rk = risk_at(book, sym, d)
    if rk:
        add("risk score", _f(r"score (\d+(?:\.\d+)?)/100", ctx), float(rk["score"]), 0.5)
        m = re.search(r"Risk regime \(rule-based, not a forecast\): (LOW|MEDIUM|HIGH)", ctx)
        rows.append({"check": "risk level", "claimed": m.group(1) if m else None, "expected": rk["level"], "status": _text_status(m.group(1) if m else None, rk["level"])})
    line = macro_line_for(d)
    if line:
        has_macro_section = "Macro backdrop" in ctx  # older contexts (the committee's first day) had no macro line at all
        rows.append({"check": "macro line (verbatim)", "claimed": "present" if line in ctx else "absent", "expected": "present", "status": "verified" if line in ctx else ("mismatch" if has_macro_section else "not_found")})
    for label in ("Sharpe", "win rate", "beta", "correlation", "percentile"):  # figures this audit cannot recompute: reported, never passed
        if re.search(label, ctx):
            rows.append({"check": f"{label} (not independently checked)", "claimed": None, "expected": None, "status": "not_checked"})
    return rows


# ------------------------------------------------------------------ part B --


def headline_check(run: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ceo = run.get("ceo") or {}
    m = re.search(r"(\d+)% of the vote weight", ceo.get("headline") or "")
    if not m or ceo.get("consensus") is None:
        return None
    exp = round(float(ceo["consensus"]) * 100)
    return {"check": "headline vote-weight %", "claimed": float(m.group(1)), "expected": float(exp), "gap": float(abs(int(m.group(1)) - exp)), "tol": 0.5, "status": "verified" if int(m.group(1)) == exp else "mismatch"}


# ---------------------------------------------------------------- the audit --


def audit(runs: List[Dict[str, Any]], book, risk_at, macro_line_for) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for r in runs:
        base = {"date": r["date"], "symbol": r["symbol"]}
        for c in context_checks(r, book, risk_at, macro_line_for):
            rows.append({**base, "part": "A", "source": "context", "detail": c["check"], "claimed": c["claimed"], "expected": c["expected"], "gap": c.get("gap"), "tol": c.get("tol"), "status": c["status"]})
        h = headline_check(r)
        if h:
            rows.append({**base, "part": "B", "source": "ceo.headline", "detail": h["check"], "claimed": h["claimed"], "expected": h["expected"], "gap": h.get("gap"), "tol": h.get("tol"), "status": h["status"]})
        for a in r.get("agents", []):
            if a.get("type") == "deterministic" or not a.get("ok") or not a.get("summary"):
                continue
            bad = unsupported(a["summary"], r.get("context") or "")
            bad_texts = Counter(n.text for n in bad)
            for n in numbers(a["summary"]):
                if n.wording:
                    continue
                status = "unsupported" if bad_texts.get(n.text, 0) > 0 else "supported"
                if status == "unsupported":
                    bad_texts[n.text] -= 1
                rows.append({**base, "part": "C", "source": f"analyst:{a.get('agent')}|{a.get('model', '')}", "detail": n.text, "claimed": n.value, "expected": None, "status": status})
    return {"rows": rows, "summary": summarise(rows, runs)}


def summarise(rows: List[Dict[str, Any]], runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    def material(r: Dict[str, Any]) -> bool:
        """A mismatch is 'rounding-level' when the gap is within twice the check's display tolerance (e.g. 0.1 of a percentage point)."""
        return r["status"] == "mismatch" and (r.get("gap") is None or r.get("tol") is None or r["gap"] > 2 * r["tol"] + 1e-9)

    def rate(part: str, bad: str, good: str) -> Dict[str, Any]:
        c = Counter(r["status"] for r in rows if r["part"] == part)
        n = c[bad] + c[good]
        mat = sum(1 for r in rows if r["part"] == part and material(r))
        return {"checked": n, "bad": c[bad], "bad_material": mat, "bad_rounding_level": c[bad] - mat if part != "C" else 0, "good": c[good], "rate": (c[bad] / n) if n else None,
                "rate_material": (mat / n) if n and part != "C" else None, "not_checked": c["not_checked"] + c["not_recomputable"] + c["not_found"]}

    per_agent, per_model, examples = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), []
    for r in rows:
        if r["part"] != "C":
            continue
        agent, _, model = r["source"].removeprefix("analyst:").partition("|")
        bad = r["status"] == "unsupported"
        for table, key in ((per_agent, agent), (per_model, model or "unknown")):
            table[key][0] += 1
            table[key][1] += bad
        if bad and len(examples) < 25:
            examples.append({"date": r["date"], "symbol": r["symbol"], "agent": agent, "number": r["detail"]})
    by_check = defaultdict(Counter)
    for r in rows:
        if r["part"] == "A":
            by_check[r["detail"]][r["status"]] += 1
    mism = [{"date": r["date"], "symbol": r["symbol"], "check": r["detail"], "claimed": r["claimed"], "expected": r["expected"], "gap": r.get("gap"), "material": material(r)} for r in rows if r["status"] == "mismatch"][:60]
    c_by_date: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    a_by_date: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["part"] == "C":
            c_by_date[r["date"]][0] += 1
            c_by_date[r["date"]][1] += r["status"] == "unsupported"
        elif r["part"] == "A" and r["status"] in ("verified", "mismatch"):
            a_by_date[r["date"]][0] += 1
            a_by_date[r["date"]][1] += r["status"] == "mismatch"
    return {
        "runs": len(runs),
        "dates": sorted({r["date"] for r in runs}),
        "A_context": {**rate("A", "mismatch", "verified"), "by_check": {k: dict(v) for k, v in sorted(by_check.items())}},
        "B_headline": rate("B", "mismatch", "verified"),
        "C_llm_prose": {**rate("C", "unsupported", "supported"), "analyst_rows": sum(1 for r in runs for a in r.get("agents", []) if a.get("type") != "deterministic" and a.get("ok") and a.get("summary"))},
        "C_by_date": {k: {"numbers": v[0], "unsupported": v[1], "rate": v[1] / v[0] if v[0] else None} for k, v in sorted(c_by_date.items())},
        "A_by_date": {k: {"checks": v[0], "mismatches": v[1], "rate": v[1] / v[0] if v[0] else None} for k, v in sorted(a_by_date.items())},
        "C_by_agent": {k: {"numbers": v[0], "unsupported": v[1], "rate": v[1] / v[0] if v[0] else None} for k, v in sorted(per_agent.items())},
        "C_by_model": {k: {"numbers": v[0], "unsupported": v[1], "rate": v[1] / v[0] if v[0] else None} for k, v in sorted(per_model.items())},
        "mismatches": mism,
        "examples_unsupported": examples,
    }


def render_markdown(s: Dict[str, Any]) -> str:
    pct = lambda r: "n/a" if r is None else f"{r:.1%}"  # noqa: E731
    if not s["runs"]:
        return "# S3 baseline (T2)\n\nNo committee runs are stored yet, so there is nothing to audit.\n"
    a, b, c = s["A_context"], s["B_headline"], s["C_llm_prose"]
    L = [
        "# S3 baseline: how far the committee's outputs are from their own source data (T2)",
        "",
        f"Audit of the **{s['runs']} committee runs stored so far** ({s['dates'][0]} to {s['dates'][-1]}), with **no new model calls**. This is the 'before' number every later S3 task is measured against. Reproduce it with `python -m app.scripts.baseline_discrepancy` (see that file's docstring for the exact rules and limits).",
        "",
        "## The headline numbers",
        "",
        "| Measure | Result | What it means |",
        "|---|---|---|",
        f"| **A. Context fidelity**: numbers the committee is told, recomputed from raw prices | **{pct(a['rate'])} differ** ({a['bad']} of {a['checked']} checks); **{pct(a['rate_material'])} by more than rounding** ({a['bad_material']}) | The deterministic code that writes the analysts' briefing |",
        f"| **B. Headline**: CEO vote-weight % vs the stored consensus | **{pct(b['rate'])} differ** ({b['bad']} of {b['checked']}); {b['bad_material']} by more than 1 point | The deterministic summary line |",
        f"| **C. AI prose**: numbers analysts wrote that trace to nothing in their briefing | **{pct(c['rate'])} unsupported** ({c['bad']} of {c['checked']} numbers, {c['analyst_rows']} analyst write-ups) | The gap the A6 gate exists to close |",
        f"| Figures this audit could NOT recompute (Sharpe, win rate, beta, correlations, percentiles) | {a['not_checked']} occurrences | Reported as unchecked, never counted as passed |",
        "",
        "## A. Context fidelity, by check",
        "",
        "| Check | verified | mismatch | not recomputable / not found |",
        "|---|---:|---:|---:|",
    ]
    for k, v in a["by_check"].items():
        L.append(f"| {k} | {v.get('verified', 0)} | {v.get('mismatch', 0)} | {v.get('not_checked', 0) + v.get('not_recomputable', 0) + v.get('not_found', 0)} |")
    if s["mismatches"]:
        L += ["", "First mismatches (claimed vs recomputed):", "", "| Date | Symbol | Check | Claimed | Recomputed |", "|---|---|---|---:|---:|"]
        L += [f"| {m['date']} | {m['symbol']} | {m['check']} | {m['claimed']} | {m['expected']} |" for m in s["mismatches"][:15]]
    L += ["", "## By day (read this before trusting any single rate)", "", "| Day | A: checks | A: differ | C: numbers | C: unsupported | C rate |", "|---|---:|---:|---:|---:|---:|"]
    for day in s["dates"]:
        av, cv = s["A_by_date"].get(day, {}), s["C_by_date"].get(day, {})
        L.append(f"| {day} | {av.get('checks', 0)} | {av.get('mismatches', 0)} | {cv.get('numbers', 0)} | {cv.get('unsupported', 0)} | {pct(cv.get('rate'))} |")
    L += ["", "## C. AI prose, by analyst and by model (all days)", "", "| Analyst | numbers written | unsupported | rate |", "|---|---:|---:|---:|"]
    L += [f"| {k} | {v['numbers']} | {v['unsupported']} | {pct(v['rate'])} |" for k, v in s["C_by_agent"].items()]
    L += ["", "| Model that answered | numbers written | unsupported | rate |", "|---|---:|---:|---:|"]
    L += [f"| {k} | {v['numbers']} | {v['unsupported']} | {pct(v['rate'])} |" for k, v in s["C_by_model"].items()]
    L += ["", "First unsupported numbers (an analyst wrote a figure that is not in its briefing):", "", "| Date | Symbol | Analyst | Number |", "|---|---|---|---|"]
    L += [f"| {e['date']} | {e['symbol']} | {e['agent']} | `{e['number']}` |" for e in s["examples_unsupported"][:20]]
    L += [
        "",
        "## How to read this honestly",
        "",
        "- **Unsupported does not always mean invented.** An analyst may add two figures from its briefing, or quote a note it received that is not stored. What matters for S3 is that a reader cannot trace the figure, which is exactly what the A6 gate will require.",
        "- Whole numbers up to 10 and years are treated as wording, not claims. A fabricated small number would be missed.",
        "- A. can only prove what it can recompute; the rest is listed as not independently checked.",
        f"- The sample is small ({s['runs']} runs over {len(s['dates'])} trading days) and all of it is live, forward-recorded data. Treat the rates as a starting point, not a stable estimate.",
        "- The full per-number results are in `docs/s3/baseline.csv`.",
    ]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------- CLI --


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Baseline discrepancy audit of the stored committee runs (S3 T2).")
    p.add_argument("--csv", help="write the per-number results here")
    p.add_argument("--json", help="write the summary here")
    p.add_argument("--from-json", help="render from a summary file instead of auditing (no database needed)")
    p.add_argument("--markdown", help="write the markdown report here")
    args = p.parse_args(argv)
    if args.from_json:
        summary = json.load(open(args.from_json, encoding="utf-8"))
        rows: List[Dict[str, Any]] = []
    else:
        from app import db, free_data, paper_cycle, risk

        book = paper_cycle.load_book()
        runs = sorted(db.list_all_committee_runs(), key=lambda r: (r["date"], r["symbol"]))
        out = audit(runs, book, risk.risk_at, lambda d: free_data.macro_line(free_data.macro_as_of(d)))
        rows, summary = out["rows"], out["summary"]
    if args.csv and rows:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["date", "symbol", "part", "source", "detail", "claimed", "expected", "gap", "tol", "status"], restval="")
            w.writeheader()
            w.writerows(rows)
    if args.json:
        json.dump(summary, open(args.json, "w", encoding="utf-8"), indent=2, default=str)
    if args.markdown:
        open(args.markdown, "w", encoding="utf-8").write(render_markdown(summary))
    print(json.dumps({k: summary[k] for k in ("runs", "A_context", "B_headline", "C_llm_prose")}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
