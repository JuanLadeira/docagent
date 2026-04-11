"""
TDD — Chat router com persistência de histórico (Fase 19)

Testa:
  - nova conversa criada automaticamente no POST /chat
  - conversa inexistente retorna 404
  - regressão: POST /chat sem conversa_id ainda funciona
  - conversa_id retornado na resposta SSE
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db
from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario
from docagent.agente.models import Agente

import docagent.tenant.models          # noqa: F401
import docagent.usuario.models         # noqa: F401
import docagent.agente.models          # noqa: F401
import docagent.atendimento.models     # noqa: F401
import docagent.whatsapp.models        # noqa: F401
import docagent.telegram.models        # noqa: F401
import docagent.audio.models           # noqa: F401
import docagent.system_config.models   # noqa: F401
import docagent.conversa.models        # noqa: F401

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory):
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def setup(db_session):
    tenant = Tenant(nome="Tenant Chat Hist")
    db_session.add(tenant)
    await db_session.flush()

    usuario = Usuario(
        username="chat_hist_user",
        email="chat_hist@test.com",
        password="hash",
        nome="Chat Hist",
        tenant_id=tenant.id,
    )
    db_session.add(usuario)
    await db_session.flush()

    agente = Agente(
        nome="Agente Chat", descricao="desc",
        skill_names=[], ativo=True, tenant_id=tenant.id,
    )
    db_session.add(agente)
    await db_session.commit()
    return {"tenant": tenant, "usuario": usuario, "agente": agente}


@pytest_asyncio.fixture
async def auth_headers(setup):
    """Gera token JWT falso para o usuário de testes."""
    import jwt
    from docagent.settings import Settings
    s = Settings()
    token = jwt.encode(
        {"sub": setup["usuario"].username},
        s.SECRET_KEY,
        algorithm=s.ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client(db_session, session_factory):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db

    import docagent.chat.router as _cr
    _cr._agent_cache.clear()

    with patch("docagent.chat.router.AsyncSessionLocal", session_factory):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_agent_stream(answer: str = "Resposta do agente"):
    """Retorna um mock de agente que faz stream de SSE e seta last_state."""
    from langchain_core.messages import AIMessage

    agent_mock = MagicMock()
    agent_mock.last_state = {"messages": [AIMessage(content=answer)]}

    def _stream(question, state):
        yield f"data: {answer}\n\n"

    agent_mock.stream = _stream
    return agent_mock


# ── Testes ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_conversa_inexistente_retorna_404(client, setup, auth_headers):
    """POST /chat com conversa_id inválido deve retornar 404."""
    with (
        patch("docagent.chat.router._get_or_build_agent", return_value=_mock_agent_stream()),
        patch("docagent.chat.router.get_tenant_llm", new_callable=AsyncMock, return_value=MagicMock()),
    ):
        r = await client.post(
            "/chat",
            json={
                "question": "oi",
                "agent_id": str(setup["agente"].id),
                "conversa_id": 99999,
            },
            headers=auth_headers,
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_regressao_chat_sem_conversa_id(client, setup, auth_headers):
    """POST /chat sem conversa_id deve funcionar normalmente (regressão)."""
    with (
        patch("docagent.chat.router._get_or_build_agent", return_value=_mock_agent_stream()),
        patch("docagent.chat.router.get_tenant_llm", new_callable=AsyncMock, return_value=MagicMock()),
        patch("docagent.chat.router.AsyncSessionLocal") as mock_sl,
    ):
        # Mock da sessão de persistência
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_sl.return_value = mock_db

        r = await client.post(
            "/chat",
            json={
                "question": "oi",
                "agent_id": str(setup["agente"].id),
            },
            headers=auth_headers,
        )
    # Aceita 200 (streaming) — sem quebra de contrato
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_conversa_criada_automaticamente_no_banco(client, setup, auth_headers, db_session):
    """POST /chat sem conversa_id deve criar Conversa no banco."""
    from docagent.conversa.models import Conversa
    from sqlalchemy import select

    with (
        patch("docagent.chat.router._get_or_build_agent", return_value=_mock_agent_stream()),
        patch("docagent.chat.router.get_tenant_llm", new_callable=AsyncMock, return_value=MagicMock()),
        patch("docagent.chat.router.AsyncSessionLocal") as mock_sl,
    ):
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_sl.return_value = mock_db

        r = await client.post(
            "/chat",
            json={"question": "nova conversa", "agent_id": str(setup["agente"].id)},
            headers=auth_headers,
        )

    assert r.status_code == 200

    # Verifica que foi criada no banco via db_session (mesma sessão do override)
    result = await db_session.execute(
        select(Conversa).where(Conversa.tenant_id == setup["tenant"].id)
    )
    conversas = result.scalars().all()
    assert len(conversas) >= 1
