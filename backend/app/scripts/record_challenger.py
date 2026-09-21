"""Record an outside challenger's daily calls for the arena (see app/arena.py).

    # one call
    python -m app.scripts.record_challenger --source tradingagents --date 2026-09-21 --symbol NVDA --decision BUY

    # a whole day from a file: {"NVDA": "BUY", "AAPL": "HOLD"}  or  [{"symbol": "NVDA", "decision": "BUY", "note": "..."}]
    python -m app.scripts.record_challenger --source tradingagents --date 2026-09-21 --file today.json

    # what is on record
    python -m app.scripts.record_challenger --list

The next paper cycle creates (or advances) the account "Challenger: <source>", which trades exactly on these calls,
and the Research tab judges it with the same live evidence gate as our own strategies. Exit code 1 on invalid input;
symbols or calls that cannot be read are reported and skipped, never guessed.
"""
from __future__ import annotations

import argparse
import json
import sys

from .. import arena


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Record a challenger's calls for the arena.")
    p.add_argument("--source", help="challenger name, e.g. tradingagents")
    p.add_argument("--date", help="the date the calls are for, YYYY-MM-DD (not in the future)")
    p.add_argument("--file", help="JSON file: {symbol: decision} or [{symbol, decision, ...}]")
    p.add_argument("--symbol")
    p.add_argument("--decision")
    p.add_argument("--list", action="store_true", help="show what is on record")
    a = p.parse_args(argv)
    if a.list:
        print(json.dumps(arena.summary(a.source), indent=2))
        return 0
    if not (a.source and a.date and (a.file or (a.symbol and a.decision))):
        p.error("need --source and --date plus either --file or --symbol with --decision")
    try:
        decisions = json.load(open(a.file, encoding="utf8")) if a.file else {a.symbol: a.decision}
        out = arena.record(a.source, a.date, decisions)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0 if out["recorded"] else 1


if __name__ == "__main__":
    sys.exit(main())
