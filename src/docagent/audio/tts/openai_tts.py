"""
OpenAITTS — síntese de voz via OpenAI Text-to-Speech API.
Retorna bytes MP3 (formato nativo da API).
"""
import logging

import httpx

log = logging.getLogger(__name__)


class OpenAITTS:

    async def sintetizar(self, texto: str, voz: str, api_key: str) -> bytes:
        if not api_key:
            raise ValueError("api_key é obrigatória para o provider OpenAI TTS")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "tts-1",
                    "input": texto,
                    "voice": voz,
                    "response_format": "mp3",
                },
            )
            response.raise_for_status()
            return response.content
