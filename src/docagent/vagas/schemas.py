from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FonteNome = Literal["GUPY", "DUCKDUCKGO", "LINKEDIN", "INDEED"]
FONTES_DISPONIVEIS: list[FonteNome] = ["GUPY", "DUCKDUCKGO", "LINKEDIN", "INDEED"]

ModalidadeVaga = Literal["HOMEOFFICE", "PRESENCIAL", "HIBRIDO"]


class PipelineConfig(BaseModel):
    """Configurações do pipeline de vagas."""

    max_vagas_por_fonte: int = Field(default=20, ge=1, le=100, description="Máximo de vagas por fonte (cada fonte contribui até este limite)")
    max_personalizar: int = Field(default=10, ge=1, le=50, description="Máximo de candidaturas geradas")
    fontes: list[FonteNome] = Field(
        default_factory=lambda: list(FONTES_DISPONIVEIS),
        description="Origens de busca de vagas",
    )
    candidatura_simplificada: bool = Field(
        default=False,
        description="Gera resumo curto (1 parágrafo) e carta direta (3 frases)",
    )
    apenas_simplificadas: bool = Field(
        default=False,
        description="Buscar apenas vagas com candidatura simplificada (Easy Apply, Gupy Apply...)",
    )
    modalidade: ModalidadeVaga | None = Field(
        default=None,
        description=(
            "Filtra vagas por modalidade de trabalho. "
            "None = qualquer modalidade. "
            "HOMEOFFICE / PRESENCIAL / HIBRIDO descarta vagas sem esse atributo identificado no texto."
        ),
    )


# ──────────────────────────────────────────────
# Candidato
# ──────────────────────────────────────────────

class CandidatoPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    usuario_id: int
    nome: str
    email: str
    telefone: str
    skills: list
    experiencias: list
    formacao: list
    cargo_desejado: str
    resumo: str
    cv_filename: str
    created_at: datetime


# ──────────────────────────────────────────────
# PipelineRun
# ──────────────────────────────────────────────

class PipelineRunCreate(BaseModel):
    cv_filename: str


class PipelineRunPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    usuario_id: int
    candidato_id: int | None
    status: str
    etapa_atual: str | None
    erro: str | None
    vagas_encontradas: int
    candidaturas_criadas: int
    created_at: datetime


class PipelineIniciadoResponse(BaseModel):
    pipeline_run_id: int
    status: str
    message: str


# ──────────────────────────────────────────────
# Vaga
# ──────────────────────────────────────────────

class VagaPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_run_id: int
    titulo: str
    empresa: str
    localizacao: str
    descricao: str
    requisitos: str
    url: str
    fonte: str
    match_score: float
    candidatura_simplificada: bool = False


class VagaResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    empresa: str
    localizacao: str
    url: str
    fonte: str
    match_score: float
    candidatura_simplificada: bool = False


# ──────────────────────────────────────────────
# Candidatura
# ──────────────────────────────────────────────

class CandidaturaPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_run_id: int
    vaga_id: int
    candidato_id: int
    resumo_personalizado: str
    carta_apresentacao: str
    status: str
    simplificada: bool = False


class CandidaturaUpdate(BaseModel):
    status: str


class CandidaturaResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vaga_id: int
    status: str
    simplificada: bool = False


# ──────────────────────────────────────────────
# Detalhe de PipelineRun (com vagas + candidaturas)
# ──────────────────────────────────────────────

class PipelineRunDetalhe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    usuario_id: int
    candidato_id: int | None
    status: str
    etapa_atual: str | None
    erro: str | None
    vagas_encontradas: int
    candidaturas_criadas: int
    created_at: datetime
    vagas: list[VagaResumo] = []
    candidaturas: list[CandidaturaResumo] = []
