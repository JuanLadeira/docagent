"""
Router do módulo de vagas.
Endpoints para pipeline de busca de emprego multi-agente.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Form, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse, Response

from docagent.auth.current_user import CurrentUser
from docagent.database import AsyncDBSession
from docagent.vagas.models import CandidaturaStatus
from docagent.vagas.pipeline import executar_pipeline, executar_pipeline_reuso
from docagent.vagas.schemas import (
    CandidaturaPublic,
    CandidaturaUpdate,
    PipelineConfig,
    PipelineIniciadoResponse,
    PipelineRunDetalhe,
    PipelineRunPublic,
    VagaPublic,
)
from docagent.vagas.services import (
    CandidatoService,
    CandidaturaService,
    PipelineRunService,
    VagaService,
)
from docagent.vagas.sse import vagas_sse_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vagas", tags=["Vagas"])


def extrair_texto_pdf(conteudo: bytes, filename: str) -> str:
    """Extrai texto de PDF usando PyMuPDF (síncrono — chamar via to_thread)."""
    import tempfile
    import os
    from langchain_community.document_loaders import PyMuPDFLoader

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(conteudo)
        tmp_path = tmp.name

    try:
        loader = PyMuPDFLoader(tmp_path)
        docs = loader.load()
        return "\n".join(doc.page_content for doc in docs)
    finally:
        os.unlink(tmp_path)


# ──────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────

@router.post(
    "/pipeline",
    response_model=PipelineIniciadoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def iniciar_pipeline(
    current_user: CurrentUser,
    session: AsyncDBSession,
    cv: UploadFile = File(...),
    config_json: str = Form(default="{}"),
):
    """Recebe CV em PDF + config opcional JSON, cria PipelineRun e lança pipeline em background.

    config_json (Form field, opcional): JSON com campos de PipelineConfig:
      - max_vagas (int 1-50, default 20)
      - max_personalizar (int 1-20, default 10)
      - fontes (list: GUPY, DUCKDUCKGO, LINKEDIN, INDEED)
      - candidatura_simplificada (bool, default false)
    """
    conteudo = await cv.read()
    cv_text = await asyncio.to_thread(extrair_texto_pdf, conteudo, cv.filename or "cv.pdf")

    if not cv_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF não contém texto legível. Verifique se o arquivo não está scaneado.",
        )

    try:
        config = PipelineConfig.model_validate_json(config_json) if config_json.strip() else PipelineConfig()
    except Exception:
        logger.warning("iniciar_pipeline: config_json inválido, usando defaults. Recebido: %r", config_json)
        config = PipelineConfig()

    run_service = PipelineRunService(session)
    run = await run_service.criar(
        tenant_id=current_user.tenant_id,
        usuario_id=current_user.id,
    )

    asyncio.create_task(
        executar_pipeline(
            tenant_id=current_user.tenant_id,
            usuario_id=current_user.id,
            pipeline_run_id=run.id,
            cv_text=cv_text,
            cv_filename=cv.filename or "cv.pdf",
            config=config.model_dump(),
        )
    )

    return PipelineIniciadoResponse(
        pipeline_run_id=run.id,
        status=run.status,
        message=f"Pipeline iniciado. Acompanhe via /api/vagas/pipeline/{run.id}/eventos",
    )


@router.get("/pipeline/{run_id}/eventos")
async def eventos_pipeline(
    run_id: int,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    """SSE — progresso do pipeline em tempo real."""
    run_service = PipelineRunService(session)
    run = await run_service.get_by_id(run_id)

    if not run or run.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Pipeline não encontrado.")

    async def event_stream():
        queue = await vagas_sse_manager.subscribe(run_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") in ("CONCLUIDO", "ERRO"):
                        break
                except asyncio.TimeoutError:
                    yield "data: {\"type\": \"ping\"}\n\n"
        finally:
            vagas_sse_manager.unsubscribe(run_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ──────────────────────────────────────────────
# Candidatos (perfis extraídos dos CVs)
# ──────────────────────────────────────────────

@router.post("/candidatos/{candidato_id}/pipeline", response_model=PipelineIniciadoResponse, status_code=201)
async def reutilizar_pipeline(
    candidato_id: int,
    current_user: CurrentUser,
    session: AsyncDBSession,
    config_json: str = Form(default="{}"),
):
    """Inicia novo pipeline reutilizando um Candidato existente.

    Não exige upload de CV. Exclui automaticamente URLs de vagas já encontradas
    em runs anteriores do mesmo candidato.
    """
    candidato_service = CandidatoService(session)
    candidato = await candidato_service.get_by_id(candidato_id)

    if not candidato or candidato.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Candidato não encontrado.")

    try:
        config = PipelineConfig.model_validate_json(config_json) if config_json.strip() else PipelineConfig()
    except Exception:
        logger.warning("reutilizar_pipeline: config_json inválido, usando defaults.")
        config = PipelineConfig()

    # Coleta URLs já encontradas para excluir desta busca
    vaga_service = VagaService(session)
    excluir_urls = await vaga_service.listar_urls_por_candidato(candidato_id)

    run_service = PipelineRunService(session)
    run = await run_service.criar(
        tenant_id=current_user.tenant_id,
        usuario_id=current_user.id,
    )

    asyncio.create_task(
        executar_pipeline_reuso(
            tenant_id=current_user.tenant_id,
            usuario_id=current_user.id,
            pipeline_run_id=run.id,
            candidato_id=candidato_id,
            excluir_urls=excluir_urls,
            config=config.model_dump(),
        )
    )

    return PipelineIniciadoResponse(
        pipeline_run_id=run.id,
        status=run.status,
        message=f"Pipeline iniciado para {candidato.nome or 'candidato'}. {len(excluir_urls)} vagas anteriores excluídas da busca.",
    )


@router.get("/candidatos", response_model=list[dict])
async def listar_candidatos(
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    """Lista os perfis de candidato criados pelos CVs enviados pelo tenant."""
    service = CandidatoService(session)
    candidatos = await service.listar_por_tenant(current_user.tenant_id)
    return [
        {
            "id": c.id,
            "nome": c.nome,
            "cargo_desejado": c.cargo_desejado,
            "email": c.email,
            "skills": c.skills,
            "cv_filename": c.cv_filename,
            "created_at": c.created_at.isoformat(),
        }
        for c in candidatos
    ]


# ──────────────────────────────────────────────
# Listagem de PipelineRuns
# ──────────────────────────────────────────────

@router.get("/pipelines", response_model=list[PipelineRunPublic])
async def listar_pipelines(
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    service = PipelineRunService(session)
    return await service.listar_por_tenant(current_user.tenant_id)


@router.get("/pipelines/{run_id}", response_model=PipelineRunDetalhe)
async def get_pipeline_detalhe(
    run_id: int,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    run_service = PipelineRunService(session)
    vaga_service = VagaService(session)
    cand_service = CandidaturaService(session)

    run = await run_service.get_by_id(run_id)
    if not run or run.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Pipeline não encontrado.")

    vagas = await vaga_service.listar_por_pipeline_run(run_id)
    candidaturas = await cand_service.listar_por_pipeline_run(run_id)

    return PipelineRunDetalhe(
        id=run.id,
        tenant_id=run.tenant_id,
        usuario_id=run.usuario_id,
        candidato_id=run.candidato_id,
        status=run.status,
        etapa_atual=run.etapa_atual,
        erro=run.erro,
        vagas_encontradas=run.vagas_encontradas,
        candidaturas_criadas=run.candidaturas_criadas,
        created_at=run.created_at,
        vagas=[v for v in vagas],
        candidaturas=[c for c in candidaturas],
    )


# ──────────────────────────────────────────────
# Vagas
# ──────────────────────────────────────────────

@router.get("/vagas", response_model=list[VagaPublic])
async def listar_vagas(
    current_user: CurrentUser,
    session: AsyncDBSession,
    pipeline_run_id: int = Query(...),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
):
    # Verifica que o run pertence ao tenant
    run_service = PipelineRunService(session)
    run = await run_service.get_by_id(pipeline_run_id)
    if not run or run.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Pipeline não encontrado.")

    vaga_service = VagaService(session)
    return await vaga_service.listar_por_pipeline_run(pipeline_run_id, min_score=min_score)


# ──────────────────────────────────────────────
# Candidaturas
# ──────────────────────────────────────────────

@router.get("/candidaturas", response_model=list[CandidaturaPublic])
async def listar_candidaturas(
    current_user: CurrentUser,
    session: AsyncDBSession,
    pipeline_run_id: int = Query(...),
    status_filtro: str | None = Query(None, alias="status"),
):
    run_service = PipelineRunService(session)
    run = await run_service.get_by_id(pipeline_run_id)
    if not run or run.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Pipeline não encontrado.")

    cand_service = CandidaturaService(session)
    status_enum = None
    if status_filtro:
        try:
            status_enum = CandidaturaStatus(status_filtro)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Status inválido: {status_filtro}")

    return await cand_service.listar_por_pipeline_run(pipeline_run_id, status=status_enum)


@router.get("/candidaturas/{candidatura_id}", response_model=CandidaturaPublic)
async def get_candidatura(
    candidatura_id: int,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    cand_service = CandidaturaService(session)
    candidatura = await cand_service.get_by_id(candidatura_id)

    if not candidatura or candidatura.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada.")

    return candidatura


@router.get("/candidaturas/{candidatura_id}/pdf")
async def download_pdf_candidatura(
    candidatura_id: int,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    """Gera e retorna PDF com o currículo adaptado + carta de apresentação."""
    cand_service = CandidaturaService(session)
    candidatura = await cand_service.get_by_id(candidatura_id)

    if not candidatura or candidatura.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada.")

    vaga_service = VagaService(session)
    vaga = await vaga_service.get_by_id(candidatura.vaga_id)

    candidato_service = CandidatoService(session)
    candidato = await candidato_service.get_by_id(candidatura.candidato_id)

    from docagent.vagas.pdf_generator import DadosCandidatura, gerar_pdf_candidatura

    dados = DadosCandidatura(
        nome_candidato=candidato.nome if candidato else "Candidato",
        email=candidato.email if candidato else "",
        telefone=candidato.telefone if candidato else "",
        cargo_desejado=candidato.cargo_desejado if candidato else "",
        titulo_vaga=vaga.titulo if vaga else "",
        empresa=vaga.empresa if vaga else "",
        resumo_personalizado=candidatura.resumo_personalizado,
        skills=candidato.skills if candidato else [],
        experiencias=candidato.experiencias if candidato else [],
        formacao=candidato.formacao if candidato else [],
        cv_texto=candidato.cv_texto if candidato else "",
        simplificada=candidatura.simplificada,
    )

    pdf_bytes = await asyncio.to_thread(gerar_pdf_candidatura, dados)

    nome_arquivo = f"candidatura_{candidatura_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.patch("/candidaturas/{candidatura_id}", response_model=CandidaturaPublic)
async def atualizar_candidatura(
    candidatura_id: int,
    data: CandidaturaUpdate,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    try:
        novo_status = CandidaturaStatus(data.status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Status inválido: {data.status}")

    cand_service = CandidaturaService(session)
    candidatura = await cand_service.get_by_id(candidatura_id)

    if not candidatura or candidatura.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada.")

    return await cand_service.atualizar_status(candidatura_id, novo_status)
