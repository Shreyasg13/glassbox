"""Text-to-speech for the Strategy Lenses carousel -- server-side
generation (not each browser's own SpeechSynthesis voices) so every
persona sounds the same for every visitor, and so each of the 8 personas
can have a genuinely distinct assigned voice.

Provider chain: Hugging Face's hosted Inference API running the
open-source Kokoro-82M model (free, no per-request cost), falling
through to ElevenLabs (paid) on any failure. Pattern verified against a
real, working implementation at github.com/Shreyasg13/Portfolio_Website
(netlify/functions/_shared/tts.mjs) -- same provider order, same
retry-on-cold-start idea, same graceful "not configured" contract as
this project's own LLM providers (app/providers/*.py).

TWO THINGS VERIFIED LIVE, WORTH KNOWING BEFORE TOUCHING THIS FILE:

1. The endpoint. The reference repo's code comments implied the legacy
   `api-inference.huggingface.co/models/{model}` hostname; a live request
   to it during this build returned nothing (connection reset/unreachable).
   `https://router.huggingface.co/hf-inference/models/{model}` DID
   respond (401 without a token, which confirms the route exists) --
   Hugging Face has evidently migrated routing since the reference repo
   was written. This module uses the router hostname.

2. Voice selection is UNVERIFIED. Kokoro-82M's own model card
   (huggingface.co/hexgrad/Kokoro-82M) documents usage only via the
   local `kokoro` PyPI package (`pipeline(text, voice='af_heart')`), not
   via the hosted Inference API -- there's no confirmation the hosted
   endpoint's request handler actually respects a `parameters.voice`
   field the way this code sends it. This was not verifiable without a
   real HUGGINGFACE_API_KEY (every unauthenticated probe correctly 401s).
   If the hosted endpoint ignores `parameters.voice`, every persona will
   still get real speech -- just from Kokoro's handler-default voice
   instead of a distinct one per persona. That's a degraded-but-working
   outcome, not a broken one; if it turns out to happen, the ElevenLabs
   fallback (which DOES support per-request voice_id, verified in the
   reference repo's own working code) becomes the practical way to get
   genuinely distinct voices, at the cost of needing that paid key too.

Real, confirmed-valid Kokoro-82M voice IDs used for persona assignment
(from https://huggingface.co/hexgrad/Kokoro-82M/raw/main/VOICES.md,
fetched directly during this build): am_michael, am_puck, am_fenrir,
am_eric, am_onyx (US English male), bm_george, bm_fable, bm_lewis (UK
English male). All 8 Strategy Lens personas are archetypes of real men
(Buffett, Lynch, Griffin, Dalio, Simons, Englander, Shaw, Soros), hence
an all-male voice set; the two personas marked `lead: true` in
lensData.ts got the two highest-graded voices per VOICES.md's own
quality grading (am_michael, am_fenrir).
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional, Tuple

import httpx

HF_MODEL = "hexgrad/Kokoro-82M"
HF_ROUTER_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"
ELEVENLABS_URL_TMPL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MAX_CHARS = 800

TTSResult = Tuple[bytes, str]  # (audio_bytes, content_type)


async def _try_hugging_face(text: str, voice_id: str) -> Optional[TTSResult]:
    hf_token = os.environ.get("HUGGINGFACE_API_KEY")
    if not hf_token:
        return None
    headers = {"Authorization": f"Bearer {hf_token}", "Content-Type": "application/json"}
    body = {"inputs": text, "parameters": {"voice": voice_id}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(HF_ROUTER_URL, headers=headers, json=body)
            # Free/serverless-backed models can cold-start and report 503
            # with an estimated wait; one short retry covers most of that.
            if resp.status_code == 503:
                await asyncio.sleep(3.0)
                resp = await client.post(HF_ROUTER_URL, headers=headers, json=body)
            if resp.status_code != 200:
                return None
            content_type = resp.headers.get("content-type", "audio/flac")
            if "audio" not in content_type and "octet-stream" not in content_type:
                # A 200 with a JSON body (e.g. a queued/loading response
                # shape some HF handlers use) is not audio -- treat as a
                # miss rather than returning garbage bytes as "audio".
                return None
            return resp.content, content_type
        except httpx.HTTPError:
            return None


async def _try_eleven_labs(text: str, voice_id: str) -> Optional[TTSResult]:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return None
    url = ELEVENLABS_URL_TMPL.format(voice_id=voice_id)
    headers = {"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    body = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                return None
            return resp.content, "audio/mpeg"
        except httpx.HTTPError:
            return None


async def generate_speech(text: str, voice_id: str) -> Optional[TTSResult]:
    """Returns (audio_bytes, content_type) on success, or None if every
    configured provider is unavailable/unconfigured/failed -- callers
    (the /api/tts route) turn None into a clean 503, matching the
    "not configured" contract every other provider in this codebase uses
    rather than raising and surfacing a stack trace to a public endpoint.

    Note: ElevenLabs uses its own voice-id namespace (e.g. "pNInz6obpgDQGcFmaJgB"),
    entirely different from Kokoro's ("am_michael" etc.) -- a caller
    falling through to ElevenLabs with a Kokoro voice_id will simply get
    a 404 from ElevenLabs and fall through to returning None. Wiring a
    real per-persona ElevenLabs voice mapping is future work for if that
    key ever gets configured; today this project only has a
    HUGGINGFACE_API_KEY path realistically available.
    """
    trimmed = text.strip()[:MAX_CHARS]
    if not trimmed:
        return None
    return (await _try_hugging_face(trimmed, voice_id)) or (await _try_eleven_labs(trimmed, voice_id))
