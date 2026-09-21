"""The one daily job: wait for the US close to be final, then sync -> free data -> committee -> paper cycle -> snapshot.

    python -m app.scripts.run_daily_pipeline                # what cron runs
    python -m app.scripts.run_daily_pipeline --no-wait      # do not sleep for today's close (process the last finished day)
    python -m app.scripts.run_daily_pipeline --force        # redo every stage for the target day
    python -m app.scripts.run_daily_pipeline --status       # print the recent runs and exit

Cron (host crontab). It replaces the separate sync / free-data / committee / paper-cycle / weekly entries:

    35 20 * * 1-5 cd /home/shrey/glassbox && /usr/bin/docker compose exec -T backend python -m app.scripts.run_daily_pipeline >> /home/shrey/glassbox/logs/pipeline.log 2>&1
    45 23 * * 1-5 cd /home/shrey/glassbox && /usr/bin/docker compose exec -T backend python -m app.scripts.run_daily_pipeline --no-wait >> /home/shrey/glassbox/logs/pipeline.log 2>&1

The 23:45 line is a safety net: on a healthy day it finds everything done and exits in seconds; if the first run
crashed (or the VM restarted) it redoes only what is missing. See app/pipeline.py for the rules.
Exit code: 0 = done (or nothing to do / market closed), 1 = a fatal stage failed, 2 = finished with a non-fatal stage failing.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .. import pipeline
from ..logging_config import quiet_http_clients

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
quiet_http_clients()  # httpx INFO lines carry the Gemini ?key= URL


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run the daily pipeline.")
    p.add_argument("--no-wait", action="store_true", help="do not wait for today's close; process the most recent finished trading day")
    p.add_argument("--force", action="store_true", help="redo every stage even if it already succeeded for the target day")
    p.add_argument("--status", action="store_true", help="print the recent pipeline runs and exit")
    args = p.parse_args(argv)
    if args.status:
        print(json.dumps(pipeline.status_history()[-7:], indent=2))
        return 0
    out = pipeline.run(wait=not args.no_wait, force=args.force)
    print(json.dumps({k: out.get(k) for k in ("status", "target", "message", "stages", "sync", "partial")}, indent=2, default=str))
    return int(out.get("exit_code", 0))


if __name__ == "__main__":
    sys.exit(main())
