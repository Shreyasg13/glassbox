"""TTS provider-chain correctness: request shape, fallback, and the
"not configured" contract -- verified without needing real
HUGGINGFACE_API_KEY/ELEVENLABS_API_KEY credentials or a live model
deployment.

The Hugging Face path is mocked at the `AsyncInferenceClient` level, not
via respx/httpx -- app/tts.py uses the official huggingface_hub client
for that path (see its module docstring for why: hand-rolled REST
against a guessed provider/endpoint is exactly what produced a real,
live-verified bug once real credentials were available to test against).
ElevenLabs remains a plain httpx call and is still mocked via respx.
"""
from __future__ import annotations

import httpx
import respx

from app import tts


def _fake_hf_client(*, result=None, raises=None):
    """Factory for a stand-in AsyncInferenceClient. `result` is the bytes
    text_to_speech() should return; `raises` is an exception it should
    raise instead."""

    class _FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def text_to_speech(self, _text, *, model, extra_body):
            if raises:
                raise raises
            return result

    return _FakeClient


async def test_hugging_face_success_returns_audio_bytes(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    monkeypatch.setattr(tts, "AsyncInferenceClient", _fake_hf_client(result=b"RIFF\x00\x00fake-wav-bytes"))
    result = await tts.generate_speech("hello there", "am_michael")
    assert result == (b"RIFF\x00\x00fake-wav-bytes", "audio/wav")


async def test_hugging_face_passes_correct_provider_model_and_voice(monkeypatch):
    """Regression test for the real bug this file was rewritten to fix:
    the original implementation guessed a provider/hostname that turned
    out to be wrong for this model (confirmed live: "Model not supported
    by provider hf-inference"). This asserts the exact provider, model id,
    and voice parameter actually reach the client call."""
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    captured: dict = {}

    class _CapturingClient:
        def __init__(self, *, provider, api_key, timeout):
            captured["provider"] = provider
            captured["api_key"] = api_key

        async def text_to_speech(self, text, *, model, extra_body):
            captured["text"] = text
            captured["model"] = model
            captured["extra_body"] = extra_body
            return b"RIFFdata"

    monkeypatch.setattr(tts, "AsyncInferenceClient", _CapturingClient)
    await tts.generate_speech("hello world", "bm_george")
    assert captured["provider"] == tts.HF_PROVIDER == "fal-ai"
    assert captured["model"] == tts.HF_MODEL == "hexgrad/Kokoro-82M"
    assert captured["extra_body"] == {"voice": "bm_george"}
    assert captured["text"] == "hello world"
    assert captured["api_key"] == "fake-hf-token"


@respx.mock
async def test_hugging_face_failure_falls_through_to_eleven_labs(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-el-key")
    monkeypatch.setattr(tts, "AsyncInferenceClient", _fake_hf_client(raises=RuntimeError("boom")))
    respx.post(tts.ELEVENLABS_URL_TMPL.format(voice_id="am_michael")).mock(
        return_value=httpx.Response(200, content=b"elevenlabs-audio")
    )
    result = await tts.generate_speech("hello", "am_michael")
    assert result == (b"elevenlabs-audio", "audio/mpeg")


async def test_hugging_face_empty_result_falls_through(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(tts, "AsyncInferenceClient", _fake_hf_client(result=b""))
    result = await tts.generate_speech("hello", "am_michael")
    assert result is None


async def test_both_unconfigured_returns_none_cleanly(monkeypatch):
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    result = await tts.generate_speech("hello", "am_michael")
    assert result is None


def test_sniff_audio_content_type():
    assert tts._sniff_audio_content_type(b"RIFF\x00\x00\x00\x00WAVEfmt ") == "audio/wav"
    assert tts._sniff_audio_content_type(b"fLaC\x00\x00") == "audio/flac"
    assert tts._sniff_audio_content_type(b"ID3\x03\x00") == "audio/mpeg"
    assert tts._sniff_audio_content_type(b"\xff\xfb\x90\x00") == "audio/mpeg"
    assert tts._sniff_audio_content_type(b"unknown-bytes") == "audio/mpeg"


async def test_empty_text_returns_none_without_any_request():
    result = await tts.generate_speech("   ", "am_michael")
    assert result is None
