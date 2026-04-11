"""
PiperTTS — síntese de voz local via binário piper + conversão WAV→OGG com ffmpeg.

Fluxo:
  texto → piper (stdin) → WAV (stdout) → ffmpeg → OGG/OPUS (stdout)

Roda como subprocess async para não bloquear o event loop.
Falha graciosamente se piper ou ffmpeg não estiverem disponíveis.
"""
import asyncio
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# Diretório onde os modelos .onnx ficam armazenados no container
PIPER_MODELS_DIR = Path(os.environ.get("PIPER_MODELS_DIR", "/app/models/piper"))


def _resolver_path_modelo(voz: str) -> str:
    """Resolve 'pt_BR-faber-medium' → '/app/models/piper/pt_BR-faber-medium.onnx'.
    Se já for um path absoluto, retorna como está.
    """
    if os.path.isabs(voz):
        return voz
    candidato = PIPER_MODELS_DIR / f"{voz}.onnx"
    return str(candidato)


class PiperTTS:

    async def sintetizar(self, texto: str, voz: str) -> bytes:
        """Sintetiza texto em áudio OGG/OPUS via piper + ffmpeg."""
        model_path = _resolver_path_modelo(voz)
        try:
            # Passo 1: piper lê texto do stdin e gera WAV no stdout
            piper_proc = await asyncio.create_subprocess_exec(
                "piper",
                "--model", model_path,
                "--output-raw",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            wav_bytes, piper_err = await piper_proc.communicate(input=texto.encode())

            if piper_proc.returncode != 0:
                log.warning("piper stderr: %s", piper_err.decode(errors="replace"))

        except FileNotFoundError as e:
            raise RuntimeError(
                "Binário 'piper' não encontrado. "
                "Instale o piper-tts e certifique-se que está no PATH."
            ) from e

        try:
            # Passo 2: ffmpeg converte WAV raw → OGG/OPUS
            ffmpeg_proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-f", "s16le",       # formato PCM raw do piper
                "-ar", "22050",      # sample rate padrão do piper
                "-ac", "1",          # mono
                "-i", "pipe:0",      # stdin
                "-c:a", "libopus",
                "-b:a", "64k",
                "-f", "ogg",
                "pipe:1",            # stdout
                "-loglevel", "error",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            ogg_bytes, ffmpeg_err = await ffmpeg_proc.communicate(input=wav_bytes)

            if ffmpeg_proc.returncode != 0:
                log.warning("ffmpeg stderr: %s", ffmpeg_err.decode(errors="replace"))

        except FileNotFoundError as e:
            raise RuntimeError(
                "Binário 'ffmpeg' não encontrado. "
                "Instale ffmpeg no sistema (apt install ffmpeg)."
            ) from e

        return ogg_bytes
