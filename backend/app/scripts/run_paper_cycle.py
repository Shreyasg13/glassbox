"""Runs the daily paper-trading cycle (see app/paper_cycle.py).

    python -m app.scripts.run_paper_cycle --bootstrap     # once: backfill history + create accounts
    python -m app.scripts.run_paper_cycle                 # every weekday, after the data sync
    python -m app.scripts.run_paper_cycle --dry-run       # compute, print, save nothing

Cron (host crontab, 15 minutes after the market-data sync at 22:00 UTC):

    15 22 * * 1-5 cd /home/shrey/glassbox && /usr/bin/docker compose exec -T backend python -m app.scripts.run_paper_cycle >> /home/shrey/glassbox/logs/paper_cycle.log 2>&1

Idempotent: running it twice on the same data processes nothing the second time.
Exit code 0 = ran (or nothing new), 1 = could not run.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .. import paper_cycle

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_paper_cycle")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the paper-trading cycle.")
    parser.add_argument("--bootstrap", action="store_true", help="first run only: create accounts and backfill the backtest")
    parser.add_argument("--start", help=f"backtest start date YYYY-MM-DD (bootstrap only; default {paper_cycle.BACKTEST_START})")
    parser.add_argument("--dry-run", action="store_true", help="compute and print, but save nothing")
    args = parser.parse_args(argv)
    try:
        result = paper_cycle.run_cycle(bootstrap=args.bootstrap, start=args.start, dry_run=args.dry_run)
    except paper_cycle.CycleError as exc:
        log.error("%s", exc)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
