"""Refreshes the free public data cache (see app/free_data.py).

    python -m app.scripts.refresh_free_data            # refresh what is stale
    python -m app.scripts.refresh_free_data --force    # refetch everything

Cron (host crontab): after the price sync (22:00) and BEFORE the committee (22:15), so a review reads fresh filings:

    5 22 * * 1-5 cd /home/shrey/glassbox && /usr/bin/docker compose exec -T backend python -m app.scripts.refresh_free_data >> /home/shrey/glassbox/logs/free_data.log 2>&1

SEC data needs SEC_USER_AGENT (a string with a contact email, per the SEC's fair-access policy) in the
environment; without it the SEC part is skipped and says so, while the Treasury and BLS macro data (which
need no key) still refresh. Exit code 1 only if EVERY source failed.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .. import data_source as ds
from .. import free_data
from ..logging_config import quiet_http_clients

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
quiet_http_clients()
log = logging.getLogger("refresh_free_data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the free public data cache.")
    parser.add_argument("--force", action="store_true", help="refetch even fresh data")
    args = parser.parse_args(argv)
    status = free_data.refresh_all(sorted(ds.STOCK_INFO), force=args.force)
    for name, s in sorted(status.items()):
        log.info("%-18s %s  %s", name, "ok " if s["ok"] else "OFF", s["detail"])
    print(json.dumps({k: {"ok": v["ok"], "detail": v["detail"]} for k, v in status.items()}, indent=2))
    return 0 if any(s["ok"] for s in status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
