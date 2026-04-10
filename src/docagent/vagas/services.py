from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.database import AsyncDBSession
from docagent.vagas.models import (
    Candidato,
    Candidatura,
    CandidaturaStatus,
    FonteVaga,
    PipelineRun,
    PipelineStatus,
    Vaga,
)


class CandidatoService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def criar(
        self,
        tenant_id: int,
        usuario_id: int,
        nome: str,
        email: str,
        telefone: str,
        skills: list,
        experiencias: list,
        formacao: list,
        cargo_desejado: str,
        resumo: str,
        cv_filename: str,
        cv_texto: str = "",
    ) -> Candidato:
        candidato = Candidato(
            tenant_id=tenant_id,
            usuario_id=usuario_id,
            nome=nome,
            email=email,
            telefone=telefone,
            skills=skills,
            experiencias=experiencias,
            formacao=formacao,
            cargo_desejado=cargo_desejado,
            resumo=resumo,
            cv_filename=cv_filename,
            cv_texto=cv_texto,
        )
        self.session.add(candidato)
        await self.session.flush()
        await self.session.refresh(candidato)
        return candidato

    async def get_by_id(self, candidato_id: int) -> Candidato | None:
        return await self.session.get(Candidato, candidato_id)

    async def listar_por_tenant(self, tenant_id: int) -> list[Candidato]:
        result = await self.session.execute(
            select(Candidato)
            .where(Candidato.tenant_id == tenant_id)
            .order_by(Candidato.id.desc())
        )
        return list(result.scalars().all())


class PipelineRunService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def criar(self, tenant_id: int, usuario_id: int) -> PipelineRun:
        run = PipelineRun(
            tenant_id=tenant_id,
            usuario_id=usuario_id,
            status=PipelineStatus.PENDENTE.value,
            etapa_atual="",
        )
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def get_by_id(self, run_id: int) -> PipelineRun | None:
        return await self.session.get(PipelineRun, run_id)

    async def listar_por_tenant(self, tenant_id: int) -> list[PipelineRun]:
        result = await self.session.execute(
            select(PipelineRun)
            .where(PipelineRun.tenant_id == tenant_id)
            .order_by(PipelineRun.id.desc())
        )
        return list(result.scalars().all())

    async def atualizar_status(
        self,
        run_id: int,
        status: PipelineStatus,
        etapa_atual: str = "",
        candidato_id: int | None = None,
    ) -> None:
        run = await self.session.get(PipelineRun, run_id)
        if not run:
            return
        run.status = status.value
        if etapa_atual:
            run.etapa_atual = etapa_atual
        if candidato_id is not None:
            run.candidato_id = candidato_id
        await self.session.flush()

    async def finalizar(
        self, run_id: int, vagas_encontradas: int, candidaturas_criadas: int
    ) -> None:
        run = await self.session.get(PipelineRun, run_id)
        if not run:
            return
        run.status = PipelineStatus.CONCLUIDO.value
        run.etapa_atual = "Concluído"
        run.vagas_encontradas = vagas_encontradas
        run.candidaturas_criadas = candidaturas_criadas
        await self.session.flush()

    async def registrar_erro(self, run_id: int, mensagem: str) -> None:
        run = await self.session.get(PipelineRun, run_id)
        if not run:
            return
        run.status = PipelineStatus.ERRO.value
        run.erro = mensagem
        await self.session.flush()


class VagaService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def criar(
        self,
        tenant_id: int,
        pipeline_run_id: int,
        titulo: str,
        empresa: str,
        localizacao: str,
        descricao: str,
        requisitos: str,
        url: str,
        fonte: FonteVaga,
        match_score: float,
        raw_data: dict,
        candidatura_simplificada: bool = False,
    ) -> Vaga:
        vaga = Vaga(
            tenant_id=tenant_id,
            pipeline_run_id=pipeline_run_id,
            titulo=titulo,
            empresa=empresa,
            localizacao=localizacao,
            descricao=descricao,
            requisitos=requisitos,
            url=url,
            fonte=fonte.value,
            match_score=match_score,
            raw_data=raw_data,
            candidatura_simplificada=candidatura_simplificada,
        )
        self.session.add(vaga)
        await self.session.flush()
        await self.session.refresh(vaga)
        return vaga

    async def get_by_id(self, vaga_id: int) -> Vaga | None:
        return await self.session.get(Vaga, vaga_id)

    async def listar_por_pipeline_run(
        self, pipeline_run_id: int, min_score: float = 0.0
    ) -> list[Vaga]:
        result = await self.session.execute(
            select(Vaga)
            .where(
                Vaga.pipeline_run_id == pipeline_run_id,
                Vaga.match_score >= min_score,
            )
            .order_by(Vaga.match_score.desc())
        )
        return list(result.scalars().all())

    async def criar_em_lote(self, vagas_data: list[dict]) -> list[Vaga]:
        vagas = []
        for data in vagas_data:
            vaga = await self.criar(**data)
            vagas.append(vaga)
        return vagas

    async def listar_urls_por_candidato(self, candidato_id: int) -> list[str]:
        """Retorna todas as URLs de vagas já encontradas para um candidato (todos os seus runs)."""
        result = await self.session.execute(
            select(Vaga.url)
            .join(PipelineRun, Vaga.pipeline_run_id == PipelineRun.id)
            .where(PipelineRun.candidato_id == candidato_id)
            .where(Vaga.url != "")
        )
        return list(result.scalars().all())


class CandidaturaService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def criar(
        self,
        tenant_id: int,
        pipeline_run_id: int,
        vaga_id: int,
        candidato_id: int,
        resumo_personalizado: str,
        carta_apresentacao: str,
        simplificada: bool = False,
    ) -> Candidatura:
        candidatura = Candidatura(
            tenant_id=tenant_id,
            pipeline_run_id=pipeline_run_id,
            vaga_id=vaga_id,
            candidato_id=candidato_id,
            resumo_personalizado=resumo_personalizado,
            carta_apresentacao=carta_apresentacao,
            status=CandidaturaStatus.AGUARDANDO_ENVIO.value,
            simplificada=simplificada,
        )
        self.session.add(candidatura)
        await self.session.flush()
        await self.session.refresh(candidatura)
        return candidatura

    async def get_by_id(self, candidatura_id: int) -> Candidatura | None:
        return await self.session.get(Candidatura, candidatura_id)

    async def listar_por_pipeline_run(
        self, pipeline_run_id: int, status: CandidaturaStatus | None = None
    ) -> list[Candidatura]:
        query = select(Candidatura).where(
            Candidatura.pipeline_run_id == pipeline_run_id
        )
        if status is not None:
            query = query.where(Candidatura.status == status.value)
        result = await self.session.execute(query.order_by(Candidatura.id))
        return list(result.scalars().all())

    async def atualizar_status(
        self, candidatura_id: int, status: CandidaturaStatus
    ) -> Candidatura | None:
        candidatura = await self.session.get(Candidatura, candidatura_id)
        if not candidatura:
            return None
        candidatura.status = status.value
        await self.session.flush()
        await self.session.refresh(candidatura)
        return candidatura


def get_candidato_service(session: AsyncDBSession) -> CandidatoService:
    return CandidatoService(session)


def get_pipeline_run_service(session: AsyncDBSession) -> PipelineRunService:
    return PipelineRunService(session)


def get_vaga_service(session: AsyncDBSession) -> VagaService:
    return VagaService(session)


def get_candidatura_service(session: AsyncDBSession) -> CandidaturaService:
    return CandidaturaService(session)


CandidatoServiceDep = Annotated[CandidatoService, Depends(get_candidato_service)]
PipelineRunServiceDep = Annotated[PipelineRunService, Depends(get_pipeline_run_service)]
VagaServiceDep = Annotated[VagaService, Depends(get_vaga_service)]
CandidaturaServiceDep = Annotated[CandidaturaService, Depends(get_candidatura_service)]
