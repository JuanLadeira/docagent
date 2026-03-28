"""Testes unitários para AtendimentoService (base) e WhatsappAtendimentoService."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from docagent.atendimento.models import Atendimento, AtendimentoStatus, MensagemOrigem
from docagent.atendimento.services import AtendimentoService
from docagent.whatsapp.atendimento_service import WhatsappAtendimentoService
from tests.test_atendimento.conftest import (
    _criar_tenant_e_owner,
    _criar_agente,
    _criar_instancia,
    _criar_atendimento,
)


@pytest_asyncio.fixture
async def setup(db_session):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    agente = await _criar_agente(db_session)
    instancia = await _criar_instancia(db_session, tenant.id, agente.id)
    return tenant, instancia


@pytest_asyncio.fixture
async def base_service(db_session):
    return AtendimentoService(db_session)


@pytest_asyncio.fixture
async def wa_service(db_session):
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client.post.return_value = mock_response
    return WhatsappAtendimentoService(db_session, mock_client)


# ── WhatsappAtendimentoService: criar_ou_retomar ──────────────────────────────

@pytest.mark.asyncio
async def test_criar_atendimento_novo(db_session, setup, wa_service):
    """Primeiro contato cria atendimento ATIVO."""
    _, instancia = setup
    at = await wa_service.criar_ou_retomar(instancia.id, instancia.tenant_id, "5511111111111")
    assert at.numero == "5511111111111"
    assert at.status == AtendimentoStatus.ATIVO
    assert at.instancia_id == instancia.id


@pytest.mark.asyncio
async def test_retomar_atendimento_existente(db_session, setup, wa_service):
    """Mesmo número retorna atendimento existente (não cria novo)."""
    tenant, instancia = setup
    existing = await _criar_atendimento(db_session, instancia.id, tenant.id, "5511111111111")
    at = await wa_service.criar_ou_retomar(instancia.id, instancia.tenant_id, "5511111111111")
    assert at.id == existing.id


@pytest.mark.asyncio
async def test_novo_apos_encerrado(db_session, setup, wa_service):
    """Número com atendimento ENCERRADO gera novo atendimento."""
    tenant, instancia = setup
    encerrado = await _criar_atendimento(db_session, instancia.id, tenant.id, "5511111111111", "ENCERRADO")
    at = await wa_service.criar_ou_retomar(instancia.id, instancia.tenant_id, "5511111111111")
    assert at.id != encerrado.id
    assert at.status == AtendimentoStatus.ATIVO


# ── AtendimentoService base: salvar_mensagem ──────────────────────────────────

@pytest.mark.asyncio
async def test_salvar_mensagem(db_session, setup, base_service):
    """Salva mensagem com origem e conteúdo corretos."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)
    msg = await base_service.salvar_mensagem(atendimento.id, MensagemOrigem.CONTATO, "Olá!")
    assert msg.origem == MensagemOrigem.CONTATO
    assert msg.conteudo == "Olá!"
    assert msg.atendimento_id == atendimento.id


# ── AtendimentoService base: transições de status ────────────────────────────

@pytest.mark.asyncio
async def test_assumir(db_session, setup, base_service):
    """Assumir muda status para HUMANO."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)
    at = await base_service.assumir(atendimento)
    assert at.status == AtendimentoStatus.HUMANO


@pytest.mark.asyncio
async def test_devolver(db_session, setup, base_service):
    """Devolver muda status para ATIVO."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id, status="HUMANO")
    at = await base_service.devolver(atendimento)
    assert at.status == AtendimentoStatus.ATIVO


@pytest.mark.asyncio
async def test_encerrar(db_session, setup, base_service):
    """Encerrar muda status para ENCERRADO."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)
    at = await base_service.encerrar(atendimento)
    assert at.status == AtendimentoStatus.ENCERRADO


# ── WhatsappAtendimentoService: enviar_mensagem_operador ──────────────────────

@pytest.mark.asyncio
async def test_enviar_mensagem_operador_nao_humano_raises(db_session, setup, wa_service):
    """Enviar mensagem de operador em atendimento não-HUMANO lança 400."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)  # status=ATIVO
    with pytest.raises(HTTPException) as exc:
        await wa_service.enviar_mensagem_operador(atendimento, "texto")
    assert exc.value.status_code == 400
