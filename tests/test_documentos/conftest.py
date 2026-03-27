"""
Fixtures compartilhadas para testes da Fase 15 (Documentos RAG por Agente).
Usa SQLite in-memory async para isolamento total entre testes.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db
from docagent.auth.security import get_password_hash
from docagent.agente.models import Agente
from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole

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


async def _create_owner(db_session, username="owner", password="senha123"):
    tenant = Tenant(nome="Tenant Teste")
    db_session.add(tenant)
    await db_session.flush()

    user = Usuario(
        username=username,
        email=f"{username}@test.com",
        password=get_password_hash(password),
        nome="Owner Teste",
        tenant_id=tenant.id,
        role=UsuarioRole.OWNER,
        ativo=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _get_token(client: AsyncClient, username="owner", password="senha123") -> str:
    response = await client.post(
        "/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def owner_token(client: AsyncClient, db_session: AsyncSession) -> str:
    await _create_owner(db_session)
    return await _get_token(client)


@pytest_asyncio.fixture
async def auth_headers(owner_token: str) -> dict:
    return {"Authorization": f"Bearer {owner_token}"}


@pytest_asyncio.fixture
async def agente_fixture(db_session: AsyncSession) -> Agente:
    """Cria um agente com rag_search para os testes."""
    agente = Agente(
        nome="RAG Agent",
        descricao="Agente de teste",
        skill_names=["rag_search"],
        ativo=True,
    )
    db_session.add(agente)
    await db_session.flush()
    await db_session.refresh(agente)
    return agente


@pytest.fixture
def mock_ingest():
    """Mock do IngestService para não chamar Ollama/ChromaDB nos testes."""
    with patch("docagent.agente.documento_service.IngestService") as MockClass:
        instance = MockClass.return_value
        instance.ingest.return_value = {
            "filename": "doc.pdf",
            "chunks": 5,
            "collection_id": "agente_1",
        }
        yield instance


@pytest.fixture
def mock_chroma_delete():
    """Mock da função delete_document_from_vectorstore."""
    with patch(
        "docagent.agente.documento_service.delete_document_from_vectorstore",
        return_value=3,
    ) as mock:
        yield mock
