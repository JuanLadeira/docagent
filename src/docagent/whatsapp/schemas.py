from datetime import datetime

from pydantic import BaseModel, ConfigDict

from docagent.whatsapp.models import ConexaoStatus


# --- Instâncias ---
class InstanciaCreate(BaseModel):
    instance_name: str
    agente_id: int | None = None


class InstanciaUpdate(BaseModel):
    agente_id: int | None = None


class InstanciaPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instance_name: str
    status: ConexaoStatus
    tenant_id: int
    agente_id: int | None = None
    created_at: datetime
    updated_at: datetime


class QRCodeResponse(BaseModel):
    instance_name: str
    qrcode_base64: str | None = None
    status: str


# --- Mensagens ---
class MensagemTextoRequest(BaseModel):
    number: str
    text: str


class MensagemMidiaRequest(BaseModel):
    number: str
    mediatype: str
    mimetype: str
    caption: str | None = None
    media: str
    fileName: str | None = None


class MensagemResponse(BaseModel):
    key: dict
    status: str


# --- Admin ---
class InstanciaResumoStatus(BaseModel):
    total: int
    criadas: int
    conectando: int
    conectadas: int
    desconectadas: int


# --- Webhook ---
class WebhookEvento(BaseModel):
    event: str
    instance: str
    data: dict
