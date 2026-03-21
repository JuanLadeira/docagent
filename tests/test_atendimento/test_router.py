"""Testes de integração para endpoints REST de atendimento."""
import pytest
from httpx import AsyncClient

from tests.test_atendimento.conftest import (
    _criar_tenant_e_owner,
    _criar_instancia,
    _criar_atendimento,
    _criar_mensagem,
)


@pytest.mark.asyncio
async def test_listar_atendimentos(client: AsyncClient, db_session):
    """Lista atendimentos do tenant autenticado."""
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    await _criar_atendimento(db_session, instancia.id, tenant.id)

    r = await client.get("/api/atendimentos", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_isolamento_tenant(client: AsyncClient, db_session):
    """Atendimentos de outro tenant não aparecem na listagem."""
    tenant1, _, token1 = await _criar_tenant_e_owner(db_session, username="owner1")
    tenant2, _, _ = await _criar_tenant_e_owner(db_session, username="owner2")
    instancia2 = await _criar_instancia(db_session, tenant2.id, instance_name="inst-tenant2")
    await _criar_atendimento(db_session, instancia2.id, tenant2.id)

    r = await client.get("/api/atendimentos", headers={"Authorization": f"Bearer {token1}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_detalhe_com_mensagens(client: AsyncClient, db_session):
    """Endpoint de detalhe retorna atendimento com mensagens."""
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)
    await _criar_mensagem(db_session, atendimento.id, "CONTATO", "Olá!")

    r = await client.get(
        f"/api/atendimentos/{atendimento.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == atendimento.id
    assert len(data["mensagens"]) == 1
    assert data["mensagens"][0]["conteudo"] == "Olá!"


@pytest.mark.asyncio
async def test_assumir_endpoint(client: AsyncClient, db_session):
    """POST /assumir muda status para HUMANO."""
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)

    r = await client.post(
        f"/api/atendimentos/{atendimento.id}/assumir",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "HUMANO"


@pytest.mark.asyncio
async def test_devolver_endpoint(client: AsyncClient, db_session):
    """POST /devolver muda status para ATIVO."""
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id, status="HUMANO")

    r = await client.post(
        f"/api/atendimentos/{atendimento.id}/devolver",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ATIVO"


@pytest.mark.asyncio
async def test_encerrar_endpoint(client: AsyncClient, db_session):
    """POST /encerrar muda status para ENCERRADO."""
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)

    r = await client.post(
        f"/api/atendimentos/{atendimento.id}/encerrar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ENCERRADO"


@pytest.mark.asyncio
async def test_enviar_mensagem_operador_humano(client: AsyncClient, db_session, mock_evolution):
    """Operador envia mensagem quando status é HUMANO — chama Evolution API."""
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id, status="HUMANO")

    r = await client.post(
        f"/api/atendimentos/{atendimento.id}/mensagens",
        json={"conteudo": "Oi, sou o operador!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    assert r.json()["origem"] == "OPERADOR"
    assert r.json()["conteudo"] == "Oi, sou o operador!"
    mock_evolution.post.assert_called_once()


@pytest.mark.asyncio
async def test_enviar_mensagem_nao_humano_retorna_400(client: AsyncClient, db_session):
    """Operador não pode enviar mensagem quando status não é HUMANO."""
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id, status="ATIVO")

    r = await client.post(
        f"/api/atendimentos/{atendimento.id}/mensagens",
        json={"conteudo": "texto"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
