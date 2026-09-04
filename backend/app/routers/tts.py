from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel

from .. import tts

router = APIRouter(prefix="/api", tags=["tts"])


class TTSRequest(BaseModel):
    text: str
    # Two separate ids -- ElevenLabs and Kokoro/Hugging Face use entirely
    # different voice-id namespaces (see app/tts.py's module docstring).
    elevenlabs_voice_id: str
    kokoro_voice_id: str


@router.post("/tts")
async def api_tts(body: TTSRequest):
    result = await tts.generate_speech(body.text, body.elevenlabs_voice_id, body.kokoro_voice_id)
    if result is None:
        return Response(
            content='{"error": "Voice output isn\'t configured or is temporarily unavailable."}',
            media_type="application/json",
            status_code=503,
        )
    audio_bytes, content_type = result
    return Response(content=audio_bytes, media_type=content_type)
