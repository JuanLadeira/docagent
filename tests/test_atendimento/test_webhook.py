"""
Testes de integração para o webhook com gestão de atendimentos.

Valida que:
- Mensagens de grupo (@g.us) são ignoradas
- Primeiro contato cria atendimento
- Segundo contato do mesmo número retoma (não cria novo)
- Status HUMANO impede o agente de responder
- Status ATIVO aciona o agente e salva a resposta
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from docagent.atendimento.models import Atendimento, AtendimentoStatus, MensagemAtendimento, MensagemOrigem
from tests.test_atendimento.conftest import (
    _criar_tenant_e_owner,
    _criar_agente,
    _criar_instancia,
    _criar_atendimento,
)

WEBHOOK_URL = "/api/whatsapp/webhook"


def _build_payload(instance_name, remote_jid, text="Olá", from_me=False):
    return {
        "event": "MESSAGES_UPSERT",
        "instance": instance_name,
        "data": {
            "key": {"fromMe": from_me, "remoteJid": remote_jid},
            "message": {"conversation": text},
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


def _mock_httpx():
    mock_httpx = AsyncMock()
    mock_httpx.__aenter__ = AsyncMock(return_value=mock_httpx)
    mock_httpx.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))
    return mock_httpx


@pytest.mark.asyncio
async def test_mensagem_grupo_ignorada(client, db_session):
    """Mensagens de grupos (@g.us) não criam atendimento."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    instancia = await _criar_instancia(db_session, tenant.id, agente.id)

    payload = _build_payload(instancia.instance_name, "112233445566@g.us", "Msg de grupo")
    with patch("docagent.whatsapp.router.ConfigurableAgent"):
        r = await client.post(WEBHOOK_URL, json=payload)

    assert r.status_code == 200
    result = await db_session.execute(select(Atendimento))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_primeiro_contato_cria_atendimento(client, db_session):
    """Primeira mensagem de um número cria atendimento ATIVO."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    instancia = await _criar_instancia(db_session, tenant.id, agente.id)

    mock_agent_cls, _ = _mock_agent_com_resposta()
    mock_httpx = _mock_httpx()

    payload = _build_payload(instancia.instance_name, "5511999999999@s.whatsapp.net", "Oi")
    with (
        patch("docagent.whatsapp.router.ConfigurableAgent", mock_agent_cls),
        patch("docagent.whatsapp.router.httpx.AsyncClient", return_value=mock_httpx),
    ):
        r = await client.post(WEBHOOK_URL, json=payload)

    assert r.status_code == 200
    db_session.expire_all()
    result = await db_session.execute(select(Atendimento))
    atendimentos = result.scalars().all()
    assert len(atendimentos) == 1
    assert atendimentos[0].numero == "5511999999999"
    assert atendimentos[0].status == AtendimentoStatus.ATIVO


@pytest.mark.asyncio
async def test_segundo_contato_retoma_atendimento(client, db_session):
    """Segunda mensagem do mesmo número retoma atendimento existente."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    instancia = await _criar_instancia(db_session, tenant.id, agente.id)
    existing = await _criar_atendimento(db_session, instancia.id, tenant.id, "5511999999999")

    mock_agent_cls, _ = _mock_agent_com_resposta()
    mock_httpx = _mock_httpx()

    payload = _build_payload(instancia.instance_name, "5511999999999@s.whatsapp.net", "Mais uma")
    with (
        patch("docagent.whatsapp.router.ConfigurableAgent", mock_agent_cls),
        patch("docagent.whatsapp.router.httpx.AsyncClient", return_value=mock_httpx),
    ):
        r = await client.post(WEBHOOK_URL, json=payload)

    assert r.status_code == 200
    db_session.expire_all()
    result = await db_session.execute(select(Atendimento))
    atendimentos = result.scalars().all()
    assert len(atendimentos) == 1  # não criou novo
    assert atendimentos[0].id == existing.id


@pytest.mark.asyncio
async def test_humano_nao_aciona_agente(client, db_session):
    """Quando atendimento é HUMANO, o agente NÃO deve ser acionado."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    instancia = await _criar_instancia(db_session, tenant.id, agente.id)
    await _criar_atendimento(db_session, instancia.id, tenant.id, "5511999999999", "HUMANO")

    payload = _build_payload(instancia.instance_name, "5511999999999@s.whatsapp.net", "Nova msg")
    with patch("docagent.whatsapp.router.ConfigurableAgent") as mock_agent_cls:
        r = await client.post(WEBHOOK_URL, json=payload)

    assert r.status_code == 200
    mock_agent_cls.assert_not_called()


@pytest.mark.asyncio
async def test_ativo_salva_mensagem_agente(client, db_session):
    """Quando ATIVO, o agente responde e salva MensagemAtendimento(AGENTE)."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    instancia = await _criar_instancia(db_session, tenant.id, agente.id)
    await _criar_atendimento(db_session, instancia.id, tenant.id, "5511999999999", "ATIVO")

    mock_agent_cls, mock_agent = _mock_agent_com_resposta("Resposta do agente")
    mock_httpx = _mock_httpx()

    payload = _build_payload(instancia.instance_name, "5511999999999@s.whatsapp.net", "Preciso de ajuda")
    with (
        patch("docagent.whatsapp.router.ConfigurableAgent", mock_agent_cls),
        patch("docagent.whatsapp.router.httpx.AsyncClient", return_value=mock_httpx),
    ):
        r = await client.post(WEBHOOK_URL, json=payload)

    assert r.status_code == 200
    mock_agent.run.assert_called_once()

    db_session.expire_all()
    result = await db_session.execute(
        select(MensagemAtendimento).where(MensagemAtendimento.origem == MensagemOrigem.AGENTE)
    )
    msgs_agente = result.scalars().all()
    assert len(msgs_agente) == 1
    assert msgs_agente[0].conteudo == "Resposta do agente"
