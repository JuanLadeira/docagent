"""
Testes dos endpoints de tenant após correção de segurança.

Os endpoints públicos de CRUD (/api/tenants/, /api/tenants/{id}) foram removidos.
O CRUD agora está em /api/admin/tenants/* com autenticação de admin.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db

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
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.tenant
class TestTenantEndpoints:
    """Verifica que os endpoints públicos foram removidos (segurança)."""

    async def test_create_tenant_publico_removido(self, client: AsyncClient):
        r = await client.post("/api/tenants/", json={"nome": "Casa Nova"})
        assert r.status_code in (404, 405)

    async def test_get_tenant_publico_removido(self, client: AsyncClient):
        r = await client.get("/api/tenants/1")
        assert r.status_code in (404, 405)

    async def test_list_tenants_publico_removido(self, client: AsyncClient):
        r = await client.get("/api/tenants/")
        assert r.status_code in (404, 405)

    async def test_update_tenant_publico_removido(self, client: AsyncClient):
        r = await client.put("/api/tenants/1", json={"nome": "Novo"})
        assert r.status_code in (404, 405)

    async def test_delete_tenant_publico_removido(self, client: AsyncClient):
        r = await client.delete("/api/tenants/1")
        assert r.status_code in (404, 405)

    async def test_llm_config_requer_auth(self, client: AsyncClient):
        r = await client.get("/api/tenants/me/llm-config")
        assert r.status_code == 401

        r = await client.put("/api/tenants/me/llm-config", json={})
        assert r.status_code == 401
