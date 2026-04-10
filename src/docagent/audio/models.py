"""
Modelos de configuração de áudio (STT + TTS) por tenant/agente.
"""
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from docagent.database import Base

if TYPE_CHECKING:
    pass


class SttProvider(str, Enum):
    FASTER_WHISPER = "faster_whisper"
    OPENAI = "openai"


class TtsProvider(str, Enum):
    PIPER = "piper"
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"


class ModoResposta(str, Enum):
    AUDIO_APENAS = "audio_apenas"
    TEXTO_APENAS = "texto_apenas"
    AUDIO_E_TEXTO = "audio_e_texto"


class AudioConfig(Base):
    __tablename__ = "audio_config"
    __table_args__ = (
        UniqueConstraint("tenant_id", "agente_id", name="uq_audio_config_tenant_agente"),
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    agente_id: Mapped[int | None] = mapped_column(ForeignKey("agente.id"), nullable=True)
    # agente_id IS NULL → config padrão do tenant
    # agente_id preenchido → config específica do agente

    # STT
    stt_habilitado: Mapped[bool] = mapped_column(default=False)
    stt_provider: Mapped[str] = mapped_column(default=SttProvider.FASTER_WHISPER.value)
    stt_modelo: Mapped[str] = mapped_column(default="base")

    # TTS
    tts_habilitado: Mapped[bool] = mapped_column(default=False)
    tts_provider: Mapped[str] = mapped_column(default=TtsProvider.PIPER.value)
    piper_voz: Mapped[str] = mapped_column(default="pt_BR-faber-medium")
    openai_tts_voz: Mapped[str] = mapped_column(default="nova")
    elevenlabs_voice_id: Mapped[str | None] = mapped_column(nullable=True)
    elevenlabs_api_key: Mapped[str | None] = mapped_column(nullable=True)

    # Modo de resposta
    modo_resposta: Mapped[str] = mapped_column(default=ModoResposta.AUDIO_E_TEXTO.value)
