"""TTS provider-chain correctness: request shape, fallback, and the
"not configured" contract -- verified without needing real
ELEVENLABS_API_KEY/HUGGINGFACE_API_KEY credentials or a live model
deployment.

ElevenLabs is primary (see app/tts.py's module docstring for why this
order flipped from an earlier Kokoro-primary version -- the free tier's
account credits were exhausted three times across two different keys
during real verification), Kokoro/Hugging Face is the fallback. The two
providers use different voice-id namespaces, so generate_speech() takes
two separate ids -- tests assert each provider receives its OWN id, not
the other's, since a mixed-up id was a real, disclosed gap in an earlier
version of this file.

The Hugging Face path is mocked at the `AsyncInferenceClient` level, not
via respx/httpx -- app/tts.py uses the official huggingface_hub client
for that path (see the module docstring for the earlier real,
live-verified bug that came from hand-rolling REST against a guessed
provider/endpoint instead). ElevenLabs remains a plain httpx call and is
mocked via respx.
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


@respx.mock
async def test_eleven_labs_success_returns_audio_bytes(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-el-key")
    respx.post(tts.ELEVENLABS_URL_TMPL.format(voice_id="el-voice-1")).mock(
        return_value=httpx.Response(200, content=b"elevenlabs-audio")
    )
    result = await tts.generate_speech("hello there", elevenlabs_voice_id="el-voice-1", kokoro_voice_id="am_michael")
    assert result == (b"elevenlabs-audio", "audio/mpeg")


@respx.mock
async def test_eleven_labs_receives_its_own_voice_id_not_kokoros(monkeypatch):
    """Regression test for the real gap this file was updated to close:
    an earlier version passed the SAME voice_id to both providers, which
    would silently 404 against ElevenLabs once it became primary (it
    uses a completely different id namespace than Kokoro's short codes).
    """
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-el-key")
    route = respx.post(tts.ELEVENLABS_URL_TMPL.format(voice_id="el-voice-1")).mock(
        return_value=httpx.Response(200, content=b"audio")
    )
    # A request hitting the KOKORO-shaped id would 404 since no route is
    # registered for it -- respx raises if an unmatched URL is called.
    await tts.generate_speech("hello", elevenlabs_voice_id="el-voice-1", kokoro_voice_id="am_michael")
    assert route.called


@respx.mock
async def test_eleven_labs_failure_falls_through_to_hugging_face(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-el-key")
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    respx.post(tts.ELEVENLABS_URL_TMPL.format(voice_id="el-voice-1")).mock(return_value=httpx.Response(500))
    monkeypatch.setattr(tts, "AsyncInferenceClient", _fake_hf_client(result=b"RIFF\x00\x00fake-wav-bytes"))
    result = await tts.generate_speech("hello", elevenlabs_voice_id="el-voice-1", kokoro_voice_id="am_michael")
    assert result == (b"RIFF\x00\x00fake-wav-bytes", "audio/wav")


async def test_hugging_face_passes_correct_provider_model_and_voice(monkeypatch):
    """Regression test for the real bug this file was rewritten to fix
    earlier: the original implementation guessed a provider/hostname that
    turned out to be wrong for this model (confirmed live: "Model not
    supported by provider hf-inference"). This asserts the exact
    provider, model id, and voice parameter actually reach the client
    call -- ElevenLabs unconfigured here so Kokoro is reached directly."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
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
    await tts.generate_speech("hello world", elevenlabs_voice_id="el-voice-1", kokoro_voice_id="bm_george")
    assert captured["provider"] == tts.HF_PROVIDER == "fal-ai"
    assert captured["model"] == tts.HF_MODEL == "hexgrad/Kokoro-82M"
    assert captured["extra_body"] == {"voice": "bm_george"}
    assert captured["text"] == "hello world"
    assert captured["api_key"] == "fake-hf-token"


async def test_hugging_face_empty_result_returns_none(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake-hf-token")
    monkeypatch.setattr(tts, "AsyncInferenceClient", _fake_hf_client(result=b""))
    result = await tts.generate_speech("hello", elevenlabs_voice_id="el-voice-1", kokoro_voice_id="am_michael")
    assert result is None


async def test_both_unconfigured_returns_none_cleanly(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    result = await tts.generate_speech("hello", elevenlabs_voice_id="el-voice-1", kokoro_voice_id="am_michael")
    assert result is None


def test_sniff_audio_content_type():
    assert tts._sniff_audio_content_type(b"RIFF\x00\x00\x00\x00WAVEfmt ") == "audio/wav"
    assert tts._sniff_audio_content_type(b"fLaC\x00\x00") == "audio/flac"
    assert tts._sniff_audio_content_type(b"ID3\x03\x00") == "audio/mpeg"
    assert tts._sniff_audio_content_type(b"\xff\xfb\x90\x00") == "audio/mpeg"
    assert tts._sniff_audio_content_type(b"unknown-bytes") == "audio/mpeg"


async def test_empty_text_returns_none_without_any_request():
    result = await tts.generate_speech("   ", elevenlabs_voice_id="el-voice-1", kokoro_voice_id="am_michael")
    assert result is None
