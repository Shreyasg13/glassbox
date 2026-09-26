"""Single source of truth for the research-only disclaimer.

The wording lives in `config/disclaimer.md` (marked PENDING LEGAL REVIEW) so
counsel can change it in one place. This module loads it once, caches it, and
provides a hardcoded fallback if the file is missing or empty.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger("glassbox.disclaimer")

_DEFAULT = "Simulated research, not investment advice."
_MARKER = "<!-- PENDING LEGAL REVIEW"
_cache: Optional[str] = None
_cache_path: Optional[str] = None
_warned = False


def _default_path() -> Path:
    # backend/app/disclaimer.py -> backend/config/disclaimer.md
    return Path(__file__).resolve().parents[1] / "config" / "disclaimer.md"


def _resolved_path() -> Path:
    path_str = os.environ.get("GLASSBOX_DISCLAIMER_PATH")
    return Path(path_str) if path_str else _default_path()


def _path_key() -> str:
    """Return a string key representing the current disclaimer path."""
    path_str = os.environ.get("GLASSBOX_DISCLAIMER_PATH")
    return path_str or str(_default_path())


def _read_file(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    # Strip the HTML comment marker (<!-- PENDING LEGAL REVIEW ... -->) and any surrounding whitespace
    if text.startswith(_MARKER):
        # Find the end of the comment -->
        end_idx = text.find("-->")
        if end_idx != -1:
            text = text[end_idx + 3 :]
        else:
            # Fallback: find first newline
            newline_idx = text.find("\n")
            if newline_idx != -1:
                text = text[newline_idx + 1 :]
    return text.strip()


def text() -> str:
    """Return the disclaimer text (cached per path). Falls back to the hardcoded default."""
    global _cache, _cache_path, _warned
    current_key = _path_key()
    if _cache is not None and _cache_path == current_key:
        return _cache

    path = _resolved_path()
    raw = _read_file(path)

    if not raw:
        if not _warned:
            log.warning("disclaimer file missing or empty at %s; using hardcoded fallback", path)
            _warned = True
        _cache = _DEFAULT
    else:
        _cache = raw
    _cache_path = current_key
    return _cache


def pending_legal_review() -> bool:
    """True while the PENDING LEGAL REVIEW marker comment is present in the file."""
    path = _resolved_path()
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return True  # assume pending if we can't read it
    return _MARKER in content


def clear_cache() -> None:
    """Clear the cached value (for tests)."""
    global _cache, _cache_path
    _cache = None
    _cache_path = None