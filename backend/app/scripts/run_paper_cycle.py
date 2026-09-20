"""Runs the daily paper-trading cycle (see app/paper_cycle.py).

    python -m app.scripts.run_paper_cycle --bootstrap     # once: backfill history + create accounts
    python -m app.scripts.run_paper_cycle                 # every weekday, after the data sync
    python -m app.scripts.run_paper_cycle --dry-run       # compute, print, save nothing
    python -m app.scripts.run_paper_cycle --rebuild       # replay every account from scratch and check it matches (writes nothing)
    python -m app.scripts.run_paper_cycle --rebuild --apply   # ...and replace the accounts whose replay matched to the cent

Cron (host crontab, AFTER the committee review, which starts 15 minutes after the market-data sync at 22:00 UTC --
the committee's calls feed the "Committee on all symbols" account, so they must exist before this runs):

    45 22 * * 1-5 cd /home/shrey/glassbox && /usr/bin/docker compose exec -T backend python -m app.scripts.run_paper_cycle >> /home/shrey/glassbox/logs/paper_cycle.log 2>&1

Idempotent: running it twice on the same data processes nothing the second time.
Exit code 0 = ran (or nothing new), 1 = could not run.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from .. import paper_cycle
from ..logging_config import quiet_http_clients

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
quiet_http_clients()  # httpx INFO lines carry the Gemini ?key= URL
log = logging.getLogger("run_paper_cycle")


def _wait_for_committee(max_wait_s: float = 1800.0, poll_s: float = 20.0) -> None:
    """The committee's decisions feed one paper account, so let a review that is still running finish first."""
    from .. import committee_daily

    waited = 0.0
    while waited < max_wait_s and committee_daily.is_running():
        if waited == 0:
            log.info("committee review in progress; waiting for it before the paper cycle")
        time.sleep(poll_s)
        waited += poll_s


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the paper-trading cycle.")
    parser.add_argument("--bootstrap", action="store_true", help="first run only: create accounts and backfill the backtest")
    parser.add_argument("--start", help=f"backtest start date YYYY-MM-DD (bootstrap only; default {paper_cycle.BACKTEST_START})")
    parser.add_argument("--dry-run", action="store_true", help="compute and print, but save nothing")
    parser.add_argument("--rebuild", action="store_true", help="replay every account from scratch and verify it reproduces the stored curve")
    parser.add_argument("--apply", action="store_true", help="with --rebuild: replace the accounts whose replay matched")
    args = parser.parse_args(argv)
    try:
        if args.rebuild:
            print(json.dumps(paper_cycle.rebuild_accounts(apply=args.apply), indent=2))
            return 0
        if not (args.dry_run or args.bootstrap):
            _wait_for_committee()
        result = paper_cycle.run_cycle(bootstrap=args.bootstrap, start=args.start, dry_run=args.dry_run)
    except paper_cycle.CycleError as exc:
        log.error("%s", exc)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
