"""
Testes TDD para o router de vagas.
Sprint 5 — RED antes de implementar vagas/router.py
"""
import io
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from docagent.vagas.models import CandidaturaStatus, FonteVaga, PipelineStatus
from docagent.vagas.services import (
    CandidaturaService,
    CandidatoService,
    PipelineRunService,
    VagaService,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _criar_run_completo(db_session, tenant, owner):
    """Cria run, candidato, vaga e candidatura para testes de leitura."""
    run_service = PipelineRunService(db_session)
    candidato_service = CandidatoService(db_session)
    vaga_service = VagaService(db_session)
    cand_service = CandidaturaService(db_session)

    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)
    candidato = await candidato_service.criar(
        tenant_id=tenant.id, usuario_id=owner.id,
        nome="João", email="joao@test.com", telefone="",
        skills=["Python"], experiencias=[], formacao=[],
        cargo_desejado="Dev Python", resumo="Dev.", cv_filename="cv.pdf",
    )
    vaga = await vaga_service.criar(
        tenant_id=tenant.id, pipeline_run_id=run.id,
        titulo="Dev Python", empresa="Corp", localizacao="Remoto",
        descricao="Python dev", requisitos="Python",
        url="https://corp.io/1", fonte=FonteVaga.GUPY,
        match_score=0.9, raw_data={},
    )
    candidatura = await cand_service.criar(
        tenant_id=tenant.id, pipeline_run_id=run.id,
        vaga_id=vaga.id, candidato_id=candidato.id,
        resumo_personalizado="Resumo personalizado.",
        carta_apresentacao="Carta de apresentação.",
    )
    await run_service.finalizar(run.id, vagas_encontradas=1, candidaturas_criadas=1)

    return run, candidato, vaga, candidatura


# ──────────────────────────────────────────────
# POST /api/vagas/pipeline
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_iniciar_pipeline_cria_run(client, owner_autenticado):
    tenant, owner, token = owner_autenticado

    pdf_bytes = b"%PDF-1.4 fake pdf content with some text"

    with patch("docagent.vagas.router.extrair_texto_pdf", return_value="Dev Python com experiência em FastAPI."), \
         patch("docagent.vagas.router.asyncio.create_task"):
        resp = await client.post(
            "/api/vagas/pipeline",
            files={"cv": ("curriculo.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            headers=_auth_header(token),
        )

    assert resp.status_code == 201
    data = resp.json()
    assert "pipeline_run_id" in data
    assert data["status"] == PipelineStatus.PENDENTE.value


@pytest.mark.asyncio
async def test_iniciar_pipeline_pdf_invalido_retorna_422(client, owner_autenticado):
    _, _, token = owner_autenticado

    with patch("docagent.vagas.router.extrair_texto_pdf", return_value="   "):
        resp = await client.post(
            "/api/vagas/pipeline",
            files={"cv": ("vazio.pdf", io.BytesIO(b""), "application/pdf")},
            headers=_auth_header(token),
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_iniciar_pipeline_sem_auth_retorna_401(client, owner_autenticado):
    pdf_bytes = b"%PDF fake"
    resp = await client.post(
        "/api/vagas/pipeline",
        files={"cv": ("cv.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 401


# ──────────────────────────────────────────────
# GET /api/vagas/pipelines
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listar_pipelines(client, db_session, owner_autenticado):
    tenant, owner, token = owner_autenticado
    run_service = PipelineRunService(db_session)
    await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)
    await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    resp = await client.get("/api/vagas/pipelines", headers=_auth_header(token))

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_listar_pipelines_isolamento_tenant(client, db_session, owner_autenticado):
    """Tenant A não vê pipelines do Tenant B."""
    tenant_a, owner_a, token_a = owner_autenticado

    from docagent.tenant.models import Tenant
    from docagent.usuario.models import Usuario, UsuarioRole
    from docagent.auth.security import get_password_hash

    tenant_b = Tenant(nome="Tenant B")
    db_session.add(tenant_b)
    await db_session.flush()
    owner_b = Usuario(
        username="owner_b", email="b@test.com",
        password=get_password_hash("senha123"),
        nome="Owner B", tenant_id=tenant_b.id,
        role=UsuarioRole.OWNER, ativo=True,
    )
    db_session.add(owner_b)
    await db_session.flush()

    run_service = PipelineRunService(db_session)
    await run_service.criar(tenant_id=tenant_a.id, usuario_id=owner_a.id)
    await run_service.criar(tenant_id=tenant_b.id, usuario_id=owner_b.id)

    resp = await client.get("/api/vagas/pipelines", headers=_auth_header(token_a))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ──────────────────────────────────────────────
# GET /api/vagas/pipelines/{run_id}
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_pipeline_detalhe(client, db_session, owner_autenticado):
    tenant, owner, token = owner_autenticado
    run, _, vaga, candidatura = await _criar_run_completo(db_session, tenant, owner)

    resp = await client.get(f"/api/vagas/pipelines/{run.id}", headers=_auth_header(token))

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run.id
    assert data["status"] == PipelineStatus.CONCLUIDO.value
    assert len(data["vagas"]) == 1
    assert len(data["candidaturas"]) == 1


@pytest.mark.asyncio
async def test_get_pipeline_outro_tenant_retorna_404(client, db_session, owner_autenticado):
    tenant_a, owner_a, token_a = owner_autenticado

    from docagent.tenant.models import Tenant
    from docagent.usuario.models import Usuario, UsuarioRole
    from docagent.auth.security import get_password_hash

    tenant_b = Tenant(nome="Tenant B")
    db_session.add(tenant_b)
    await db_session.flush()
    owner_b = Usuario(
        username="owner_b2", email="b2@test.com",
        password=get_password_hash("senha123"),
        nome="Owner B2", tenant_id=tenant_b.id,
        role=UsuarioRole.OWNER, ativo=True,
    )
    db_session.add(owner_b)
    await db_session.flush()

    run_service = PipelineRunService(db_session)
    run_b = await run_service.criar(tenant_id=tenant_b.id, usuario_id=owner_b.id)

    resp = await client.get(f"/api/vagas/pipelines/{run_b.id}", headers=_auth_header(token_a))
    assert resp.status_code == 404


# ──────────────────────────────────────────────
# GET /api/vagas/vagas
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listar_vagas_por_pipeline_run(client, db_session, owner_autenticado):
    tenant, owner, token = owner_autenticado
    run, _, vaga, _ = await _criar_run_completo(db_session, tenant, owner)

    resp = await client.get(
        f"/api/vagas/vagas?pipeline_run_id={run.id}",
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["titulo"] == "Dev Python"


@pytest.mark.asyncio
async def test_listar_vagas_min_score(client, db_session, owner_autenticado):
    tenant, owner, token = owner_autenticado
    run_service = PipelineRunService(db_session)
    vaga_service = VagaService(db_session)
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    for score in [0.2, 0.6, 0.9]:
        await vaga_service.criar(
            tenant_id=tenant.id, pipeline_run_id=run.id,
            titulo=f"Vaga {score}", empresa="", localizacao="",
            descricao="", requisitos="", url=f"https://x.io/{score}",
            fonte=FonteVaga.GUPY, match_score=score, raw_data={},
        )

    resp = await client.get(
        f"/api/vagas/vagas?pipeline_run_id={run.id}&min_score=0.5",
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ──────────────────────────────────────────────
# GET /api/vagas/candidaturas
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listar_candidaturas_por_pipeline_run(client, db_session, owner_autenticado):
    tenant, owner, token = owner_autenticado
    run, _, _, candidatura = await _criar_run_completo(db_session, tenant, owner)

    resp = await client.get(
        f"/api/vagas/candidaturas?pipeline_run_id={run.id}",
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == CandidaturaStatus.AGUARDANDO_ENVIO.value


# ──────────────────────────────────────────────
# GET /api/vagas/candidaturas/{id}
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_candidatura_detalhe(client, db_session, owner_autenticado):
    tenant, owner, token = owner_autenticado
    _, _, _, candidatura = await _criar_run_completo(db_session, tenant, owner)

    resp = await client.get(
        f"/api/vagas/candidaturas/{candidatura.id}",
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["resumo_personalizado"] == "Resumo personalizado."
    assert data["carta_apresentacao"] == "Carta de apresentação."


# ──────────────────────────────────────────────
# PATCH /api/vagas/candidaturas/{id}
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_atualizar_status_candidatura_para_enviada(client, db_session, owner_autenticado):
    tenant, owner, token = owner_autenticado
    _, _, _, candidatura = await _criar_run_completo(db_session, tenant, owner)

    resp = await client.patch(
        f"/api/vagas/candidaturas/{candidatura.id}",
        json={"status": CandidaturaStatus.ENVIADA.value},
        headers=_auth_header(token),
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == CandidaturaStatus.ENVIADA.value


@pytest.mark.asyncio
async def test_atualizar_status_candidatura_invalido_retorna_422(client, db_session, owner_autenticado):
    tenant, owner, token = owner_autenticado
    _, _, _, candidatura = await _criar_run_completo(db_session, tenant, owner)

    resp = await client.patch(
        f"/api/vagas/candidaturas/{candidatura.id}",
        json={"status": "STATUS_INVALIDO"},
        headers=_auth_header(token),
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_atualizar_candidatura_outro_tenant_retorna_404(client, db_session, owner_autenticado):
    tenant_a, owner_a, token_a = owner_autenticado

    from docagent.tenant.models import Tenant
    from docagent.usuario.models import Usuario, UsuarioRole
    from docagent.auth.security import get_password_hash

    tenant_b = Tenant(nome="Tenant B")
    db_session.add(tenant_b)
    await db_session.flush()
    owner_b = Usuario(
        username="owner_b3", email="b3@test.com",
        password=get_password_hash("senha123"),
        nome="Owner B3", tenant_id=tenant_b.id,
        role=UsuarioRole.OWNER, ativo=True,
    )
    db_session.add(owner_b)
    await db_session.flush()

    run_service = PipelineRunService(db_session)
    cand_service = CandidaturaService(db_session)
    vaga_service = VagaService(db_session)
    candidato_service = CandidatoService(db_session)

    run = await run_service.criar(tenant_id=tenant_b.id, usuario_id=owner_b.id)
    candidato = await candidato_service.criar(
        tenant_id=tenant_b.id, usuario_id=owner_b.id,
        nome="B", email="", telefone="", skills=[],
        experiencias=[], formacao=[], cargo_desejado="",
        resumo="", cv_filename="cv.pdf",
    )
    vaga = await vaga_service.criar(
        tenant_id=tenant_b.id, pipeline_run_id=run.id,
        titulo="Vaga B", empresa="", localizacao="",
        descricao="", requisitos="", url="https://b.io",
        fonte=FonteVaga.GUPY, match_score=0.5, raw_data={},
    )
    candidatura_b = await cand_service.criar(
        tenant_id=tenant_b.id, pipeline_run_id=run.id,
        vaga_id=vaga.id, candidato_id=candidato.id,
        resumo_personalizado="", carta_apresentacao="",
    )

    resp = await client.patch(
        f"/api/vagas/candidaturas/{candidatura_b.id}",
        json={"status": CandidaturaStatus.ENVIADA.value},
        headers=_auth_header(token_a),
    )
    assert resp.status_code == 404
