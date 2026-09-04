"""Fallback-chain correctness for complete_with_logging: single-model
behavior is unchanged, a failing primary falls through to the next
configured model, the quota pre-check skips a candidate it believes is
exhausted, and every candidate failing still raises (rather than
returning something falsy silently). db.create_llm_call/update_llm_call
are stubbed out here -- this is unit-testing the fallback/skip logic
itself, not integration-testing SQLite writes (covered elsewhere)."""
from __future__ import annotations

import pytest

from app import llm_call_logging as lcl
from app.providers import gemini_quota


class _FakeProvider:
    """Stand-in for get_provider()'s return value. `behaviors` maps a
    model id to either a return string (success) or an Exception instance
    (failure) -- `complete()` looks itself up by the `model` kwarg it's
    called with, exactly like the real dispatch."""

    def __init__(self, behaviors: dict):
        self.behaviors = behaviors
        self.calls: list[dict] = []

    async def complete(self, prompt, *, model, **kwargs):
        self.calls.append({"model": model, "retry": kwargs.get("retry")})
        outcome = self.behaviors[model]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def _stub_db(monkeypatch):
    monkeypatch.setattr(lcl.db, "create_llm_call", lambda *_a, **_kw: None)
    monkeypatch.setattr(lcl.db, "update_llm_call", lambda *_a, **_kw: None)


@pytest.fixture(autouse=True)
def _clear_gemini_quota_state():
    # gemini_quota's tracker is module-level state shared across tests --
    # reset it before/after each test so one test's recorded calls can't
    # leak into another's has_headroom() checks.
    gemini_quota._call_log.clear()
    yield
    gemini_quota._call_log.clear()


async def test_no_fallback_configured_behaves_like_a_single_call(monkeypatch):
    fake = _FakeProvider({"model-a": "the answer"})
    monkeypatch.setattr(lcl, "get_provider", lambda _name: fake)
    text, model_used = await lcl.complete_with_logging("gemini", "model-a", "prompt")
    assert (text, model_used) == ("the answer", "model-a")
    assert fake.calls == [{"model": "model-a", "retry": True}]  # sole candidate keeps normal retry


async def test_primary_failure_falls_through_to_next_model(monkeypatch):
    fake = _FakeProvider({"model-a": RuntimeError("429"), "model-b": "backup answer"})
    monkeypatch.setattr(lcl, "get_provider", lambda _name: fake)
    fallback_events = []

    async def on_fallback(candidate, reason):
        fallback_events.append((candidate, reason))

    text, model_used = await lcl.complete_with_logging(
        "gemini", "model-a", "prompt", fallback_models=["model-b"], on_fallback=on_fallback
    )
    assert (text, model_used) == ("backup answer", "model-b")
    # non-final candidate (model-a) must fail fast (retry=False); final
    # candidate (model-b) gets the provider's normal retry behavior
    assert fake.calls == [{"model": "model-a", "retry": False}, {"model": "model-b", "retry": True}]
    assert fallback_events == [("model-b", "trying after 'model-a' failed")]


async def test_all_candidates_failing_raises_the_last_exception(monkeypatch):
    final_error = RuntimeError("both exhausted")
    fake = _FakeProvider({"model-a": RuntimeError("429 a"), "model-b": final_error})
    monkeypatch.setattr(lcl, "get_provider", lambda _name: fake)
    with pytest.raises(RuntimeError) as exc_info:
        await lcl.complete_with_logging("gemini", "model-a", "prompt", fallback_models=["model-b"])
    assert exc_info.value is final_error


async def test_quota_precheck_skips_a_known_exhausted_candidate(monkeypatch):
    fake = _FakeProvider({"model-b": "answer from third model"})
    monkeypatch.setattr(lcl, "get_provider", lambda _name: fake)

    # model-a: not in GEMINI_LIMITS at all -> has_headroom() always True,
    # so it WOULD be attempted if it were a real model. To exercise the
    # skip path deterministically, patch has_headroom directly rather
    # than trying to naturally exhaust a real ceiling via record_call().
    def fake_has_headroom(model, _tokens=0):
        return model != "model-a"

    monkeypatch.setattr(gemini_quota, "has_headroom", fake_has_headroom)
    skip_events = []

    async def on_fallback(candidate, reason):
        skip_events.append((candidate, reason))

    text, model_used = await lcl.complete_with_logging(
        "gemini", "model-a", "prompt", fallback_models=["model-b"], on_fallback=on_fallback
    )
    assert (text, model_used) == ("answer from third model", "model-b")
    # model-a was never actually called -- only skipped via the pre-check
    assert fake.calls == [{"model": "model-b", "retry": True}]
    assert skip_events == [
        ("model-a", "skipped: local quota tracker reports no headroom"),
        ("model-b", "trying after 'model-a' was skipped"),
    ]


async def test_quota_precheck_never_skips_the_final_candidate(monkeypatch):
    # Even if the tracker believes the LAST candidate is exhausted too,
    # it must still be attempted -- refusing every candidate would be
    # strictly worse than trying the one we have left.
    fake = _FakeProvider({"model-a": "answer despite tracker pessimism"})
    monkeypatch.setattr(lcl, "get_provider", lambda _name: fake)
    monkeypatch.setattr(gemini_quota, "has_headroom", lambda *_a, **_kw: False)
    text, model_used = await lcl.complete_with_logging("gemini", "model-a", "prompt")
    assert (text, model_used) == ("answer despite tracker pessimism", "model-a")


async def test_non_gemini_provider_fallback_ignores_quota_tracker(monkeypatch):
    # The quota pre-check is gemini-specific (no known ceiling data for
    # other providers) -- a claude agent with a fallback list configured
    # should still just try candidates in order with no skip logic.
    fake = _FakeProvider({"claude-a": RuntimeError("rate limited"), "claude-b": "claude backup"})
    monkeypatch.setattr(lcl, "get_provider", lambda _name: fake)
    text, model_used = await lcl.complete_with_logging(
        "claude", "claude-a", "prompt", fallback_models=["claude-b"]
    )
    assert (text, model_used) == ("claude backup", "claude-b")


def test_candidate_chain_dedupes_while_preserving_order():
    assert lcl._candidate_chain("a", ["b", "a", "c", "b"]) == ["a", "b", "c"]
    assert lcl._candidate_chain("a", None) == ["a"]
    assert lcl._candidate_chain("a", []) == ["a"]
