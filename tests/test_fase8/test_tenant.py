"""Testes de integracao para CRUD de tenants."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_tenant(client: AsyncClient):
    response = await client.post("/api/tenants/", json={"nome": "Acme Corp", "descricao": "Empresa de teste"})
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "Acme Corp"
    assert data["descricao"] == "Empresa de teste"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_tenants(client: AsyncClient):
    await client.post("/api/tenants/", json={"nome": "Tenant A"})
    await client.post("/api/tenants/", json={"nome": "Tenant B"})

    response = await client.get("/api/tenants/")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_tenant(client: AsyncClient):
    create = await client.post("/api/tenants/", json={"nome": "Tenant X"})
    tenant_id = create.json()["id"]

    response = await client.get(f"/api/tenants/{tenant_id}")
    assert response.status_code == 200
    assert response.json()["nome"] == "Tenant X"


@pytest.mark.asyncio
async def test_get_tenant_not_found(client: AsyncClient):
    response = await client.get("/api/tenants/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_tenant(client: AsyncClient):
    create = await client.post("/api/tenants/", json={"nome": "Antigo"})
    tenant_id = create.json()["id"]

    response = await client.put(f"/api/tenants/{tenant_id}", json={"nome": "Novo"})
    assert response.status_code == 200
    assert response.json()["nome"] == "Novo"


@pytest.mark.asyncio
async def test_delete_tenant(client: AsyncClient):
    create = await client.post("/api/tenants/", json={"nome": "Para deletar"})
    tenant_id = create.json()["id"]

    delete = await client.delete(f"/api/tenants/{tenant_id}")
    assert delete.status_code == 204

    get = await client.get(f"/api/tenants/{tenant_id}")
    assert get.status_code == 404
