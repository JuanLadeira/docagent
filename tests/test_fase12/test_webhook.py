"""
Testes de integração para o endpoint de webhook (Fase 12).

O webhook SEMPRE deve retornar 200, mesmo que o processamento falhe.
Usa mock de AsyncSessionLocal para isolar o banco nos handlers internos.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient

from tests.test_fase12.conftest import _criar_tenant_e_owner, _criar_agente, _criar_instancia


WEBHOOK_URL = "/api/whatsapp/webhook"

EVENTO_QRCODE = {
    "event": "QRCODE_UPDATED",
    "instance": "instancia-teste",
    "data": {"qrcode": {"base64": "data:image/png;base64,abc123"}},
}

EVENTO_CONNECTION_OPEN = {
    "event": "CONNECTION_UPDATE",
    "instance": "instancia-teste",
    "data": {"state": "open"},
}

EVENTO_CONNECTION_CLOSE = {
    "event": "CONNECTION_UPDATE",
    "instance": "instancia-teste",
    "data": {"state": "close"},
}

EVENTO_MENSAGEM = {
    "event": "MESSAGES_UPSERT",
    "instance": "instancia-teste",
    "data": {
        "key": {"fromMe": False, "remoteJid": "5511999999999@s.whatsapp.net"},
        "message": {"conversation": "Ola agente!"},
    },
}

EVENTO_DESCONHECIDO = {
    "event": "PRESENCE_UPDATE",
    "instance": "instancia-teste",
    "data": {},
}


@pytest.mark.asyncio
async def test_webhook_sempre_retorna_200(client: AsyncClient):
    """Webhook deve retornar 200 para qualquer evento, mesmo sem instancia no banco."""
    response = await client.post(WEBHOOK_URL, json=EVENTO_QRCODE)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_evento_desconhecido_retorna_200(client: AsyncClient):
    response = await client.post(WEBHOOK_URL, json=EVENTO_DESCONHECIDO)
    assert response.status_code == 200
    data = response.json()
    assert data["event"] == "PRESENCE_UPDATE"


@pytest.mark.asyncio
async def test_webhook_qrcode_faz_broadcast(client: AsyncClient, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    await _criar_instancia(db_session, tenant.id)

    with patch("docagent.whatsapp.router.sse_manager") as mock_sse:
        mock_sse.broadcast = AsyncMock()
        response = await client.post(WEBHOOK_URL, json=EVENTO_QRCODE)

    assert response.status_code == 200
    mock_sse.broadcast.assert_called_once()
    call_args = mock_sse.broadcast.call_args
    assert call_args[0][1]["type"] == "QRCODE_UPDATED"
    assert "qr_base64" in call_args[0][1]


@pytest.mark.asyncio
async def test_webhook_connection_update_open_atualiza_status(client: AsyncClient, db_session):
    from docagent.whatsapp.models import ConexaoStatus, WhatsappInstancia
    from sqlalchemy import select

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    await _criar_instancia(db_session, tenant.id)

    response = await client.post(WEBHOOK_URL, json=EVENTO_CONNECTION_OPEN)
    assert response.status_code == 200

    result = await db_session.execute(
        select(WhatsappInstancia).where(WhatsappInstancia.instance_name == "instancia-teste")
    )
    instancia = result.scalar_one_or_none()
    assert instancia is not None
    assert instancia.status == ConexaoStatus.CONECTADA


@pytest.mark.asyncio
async def test_webhook_connection_update_close_atualiza_status(client: AsyncClient, db_session):
    from docagent.whatsapp.models import ConexaoStatus, WhatsappInstancia
    from sqlalchemy import select

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    await _criar_instancia(db_session, tenant.id)

    response = await client.post(WEBHOOK_URL, json=EVENTO_CONNECTION_CLOSE)
    assert response.status_code == 200

    result = await db_session.execute(
        select(WhatsappInstancia).where(WhatsappInstancia.instance_name == "instancia-teste")
    )
    instancia = result.scalar_one_or_none()
    assert instancia is not None
    assert instancia.status == ConexaoStatus.DESCONECTADA


@pytest.mark.asyncio
async def test_webhook_mensagem_sem_agente_ignorada(client: AsyncClient, db_session):
    """Mensagem recebida sem agente vinculado nao deve chamar LLM."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    await _criar_instancia(db_session, tenant.id, agente_id=None)

    with patch("docagent.whatsapp.router.ConfigurableAgent") as mock_agent_cls:
        response = await client.post(WEBHOOK_URL, json=EVENTO_MENSAGEM)

    assert response.status_code == 200
    mock_agent_cls.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_mensagem_from_me_ignorada(client: AsyncClient, db_session):
    """Mensagens enviadas pelo proprio bot nao devem ser processadas."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session, tenant_id=tenant.id)
    await _criar_instancia(db_session, tenant.id, agente_id=agente.id)

    evento_from_me = {
        "event": "MESSAGES_UPSERT",
        "instance": "instancia-teste",
        "data": {
            "key": {"fromMe": True, "remoteJid": "5511999999999@s.whatsapp.net"},
            "message": {"conversation": "mensagem propria"},
        },
    }

    with patch("docagent.whatsapp.router.ConfigurableAgent") as mock_agent_cls:
        response = await client.post(WEBHOOK_URL, json=evento_from_me)

    assert response.status_code == 200
    mock_agent_cls.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_mensagem_com_agente_executa_e_responde(client: AsyncClient, db_session):
    """Com agente vinculado, deve rodar o agente e enviar resposta via Evolution."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session, tenant_id=tenant.id)
    await _criar_instancia(db_session, tenant.id, agente_id=agente.id)

    from langchain_core.messages import AIMessage

    mock_agent_instance = MagicMock()
    mock_agent_instance.run.return_value = {
        "messages": [AIMessage(content="Resposta do agente")]
    }
    mock_agent_instance.last_state = None

    mock_agent_cls = MagicMock()
    mock_agent_cls.return_value.build.return_value = mock_agent_instance

    mock_httpx_client = AsyncMock()
    mock_httpx_response = MagicMock()
    mock_httpx_response.raise_for_status = MagicMock()
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=False)
    mock_httpx_client.post = AsyncMock(return_value=mock_httpx_response)

    with (
        patch("docagent.whatsapp.router.ConfigurableAgent", mock_agent_cls),
        patch("docagent.whatsapp.router.httpx.AsyncClient", return_value=mock_httpx_client),
    ):
        response = await client.post(WEBHOOK_URL, json=EVENTO_MENSAGEM)

    assert response.status_code == 200
    mock_agent_instance.run.assert_called_once()
    call_args = mock_agent_instance.run.call_args[0]
    assert call_args[0] == "Ola agente!"
    mock_httpx_client.post.assert_called_once()
