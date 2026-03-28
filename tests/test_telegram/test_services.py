"""Testes unitários do TelegramService."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response

from docagent.telegram.models import TelegramInstancia, TelegramBotStatus

from tests.test_telegram.conftest import (
    _criar_tenant_e_owner,
    _criar_agente,
    _criar_telegram_instancia,
)

WEBHOOK_URL = "http://api:8000/api/telegram/webhook/test-token:123ABC"


def _make_mock_client(ok=True):
    client = AsyncMock()
    resp = MagicMock(spec=Response)
    resp.status_code = 200
    resp.json.return_value = {"ok": ok, "result": {"username": "test_bot"}}
    resp.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_criar_instancia_salva_no_banco(db_session):
    from docagent.telegram.services import TelegramService
    from docagent.telegram.schemas import TelegramInstanciaCreate

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    svc = TelegramService(db_session)
    data = TelegramInstanciaCreate(bot_token="novo-token:456", cria_atendimentos=True)

    mock_client = _make_mock_client()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_client):
        inst = await svc.criar_instancia(tenant.id, data, WEBHOOK_URL)

    assert inst.id is not None
    assert inst.bot_token == "novo-token:456"
    assert inst.tenant_id == tenant.id
    assert inst.webhook_configured is True
    assert inst.bot_username == "test_bot"


@pytest.mark.asyncio
async def test_criar_instancia_chama_set_webhook(db_session):
    from docagent.telegram.services import TelegramService
    from docagent.telegram.schemas import TelegramInstanciaCreate

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    svc = TelegramService(db_session)
    data = TelegramInstanciaCreate(bot_token="novo-token:789")

    mock_client = _make_mock_client()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_client):
        await svc.criar_instancia(tenant.id, data, WEBHOOK_URL)

    mock_client.post.assert_called()
    call_args = mock_client.post.call_args_list
    urls = [str(c[0][0]) for c in call_args]
    assert any("/setWebhook" in u for u in urls)


@pytest.mark.asyncio
async def test_criar_instancia_preserva_cria_atendimentos_false(db_session):
    from docagent.telegram.services import TelegramService
    from docagent.telegram.schemas import TelegramInstanciaCreate

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    svc = TelegramService(db_session)
    data = TelegramInstanciaCreate(bot_token="notif-token:111", cria_atendimentos=False)

    mock_client = _make_mock_client()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_client):
        inst = await svc.criar_instancia(tenant.id, data, WEBHOOK_URL)

    assert inst.cria_atendimentos is False


@pytest.mark.asyncio
async def test_listar_instancias_filtra_por_tenant(db_session):
    from docagent.telegram.services import TelegramService

    tenant1, _, _ = await _criar_tenant_e_owner(db_session, username="owner1")
    tenant2, _, _ = await _criar_tenant_e_owner(db_session, username="owner2")
    await _criar_telegram_instancia(db_session, tenant1.id, bot_token="tok-1:aaa")
    await _criar_telegram_instancia(db_session, tenant1.id, bot_token="tok-2:bbb")
    await _criar_telegram_instancia(db_session, tenant2.id, bot_token="tok-3:ccc")

    svc = TelegramService(db_session)
    resultado = await svc.listar_instancias(tenant1.id)
    assert len(resultado) == 2
    tokens = {i.bot_token for i in resultado}
    assert tokens == {"tok-1:aaa", "tok-2:bbb"}


@pytest.mark.asyncio
async def test_obter_instancia_retorna_correta(db_session):
    from docagent.telegram.services import TelegramService

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    svc = TelegramService(db_session)

    resultado = await svc.obter_instancia(inst.id, tenant.id)
    assert resultado is not None
    assert resultado.id == inst.id


@pytest.mark.asyncio
async def test_obter_instancia_outro_tenant_retorna_none(db_session):
    from docagent.telegram.services import TelegramService

    tenant1, _, _ = await _criar_tenant_e_owner(db_session, username="owner1")
    tenant2, _, _ = await _criar_tenant_e_owner(db_session, username="owner2")
    inst = await _criar_telegram_instancia(db_session, tenant1.id)
    svc = TelegramService(db_session)

    resultado = await svc.obter_instancia(inst.id, tenant2.id)
    assert resultado is None


@pytest.mark.asyncio
async def test_deletar_instancia_remove_do_banco(db_session):
    from docagent.telegram.services import TelegramService
    from sqlalchemy import select

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    svc = TelegramService(db_session)

    mock_client = _make_mock_client()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_client):
        await svc.deletar_instancia(inst)

    result = await db_session.get(TelegramInstancia, inst.id)
    assert result is None


@pytest.mark.asyncio
async def test_deletar_instancia_chama_delete_webhook(db_session):
    from docagent.telegram.services import TelegramService

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    svc = TelegramService(db_session)

    mock_client = _make_mock_client()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_client):
        await svc.deletar_instancia(inst)

    mock_client.post.assert_called()
    urls = [str(c[0][0]) for c in mock_client.post.call_args_list]
    assert any("/deleteWebhook" in u for u in urls)


@pytest.mark.asyncio
async def test_enviar_texto_chama_send_message(db_session):
    from docagent.telegram.services import TelegramService

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    svc = TelegramService(db_session)

    mock_client = _make_mock_client()
    with patch("docagent.telegram.services.get_telegram_client", return_value=mock_client):
        await svc.enviar_texto(inst, chat_id=987654321, text="Olá!")

    mock_client.post.assert_called_once()
    call = mock_client.post.call_args
    assert "/sendMessage" in str(call[0][0])
    assert call[1]["json"]["chat_id"] == 987654321
    assert call[1]["json"]["text"] == "Olá!"
