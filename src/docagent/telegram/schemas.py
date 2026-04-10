from datetime import datetime

from pydantic import BaseModel, Field

from docagent.telegram.models import TelegramBotStatus


class TelegramInstanciaCreate(BaseModel):
    bot_token: str
    agente_id: int | None = None
    cria_atendimentos: bool = True


class TelegramInstanciaUpdate(BaseModel):
    agente_id: int | None = None


class TelegramInstanciaPublic(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    bot_username: str | None
    webhook_configured: bool
    status: TelegramBotStatus
    cria_atendimentos: bool
    tenant_id: int
    agente_id: int | None
    created_at: datetime
    updated_at: datetime
    # bot_token omitido intencionalmente — write-only


# ── Telegram Bot API Update objects ──────────────────────────────────────────

class TelegramUser(BaseModel):
    id: int
    first_name: str
    username: str | None = None
    is_bot: bool = False


class TelegramChat(BaseModel):
    id: int
    type: str  # "private", "group", "supergroup", "channel"
    first_name: str | None = None
    username: str | None = None


class TelegramVoice(BaseModel):
    file_id: str
    duration: int
    mime_type: str | None = None
    file_size: int | None = None


class TelegramAudio(BaseModel):
    file_id: str
    duration: int
    mime_type: str | None = None
    file_size: int | None = None


class TelegramMessage(BaseModel):
    message_id: int
    chat: TelegramChat
    text: str | None = None
    from_: TelegramUser | None = Field(None, alias="from")
    voice: TelegramVoice | None = None   # mensagem de voz gravada (ptt)
    audio: TelegramAudio | None = None   # arquivo de áudio enviado

    model_config = {"populate_by_name": True}


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None
