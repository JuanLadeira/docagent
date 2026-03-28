"""
Testes de integração do webhook Telegram.

Valida:
- Token desconhecido é ignorado (200)
- Mensagens de grupo são ignoradas
- Bots são ignorados
- Mensagens sem texto são ignoradas
- Bot com cria_atendimentos=False não cria fila
- Primeiro contato cria Atendimento com canal=TELEGRAM
- Segundo contato retoma atendimento existente
- Status HUMANO bloqueia agente
- Status ATIVO executa agente e envia resposta
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from docagent.atendimento.models import Atendimento, AtendimentoStatus, CanalAtendimento, MensagemAtendimento, MensagemOrigem

from tests.test_telegram.conftest import (
    _criar_tenant_e_owner,
    _criar_agente,
    _criar_telegram_instancia,
    _criar_atendimento_telegram,
)

WEBHOOK_URL = "/api/telegram/webhook/test-token:123ABC"

UPDATE_PRIVADO = {
    "update_id": 1,
    "message": {
        "message_id": 100,
        "chat": {"id": 123456789, "type": "private", "first_name": "João"},
        "from": {"id": 123456789, "first_name": "João", "is_bot": False},
        "text": "Olá!",
    },
}


def _build_update(chat_id=123456789, chat_type="private", text="Olá!", is_bot=False, from_id=None):
    return {
        "update_id": 1,
        "message": {
            "message_id": 100,
            "chat": {"id": chat_id, "type": chat_type, "first_name": "João"},
            "from": {"id": from_id or chat_id, "first_name": "João", "is_bot": is_bot},
            "text": text,
        },
    }


def _mock_agent_com_resposta(resposta="Resposta do agente"):
    from langchain_core.messages import AIMessage
    mock_agent = MagicMock()
    mock_agent.run.return_value = {"messages": [AIMessage(content=resposta)]}
    mock_agent.last_state = None
    mock_agent_cls = MagicMock()
    mock_agent_cls.return_value.build.return_value = mock_agent
    return mock_agent_cls, mock_agent


@pytest.mark.asyncio
async def test_token_desconhecido_retorna_200(client):
    r = await client.post("/api/telegram/webhook/token-invalido:999", json=UPDATE_PRIVADO)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_mensagem_grupo_ignorada(client, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    await _criar_telegram_instancia(db_session, tenant.id)

    payload = _build_update(chat_type="group")
    r = await client.post(WEBHOOK_URL, json=payload)

    assert r.status_code == 200
    result = await db_session.execute(select(Atendimento))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_mensagem_bot_ignorada(client, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    await _criar_telegram_instancia(db_session, tenant.id)

    payload = _build_update(is_bot=True)
    r = await client.post(WEBHOOK_URL, json=payload)

    assert r.status_code == 200
    result = await db_session.execute(select(Atendimento))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_mensagem_sem_texto_ignorada(client, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    await _criar_telegram_instancia(db_session, tenant.id)

    payload = {
        "update_id": 1,
        "message": {
            "message_id": 100,
            "chat": {"id": 123456789, "type": "private"},
            "from": {"id": 123456789, "first_name": "João", "is_bot": False},
        },
    }
    r = await client.post(WEBHOOK_URL, json=payload)

    assert r.status_code == 200
    result = await db_session.execute(select(Atendimento))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_cria_atendimentos_false_nao_cria_fila(client, db_session):
    """Bot com cria_atendimentos=False não cria Atendimento."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    await _criar_telegram_instancia(
        db_session, tenant.id, agente_id=agente.id, cria_atendimentos=False
    )

    mock_agent_cls, mock_agent = _mock_agent_com_resposta()
    with patch("docagent.telegram.router.ConfigurableAgent", mock_agent_cls):
        r = await client.post(WEBHOOK_URL, json=UPDATE_PRIVADO)

    assert r.status_code == 200
    result = await db_session.execute(select(Atendimento))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_primeiro_contato_cria_atendimento(client, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    await _criar_telegram_instancia(db_session, tenant.id, agente_id=agente.id)

    mock_agent_cls, _ = _mock_agent_com_resposta()
    with patch("docagent.telegram.router.ConfigurableAgent", mock_agent_cls):
        r = await client.post(WEBHOOK_URL, json=UPDATE_PRIVADO)

    assert r.status_code == 200
    db_session.expire_all()
    result = await db_session.execute(select(Atendimento))
    atendimentos = result.scalars().all()
    assert len(atendimentos) == 1
    assert atendimentos[0].numero == "123456789"
    assert atendimentos[0].status == AtendimentoStatus.ATIVO


@pytest.mark.asyncio
async def test_atendimento_tem_canal_telegram(client, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    await _criar_telegram_instancia(db_session, tenant.id, agente_id=agente.id)

    mock_agent_cls, _ = _mock_agent_com_resposta()
    with patch("docagent.telegram.router.ConfigurableAgent", mock_agent_cls):
        await client.post(WEBHOOK_URL, json=UPDATE_PRIVADO)

    db_session.expire_all()
    result = await db_session.execute(select(Atendimento))
    at = result.scalars().first()
    assert at.canal == CanalAtendimento.TELEGRAM
    assert at.instancia_id is None
    assert at.telegram_instancia_id is not None


@pytest.mark.asyncio
async def test_segundo_contato_retoma_atendimento(client, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id, agente_id=agente.id)
    existing = await _criar_atendimento_telegram(db_session, inst.id, tenant.id, numero="123456789")

    mock_agent_cls, _ = _mock_agent_com_resposta()
    with patch("docagent.telegram.router.ConfigurableAgent", mock_agent_cls):
        r = await client.post(WEBHOOK_URL, json=UPDATE_PRIVADO)

    assert r.status_code == 200
    db_session.expire_all()
    result = await db_session.execute(select(Atendimento))
    atendimentos = result.scalars().all()
    assert len(atendimentos) == 1  # não criou novo
    assert atendimentos[0].id == existing.id


@pytest.mark.asyncio
async def test_humano_nao_aciona_agente(client, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id, agente_id=agente.id)
    await _criar_atendimento_telegram(db_session, inst.id, tenant.id, numero="123456789", status="HUMANO")

    mock_agent_cls, _ = _mock_agent_com_resposta()
    with patch("docagent.telegram.router.ConfigurableAgent", mock_agent_cls):
        r = await client.post(WEBHOOK_URL, json=UPDATE_PRIVADO)

    assert r.status_code == 200
    mock_agent_cls.assert_not_called()


@pytest.mark.asyncio
async def test_ativo_executa_agente_e_salva_resposta(client, db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    await _criar_telegram_instancia(db_session, tenant.id, agente_id=agente.id)

    mock_agent_cls, mock_agent = _mock_agent_com_resposta("Resposta Telegram")
    mock_tg_client = AsyncMock()
    mock_tg_client.__aenter__ = AsyncMock(return_value=mock_tg_client)
    mock_tg_client.__aexit__ = AsyncMock(return_value=False)
    mock_tg_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))

    with (
        patch("docagent.telegram.router.ConfigurableAgent", mock_agent_cls),
        patch("docagent.telegram.router.get_telegram_client", return_value=mock_tg_client),
    ):
        r = await client.post(WEBHOOK_URL, json=UPDATE_PRIVADO)

    assert r.status_code == 200
    mock_agent.run.assert_called_once()

    db_session.expire_all()
    result = await db_session.execute(
        select(MensagemAtendimento).where(MensagemAtendimento.origem == MensagemOrigem.AGENTE)
    )
    msgs = result.scalars().all()
    assert len(msgs) == 1
    assert msgs[0].conteudo == "Resposta Telegram"
