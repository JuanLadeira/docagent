from datetime import datetime

from pydantic import BaseModel

from docagent.atendimento.models import AtendimentoStatus, MensagemOrigem


class MensagemPublic(BaseModel):
    id: int
    origem: MensagemOrigem
    conteudo: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AtendimentoPublic(BaseModel):
    id: int
    numero: str
    nome_contato: str | None
    instancia_id: int
    tenant_id: int
    status: AtendimentoStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AtendimentoDetalhe(AtendimentoPublic):
    mensagens: list[MensagemPublic] = []


class OperadorMensagemRequest(BaseModel):
    conteudo: str


class AtendimentoCreate(BaseModel):
    instancia_id: int
    numero: str
    mensagem_inicial: str | None = None
