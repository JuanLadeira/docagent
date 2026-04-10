"""
Testes TDD para o nó cv_analyzer do pipeline de vagas.
Sprint 2 — RED antes de implementar nodes/cv_analyzer.py
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from docagent.vagas.models import PipelineStatus
from docagent.vagas.nodes.cv_analyzer import make_cv_analyzer_node, PerfilExtraido
from docagent.vagas.pipeline_state import PipelineVagasState
from docagent.vagas.services import CandidatoService, PipelineRunService
from docagent.vagas.sse import VagasPipelineSseManager


def _make_state(
    tenant_id: int,
    usuario_id: int,
    pipeline_run_id: int,
    cv_text: str = "João Silva\nEngenheiro Python\nSkills: Python, FastAPI",
    cv_filename: str = "curriculo.pdf",
) -> PipelineVagasState:
    return PipelineVagasState(
        tenant_id=tenant_id,
        usuario_id=usuario_id,
        pipeline_run_id=pipeline_run_id,
        cv_text=cv_text,
        cv_filename=cv_filename,
        perfil=None,
        candidato_id=None,
        vagas=[],
        candidaturas=[],
        erro=None,
    )


def _make_mock_llm(perfil: PerfilExtraido) -> MagicMock:
    """LLM mock que retorna um PerfilExtraido via structured output."""
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=perfil)
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


@pytest.mark.asyncio
async def test_cv_analyzer_extrai_perfil(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil_esperado = PerfilExtraido(
        nome="João Silva",
        email="joao@example.com",
        telefone="(11) 9999-0000",
        cargo_desejado="Engenheiro de Software",
        skills=["Python", "FastAPI", "Docker"],
        experiencias=[{"cargo": "Dev", "empresa": "Acme"}],
        formacao=[{"grau": "Bacharelado", "curso": "Ciência da Computação"}],
        resumo="Desenvolvedor Python sênior.",
    )
    mock_llm = _make_mock_llm(perfil_esperado)
    sse_manager = VagasPipelineSseManager()

    state = _make_state(
        tenant_id=tenant.id,
        usuario_id=owner.id,
        pipeline_run_id=run.id,
    )

    node = make_cv_analyzer_node(db_session, sse_manager, llm=mock_llm)
    resultado = await node(state)

    assert resultado["perfil"]["nome"] == "João Silva"
    assert resultado["perfil"]["cargo_desejado"] == "Engenheiro de Software"
    assert "Python" in resultado["perfil"]["skills"]
    assert resultado["candidato_id"] is not None
    assert resultado.get("erro") is None


@pytest.mark.asyncio
async def test_cv_analyzer_persiste_candidato(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil_esperado = PerfilExtraido(
        nome="Maria Oliveira",
        email="maria@example.com",
        telefone="",
        cargo_desejado="Data Scientist",
        skills=["Python", "Pandas", "Machine Learning"],
        experiencias=[],
        formacao=[],
        resumo="Cientista de dados.",
    )
    mock_llm = _make_mock_llm(perfil_esperado)
    sse_manager = VagasPipelineSseManager()

    state = _make_state(
        tenant_id=tenant.id,
        usuario_id=owner.id,
        pipeline_run_id=run.id,
        cv_filename="maria_cv.pdf",
    )

    node = make_cv_analyzer_node(db_session, sse_manager, llm=mock_llm)
    resultado = await node(state)

    candidato_service = CandidatoService(db_session)
    candidato = await candidato_service.get_by_id(resultado["candidato_id"])

    assert candidato is not None
    assert candidato.nome == "Maria Oliveira"
    assert candidato.cargo_desejado == "Data Scientist"
    assert candidato.cv_filename == "maria_cv.pdf"
    assert candidato.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_cv_analyzer_atualiza_status_pipeline_run(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    mock_llm = _make_mock_llm(PerfilExtraido(
        nome="Ana", email="", telefone="", cargo_desejado="Dev",
        skills=[], experiencias=[], formacao=[], resumo="",
    ))
    sse_manager = VagasPipelineSseManager()
    state = _make_state(tenant.id, owner.id, run.id)

    node = make_cv_analyzer_node(db_session, sse_manager, llm=mock_llm)
    await node(state)

    run_atualizado = await run_service.get_by_id(run.id)
    assert run_atualizado.status == PipelineStatus.ANALISANDO_CV.value


@pytest.mark.asyncio
async def test_cv_analyzer_emite_sse(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    mock_llm = _make_mock_llm(PerfilExtraido(
        nome="Bob", email="", telefone="", cargo_desejado="",
        skills=[], experiencias=[], formacao=[], resumo="",
    ))
    sse_manager = VagasPipelineSseManager()
    queue = await sse_manager.subscribe(run.id)

    state = _make_state(tenant.id, owner.id, run.id)
    node = make_cv_analyzer_node(db_session, sse_manager, llm=mock_llm)
    await node(state)

    assert not queue.empty()
    event = queue.get_nowait()
    assert event["type"] == "PROGRESSO"
    assert event["etapa"] == PipelineStatus.ANALISANDO_CV.value


@pytest.mark.asyncio
async def test_cv_analyzer_trunca_texto_longo(db_session, tenant_e_owner):
    """CV com mais de 8000 chars deve ser truncado antes de ir ao LLM."""
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    cv_longo = "A" * 15000

    textos_enviados = []
    perfil_base = PerfilExtraido(
        nome="X", email="", telefone="", cargo_desejado="",
        skills=[], experiencias=[], formacao=[], resumo="",
    )

    structured = MagicMock()
    async def capturar_invoke(mensagem):
        textos_enviados.append(str(mensagem))
        return perfil_base

    structured.ainvoke = capturar_invoke
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured)

    sse_manager = VagasPipelineSseManager()
    state = _make_state(tenant.id, owner.id, run.id, cv_text=cv_longo)

    node = make_cv_analyzer_node(db_session, sse_manager, llm=llm)
    await node(state)

    # O texto enviado ao LLM não deve exceder 8000 chars
    assert len(textos_enviados) == 1
    assert len(textos_enviados[0]) < 10000  # folga para o prompt


@pytest.mark.asyncio
async def test_cv_analyzer_fallback_llm_error(db_session, tenant_e_owner):
    """Falha do LLM deve retornar perfil vazio sem travar o pipeline."""
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    structured = MagicMock()
    structured.ainvoke = AsyncMock(side_effect=Exception("LLM connection error"))
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured)

    sse_manager = VagasPipelineSseManager()
    state = _make_state(tenant.id, owner.id, run.id)

    node = make_cv_analyzer_node(db_session, sse_manager, llm=llm)
    resultado = await node(state)

    # Não deve propagar exceção — retorna perfil vazio
    assert resultado["perfil"] is not None
    assert resultado["candidato_id"] is not None  # candidato criado com dados vazios


@pytest.mark.asyncio
async def test_cv_analyzer_cv_vazio_retorna_erro(db_session, tenant_e_owner):
    """CV sem texto (scaneado/vazio) deve sinalizar erro no estado."""
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    mock_llm = _make_mock_llm(PerfilExtraido(
        nome="", email="", telefone="", cargo_desejado="",
        skills=[], experiencias=[], formacao=[], resumo="",
    ))
    sse_manager = VagasPipelineSseManager()
    state = _make_state(tenant.id, owner.id, run.id, cv_text="   ")

    node = make_cv_analyzer_node(db_session, sse_manager, llm=mock_llm)
    resultado = await node(state)

    assert resultado["erro"] is not None
    assert "vazio" in resultado["erro"].lower() or "texto" in resultado["erro"].lower()
