from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docagent.database import Base

if TYPE_CHECKING:
    from docagent.tenant.models import Tenant
    from docagent.usuario.models import Usuario


class PipelineStatus(str, Enum):
    PENDENTE = "PENDENTE"
    ANALISANDO_CV = "ANALISANDO_CV"
    BUSCANDO_VAGAS = "BUSCANDO_VAGAS"
    PERSONALIZANDO = "PERSONALIZANDO"
    REGISTRANDO = "REGISTRANDO"
    CONCLUIDO = "CONCLUIDO"
    ERRO = "ERRO"


class CandidaturaStatus(str, Enum):
    AGUARDANDO_ENVIO = "AGUARDANDO_ENVIO"
    ENVIADA = "ENVIADA"
    REJEITADA = "REJEITADA"


class FonteVaga(str, Enum):
    DUCKDUCKGO = "DUCKDUCKGO"
    GUPY = "GUPY"
    LINKEDIN = "LINKEDIN"
    INDEED = "INDEED"


class Candidato(Base):
    __tablename__ = "candidatos"

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    telefone: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    experiencias: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    formacao: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cargo_desejado: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    resumo: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cv_filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    cv_texto: Mapped[str] = mapped_column(Text, nullable=False, default="")

    tenant: Mapped["Tenant"] = relationship("Tenant")
    usuario: Mapped["Usuario"] = relationship("Usuario")
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(
        "PipelineRun", back_populates="candidato"
    )
    candidaturas: Mapped[list["Candidatura"]] = relationship(
        "Candidatura", back_populates="candidato"
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False
    )
    candidato_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidatos.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=PipelineStatus.PENDENTE.value
    )
    etapa_atual: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    vagas_encontradas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidaturas_criadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tenant: Mapped["Tenant"] = relationship("Tenant")
    usuario: Mapped["Usuario"] = relationship("Usuario")
    candidato: Mapped["Candidato | None"] = relationship(
        "Candidato", back_populates="pipeline_runs"
    )
    vagas: Mapped[list["Vaga"]] = relationship(
        "Vaga", back_populates="pipeline_run", cascade="all, delete-orphan"
    )
    candidaturas: Mapped[list["Candidatura"]] = relationship(
        "Candidatura", back_populates="pipeline_run", cascade="all, delete-orphan"
    )


class Vaga(Base):
    __tablename__ = "vagas"

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    titulo: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    empresa: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    localizacao: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    descricao: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requisitos: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    fonte: Mapped[str] = mapped_column(String(50), nullable=False, default=FonteVaga.DUCKDUCKGO.value)
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # True quando a plataforma oferece candidatura direta/simplificada (Easy Apply, Gupy Apply etc.)
    candidatura_simplificada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    pipeline_run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="vagas")
    candidatura: Mapped["Candidatura | None"] = relationship(
        "Candidatura", back_populates="vaga"
    )


class Candidatura(Base):
    __tablename__ = "candidaturas"

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vaga_id: Mapped[int] = mapped_column(
        ForeignKey("vagas.id", ondelete="CASCADE"), nullable=False
    )
    candidato_id: Mapped[int] = mapped_column(
        ForeignKey("candidatos.id", ondelete="CASCADE"), nullable=False
    )
    resumo_personalizado: Mapped[str] = mapped_column(Text, nullable=False, default="")
    carta_apresentacao: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=CandidaturaStatus.AGUARDANDO_ENVIO.value
    )
    simplificada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    pipeline_run: Mapped["PipelineRun"] = relationship(
        "PipelineRun", back_populates="candidaturas"
    )
    vaga: Mapped["Vaga"] = relationship("Vaga", back_populates="candidatura")
    candidato: Mapped["Candidato"] = relationship("Candidato", back_populates="candidaturas")
