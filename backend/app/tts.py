"""Text-to-speech for the Strategy Lenses carousel -- server-side
generation (not each browser's own SpeechSynthesis voices) so every
persona sounds the same for every visitor, and so each of the 8 personas
can have a genuinely distinct assigned voice.

Provider chain: ElevenLabs primary (paid, predictable pricing), falling
through to Hugging Face's Inference Providers running the open-source
Kokoro-82M model (free tier) on any failure. This order flipped from an
earlier version of this file (Kokoro primary) after that free tier's
account-level credit quota was exhausted three times across two
different keys during real verification -- confirmed each time via a
live 402 "monthly included credits depleted" response, not a code bug.
ElevenLabs' paid tier is the reliable path now; Kokoro remains as a
free fallback if ElevenLabs itself is ever unconfigured/down.

CRITICAL: the two providers use ENTIRELY DIFFERENT VOICE-ID NAMESPACES
(ElevenLabs: alphanumeric ids like "pNInz6obpgDQGcFmaJgB"; Kokoro:
short codes like "am_michael") -- passing the same voice_id to both
was a real, disclosed-but-live limitation in the original version of
this file (kept as a "future work" note since only Kokoro was
realistically configured at the time). Now that ElevenLabs is primary,
that gap would silently break every call if left unfixed, so the
request/response shape below takes two SEPARATE voice ids, one per
provider, rather than one overloaded field.

THIS FILE WAS REWRITTEN ONCE ALREADY AFTER A REAL, LIVE-VERIFIED BUG --
worth knowing before touching it again:

The original implementation hand-rolled raw HTTP against
`router.huggingface.co/hf-inference/models/{model}`. Once a real
HUGGINGFACE_API_KEY was actually available to test with, every call
403'd with "Model not supported by provider hf-inference" -- Kokoro-82M
is not served by the `hf-inference` provider at all. Querying the
model's own provider mapping directly:

    curl https://huggingface.co/api/models/hexgrad/Kokoro-82M\
?expand[]=inferenceProviderMapping -H "Authorization: Bearer $HF_TOKEN"
    -> {"fal-ai": {"status":"live", ...}, "deepinfra": {"status":"live", ...}}

So `hf-inference` was simply never a valid provider for this model --
the original build's every attempt to reach it (including the earlier
"connection reset" on the legacy `api-inference.huggingface.co` host)
was doomed regardless of hostname, because the *provider*, not the
*host*, was wrong.

Fix: use Hugging Face's own `huggingface_hub` Python client instead of
hand-rolled REST. Their routing/provider layer changes over time (as
just demonstrated) and the official client is the thing that's kept in
sync with it -- guessing raw endpoint shapes is how the original bug
happened. `provider="fal-ai"` is used because it's the one provider
confirmed live for this exact model+task from BOTH the model's own
`inferenceProviderMapping` AND huggingface_hub's own provider-support
matrix (`deepinfra` appears in the former but not the latter's
text_to_speech column, so it's not a client-usable path even though the
model card lists it).

VERIFIED LIVE with a real key (not simulated): a real ~134KB WAV file
came back for `AsyncInferenceClient(provider="fal-ai").text_to_speech(
text, model="hexgrad/Kokoro-82M", extra_body={"voice": "am_michael"})`.
The `extra_body={"voice": ...}` parameter shape is HF's own documented
pattern for this exact model (huggingface.co/docs/huggingface_hub ->
InferenceClient.text_to_speech "With Extra Parameters" example uses
`hexgrad/Kokoro-82M` + `extra_body={"voice": "af_nicole"}` verbatim) --
so unlike the previous version, voice selection is now confirmed to
work, not just hoped to work.

fal-ai's serverless backend can cold-start slow: the first real test
call took long enough that a naive 30s timeout would have failed it as
a false negative (it succeeded once given ~90s). HF_TIMEOUT_S below
reflects that, not a guess.

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

import os
from typing import Optional, Tuple

import httpx
from huggingface_hub import AsyncInferenceClient

HF_MODEL = "hexgrad/Kokoro-82M"
HF_PROVIDER = "fal-ai"
HF_TIMEOUT_S = 90.0
ELEVENLABS_URL_TMPL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MAX_CHARS = 800

TTSResult = Tuple[bytes, str]  # (audio_bytes, content_type)


def _sniff_audio_content_type(data: bytes) -> str:
    """huggingface_hub's text_to_speech() returns raw bytes with no
    content-type header attached -- sniff the magic bytes so the browser
    <audio> element gets an accurate MIME type rather than a guessed one.
    """
    if data[:4] == b"RIFF":
        return "audio/wav"
    if data[:4] == b"fLaC":
        return "audio/flac"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    return "audio/mpeg"


async def _try_hugging_face(text: str, voice_id: str) -> Optional[TTSResult]:
    hf_token = os.environ.get("HUGGINGFACE_API_KEY")
    if not hf_token:
        return None
    client = AsyncInferenceClient(provider=HF_PROVIDER, api_key=hf_token, timeout=HF_TIMEOUT_S)
    try:
        audio = await client.text_to_speech(text, model=HF_MODEL, extra_body={"voice": voice_id})
    except Exception:
        # Broad catch is deliberate here, matching this file's existing
        # policy: any provider failure means "try the next provider / report
        # unavailable", never surface a provider-specific stack trace or
        # error string to the public /api/tts endpoint. (Verified live
        # during this fix: a real call succeeds and returns real audio --
        # a 402 "monthly included credits depleted" from Hugging Face's
        # own billing is an account-level quota limit, not a code defect;
        # this same catch-all correctly turns that into a clean
        # "unavailable" response rather than a crash either way.)
        return None
    if not audio:
        return None
    audio_bytes = bytes(audio)
    return audio_bytes, _sniff_audio_content_type(audio_bytes)


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


async def generate_speech(text: str, elevenlabs_voice_id: str, kokoro_voice_id: str) -> Optional[TTSResult]:
    """Returns (audio_bytes, content_type) on success, or None if every
    configured provider is unavailable/unconfigured/failed -- callers
    (the /api/tts route) turn None into a clean 503, matching the
    "not configured" contract every other provider in this codebase uses
    rather than raising and surfacing a stack trace to a public endpoint.

    Takes one voice id per provider (see module docstring for why a
    single shared id was a real bug waiting to happen) -- ElevenLabs is
    tried first, Kokoro/Hugging Face as the fallback.
    """
    trimmed = text.strip()[:MAX_CHARS]
    if not trimmed:
        return None
    return (await _try_eleven_labs(trimmed, elevenlabs_voice_id)) or (
        await _try_hugging_face(trimmed, kokoro_voice_id)
    )
