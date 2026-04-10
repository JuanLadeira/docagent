"""
ElevenLabsTTS — síntese de voz via ElevenLabs API.
Retorna bytes MP3.
"""
import logging

import httpx

log = logging.getLogger(__name__)

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"


class ElevenLabsTTS:

    async def sintetizar(self, texto: str, voice_id: str, api_key: str) -> bytes:
        if not voice_id:
            raise ValueError("voice_id é obrigatório para o provider ElevenLabs")
        if not api_key:
            raise ValueError("api_key é obrigatória para o provider ElevenLabs")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": texto,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
            )
            response.raise_for_status()
            return response.content
