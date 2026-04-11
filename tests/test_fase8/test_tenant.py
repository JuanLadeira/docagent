"""
Testes dos endpoints de tenant.

Após a correção de segurança (CVE-like: endpoints públicos sem auth),
o CRUD de tenants foi movido para /api/admin/tenants/* com autenticação de admin.
Os endpoints públicos antigos (/api/tenants/{id}) foram removidos.
Apenas /api/tenants/me/* permanece, protegido por user JWT.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_crud_tenant_publico_nao_existe(client: AsyncClient):
    """Endpoints públicos de CRUD foram removidos — retornam 404/405."""
    r = await client.get("/api/tenants/")
    assert r.status_code in (404, 405)

    r = await client.post("/api/tenants/", json={"nome": "x"})
    assert r.status_code in (404, 405)

    r = await client.get("/api/tenants/1")
    assert r.status_code in (404, 405)

    r = await client.put("/api/tenants/1", json={"nome": "x"})
    assert r.status_code in (404, 405)

    r = await client.delete("/api/tenants/1")
    assert r.status_code in (404, 405)


@pytest.mark.asyncio
async def test_llm_config_requer_autenticacao(client: AsyncClient):
    """Endpoint de config LLM exige Bearer token."""
    r = await client.get("/api/tenants/me/llm-config")
    assert r.status_code == 401

    r = await client.put("/api/tenants/me/llm-config", json={})
    assert r.status_code == 401
