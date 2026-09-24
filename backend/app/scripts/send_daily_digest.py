"""Send (or preview) the daily admin digest email (see app/digest.py).

    python -m app.scripts.send_daily_digest             # send, if DIGEST_SMTP_* is configured
    python -m app.scripts.send_daily_digest --preview out.html   # render only, write the HTML, never send

Needs DIGEST_SMTP_USER, DIGEST_SMTP_APP_PASSWORD and DIGEST_TO_EMAIL in the environment (DIGEST_SMTP_HOST
defaults to smtp.gmail.com, DIGEST_SMTP_PORT to 587 -- a Gmail "App password" works with the defaults).
Without them, this reports "not configured" and exits 0 -- sending is optional, never a required step.

Cron: this is normally NOT scheduled directly -- it runs as the "digest_email" stage inside
app.scripts.run_daily_pipeline, after everything else that day has finished.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .. import digest
from ..logging_config import quiet_http_clients

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
quiet_http_clients()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Send or preview the daily admin digest email.")
    p.add_argument("--preview", metavar="FILE", help="render the HTML to FILE and never send")
    args = p.parse_args(argv)
    if args.preview:
        html = digest.render_html(digest.gather())
        with open(args.preview, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"wrote {args.preview}")
        return 0
    out = digest.run()
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
