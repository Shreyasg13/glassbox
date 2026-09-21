"""Writes the weekly research digest (see app/research.py).

    python -m app.scripts.run_weekly_research             # write this week's digest to Admin -> Reports
    python -m app.scripts.run_weekly_research --dry-run   # print it, write nothing

Cron (host crontab): Friday evening, after the committee (22:15) and the paper cycle (22:45) have finished:

    30 23 * * 5 cd /home/shrey/glassbox && /usr/bin/docker compose exec -T backend python -m app.scripts.run_weekly_research >> /home/shrey/glassbox/logs/weekly_research.log 2>&1

Idempotent: one digest per week (keyed by the latest data date). It only reads and reports; it never
changes an agent, a weight or a strategy.
"""
from __future__ import annotations

import argparse
import logging
import sys

from .. import research

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_weekly_research")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the weekly research digest.")
    parser.add_argument("--dry-run", action="store_true", help="print the digest, write nothing")
    args = parser.parse_args(argv)
    try:
        out = research.run_weekly(dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001 -- cron: log and exit non-zero rather than a traceback
        log.error("weekly research failed: %s: %s", type(exc).__name__, exc)
        return 1
    print(out["digest"]["text"])
    log.info("digest for %s: %s", out.get("date"), "written" if out["written"] else "not written (dry run or already exists)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
