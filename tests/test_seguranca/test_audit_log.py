"""
Fase 21c — Audit Log.

Testa AuditService, instrumentação nos endpoints admin/auth e
o endpoint GET /api/admin/audit-logs.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from docagent.audit.models import ActorTipo, AuditLog
from docagent.audit.services import AuditService
from docagent.database import Base

import docagent.audit.models      # noqa: F401 — registra no metadata
import docagent.tenant.models     # noqa: F401
import docagent.usuario.models    # noqa: F401
import docagent.agente.models     # noqa: F401
import docagent.atendimento.models # noqa: F401
import docagent.whatsapp.models   # noqa: F401
import docagent.telegram.models   # noqa: F401
import docagent.audio.models      # noqa: F401
import docagent.system_config.models # noqa: F401
import docagent.conversa.models   # noqa: F401

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── fixtures de unidade ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ── AuditService ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_registrar_cria_registro_no_banco(db):
    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=1,
        actor_username="admin",
        acao="criar_tenant",
        recurso_tipo="tenant",
        recurso_id=42,
        dados_depois={"nome": "Acme"},
    )
    await db.commit()

    result = await db.execute(select(AuditLog))
    logs = result.scalars().all()
    assert len(logs) == 1
    log = logs[0]
    assert log.acao == "criar_tenant"
    assert log.actor_username == "admin"
    assert log.recurso_id == 42
    assert log.dados_depois == {"nome": "Acme"}


@pytest.mark.asyncio
async def test_registrar_nao_falha_com_db_com_problema(db):
    """AuditService.registrar deve engolir erros silenciosamente."""
    # Passa uma sessão já fechada/inválida para simular problema
    await db.close()
    # Não deve lançar exceção
    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.USUARIO,
        actor_id=99,
        actor_username="user",
        acao="login",
    )


@pytest.mark.asyncio
async def test_listar_sem_filtros_retorna_todos(db):
    for i in range(3):
        await AuditService.registrar(
            db,
            actor_tipo=ActorTipo.ADMIN,
            actor_id=1,
            actor_username="admin",
            acao=f"acao_{i}",
        )
    await db.commit()

    items, total = await AuditService.listar(db)
    assert total == 3
    assert len(items) == 3


@pytest.mark.asyncio
async def test_listar_filtra_por_acao(db):
    await AuditService.registrar(db, ActorTipo.ADMIN, 1, "admin", acao="criar_tenant")
    await AuditService.registrar(db, ActorTipo.ADMIN, 1, "admin", acao="deletar_tenant")
    await AuditService.registrar(db, ActorTipo.ADMIN, 1, "admin", acao="criar_tenant")
    await db.commit()

    items, total = await AuditService.listar(db, acao="criar_tenant")
    assert total == 2
    assert all(i.acao == "criar_tenant" for i in items)


@pytest.mark.asyncio
async def test_listar_paginacao(db):
    for i in range(5):
        await AuditService.registrar(db, ActorTipo.ADMIN, 1, "admin", acao=f"a{i}")
    await db.commit()

    items, total = await AuditService.listar(db, page=1, page_size=2)
    assert total == 5
    assert len(items) == 2

    items2, _ = await AuditService.listar(db, page=2, page_size=2)
    assert len(items2) == 2
    # Páginas distintas — IDs diferentes
    assert {i.id for i in items}.isdisjoint({i.id for i in items2})


# ── integração via HTTP ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, db_session):
    """Cria admin no banco in-memory, faz login e retorna (client, headers)."""
    from docagent.admin.models import Admin
    from docagent.auth.security import get_password_hash

    admin = Admin(
        username="admin_test",
        email="admin@test.com",
        password=get_password_hash("senha123"),
        nome="Admin Test",
        ativo=True,
    )
    db_session.add(admin)
    await db_session.flush()

    r = await client.post(
        "/api/admin/login",
        data={"username": "admin_test", "password": "senha123"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_login_admin_registra_audit(admin_client: tuple):
    client, headers = admin_client
    # Faz um segundo login para garantir que é registrado
    r = await client.post(
        "/api/admin/login",
        data={"username": "admin_test", "password": "senha123"},
    )
    assert r.status_code == 200

    # Lista os audit logs
    r = await client.get("/api/admin/audit-logs", headers=headers)
    assert r.status_code == 200
    data = r.json()
    logins = [i for i in data["items"] if i["acao"] == "login_admin"]
    assert len(logins) >= 1


@pytest.mark.asyncio
async def test_criar_tenant_registra_audit(admin_client: tuple):
    client, headers = admin_client

    r = await client.post(
        "/api/admin/tenants",
        json={"nome": "Tenant Auditado"},
        headers=headers,
    )
    assert r.status_code == 201

    r = await client.get(
        "/api/admin/audit-logs?acao=criar_tenant", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert data["items"][0]["recurso_tipo"] == "tenant"


@pytest.mark.asyncio
async def test_audit_logs_requer_autenticacao(client: AsyncClient):
    r = await client.get("/api/admin/audit-logs")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_audit_logs_paginacao_e_filtros(admin_client: tuple):
    client, headers = admin_client

    r = await client.get(
        "/api/admin/audit-logs?page=1&page_size=10", headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "has_more" in data
    assert data["page"] == 1
    assert data["page_size"] == 10
