from pydantic import BaseModel, Field

from docagent.audio.models import ModoResposta, SttProvider, TtsProvider


class AudioConfigBase(BaseModel):
    stt_habilitado: bool = False
    stt_provider: SttProvider = SttProvider.FASTER_WHISPER
    stt_modelo: str = "base"

    tts_habilitado: bool = False
    tts_provider: TtsProvider = TtsProvider.PIPER
    piper_voz: str = "pt_BR-faber-medium"
    openai_tts_voz: str = "nova"
    elevenlabs_voice_id: str | None = None
    elevenlabs_api_key: str | None = Field(None, description="Criptografado em repouso")

    modo_resposta: ModoResposta = ModoResposta.AUDIO_E_TEXTO


class AudioConfigCreate(AudioConfigBase):
    pass


class AudioConfigUpdate(AudioConfigBase):
    pass


class AudioConfigPublic(AudioConfigBase):
    id: int
    tenant_id: int
    agente_id: int | None = None
    is_agent_override: bool = False

    model_config = {"from_attributes": True}
