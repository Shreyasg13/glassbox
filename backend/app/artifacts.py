"""Small files that only lived on the VM disk, mirrored into the database so a rebuilt VM restores them.

Two kinds of file matter and are not derivable from the price table:
  * training_results/*.json  -- the fitted per-symbol strategy parameters the engine signals use
  * free_data/**/*.json      -- the cached SEC / Treasury / BLS pulls (re-fetchable, but slowly, and SEC is rate-limited)

`mirror()` writes a file to the `blobs` table only when its content hash changed, so a run costs a few reads and
almost no writes. `restore_missing()` runs on a fresh disk and puts back only files that are absent: it never
overwrites a file that exists, so restoring can never clobber newer local work. Prices are not mirrored here
(they are rows in `price_bars`), and nothing secret is ever in these directories.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from . import db, free_data
from .data_source import TRADING_STORAGE_PATH

log = logging.getLogger("glassbox.artifacts")

MAX_FILE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 40_000_000


def roots() -> Dict[str, Path]:
    return {"training_results": TRADING_STORAGE_PATH / "training_results", "free_data": free_data.data_dir()}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _files() -> List[tuple]:
    out = []
    for prefix, root in roots().items():
        if root.is_dir():
            out += [(f"{prefix}/{p.relative_to(root).as_posix()}", p) for p in sorted(root.rglob("*.json")) if p.is_file()]
    return out


def mirror(now: datetime | None = None) -> Dict[str, Any]:
    """Copy new or changed artifact files into the database. Returns counts and anything skipped (with the reason)."""
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    have = db.list_blob_meta()
    written = unchanged = total = 0
    skipped: List[Dict[str, str]] = []
    for name, path in _files():
        try:
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                skipped.append({"name": name, "why": f"{size} bytes exceeds the {MAX_FILE_BYTES} limit"})
                continue
            text = path.read_text(encoding="utf-8")
            json.loads(text)  # a half-written or corrupt file must not overwrite a good copy
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            skipped.append({"name": name, "why": f"unreadable: {type(exc).__name__}"})
            continue
        total += size
        if total > MAX_TOTAL_BYTES:
            skipped.append({"name": name, "why": "total size limit reached"})
            continue
        sha = _sha(text)
        if have.get(name) == sha:
            unchanged += 1
            continue
        db.put_blob(name, text, sha, stamp)
        written += 1
    return {"written": written, "unchanged": unchanged, "skipped": skipped, "bytes": total}


def _safe_target(name: str) -> Path | None:
    prefix, _, rest = name.partition("/")
    root = roots().get(prefix)
    if root is None or not rest or rest.startswith("/") or ".." in Path(rest).parts:
        return None
    target = (root / rest).resolve()
    return target if root.resolve() in target.parents else None


def restore_missing() -> Dict[str, Any]:
    """Write back every mirrored file that is absent from disk (never overwrites an existing file)."""
    restored: List[str] = []
    skipped: List[str] = []
    for name in sorted(db.list_blob_meta()):
        target = _safe_target(name)
        if target is None:
            skipped.append(name)
            continue
        if target.exists():
            continue
        blob = db.get_blob(name)
        if not blob:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(blob["content"], encoding="utf-8")
        tmp.replace(target)
        restored.append(name)
    return {"restored": restored, "skipped": skipped}
