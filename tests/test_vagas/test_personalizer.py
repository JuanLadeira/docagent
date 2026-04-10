"""
Testes TDD para os nós personalizer e registrar.
Sprint 4 — RED antes de implementar nodes/personalizer.py e nodes/registrar.py
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from docagent.vagas.models import CandidaturaStatus, FonteVaga, PipelineStatus
from docagent.vagas.nodes.personalizer import make_personalizer_node
from docagent.vagas.nodes.registrar import make_registrar_node
from docagent.vagas.pipeline_state import PipelineVagasState
from docagent.vagas.services import (
    CandidatoService,
    CandidaturaService,
    PipelineRunService,
    VagaService,
)
from docagent.vagas.sse import VagasPipelineSseManager


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

async def _criar_setup(db_session, tenant, owner, n_vagas=3):
    """Cria run, candidato e n_vagas persistidas. Retorna (run, candidato, vagas_dicts)."""
    run_service = PipelineRunService(db_session)
    candidato_service = CandidatoService(db_session)
    vaga_service = VagaService(db_session)

    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)
    candidato = await candidato_service.criar(
        tenant_id=tenant.id, usuario_id=owner.id,
        nome="João Silva", email="joao@example.com", telefone="",
        skills=["Python", "FastAPI"], experiencias=[],
        formacao=[], cargo_desejado="Dev Python",
        resumo="Dev Python sênior.", cv_filename="cv.pdf",
    )

    vagas_dicts = []
    for i in range(n_vagas):
        vaga = await vaga_service.criar(
            tenant_id=tenant.id, pipeline_run_id=run.id,
            titulo=f"Vaga {i}", empresa=f"Empresa {i}",
            localizacao="Remoto", descricao=f"Python FastAPI vaga {i}",
            requisitos="Python, FastAPI", url=f"https://example.com/{i}",
            fonte=FonteVaga.GUPY, match_score=0.8 - i * 0.1, raw_data={},
        )
        vagas_dicts.append({"id": vaga.id, "titulo": vaga.titulo,
                             "empresa": vaga.empresa, "url": vaga.url,
                             "match_score": vaga.match_score})

    return run, candidato, vagas_dicts


def _make_state(tenant_id, usuario_id, pipeline_run_id, candidato_id, vagas) -> PipelineVagasState:
    return PipelineVagasState(
        tenant_id=tenant_id,
        usuario_id=usuario_id,
        pipeline_run_id=pipeline_run_id,
        cv_text="",
        cv_filename="cv.pdf",
        perfil={"nome": "João", "skills": ["Python", "FastAPI"],
                "cargo_desejado": "Dev Python", "resumo": "Dev sênior."},
        candidato_id=candidato_id,
        vagas=vagas,
        candidaturas=[],
        erro=None,
    )


def _make_mock_llm(resumo="Resumo personalizado.", carta="Carta de apresentação."):
    """LLM mock que retorna resumo e carta."""
    resposta = MagicMock()
    resposta.content = f'{{"resumo": "{resumo}", "carta": "{carta}"}}'
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=resposta)
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=chain)
    return llm


# ──────────────────────────────────────────────
# Personalizer
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_personalizer_cria_candidaturas(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run, candidato, vagas = await _criar_setup(db_session, tenant, owner, n_vagas=3)

    state = _make_state(tenant.id, owner.id, run.id, candidato.id, vagas)
    mock_llm = _make_mock_llm()
    sse_manager = VagasPipelineSseManager()

    node = make_personalizer_node(db_session, sse_manager, llm=mock_llm)
    resultado = await node(state)

    assert len(resultado["candidaturas"]) == 3
    assert resultado.get("erro") is None


@pytest.mark.asyncio
async def test_personalizer_persiste_candidaturas_individualmente(db_session, tenant_e_owner):
    """Cada candidatura deve ser persistida ao ser gerada, não em batch."""
    tenant, owner = tenant_e_owner
    run, candidato, vagas = await _criar_setup(db_session, tenant, owner, n_vagas=2)

    state = _make_state(tenant.id, owner.id, run.id, candidato.id, vagas)
    mock_llm = _make_mock_llm(
        resumo="CV adaptado para a vaga.",
        carta="Prezados, tenho interesse nesta oportunidade.",
    )
    sse_manager = VagasPipelineSseManager()

    node = make_personalizer_node(db_session, sse_manager, llm=mock_llm)
    await node(state)

    cand_service = CandidaturaService(db_session)
    persistidas = await cand_service.listar_por_pipeline_run(run.id)

    assert len(persistidas) == 2
    for c in persistidas:
        assert c.status == CandidaturaStatus.AGUARDANDO_ENVIO.value
        assert c.candidato_id == candidato.id


@pytest.mark.asyncio
async def test_personalizer_limita_top10(db_session, tenant_e_owner):
    """Com mais de 10 vagas, personalizer processa apenas as top 10."""
    tenant, owner = tenant_e_owner
    run, candidato, vagas = await _criar_setup(db_session, tenant, owner, n_vagas=15)

    state = _make_state(tenant.id, owner.id, run.id, candidato.id, vagas)
    mock_llm = _make_mock_llm()
    sse_manager = VagasPipelineSseManager()

    node = make_personalizer_node(db_session, sse_manager, llm=mock_llm)
    resultado = await node(state)

    assert len(resultado["candidaturas"]) == 10

    cand_service = CandidaturaService(db_session)
    persistidas = await cand_service.listar_por_pipeline_run(run.id)
    assert len(persistidas) == 10


@pytest.mark.asyncio
async def test_personalizer_processa_em_sequencia(db_session, tenant_e_owner):
    """LLM deve ser chamado uma vez por vaga (não em paralelo)."""
    tenant, owner = tenant_e_owner
    run, candidato, vagas = await _criar_setup(db_session, tenant, owner, n_vagas=3)

    state = _make_state(tenant.id, owner.id, run.id, candidato.id, vagas)

    call_count = 0

    async def mock_ainvoke(prompt):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.content = '{"resumo": "resumo", "carta": "carta"}'
        return resp

    chain = MagicMock()
    chain.ainvoke = mock_ainvoke
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=chain)

    sse_manager = VagasPipelineSseManager()
    node = make_personalizer_node(db_session, sse_manager, llm=llm)
    await node(state)

    assert call_count == 3  # uma chamada por vaga


@pytest.mark.asyncio
async def test_personalizer_emite_sse_progresso(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run, candidato, vagas = await _criar_setup(db_session, tenant, owner, n_vagas=2)

    state = _make_state(tenant.id, owner.id, run.id, candidato.id, vagas)
    mock_llm = _make_mock_llm()
    sse_manager = VagasPipelineSseManager()
    queue = await sse_manager.subscribe(run.id)

    node = make_personalizer_node(db_session, sse_manager, llm=mock_llm)
    await node(state)

    eventos = []
    while not queue.empty():
        eventos.append(queue.get_nowait())

    assert any(e["etapa"] == PipelineStatus.PERSONALIZANDO.value for e in eventos)
    # Deve haver mensagens de progresso incremental
    mensagens = [e.get("mensagem", "") for e in eventos]
    assert any("1/" in m or "2/" in m for m in mensagens)


@pytest.mark.asyncio
async def test_personalizer_fallback_llm_error(db_session, tenant_e_owner):
    """Falha do LLM em uma vaga não deve parar o restante."""
    tenant, owner = tenant_e_owner
    run, candidato, vagas = await _criar_setup(db_session, tenant, owner, n_vagas=3)

    state = _make_state(tenant.id, owner.id, run.id, candidato.id, vagas)

    call_count = 0

    async def mock_ainvoke_com_falha(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("LLM rate limit")
        resp = MagicMock()
        resp.content = '{"resumo": "resumo ok", "carta": "carta ok"}'
        return resp

    chain = MagicMock()
    chain.ainvoke = mock_ainvoke_com_falha
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=chain)

    sse_manager = VagasPipelineSseManager()
    node = make_personalizer_node(db_session, sse_manager, llm=llm)
    resultado = await node(state)

    # Deve gerar candidaturas para as vagas que não falharam
    assert len(resultado["candidaturas"]) >= 2
    assert resultado.get("erro") is None


@pytest.mark.asyncio
async def test_personalizer_atualiza_status_pipeline_run(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run, candidato, vagas = await _criar_setup(db_session, tenant, owner, n_vagas=1)

    state = _make_state(tenant.id, owner.id, run.id, candidato.id, vagas)
    mock_llm = _make_mock_llm()
    sse_manager = VagasPipelineSseManager()

    node = make_personalizer_node(db_session, sse_manager, llm=mock_llm)
    await node(state)

    run_service = PipelineRunService(db_session)
    run_atualizado = await run_service.get_by_id(run.id)
    assert run_atualizado.status == PipelineStatus.PERSONALIZANDO.value


# ──────────────────────────────────────────────
# Registrar
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_registrar_finaliza_pipeline_run(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    state = PipelineVagasState(
        tenant_id=tenant.id, usuario_id=owner.id,
        pipeline_run_id=run.id, cv_text="", cv_filename="cv.pdf",
        perfil={}, candidato_id=1,
        vagas=[{"id": 1}, {"id": 2}, {"id": 3}],
        candidaturas=[{"id": 1}, {"id": 2}],
        erro=None,
    )
    sse_manager = VagasPipelineSseManager()

    node = make_registrar_node(db_session, sse_manager)
    await node(state)

    run_finalizado = await run_service.get_by_id(run.id)
    assert run_finalizado.status == PipelineStatus.CONCLUIDO.value
    assert run_finalizado.vagas_encontradas == 3
    assert run_finalizado.candidaturas_criadas == 2


@pytest.mark.asyncio
async def test_registrar_emite_sse_concluido(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    state = PipelineVagasState(
        tenant_id=tenant.id, usuario_id=owner.id,
        pipeline_run_id=run.id, cv_text="", cv_filename="cv.pdf",
        perfil={}, candidato_id=1,
        vagas=[{"id": 1}],
        candidaturas=[{"id": 1}],
        erro=None,
    )
    sse_manager = VagasPipelineSseManager()
    queue = await sse_manager.subscribe(run.id)

    node = make_registrar_node(db_session, sse_manager)
    await node(state)

    assert not queue.empty()
    event = queue.get_nowait()
    assert event["type"] == "CONCLUIDO"
    assert event["vagas_encontradas"] == 1
    assert event["candidaturas_criadas"] == 1


@pytest.mark.asyncio
async def test_registrar_com_erro_no_estado(db_session, tenant_e_owner):
    """Se há erro no estado (de nó anterior), registrar deve emitir SSE de erro."""
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    state = PipelineVagasState(
        tenant_id=tenant.id, usuario_id=owner.id,
        pipeline_run_id=run.id, cv_text="", cv_filename="cv.pdf",
        perfil=None, candidato_id=None,
        vagas=[], candidaturas=[],
        erro="Texto do CV vazio.",
    )
    sse_manager = VagasPipelineSseManager()
    queue = await sse_manager.subscribe(run.id)

    node = make_registrar_node(db_session, sse_manager)
    await node(state)

    assert not queue.empty()
    event = queue.get_nowait()
    assert event["type"] == "ERRO"
    assert "vazio" in event["mensagem"].lower()

    run_db = await run_service.get_by_id(run.id)
    assert run_db.status == PipelineStatus.ERRO.value
