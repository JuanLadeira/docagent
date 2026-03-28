"""Testes de integração dos endpoints CRUD de TelegramInstancia."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response

from docagent.telegram.models import TelegramInstancia

from tests.test_telegram.conftest import (
    _criar_tenant_e_owner,
    _criar_agente,
    _criar_telegram_instancia,
)

BASE_URL = "/api/telegram/instancias"


def _mock_telegram_api_ok():
    mock = AsyncMock()
    resp = MagicMock(spec=Response)
    resp.status_code = 200
    resp.json.return_value = {"ok": True, "result": {"username": "meu_bot"}}
    resp.raise_for_status = MagicMock()
    mock.post = AsyncMock(return_value=resp)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


@pytest.mark.asyncio
async def test_listar_sem_auth_retorna_401(client):
    r = await client.get(BASE_URL)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_listar_retorna_lista_vazia(client, db_session):
    _, _, token = await _criar_tenant_e_owner(db_session)
    r = await client.get(BASE_URL, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_listar_retorna_instancias_do_tenant(client, db_session):
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    await _criar_telegram_instancia(db_session, tenant.id, bot_token="tok1:aaa")
    await _criar_telegram_instancia(db_session, tenant.id, bot_token="tok2:bbb")
    r = await client.get(BASE_URL, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.asyncio
async def test_listar_nao_retorna_bot_token(client, db_session):
    """bot_token nunca deve aparecer na resposta."""
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    await _criar_telegram_instancia(db_session, tenant.id)
    r = await client.get(BASE_URL, headers={"Authorization": f"Bearer {token}"})
    assert "bot_token" not in str(r.json())


@pytest.mark.asyncio
async def test_criar_sem_auth_retorna_401(client):
    r = await client.post(BASE_URL, json={"bot_token": "tok:123"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_criar_retorna_201(client, db_session):
    _, _, token = await _criar_tenant_e_owner(db_session)
    mock_api = _mock_telegram_api_ok()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_api):
        r = await client.post(
            BASE_URL,
            json={"bot_token": "novo:999", "cria_atendimentos": True},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_criar_resposta_tem_campos_obrigatorios(client, db_session):
    _, _, token = await _criar_tenant_e_owner(db_session)
    mock_api = _mock_telegram_api_ok()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_api):
        r = await client.post(
            BASE_URL,
            json={"bot_token": "novo:888", "cria_atendimentos": False},
            headers={"Authorization": f"Bearer {token}"},
        )
    body = r.json()
    assert "id" in body
    assert "bot_username" in body
    assert "webhook_configured" in body
    assert "cria_atendimentos" in body
    assert body["cria_atendimentos"] is False
    assert "bot_token" not in body  # write-only


@pytest.mark.asyncio
async def test_deletar_sem_auth_retorna_401(client, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    r = await client.delete(f"{BASE_URL}/{inst.id}")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_deletar_retorna_204(client, db_session):
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    mock_api = _mock_telegram_api_ok()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_api):
        r = await client.delete(
            f"{BASE_URL}/{inst.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_deletar_outro_tenant_retorna_404(client, db_session):
    tenant1, _, _ = await _criar_tenant_e_owner(db_session, username="owner1")
    tenant2, _, token2 = await _criar_tenant_e_owner(db_session, username="owner2")
    inst = await _criar_telegram_instancia(db_session, tenant1.id)
    mock_api = _mock_telegram_api_ok()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_api):
        r = await client.delete(
            f"{BASE_URL}/{inst.id}",
            headers={"Authorization": f"Bearer {token2}"},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_configurar_webhook_retorna_200(client, db_session):
    tenant, _, token = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    mock_api = _mock_telegram_api_ok()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_api):
        r = await client.post(
            f"{BASE_URL}/{inst.id}/webhook/configurar",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.json()["webhook_configured"] is True
