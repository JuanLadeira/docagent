"""
AudioService — transcrição (STT), síntese (TTS) e resolução de config em cascata.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.audio.models import AudioConfig, ModoResposta, SttProvider, TtsProvider
from docagent.settings import Settings

log = logging.getLogger(__name__)


class AudioService:

    @staticmethod
    async def resolver_config(
        agente_id: int | None,
        tenant_id: int,
        db: AsyncSession,
    ) -> AudioConfig:
        """Retorna a AudioConfig efetiva seguindo a cascata:
        1. Config específica do agente (agente_id não-nulo)
        2. Config padrão do tenant (agente_id IS NULL)
        3. System defaults (objeto sintético, id=None, não persiste no banco)
        """
        # 1. Config do agente
        if agente_id is not None:
            result = await db.execute(
                select(AudioConfig).where(
                    AudioConfig.tenant_id == tenant_id,
                    AudioConfig.agente_id == agente_id,
                )
            )
            cfg = result.scalar_one_or_none()
            if cfg:
                return cfg

        # 2. Config padrão do tenant
        result = await db.execute(
            select(AudioConfig).where(
                AudioConfig.tenant_id == tenant_id,
                AudioConfig.agente_id.is_(None),
            )
        )
        cfg = result.scalar_one_or_none()
        if cfg:
            return cfg

        # 3. System defaults
        return AudioService._system_defaults()

    @staticmethod
    def _system_defaults() -> AudioConfig:
        """Cria um AudioConfig sintético com os valores de settings.py.
        Não é persistido no banco (id=None).
        Retorna um SimpleNamespace que satisfaz a interface de AudioConfig.
        """
        import types
        s = Settings()
        cfg = types.SimpleNamespace(
            id=None,
            tenant_id=0,
            agente_id=None,
            stt_habilitado=s.AUDIO_STT_HABILITADO,
            stt_provider=s.AUDIO_STT_PROVIDER,
            stt_modelo=s.AUDIO_STT_MODELO,
            tts_habilitado=s.AUDIO_TTS_HABILITADO,
            tts_provider=s.AUDIO_TTS_PROVIDER,
            piper_voz="pt_BR-faber-medium",
            openai_tts_voz="nova",
            elevenlabs_voice_id=None,
            elevenlabs_api_key=None,
            modo_resposta=s.AUDIO_MODO_RESPOSTA,
        )
        return cfg  # type: ignore[return-value]

    @staticmethod
    async def transcrever(
        audio_bytes: bytes,
        config: AudioConfig,
        openai_api_key: str | None = None,
    ) -> str:
        """Transcreve áudio para texto usando o provider configurado."""
        provider = config.stt_provider

        if provider == SttProvider.OPENAI.value:
            from docagent.audio.stt.openai_whisper import OpenAIWhisperSTT
            return await OpenAIWhisperSTT().transcrever(audio_bytes, openai_api_key or "")

        # Default: faster_whisper
        from docagent.audio.stt.faster_whisper import FasterWhisperSTT
        return await FasterWhisperSTT().transcrever(audio_bytes, config.stt_modelo)

    @staticmethod
    async def sintetizar(
        texto: str,
        config: AudioConfig,
        openai_api_key: str | None = None,
    ) -> bytes:
        """Sintetiza texto em áudio OGG/OPUS usando o provider configurado."""
        provider = config.tts_provider

        if provider == TtsProvider.OPENAI.value:
            from docagent.audio.tts.openai_tts import OpenAITTS
            return await OpenAITTS().sintetizar(texto, config.openai_tts_voz, openai_api_key or "")

        if provider == TtsProvider.ELEVENLABS.value:
            from docagent.audio.tts.elevenlabs import ElevenLabsTTS
            api_key = _decrypt_if_needed(config.elevenlabs_api_key or "")
            return await ElevenLabsTTS().sintetizar(texto, config.elevenlabs_voice_id or "", api_key)

        # Default: piper
        from docagent.audio.tts.piper import PiperTTS
        return await PiperTTS().sintetizar(texto, config.piper_voz)


def _decrypt_if_needed(value: str) -> str:
    """Decriptografa com Fernet se AUDIO_FERNET_KEY estiver configurada."""
    key = Settings().AUDIO_FERNET_KEY
    if not key or not value:
        return value
    try:
        from cryptography.fernet import Fernet
        f = Fernet(key.encode())
        return f.decrypt(value.encode()).decode()
    except Exception:
        log.warning("audio: falha ao decriptografar elevenlabs_api_key — usando plaintext")
        return value
