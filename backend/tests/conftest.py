"""Shared fixtures.

The TTS layer now caches audio (memory + optional disk) and tracks a daily
character budget in module globals. Tests reuse the same text and voice ids
constantly, so without this reset one test's cached audio would satisfy the
next test's "provider failed" scenario and hide what it means to check.
"""
from __future__ import annotations

import pytest

from app import tts


@pytest.fixture(autouse=True)
def _reset_tts_state(monkeypatch):
    tts.clear_cache()
    monkeypatch.setattr(tts, "_budget_day", "")
    monkeypatch.setattr(tts, "_budget_spent", 0)
    yield
    tts.clear_cache()
