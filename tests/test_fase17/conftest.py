"""
Fixtures compartilhadas para testes da Fase 17 (Billing & Quotas).
SQLite in-memory async para isolamento total entre testes.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db
from docagent.auth.security import get_password_hash
from docagent.plano.models import Plano
from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole
from docagent.system_config.models import SystemConfig  # noqa: F401 — garante tabela criada
from docagent.assinatura.models import Assinatura  # noqa: F401

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


async def _criar_tenant(db_session, nome="Tenant Teste") -> Tenant:
    tenant = Tenant(nome=nome)
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)
    return tenant


async def _criar_owner(db_session, tenant: Tenant, username="owner") -> Usuario:
    user = Usuario(
        username=username,
        email=f"{username}@test.com",
        password=get_password_hash("senha123"),
        nome="Owner Teste",
        tenant_id=tenant.id,
        role=UsuarioRole.OWNER,
        ativo=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


async def _criar_plano(
    db_session,
    nome="Free",
    limite_agentes=1,
    limite_documentos=5,
    limite_sessoes=100,
) -> Plano:
    plano = Plano(
        nome=nome,
        limite_agentes=limite_agentes,
        limite_documentos=limite_documentos,
        limite_sessoes=limite_sessoes,
    )
    db_session.add(plano)
    await db_session.flush()
    await db_session.refresh(plano)
    return plano


async def _criar_assinatura(db_session, tenant: Tenant, plano: Plano) -> Assinatura:
    from datetime import datetime, timedelta
    assinatura = Assinatura(
        tenant_id=tenant.id,
        plano_id=plano.id,
        ativo=True,
        data_inicio=datetime.utcnow(),
        data_proxima_renovacao=datetime.utcnow() + timedelta(days=30),
    )
    db_session.add(assinatura)
    await db_session.flush()
    await db_session.refresh(assinatura)
    return assinatura


async def _get_token(client: AsyncClient, username="owner", password="senha123") -> str:
    response = await client.post(
        "/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def owner_com_assinatura(db_session, client):
    """Cria tenant, owner, plano Free e assinatura. Retorna (tenant, owner, plano, token)."""
    tenant = await _criar_tenant(db_session)
    owner = await _criar_owner(db_session, tenant)
    plano = await _criar_plano(db_session, limite_agentes=2, limite_documentos=5)
    await _criar_assinatura(db_session, tenant, plano)
    token = await _get_token(client)
    return tenant, owner, plano, token
