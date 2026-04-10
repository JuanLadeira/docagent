"""
Testes TDD para os services do módulo vagas.
Sprint 1 — RED antes de implementar services.py
"""
import pytest

from docagent.vagas.models import (
    CandidaturaStatus,
    FonteVaga,
    PipelineStatus,
)
from docagent.vagas.services import (
    CandidatoService,
    CandidaturaService,
    PipelineRunService,
    VagaService,
)


# ──────────────────────────────────────────────
# CandidatoService
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_criar_candidato(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    service = CandidatoService(db_session)

    candidato = await service.criar(
        tenant_id=tenant.id,
        usuario_id=owner.id,
        nome="João Silva",
        email="joao@example.com",
        telefone="(11) 9999-0000",
        skills=["Python", "FastAPI", "Docker"],
        experiencias=[{"cargo": "Dev", "empresa": "Acme", "periodo": "2020-2023"}],
        formacao=[{"grau": "Bacharelado", "curso": "Ciência da Computação"}],
        cargo_desejado="Engenheiro de Software",
        resumo="Desenvolvedor experiente em Python.",
        cv_filename="curriculo.pdf",
    )

    assert candidato.id is not None
    assert candidato.nome == "João Silva"
    assert candidato.tenant_id == tenant.id
    assert candidato.usuario_id == owner.id
    assert "Python" in candidato.skills


@pytest.mark.asyncio
async def test_get_candidato_by_id(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    service = CandidatoService(db_session)

    criado = await service.criar(
        tenant_id=tenant.id,
        usuario_id=owner.id,
        nome="Maria",
        email="maria@test.com",
        telefone="",
        skills=[],
        experiencias=[],
        formacao=[],
        cargo_desejado="",
        resumo="",
        cv_filename="cv.pdf",
    )

    encontrado = await service.get_by_id(criado.id)
    assert encontrado is not None
    assert encontrado.nome == "Maria"


@pytest.mark.asyncio
async def test_listar_candidatos_por_tenant(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    service = CandidatoService(db_session)

    await service.criar(
        tenant_id=tenant.id, usuario_id=owner.id, nome="A",
        email="", telefone="", skills=[], experiencias=[],
        formacao=[], cargo_desejado="", resumo="", cv_filename="a.pdf",
    )
    await service.criar(
        tenant_id=tenant.id, usuario_id=owner.id, nome="B",
        email="", telefone="", skills=[], experiencias=[],
        formacao=[], cargo_desejado="", resumo="", cv_filename="b.pdf",
    )

    lista = await service.listar_por_tenant(tenant.id)
    assert len(lista) == 2


# ──────────────────────────────────────────────
# PipelineRunService
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_criar_pipeline_run(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    service = PipelineRunService(db_session)

    run = await service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    assert run.id is not None
    assert run.status == PipelineStatus.PENDENTE.value
    assert run.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_atualizar_status_pipeline_run(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    service = PipelineRunService(db_session)

    run = await service.criar(tenant_id=tenant.id, usuario_id=owner.id)
    await service.atualizar_status(
        run.id,
        status=PipelineStatus.ANALISANDO_CV,
        etapa_atual="Analisando currículo...",
    )

    atualizado = await service.get_by_id(run.id)
    assert atualizado.status == PipelineStatus.ANALISANDO_CV.value
    assert atualizado.etapa_atual == "Analisando currículo..."


@pytest.mark.asyncio
async def test_finalizar_pipeline_run(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    service = PipelineRunService(db_session)

    run = await service.criar(tenant_id=tenant.id, usuario_id=owner.id)
    await service.finalizar(run.id, vagas_encontradas=15, candidaturas_criadas=10)

    finalizado = await service.get_by_id(run.id)
    assert finalizado.status == PipelineStatus.CONCLUIDO.value
    assert finalizado.vagas_encontradas == 15
    assert finalizado.candidaturas_criadas == 10


@pytest.mark.asyncio
async def test_registrar_erro_pipeline_run(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    service = PipelineRunService(db_session)

    run = await service.criar(tenant_id=tenant.id, usuario_id=owner.id)
    await service.registrar_erro(run.id, "Falha ao processar PDF")

    com_erro = await service.get_by_id(run.id)
    assert com_erro.status == PipelineStatus.ERRO.value
    assert com_erro.erro == "Falha ao processar PDF"


@pytest.mark.asyncio
async def test_listar_runs_por_tenant(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    service = PipelineRunService(db_session)

    await service.criar(tenant_id=tenant.id, usuario_id=owner.id)
    await service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    runs = await service.listar_por_tenant(tenant.id)
    assert len(runs) == 2


# ──────────────────────────────────────────────
# VagaService
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_criar_vaga(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    vaga_service = VagaService(db_session)

    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    vaga = await vaga_service.criar(
        tenant_id=tenant.id,
        pipeline_run_id=run.id,
        titulo="Engenheiro Python",
        empresa="TechCorp",
        localizacao="Remoto",
        descricao="Vaga para desenvolvedor Python sênior.",
        requisitos="Python, FastAPI, Docker",
        url="https://example.com/vaga/1",
        fonte=FonteVaga.GUPY,
        match_score=0.75,
        raw_data={"id": "123"},
    )

    assert vaga.id is not None
    assert vaga.titulo == "Engenheiro Python"
    assert vaga.match_score == 0.75
    assert vaga.fonte == FonteVaga.GUPY.value


@pytest.mark.asyncio
async def test_listar_vagas_por_pipeline_run(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    vaga_service = VagaService(db_session)

    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    for i in range(3):
        await vaga_service.criar(
            tenant_id=tenant.id,
            pipeline_run_id=run.id,
            titulo=f"Vaga {i}",
            empresa="Empresa",
            localizacao="",
            descricao="",
            requisitos="",
            url=f"https://example.com/{i}",
            fonte=FonteVaga.DUCKDUCKGO,
            match_score=float(i) * 0.1,
            raw_data={},
        )

    vagas = await vaga_service.listar_por_pipeline_run(run.id)
    assert len(vagas) == 3


@pytest.mark.asyncio
async def test_listar_vagas_com_filtro_min_score(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    run_service = PipelineRunService(db_session)
    vaga_service = VagaService(db_session)

    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    scores = [0.2, 0.5, 0.8]
    for i, score in enumerate(scores):
        await vaga_service.criar(
            tenant_id=tenant.id,
            pipeline_run_id=run.id,
            titulo=f"Vaga {i}",
            empresa="",
            localizacao="",
            descricao="",
            requisitos="",
            url=f"https://example.com/{i}",
            fonte=FonteVaga.GUPY,
            match_score=score,
            raw_data={},
        )

    vagas_altas = await vaga_service.listar_por_pipeline_run(run.id, min_score=0.5)
    assert len(vagas_altas) == 2


# ──────────────────────────────────────────────
# CandidaturaService
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_criar_candidatura(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    candidato_service = CandidatoService(db_session)
    run_service = PipelineRunService(db_session)
    vaga_service = VagaService(db_session)
    cand_service = CandidaturaService(db_session)

    candidato = await candidato_service.criar(
        tenant_id=tenant.id, usuario_id=owner.id, nome="João",
        email="", telefone="", skills=[], experiencias=[],
        formacao=[], cargo_desejado="", resumo="", cv_filename="cv.pdf",
    )
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)
    vaga = await vaga_service.criar(
        tenant_id=tenant.id, pipeline_run_id=run.id, titulo="Dev",
        empresa="", localizacao="", descricao="", requisitos="",
        url="https://example.com", fonte=FonteVaga.GUPY,
        match_score=0.9, raw_data={},
    )

    candidatura = await cand_service.criar(
        tenant_id=tenant.id,
        pipeline_run_id=run.id,
        vaga_id=vaga.id,
        candidato_id=candidato.id,
        resumo_personalizado="Resumo adaptado para a vaga.",
        carta_apresentacao="Carta de apresentação...",
    )

    assert candidatura.id is not None
    assert candidatura.status == CandidaturaStatus.AGUARDANDO_ENVIO.value
    assert candidatura.vaga_id == vaga.id


@pytest.mark.asyncio
async def test_atualizar_status_candidatura(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    candidato_service = CandidatoService(db_session)
    run_service = PipelineRunService(db_session)
    vaga_service = VagaService(db_session)
    cand_service = CandidaturaService(db_session)

    candidato = await candidato_service.criar(
        tenant_id=tenant.id, usuario_id=owner.id, nome="Maria",
        email="", telefone="", skills=[], experiencias=[],
        formacao=[], cargo_desejado="", resumo="", cv_filename="cv.pdf",
    )
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)
    vaga = await vaga_service.criar(
        tenant_id=tenant.id, pipeline_run_id=run.id, titulo="Dev",
        empresa="", localizacao="", descricao="", requisitos="",
        url="https://example.com", fonte=FonteVaga.GUPY,
        match_score=0.9, raw_data={},
    )
    candidatura = await cand_service.criar(
        tenant_id=tenant.id, pipeline_run_id=run.id,
        vaga_id=vaga.id, candidato_id=candidato.id,
        resumo_personalizado="", carta_apresentacao="",
    )

    await cand_service.atualizar_status(candidatura.id, CandidaturaStatus.ENVIADA)
    atualizada = await cand_service.get_by_id(candidatura.id)
    assert atualizada.status == CandidaturaStatus.ENVIADA.value


@pytest.mark.asyncio
async def test_listar_candidaturas_por_pipeline_run(db_session, tenant_e_owner):
    tenant, owner = tenant_e_owner
    candidato_service = CandidatoService(db_session)
    run_service = PipelineRunService(db_session)
    vaga_service = VagaService(db_session)
    cand_service = CandidaturaService(db_session)

    candidato = await candidato_service.criar(
        tenant_id=tenant.id, usuario_id=owner.id, nome="X",
        email="", telefone="", skills=[], experiencias=[],
        formacao=[], cargo_desejado="", resumo="", cv_filename="cv.pdf",
    )
    run = await run_service.criar(tenant_id=tenant.id, usuario_id=owner.id)

    for i in range(3):
        vaga = await vaga_service.criar(
            tenant_id=tenant.id, pipeline_run_id=run.id,
            titulo=f"Vaga {i}", empresa="", localizacao="",
            descricao="", requisitos="", url=f"https://example.com/{i}",
            fonte=FonteVaga.DUCKDUCKGO, match_score=0.5, raw_data={},
        )
        await cand_service.criar(
            tenant_id=tenant.id, pipeline_run_id=run.id,
            vaga_id=vaga.id, candidato_id=candidato.id,
            resumo_personalizado="", carta_apresentacao="",
        )

    candidaturas = await cand_service.listar_por_pipeline_run(run.id)
    assert len(candidaturas) == 3


@pytest.mark.asyncio
async def test_candidatura_isolamento_tenant(db_session):
    """Candidaturas de tenants diferentes não devem vazar."""
    from docagent.tenant.models import Tenant
    from docagent.usuario.models import Usuario, UsuarioRole
    from docagent.auth.security import get_password_hash

    t1 = Tenant(nome="Tenant1")
    t2 = Tenant(nome="Tenant2")
    db_session.add_all([t1, t2])
    await db_session.flush()

    u1 = Usuario(
        username="u1", email="u1@t.com",
        password=get_password_hash("x"), nome="U1",
        tenant_id=t1.id, role=UsuarioRole.OWNER, ativo=True,
    )
    u2 = Usuario(
        username="u2", email="u2@t.com",
        password=get_password_hash("x"), nome="U2",
        tenant_id=t2.id, role=UsuarioRole.OWNER, ativo=True,
    )
    db_session.add_all([u1, u2])
    await db_session.flush()

    run_service = PipelineRunService(db_session)
    run1 = await run_service.criar(tenant_id=t1.id, usuario_id=u1.id)
    run2 = await run_service.criar(tenant_id=t2.id, usuario_id=u2.id)

    runs_t1 = await run_service.listar_por_tenant(t1.id)
    runs_t2 = await run_service.listar_por_tenant(t2.id)

    assert len(runs_t1) == 1
    assert runs_t1[0].id == run1.id
    assert len(runs_t2) == 1
    assert runs_t2[0].id == run2.id
