"""Correctness of the local, best-effort quota tracker -- see
app/providers/gemini_quota.py's module docstring for what this tracker
can and can't actually know (no public real-time quota API exists; this
only sees calls made by this process)."""
from __future__ import annotations

from app.providers import gemini_quota


def setup_function():
    gemini_quota._call_log.clear()


def test_unknown_model_always_reports_headroom():
    assert gemini_quota.has_headroom("some-model-not-in-the-table") is True


def test_headroom_true_before_any_calls_recorded():
    model = next(iter(gemini_quota.GEMINI_LIMITS))
    assert gemini_quota.has_headroom(model) is True


def test_rpm_ceiling_reached_reports_no_headroom():
    model = "gemini-3.8-flash"
    rpm_limit, _tpm, _rpd = gemini_quota.GEMINI_LIMITS[model]
    for _ in range(rpm_limit):
        gemini_quota.record_call(model, tokens=10)
    assert gemini_quota.has_headroom(model) is False


def test_headroom_available_below_ceiling():
    model = "gemini-3.8-flash"
    rpm_limit, _tpm, _rpd = gemini_quota.GEMINI_LIMITS[model]
    for _ in range(rpm_limit - 1):
        gemini_quota.record_call(model, tokens=10)
    assert gemini_quota.has_headroom(model) is True


def test_tpm_ceiling_reached_reports_no_headroom_even_under_rpm():
    model = "gemini-3.5-flash-lite"  # RPM 15, TPM 250_000
    _rpm, tpm_limit, _rpd = gemini_quota.GEMINI_LIMITS[model]
    gemini_quota.record_call(model, tokens=tpm_limit)
    assert gemini_quota.has_headroom(model, estimated_tokens=1) is False


def test_record_call_is_a_noop_for_unknown_models():
    # Must not raise or start silently tracking a model with no known
    # ceiling -- has_headroom() for it should keep returning True.
    gemini_quota.record_call("totally-unknown-model", tokens=999_999)
    assert gemini_quota.has_headroom("totally-unknown-model") is True
