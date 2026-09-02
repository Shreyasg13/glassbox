"""TTS provider-chain correctness: request shape, retry, fallback, and
the "not configured" contract -- verified without needing real
HUGGINGFACE_API_KEY/ELEVENLABS_API_KEY credentials or a live model
deployment (see app/tts.py's module docstring for what remains
genuinely unverified without real credentials -- these tests cover the
logic that IS testable: routing, retry, fallback, graceful absence)."""
from __future__ import annotations

import httpx
import respx

from app import tts


async def _no_sleep(*_args, **_kwargs) -> None:
    return None


@respx.mock
async def test_hugging_face_success_returns_audio_bytes(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    respx.post(tts.HF_ROUTER_URL).mock(
        return_value=httpx.Response(200, content=b"fake-audio-bytes", headers={"content-type": "audio/flac"})
    )
    result = await tts.generate_speech("hello there", "am_michael")
    assert result == (b"fake-audio-bytes", "audio/flac")


@respx.mock
async def test_hugging_face_cold_start_retries_once_then_succeeds(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    monkeypatch.setattr(tts.asyncio, "sleep", _no_sleep)
    route = respx.post(tts.HF_ROUTER_URL)
    route.side_effect = [
        httpx.Response(503, json={"error": "loading", "estimated_time": 20}),
        httpx.Response(200, content=b"audio-after-retry", headers={"content-type": "audio/flac"}),
    ]
    result = await tts.generate_speech("hello", "am_michael")
    assert result == (b"audio-after-retry", "audio/flac")
    assert route.call_count == 2


@respx.mock
async def test_hugging_face_failure_falls_through_to_eleven_labs(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-el-key")
    respx.post(tts.HF_ROUTER_URL).mock(return_value=httpx.Response(500))
    respx.post(tts.ELEVENLABS_URL_TMPL.format(voice_id="am_michael")).mock(
        return_value=httpx.Response(200, content=b"elevenlabs-audio")
    )
    result = await tts.generate_speech("hello", "am_michael")
    assert result == (b"elevenlabs-audio", "audio/mpeg")


async def test_both_unconfigured_returns_none_cleanly(monkeypatch):
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    result = await tts.generate_speech("hello", "am_michael")
    assert result is None


@respx.mock
async def test_non_audio_response_treated_as_miss_not_garbage_audio(monkeypatch):
    # A 200 with a JSON body (e.g. a queued-response shape some HF
    # handlers use) must not be returned as if it were real audio bytes.
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    respx.post(tts.HF_ROUTER_URL).mock(
        return_value=httpx.Response(200, json={"status": "queued"}, headers={"content-type": "application/json"})
    )
    result = await tts.generate_speech("hello", "am_michael")
    assert result is None


async def test_empty_text_returns_none_without_any_request():
    result = await tts.generate_speech("   ", "am_michael")
    assert result is None
