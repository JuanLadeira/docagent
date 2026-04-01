"""Testes unitários dos modelos Telegram e CanalAtendimento."""
import pytest

from docagent.telegram.models import TelegramBotStatus
from docagent.atendimento.models import Atendimento, CanalAtendimento

from tests.test_telegram.conftest import (
    _criar_tenant_e_owner,
    _criar_agente,
    _criar_telegram_instancia,
)


@pytest.mark.asyncio
async def test_telegram_instancia_campos_obrigatorios(db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)
    assert inst.id is not None
    assert inst.bot_token == "test-token:123ABC"
    assert inst.bot_username == "test_bot"
    assert inst.webhook_configured is True
    assert inst.status == TelegramBotStatus.ATIVA
    assert inst.cria_atendimentos is True
    assert inst.tenant_id == tenant.id
    assert inst.agente_id is None


@pytest.mark.asyncio
async def test_telegram_instancia_cria_atendimentos_false(db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id, cria_atendimentos=False)
    assert inst.cria_atendimentos is False


@pytest.mark.asyncio
async def test_telegram_instancia_com_agente(db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session, tenant.id)
    inst = await _criar_telegram_instancia(db_session, tenant.id, agente_id=agente.id)
    assert inst.agente_id == agente.id


@pytest.mark.asyncio
async def test_atendimento_canal_whatsapp_padrao(db_session):
    """Atendimento criado sem canal explícito usa WHATSAPP por padrão."""
    from docagent.whatsapp.models import WhatsappInstancia, ConexaoStatus
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    wh_inst = WhatsappInstancia(
        instance_name="wh-teste",
        status=ConexaoStatus.CONECTADA,
        tenant_id=tenant.id,
    )
    db_session.add(wh_inst)
    await db_session.flush()
    await db_session.refresh(wh_inst)

    at = Atendimento(
        numero="5511999999999",
        instancia_id=wh_inst.id,
        tenant_id=tenant.id,
    )
    db_session.add(at)
    await db_session.flush()
    await db_session.refresh(at)
    assert at.canal == CanalAtendimento.WHATSAPP
    assert at.telegram_instancia_id is None


@pytest.mark.asyncio
async def test_atendimento_canal_telegram(db_session):
    """Atendimento Telegram tem instancia_id=None e telegram_instancia_id preenchido."""
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    inst = await _criar_telegram_instancia(db_session, tenant.id)

    at = Atendimento(
        numero="123456789",
        canal=CanalAtendimento.TELEGRAM,
        telegram_instancia_id=inst.id,
        instancia_id=None,
        tenant_id=tenant.id,
    )
    db_session.add(at)
    await db_session.flush()
    await db_session.refresh(at)

    assert at.canal == CanalAtendimento.TELEGRAM
    assert at.instancia_id is None
    assert at.telegram_instancia_id == inst.id


@pytest.mark.asyncio
async def test_canal_atendimento_enum_values():
    assert CanalAtendimento.WHATSAPP == "WHATSAPP"
    assert CanalAtendimento.TELEGRAM == "TELEGRAM"
