"""
Fixtures para testes da feature Atendimento.

Usa SQLite in-memory + mesmo padrão do test_fase12.
Importar os modelos de atendimento garante que Base.metadata os inclua.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db
from docagent.whatsapp.client import get_evolution_client
from docagent.whatsapp.models import ConexaoStatus, WhatsappInstancia
from docagent.agente.models import Agente
from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole
from docagent.auth.security import create_access_token, get_password_hash

# Importar modelos de atendimento para registrar em Base.metadata
from docagent.atendimento.models import Atendimento, AtendimentoStatus, MensagemAtendimento, MensagemOrigem  # noqa: F401

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db_session(test_session_factory):
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def mock_evolution():
    """AsyncMock do httpx.AsyncClient para a Evolution API."""
    client = AsyncMock()
    default_response = MagicMock(spec=Response)
    default_response.status_code = 200
    default_response.json.return_value = {}
    default_response.raise_for_status = MagicMock()
    client.post.return_value = default_response
    client.get.return_value = default_response
    client.delete.return_value = default_response
    return client


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession, test_session_factory, mock_evolution):
    from unittest.mock import patch

    async def override_db():
        yield db_session

    async def override_evolution():
        yield mock_evolution

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_evolution_client] = override_evolution

    import docagent.whatsapp.router as _wh_router
    _wh_router._agent_cache.clear()

    with patch("docagent.whatsapp.router.AsyncSessionLocal", test_session_factory):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _criar_tenant_e_owner(db_session, username="owner"):
    tenant = Tenant(nome="Tenant Teste")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    user = Usuario(
        username=username,
        email=f"{username}@test.com",
        password=get_password_hash("senha123"),
        nome="Owner Teste",
        tenant_id=tenant.id,
        role=UsuarioRole.OWNER,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.commit()

    token = create_access_token({"sub": user.username})
    return tenant, user, token


async def _criar_agente(db_session):
    agente = Agente(
        nome="Agente Teste",
        descricao="Para testes",
        system_prompt="Voce e um assistente de teste.",
        skill_names=[],
        ativo=True,
    )
    db_session.add(agente)
    await db_session.flush()
    await db_session.refresh(agente)
    await db_session.commit()
    return agente


async def _criar_instancia(db_session, tenant_id: int, agente_id: int | None = None, instance_name: str = "instancia-teste"):
    instancia = WhatsappInstancia(
        instance_name=instance_name,
        status=ConexaoStatus.CONECTADA,
        tenant_id=tenant_id,
        agente_id=agente_id,
    )
    db_session.add(instancia)
    await db_session.flush()
    await db_session.refresh(instancia)
    await db_session.commit()
    return instancia


async def _criar_atendimento(db_session, instancia_id, tenant_id, numero="5511999999999", status="ATIVO"):
    at = Atendimento(
        numero=numero,
        instancia_id=instancia_id,
        tenant_id=tenant_id,
        status=AtendimentoStatus(status),
    )
    db_session.add(at)
    await db_session.flush()
    await db_session.refresh(at)
    await db_session.commit()
    return at


async def _criar_mensagem(db_session, atendimento_id, origem="CONTATO", conteudo="Olá!"):
    msg = MensagemAtendimento(
        atendimento_id=atendimento_id,
        origem=MensagemOrigem(origem),
        conteudo=conteudo,
    )
    db_session.add(msg)
    await db_session.flush()
    await db_session.refresh(msg)
    await db_session.commit()
    return msg
