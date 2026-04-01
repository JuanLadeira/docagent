"""
Fixtures para testes da Fase 16 (Telegram).

Usa SQLite in-memory + mesmo padrão do test_fase12.
O webhook handler usa AsyncSessionLocal() diretamente, por isso:
  1. Patchamos AsyncSessionLocal com a factory do engine de teste.
  2. Limpamos _agent_cache entre testes.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db
from docagent.agente.models import Agente
from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole
from docagent.auth.security import create_access_token, get_password_hash

# Importar modelos de telegram e atendimento para registrar em Base.metadata
from docagent.telegram.models import TelegramInstancia, TelegramBotStatus  # noqa: F401
from docagent.system_config.models import SystemConfig  # noqa: F401
from docagent.atendimento.models import (  # noqa: F401
    Atendimento, AtendimentoStatus, CanalAtendimento, MensagemAtendimento, MensagemOrigem,
)

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
async def mock_telegram_api():
    """AsyncMock do httpx.AsyncClient para a Telegram Bot API."""
    client = AsyncMock()
    default_response = MagicMock(spec=Response)
    default_response.status_code = 200
    default_response.json.return_value = {"ok": True, "result": {"username": "test_bot"}}
    default_response.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=default_response)
    client.get = AsyncMock(return_value=default_response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession, test_session_factory, mock_telegram_api):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db

    import docagent.telegram.router as _tg_router
    _tg_router._agent_cache.clear()

    with (
        patch("docagent.telegram.router.AsyncSessionLocal", test_session_factory),
        patch("docagent.telegram.services.get_telegram_client", return_value=mock_telegram_api),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def auth_headers(db_session):
    """Cria tenant + owner e retorna headers de autenticação."""
    _, _, token = await _criar_tenant_e_owner(db_session)
    return {"Authorization": f"Bearer {token}"}


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


async def _criar_agente(db_session, tenant_id: int):
    agente = Agente(
        nome="Agente Telegram Teste",
        descricao="Para testes",
        system_prompt="Voce e um assistente de teste.",
        skill_names=[],
        ativo=True,
        tenant_id=tenant_id,
    )
    db_session.add(agente)
    await db_session.flush()
    await db_session.refresh(agente)
    await db_session.commit()
    return agente


async def _criar_telegram_instancia(
    db_session,
    tenant_id: int,
    agente_id: int | None = None,
    bot_token: str = "test-token:123ABC",
    cria_atendimentos: bool = True,
):
    instancia = TelegramInstancia(
        bot_token=bot_token,
        bot_username="test_bot",
        webhook_configured=True,
        status=TelegramBotStatus.ATIVA,
        cria_atendimentos=cria_atendimentos,
        tenant_id=tenant_id,
        agente_id=agente_id,
    )
    db_session.add(instancia)
    await db_session.flush()
    await db_session.refresh(instancia)
    await db_session.commit()
    return instancia


async def _criar_atendimento_telegram(
    db_session,
    telegram_instancia_id: int,
    tenant_id: int,
    numero: str = "123456789",
    status: str = "ATIVO",
):
    from docagent.atendimento.models import Atendimento, AtendimentoStatus, CanalAtendimento
    at = Atendimento(
        numero=numero,
        telegram_instancia_id=telegram_instancia_id,
        instancia_id=None,
        canal=CanalAtendimento.TELEGRAM,
        tenant_id=tenant_id,
        status=AtendimentoStatus(status),
    )
    db_session.add(at)
    await db_session.flush()
    await db_session.refresh(at)
    await db_session.commit()
    return at
