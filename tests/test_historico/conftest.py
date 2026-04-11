"""
Fixtures compartilhadas para testes de histórico de conversas.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from docagent.database import Base
from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario
from docagent.agente.models import Agente

# Garante que todos os modelos sejam registrados no metadata
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
async def db(session_factory):
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def setup(db):
    """Cria tenant, usuario e agente para os testes."""
    tenant = Tenant(nome="Tenant Historico")
    db.add(tenant)
    await db.flush()

    usuario = Usuario(
        username="user_hist",
        email="hist@test.com",
        password="hash",
        nome="Usuário Hist",
        tenant_id=tenant.id,
    )
    db.add(usuario)
    await db.flush()

    agente = Agente(
        nome="Agente Hist",
        descricao="desc",
        skill_names=[],
        ativo=True,
        tenant_id=tenant.id,
    )
    db.add(agente)
    await db.commit()

    return {"tenant": tenant, "usuario": usuario, "agente": agente}
