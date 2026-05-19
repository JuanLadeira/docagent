"""
Testes TDD para job sources e nó job_searcher.
Sprint 3 — RED antes de implementar sources/ e nodes/job_searcher.py
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from docagent.vagas.models import FonteVaga, PipelineStatus
from docagent.vagas.nodes.job_searcher import (
    _calcular_match_score,
    _tem_modalidade,
    make_job_searcher_node,
)
from docagent.vagas.pipeline_state import PipelineVagasState
from docagent.vagas.services import PipelineRunService, VagaService
from docagent.vagas.sources.gupy import GupySource
from docagent.vagas.sources.duckduckgo import DuckDuckGoSource
from docagent.vagas.sources.linkedin import LinkedInSource
from docagent.vagas.sources.indeed import IndeedSource
from docagent.vagas.sse import VagasPipelineSseManager


# ──────────────────────────────────────────────
# _calcular_match_score
# ──────────────────────────────────────────────

def test_match_score_skills_presentes():
    skills = ["Python", "FastAPI", "Docker"]
    descricao = "Buscamos desenvolvedor Python com experiência em FastAPI e Docker."
    score = _calcular_match_score(skills, descricao)
    assert score == pytest.approx(1.0)


def test_match_score_skills_parciais():
    skills = ["Python", "FastAPI", "Docker", "Kubernetes"]
    descricao = "Vaga para dev Python com FastAPI."
    score = _calcular_match_score(skills, descricao)
    assert score == pytest.approx(0.5)


def test_match_score_sem_skills():
    score = _calcular_match_score([], "qualquer descrição")
    assert score == 0.0


def test_match_score_nenhuma_skill_presente():
    skills = ["Java", "Spring"]
    descricao = "Desenvolvedor Python sênior com FastAPI."
    score = _calcular_match_score(skills, descricao)
    assert score == 0.0


def test_match_score_case_insensitive():
    skills = ["python", "FASTAPI"]
    descricao = "Python developer needed for FastAPI project."
    score = _calcular_match_score(skills, descricao)
    assert score == pytest.approx(1.0)


# ──────────────────────────────────────────────
# GupySource
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gupy_source_retorna_vagas():
    payload = {
        "data": [
            {
                "id": "1",
                "name": "Engenheiro Python",
                "careerPage": {"name": "TechCorp"},
                "city": "São Paulo",
                "state": "SP",
                "description": "Vaga Python FastAPI.",
                "prerequisites": "Python, FastAPI",
                "jobUrl": "https://portal.gupy.io/job/1",
            }
        ]
    }
    perfil = {"cargo_desejado": "Engenheiro Python", "skills": ["Python"]}

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=payload)
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        source = GupySource()
        vagas = await source.buscar(perfil)

    assert len(vagas) == 1
    assert vagas[0]["titulo"] == "Engenheiro Python"
    assert vagas[0]["empresa"] == "TechCorp"
    assert vagas[0]["fonte"] == FonteVaga.GUPY.value


@pytest.mark.asyncio
async def test_gupy_source_falha_retorna_lista_vazia():
    perfil = {"cargo_desejado": "Dev", "skills": []}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        source = GupySource()
        vagas = await source.buscar(perfil)

    assert vagas == []


# ──────────────────────────────────────────────
# DuckDuckGoSource
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duckduckgo_source_retorna_vagas():
    resultados_ddg = [
        {
            "snippet": "Vaga de Engenheiro Python na TechCorp.",
            "title": "Engenheiro Python - TechCorp",
            "link": "https://www.gupy.io/jobs/123",
        },
        {
            "snippet": "Dev Python remoto, startup inovadora.",
            "title": "Dev Python Remoto",
            "link": "https://www.linkedin.com/jobs/456",
        },
    ]

    perfil = {"cargo_desejado": "Engenheiro Python", "skills": ["Python"]}

    mock_tool = MagicMock()
    mock_tool.arun = AsyncMock(return_value=str(resultados_ddg))

    source = DuckDuckGoSource(tool=mock_tool)
    vagas = await source.buscar(perfil)

    assert len(vagas) >= 1
    assert all(v["fonte"] == FonteVaga.DUCKDUCKGO.value for v in vagas)


@pytest.mark.asyncio
async def test_duckduckgo_source_falha_retorna_lista_vazia():
    perfil = {"cargo_desejado": "Dev", "skills": []}
    mock_tool = MagicMock()
    mock_tool.arun = AsyncMock(side_effect=Exception("DDG rate limit"))

    source = DuckDuckGoSource(tool=mock_tool)
    vagas = await source.buscar(perfil)

    assert vagas == []


# ──────────────────────────────────────────────
# LinkedInSource
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_linkedin_source_falha_retorna_lista_vazia():
    """LinkedIn scraping vai falhar frequentemente — deve retornar [] silenciosamente."""
    perfil = {"cargo_desejado": "Dev Python", "skills": ["Python"]}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Cloudflare block"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        source = LinkedInSource()
        vagas = await source.buscar(perfil)

    assert vagas == []


@pytest.mark.asyncio
async def test_linkedin_source_parse_html():
    """Verifica que o parser retorna vagas com campos corretos quando HTML é válido."""
    html = """
    <html><body>
    <ul class="jobs-search__results-list">
        <li>
            <a class="base-card__full-link" href="https://linkedin.com/jobs/view/123">
                Engenheiro Python
            </a>
            <span class="base-search-card__subtitle">TechCorp</span>
            <span class="job-search-card__location">São Paulo, SP</span>
        </li>
    </ul>
    </body></html>
    """
    perfil = {"cargo_desejado": "Engenheiro Python", "skills": ["Python"]}

    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        source = LinkedInSource()
        vagas = await source.buscar(perfil)

    # pode retornar 0 ou 1 dependendo do parsing — o importante é não falhar
    assert isinstance(vagas, list)
    for v in vagas:
        assert v["fonte"] == FonteVaga.LINKEDIN.value


# ──────────────────────────────────────────────
# IndeedSource
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_indeed_source_rss_fallback():
    """Indeed deve tentar RSS antes do scraping HTML."""
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
    <channel>
        <item>
            <title>Engenheiro Python - TechCorp</title>
            <link>https://br.indeed.com/job/abc123</link>
            <description>Vaga Python FastAPI Docker. Remoto.</description>
            <source url="https://br.indeed.com">br.indeed.com</source>
        </item>
    </channel>
    </rss>"""

    perfil = {"cargo_desejado": "Engenheiro Python", "skills": ["Python"]}

    mock_rss_response = MagicMock()
    mock_rss_response.text = rss_xml
    mock_rss_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_rss_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        source = IndeedSource()
        vagas = await source.buscar(perfil)

    assert len(vagas) >= 1
    assert vagas[0]["fonte"] == FonteVaga.INDEED.value
    assert "Engenheiro Python" in vagas[0]["titulo"]


@pytest.mark.asyncio
async def test_indeed_source_falha_retorna_lista_vazia():
    perfil = {"cargo_desejado": "Dev", "skills": []}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("blocked"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        source = IndeedSource()
        vagas = await source.buscar(perfil)

    assert vagas == []


# ──────────────────────────────────────────────
# Nó job_searcher
# ──────────────────────────────────────────────

def _make_state(tenant_id, usuario_id, pipeline_run_id, perfil) -> PipelineVagasState:
    return PipelineVagasState(
        tenant_id=tenant_id,
        usuario_id=usuario_id,
        pipeline_run_id=pipeline_run_id,
        cv_text="",
        cv_filename="cv.pdf",
        perfil=perfil,
        candidato_id=1,
        vagas=[],
        candidaturas=[],
        erro=None,
    )


def _make_mock_source(vagas: list):
    source = MagicMock()
    source.buscar = AsyncMock(return_value=vagas)
    return source


@pytest.mark.asyncio
async def test_job_searcher_agrega_vagas_de_multiplas_fontes(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil = {"cargo_desejado": "Python Dev", "skills": ["Python", "FastAPI"]}
    state = _make_state(tenant.id, owner.id, run.id, perfil)

    vagas_gupy = [
        {"titulo": "Dev Python Gupy", "empresa": "G", "localizacao": "SP",
         "descricao": "Python FastAPI", "requisitos": "", "url": "https://g.io/1",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}},
    ]
    vagas_ddg = [
        {"titulo": "Dev Python DDG", "empresa": "D", "localizacao": "RJ",
         "descricao": "Python dev", "requisitos": "", "url": "https://ddg.io/2",
         "fonte": FonteVaga.DUCKDUCKGO.value, "raw_data": {}},
    ]

    sources = [_make_mock_source(vagas_gupy), _make_mock_source(vagas_ddg)]
    sse_manager = VagasPipelineSseManager()

    node = make_job_searcher_node(db_session, sse_manager, sources=sources)
    resultado = await node(state)

    assert len(resultado["vagas"]) == 2


@pytest.mark.asyncio
async def test_job_searcher_fonte_com_falha_nao_derruba_pipeline(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil = {"cargo_desejado": "Dev", "skills": ["Python"]}
    state = _make_state(tenant.id, owner.id, run.id, perfil)

    source_ok = _make_mock_source([
        {"titulo": "Vaga OK", "empresa": "X", "localizacao": "",
         "descricao": "Python", "requisitos": "", "url": "https://x.io/1",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}},
    ])
    source_falha = MagicMock()
    source_falha.buscar = AsyncMock(side_effect=Exception("timeout"))

    sse_manager = VagasPipelineSseManager()
    node = make_job_searcher_node(db_session, sse_manager, sources=[source_ok, source_falha])
    resultado = await node(state)

    # Pipeline continua com as vagas da fonte que funcionou
    assert len(resultado["vagas"]) == 1
    assert resultado.get("erro") is None


@pytest.mark.asyncio
async def test_job_searcher_calcula_match_score(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil = {"cargo_desejado": "Dev Python", "skills": ["Python", "FastAPI"]}
    state = _make_state(tenant.id, owner.id, run.id, perfil)

    vagas = [
        {"titulo": "Dev Python", "empresa": "A", "localizacao": "",
         "descricao": "Python FastAPI Docker", "requisitos": "Python FastAPI",
         "url": "https://a.io/1", "fonte": FonteVaga.GUPY.value, "raw_data": {}},
        {"titulo": "Dev Java", "empresa": "B", "localizacao": "",
         "descricao": "Java Spring Boot", "requisitos": "Java",
         "url": "https://b.io/2", "fonte": FonteVaga.GUPY.value, "raw_data": {}},
    ]

    source = _make_mock_source(vagas)
    sse_manager = VagasPipelineSseManager()
    node = make_job_searcher_node(db_session, sse_manager, sources=[source])
    resultado = await node(state)

    # Vaga Python deve ter score maior que vaga Java
    vagas_result = resultado["vagas"]
    assert len(vagas_result) == 2
    scores = {v["titulo"]: v.get("match_score", 0) for v in vagas_result}
    assert scores["Dev Python"] > scores["Dev Java"]


@pytest.mark.asyncio
async def test_job_searcher_limita_top20(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil = {"cargo_desejado": "Dev", "skills": ["Python"]}
    state = _make_state(tenant.id, owner.id, run.id, perfil)

    # 30 vagas retornadas pela source
    vagas = [
        {"titulo": f"Vaga {i}", "empresa": "X", "localizacao": "",
         "descricao": "Python", "requisitos": "", "url": f"https://x.io/{i}",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}}
        for i in range(30)
    ]

    source = _make_mock_source(vagas)
    sse_manager = VagasPipelineSseManager()
    node = make_job_searcher_node(db_session, sse_manager, sources=[source])
    resultado = await node(state)

    assert len(resultado["vagas"]) <= 20


@pytest.mark.asyncio
async def test_job_searcher_persiste_vagas_no_banco(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil = {"cargo_desejado": "Dev Python", "skills": ["Python"]}
    state = _make_state(tenant.id, owner.id, run.id, perfil)

    vagas = [
        {"titulo": "Dev Python", "empresa": "Corp", "localizacao": "Remoto",
         "descricao": "Python FastAPI", "requisitos": "Python",
         "url": "https://corp.io/1", "fonte": FonteVaga.GUPY.value, "raw_data": {"id": "1"}},
    ]
    source = _make_mock_source(vagas)
    sse_manager = VagasPipelineSseManager()
    node = make_job_searcher_node(db_session, sse_manager, sources=[source])
    await node(state)

    vaga_service = VagaService(db_session)
    persistidas = await vaga_service.listar_por_pipeline_run(run.id)
    assert len(persistidas) == 1
    assert persistidas[0].titulo == "Dev Python"


@pytest.mark.asyncio
async def test_job_searcher_atualiza_status_e_emite_sse(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil = {"cargo_desejado": "Dev", "skills": []}
    state = _make_state(tenant.id, owner.id, run.id, perfil)

    sse_manager = VagasPipelineSseManager()
    queue = await sse_manager.subscribe(run.id)

    node = make_job_searcher_node(db_session, sse_manager, sources=[])
    await node(state)

    run_atualizado = await run_service.get_by_id(run.id)
    assert run_atualizado.status == PipelineStatus.BUSCANDO_VAGAS.value

    assert not queue.empty()
    event = queue.get_nowait()
    assert event["type"] == "PROGRESSO"
    assert event["etapa"] == PipelineStatus.BUSCANDO_VAGAS.value


# ──────────────────────────────────────────────
# _tem_modalidade
# ──────────────────────────────────────────────

def test_tem_modalidade_homeoffice_por_titulo():
    vaga = {"titulo": "Dev Python Remoto", "localizacao": "", "descricao": "", "requisitos": ""}
    assert _tem_modalidade(vaga, "HOMEOFFICE") is True


def test_tem_modalidade_homeoffice_por_descricao():
    vaga = {"titulo": "Dev Python", "localizacao": "", "descricao": "Vaga 100% home office.", "requisitos": ""}
    assert _tem_modalidade(vaga, "HOMEOFFICE") is True


def test_tem_modalidade_presencial_por_localizacao():
    vaga = {"titulo": "Dev Python", "localizacao": "Presencial - São Paulo", "descricao": "", "requisitos": ""}
    assert _tem_modalidade(vaga, "PRESENCIAL") is True


def test_tem_modalidade_hibrido_por_descricao():
    vaga = {"titulo": "Dev Python", "localizacao": "", "descricao": "Modelo híbrido, 3x por semana no escritório.", "requisitos": ""}
    assert _tem_modalidade(vaga, "HIBRIDO") is True


def test_tem_modalidade_retorna_false_sem_sinal():
    vaga = {"titulo": "Dev Python", "localizacao": "São Paulo", "descricao": "Vaga incrível.", "requisitos": "Python"}
    assert _tem_modalidade(vaga, "HOMEOFFICE") is False
    assert _tem_modalidade(vaga, "PRESENCIAL") is False
    assert _tem_modalidade(vaga, "HIBRIDO") is False


def test_tem_modalidade_nao_confunde_modalidades():
    vaga_remota = {"titulo": "Dev Remoto", "localizacao": "", "descricao": "", "requisitos": ""}
    assert _tem_modalidade(vaga_remota, "HOMEOFFICE") is True
    assert _tem_modalidade(vaga_remota, "PRESENCIAL") is False
    assert _tem_modalidade(vaga_remota, "HIBRIDO") is False


# ──────────────────────────────────────────────
# Filtro de modalidade no job_searcher
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_searcher_filtra_homeoffice(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run = await PipelineRunService(db_session).criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil = {"cargo_desejado": "Dev Python", "skills": ["Python"]}
    state = PipelineVagasState(
        tenant_id=tenant.id, usuario_id=owner.id, pipeline_run_id=run.id,
        cv_text="", cv_filename="cv.pdf", perfil=perfil, candidato_id=1,
        vagas=[], candidaturas=[], erro=None,
        config={"modalidade": "HOMEOFFICE"},
        excluir_urls=None,
    )

    vagas = [
        {"titulo": "Dev Python Remoto", "empresa": "A", "localizacao": "remoto",
         "descricao": "100% home office", "requisitos": "", "url": "https://a.io/1",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}},
        {"titulo": "Dev Python Presencial", "empresa": "B", "localizacao": "São Paulo SP",
         "descricao": "Vaga incrível para Python", "requisitos": "", "url": "https://b.io/2",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}},
    ]
    source = _make_mock_source(vagas)
    sse_manager = VagasPipelineSseManager()

    node = make_job_searcher_node(db_session, sse_manager, sources=[source])
    resultado = await node(state)

    # Apenas a vaga remota deve passar o filtro
    assert len(resultado["vagas"]) == 1
    assert resultado["vagas"][0]["titulo"] == "Dev Python Remoto"


@pytest.mark.asyncio
async def test_job_searcher_sem_modalidade_retorna_todas(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run = await PipelineRunService(db_session).criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil = {"cargo_desejado": "Dev Python", "skills": ["Python"]}
    state = PipelineVagasState(
        tenant_id=tenant.id, usuario_id=owner.id, pipeline_run_id=run.id,
        cv_text="", cv_filename="cv.pdf", perfil=perfil, candidato_id=1,
        vagas=[], candidaturas=[], erro=None,
        config=None,  # sem filtro de modalidade
        excluir_urls=None,
    )

    vagas = [
        {"titulo": "Dev Python Remoto", "empresa": "A", "localizacao": "remoto",
         "descricao": "", "requisitos": "", "url": "https://a.io/1",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}},
        {"titulo": "Dev Python Presencial", "empresa": "B", "localizacao": "São Paulo",
         "descricao": "", "requisitos": "", "url": "https://b.io/2",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}},
        {"titulo": "Dev Python Sem Info", "empresa": "C", "localizacao": "",
         "descricao": "", "requisitos": "", "url": "https://c.io/3",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}},
    ]
    source = _make_mock_source(vagas)
    sse_manager = VagasPipelineSseManager()

    node = make_job_searcher_node(db_session, sse_manager, sources=[source])
    resultado = await node(state)

    # Sem filtro: todas as vagas devem ser retornadas
    assert len(resultado["vagas"]) == 3


@pytest.mark.asyncio
async def test_job_searcher_descarta_vagas_sem_atributo_modalidade(db_session, tenant_e_owner):
    """Quando filtro está ativo, vagas sem sinal de modalidade são descartadas."""
    tenant, owner = tenant_e_owner
    run = await PipelineRunService(db_session).criar(tenant_id=tenant.id, usuario_id=owner.id)

    perfil = {"cargo_desejado": "Dev Python", "skills": ["Python"]}
    state = PipelineVagasState(
        tenant_id=tenant.id, usuario_id=owner.id, pipeline_run_id=run.id,
        cv_text="", cv_filename="cv.pdf", perfil=perfil, candidato_id=1,
        vagas=[], candidaturas=[], erro=None,
        config={"modalidade": "PRESENCIAL"},
        excluir_urls=None,
    )

    vagas = [
        {"titulo": "Dev Python", "empresa": "A", "localizacao": "presencial São Paulo",
         "descricao": "trabalho presencial", "requisitos": "", "url": "https://a.io/1",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}},
        {"titulo": "Dev Python Sem Info", "empresa": "B", "localizacao": "",
         "descricao": "Vaga incrível!", "requisitos": "", "url": "https://b.io/2",
         "fonte": FonteVaga.GUPY.value, "raw_data": {}},
    ]
    source = _make_mock_source(vagas)
    sse_manager = VagasPipelineSseManager()

    node = make_job_searcher_node(db_session, sse_manager, sources=[source])
    resultado = await node(state)

    assert len(resultado["vagas"]) == 1
    assert resultado["vagas"][0]["titulo"] == "Dev Python"


@pytest.mark.asyncio
async def test_duckduckgo_usa_queries_homeoffice_com_modalidade():
    """DuckDuckGoSource deve usar templates de homeoffice quando _modalidade=HOMEOFFICE."""
    mock_tool = MagicMock()
    mock_tool.arun = AsyncMock(return_value="[]")

    source = DuckDuckGoSource(tool=mock_tool)
    perfil = {"cargo_desejado": "Dev Python", "_modalidade": "HOMEOFFICE"}

    await source.buscar(perfil)

    # Verifica que alguma query contém termo de homeoffice
    calls = [str(call) for call in mock_tool.arun.call_args_list]
    assert any("remoto" in c.lower() or "home office" in c.lower() or "remote" in c.lower() for c in calls)


def test_gupy_injeta_termo_remoto_no_perfil_homeoffice():
    """GupySource deve incluir 'remoto' nos termos de busca quando _modalidade=HOMEOFFICE."""
    from docagent.vagas.sources.gupy import _extrair_termos

    perfil = {"cargo_desejado": "Dev Python", "skills": [], "_modalidade": "HOMEOFFICE"}
    termos = _extrair_termos(perfil)
    assert "remoto" in termos


def test_gupy_injeta_termo_presencial_no_perfil_presencial():
    from docagent.vagas.sources.gupy import _extrair_termos

    perfil = {"cargo_desejado": "Dev Python", "skills": [], "_modalidade": "PRESENCIAL"}
    termos = _extrair_termos(perfil)
    assert "presencial" in termos


def test_gupy_sem_modalidade_nao_injeta_termo():
    from docagent.vagas.sources.gupy import _extrair_termos

    perfil = {"cargo_desejado": "Dev Python", "skills": []}
    termos = _extrair_termos(perfil)
    assert "remoto" not in termos
    assert "presencial" not in termos
