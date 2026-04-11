"""
OpenAIWhisperSTT — transcrição via OpenAI Whisper API.
"""
import logging

import httpx

log = logging.getLogger(__name__)


class OpenAIWhisperSTT:

    async def transcrever(self, audio_bytes: bytes, api_key: str) -> str:
        if not api_key:
            raise ValueError("api_key é obrigatória para o provider OpenAI Whisper")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("audio.ogg", audio_bytes, "audio/ogg")},
                data={"model": "whisper-1", "language": "pt"},
            )
            response.raise_for_status()
            return response.json().get("text", "")
