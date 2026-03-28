"""
Testes de regressão: operador responde pelo canal correto.
- WHATSAPP → envia via Evolution API
- TELEGRAM → envia via Telegram Bot API
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from docagent.atendimento.models import AtendimentoStatus, CanalAtendimento, MensagemOrigem
from docagent.atendimento.services import AtendimentoService

from tests.test_telegram.conftest import (
    _criar_tenant_e_owner,
    _criar_telegram_instancia,
    _criar_atendimento_telegram,
)


@pytest.mark.asyncio
async def test_operador_responde_telegram_usa_telegram_api(db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    at = await _criar_atendimento_telegram(db_session, inst.id, tenant.id, status="HUMANO")

    mock_evolution_client = AsyncMock()
    svc = AtendimentoService(db_session, mock_evolution_client)

    mock_tg_client = AsyncMock()
    mock_tg_client.__aenter__ = AsyncMock(return_value=mock_tg_client)
    mock_tg_client.__aexit__ = AsyncMock(return_value=False)
    mock_tg_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))

    with patch("docagent.atendimento.services.get_telegram_client", return_value=mock_tg_client):
        msg = await svc.enviar_mensagem_operador(at, "Olá pelo Telegram!")

    # Evolution API NÃO deve ser chamada
    mock_evolution_client.post.assert_not_called()
    # Telegram API deve ser chamada
    mock_tg_client.post.assert_called_once()
    call = mock_tg_client.post.call_args
    assert call[1]["json"]["text"] == "Olá pelo Telegram!"
    assert msg.origem == MensagemOrigem.OPERADOR


@pytest.mark.asyncio
async def test_operador_responde_whatsapp_usa_evolution(db_session):
    from docagent.whatsapp.models import WhatsappInstancia, ConexaoStatus
    from docagent.atendimento.models import Atendimento

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    wh_inst = WhatsappInstancia(
        instance_name="wh-test",
        status=ConexaoStatus.CONECTADA,
        tenant_id=tenant.id,
    )
    db_session.add(wh_inst)
    await db_session.flush()
    await db_session.refresh(wh_inst)

    at = Atendimento(
        numero="5511999999999",
        instancia_id=wh_inst.id,
        canal=CanalAtendimento.WHATSAPP,
        tenant_id=tenant.id,
        status=AtendimentoStatus.HUMANO,
    )
    db_session.add(at)
    await db_session.flush()
    await db_session.refresh(at)
    await db_session.commit()

    mock_evolution = AsyncMock()
    mock_evolution.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))
    svc = AtendimentoService(db_session, mock_evolution)

    msg = await svc.enviar_mensagem_operador(at, "Olá pelo WhatsApp!")

    # Evolution API deve ser chamada
    mock_evolution.post.assert_called_once()
    assert msg.origem == MensagemOrigem.OPERADOR


@pytest.mark.asyncio
async def test_operador_nao_humano_retorna_400(db_session):
    from fastapi import HTTPException

    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    at = await _criar_atendimento_telegram(db_session, inst.id, tenant.id, status="ATIVO")

    svc = AtendimentoService(db_session, AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        await svc.enviar_mensagem_operador(at, "Não deve enviar")
    assert exc_info.value.status_code == 400
