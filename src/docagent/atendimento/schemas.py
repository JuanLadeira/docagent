from datetime import datetime

from pydantic import BaseModel

from docagent.atendimento.models import AtendimentoStatus, CanalAtendimento, MensagemOrigem, Prioridade


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
    canal: CanalAtendimento
    instancia_id: int | None
    telegram_instancia_id: int | None
    tenant_id: int
    status: AtendimentoStatus
    prioridade: Prioridade
    assumido_por_id: int | None
    assumido_por_nome: str | None
    contato_id: int | None
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


class ContatoCreate(BaseModel):
    numero: str
    nome: str
    email: str | None = None
    notas: str | None = None
    instancia_id: int


class ContatoUpdate(BaseModel):
    nome: str | None = None
    email: str | None = None
    notas: str | None = None


class ContatoPublic(BaseModel):
    id: int
    numero: str
    nome: str
    email: str | None
    notas: str | None
    instancia_id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContatoDetalhe(ContatoPublic):
    atendimentos: list[AtendimentoPublic] = []
