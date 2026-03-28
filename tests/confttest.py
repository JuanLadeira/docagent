import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.auth.security import get_password_hash
from app.database.base import Base
from app.database.session import get_async_session
from app.main import app
from app.tests.factories.tenant import TenantFactory
from app.tests.factories.usuario import UsuarioFactory


@pytest.fixture(scope="function")
async def async_engine():
    """Create an async engine connected to a test container."""
    with PostgresContainer("postgres:16", driver="asyncpg") as postgres:
        # Convert the connection URL to async format
        url = postgres.get_connection_url()
        async_url = url.replace("postgresql://", "postgresql+asyncpg://")

        engine = create_async_engine(async_url, echo=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()


@pytest.fixture(scope="function")
async def session(async_engine):
    """Provide an async session for tests."""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session


@pytest.fixture(scope="function")
async def client(session):
    """Provide an async test client with dependency override."""

    async def get_session_override():
        yield session

    app.dependency_overrides[get_async_session] = get_session_override

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def tenant_factory(session) -> type[TenantFactory]:
    """Fixture that provides TenantFactory configured with the test session."""
    TenantFactory._meta.sqlalchemy_session = session
    return TenantFactory


@pytest.fixture
def usuario_factory(session) -> type[UsuarioFactory]:
    """Fixture that provides UsuarioFactory configured with the test session."""
    UsuarioFactory._meta.sqlalchemy_session = session
    return UsuarioFactory


@pytest.fixture
async def tenant(tenant_factory):
    """Create a test tenant."""
    return tenant_factory(nome="Casa Teste", descricao="Tenant para testes")


@pytest.fixture
async def usuario(usuario_factory, tenant):
    """Create a test usuario."""
    senha = "teste123"
    return usuario_factory(
        username="usuario_teste",
        email="teste@example.com",
        password=get_password_hash(senha),
        nome="Usuario Teste",
        tenant_id=tenant.id,
    )


@pytest.fixture
async def token(client, usuario):
    """Get an access token for the test user."""
    response = await client.post(
        "/auth/login",
        data={"username": usuario.username, "password": "teste123"},
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(token):
    """Get authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {token}"}


