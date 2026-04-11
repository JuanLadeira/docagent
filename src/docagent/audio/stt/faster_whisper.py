"""
FasterWhisperSTT — transcrição local via faster-whisper.

Singleton: o WhisperModel é carregado uma vez e reutilizado em todas as chamadas.
A transcrição é síncrona (CPU-bound), então roda em thread pool via asyncio.to_thread.
"""
import asyncio
import logging
import tempfile
import os
from typing import ClassVar

log = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover
    WhisperModel = None  # type: ignore[assignment,misc]


class FasterWhisperSTT:
    _model: ClassVar = None

    @classmethod
    def get_model(cls, modelo: str):
        if cls._model is None:
            if WhisperModel is None:
                raise RuntimeError(
                    "faster-whisper não está instalado. "
                    "Execute: uv add faster-whisper"
                )
            log.info("audio.stt: carregando WhisperModel('%s') — pode demorar na primeira vez", modelo)
            cls._model = WhisperModel(modelo, device="cpu", compute_type="int8")
        return cls._model

    async def transcrever(self, audio_bytes: bytes, modelo: str) -> str:
        model = self.get_model(modelo)
        texto = await asyncio.to_thread(self._transcrever_sync, model, audio_bytes)
        log.info("audio.stt: transcrição concluída (%d chars): %.120s", len(texto), texto)
        return texto

    @staticmethod
    def _transcrever_sync(model, audio_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            segments, info = model.transcribe(
                tmp_path,
                language="pt",
                beam_size=5,
                vad_filter=True,           # remove silêncio/ruído antes de transcrever
                vad_parameters={"min_silence_duration_ms": 500},
                # Evita alucinações em segmentos de áudio curtos ou com ruído
                condition_on_previous_text=False,
                # Dica de contexto para o modelo usar português brasileiro
                initial_prompt="Transcrição em português brasileiro:",
                # Descarta segmentos com confiança muito baixa de fala
                no_speech_threshold=0.6,
            )
            texto = "".join(seg.text for seg in segments).strip()
            log.info(
                "audio.stt: idioma detectado='%s' (%.0f%%), duracao=%.1fs",
                info.language, info.language_probability * 100, info.duration,
            )
            return texto
        finally:
            os.unlink(tmp_path)
