"""Testes unitários para AtendimentoService."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from docagent.atendimento.models import Atendimento, AtendimentoStatus, MensagemOrigem
from docagent.atendimento.services import AtendimentoService
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
async def service(db_session):
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client.post.return_value = mock_response
    return AtendimentoService(db_session, mock_client)


@pytest.mark.asyncio
async def test_criar_atendimento_novo(db_session, setup, service):
    """Primeiro contato cria atendimento ATIVO."""
    _, instancia = setup
    at = await service.criar_ou_retomar(instancia.id, instancia.tenant_id, "5511111111111")
    assert at.numero == "5511111111111"
    assert at.status == AtendimentoStatus.ATIVO
    assert at.instancia_id == instancia.id


@pytest.mark.asyncio
async def test_retomar_atendimento_existente(db_session, setup, service):
    """Mesmo número retorna atendimento existente (não cria novo)."""
    tenant, instancia = setup
    existing = await _criar_atendimento(db_session, instancia.id, tenant.id, "5511111111111")
    at = await service.criar_ou_retomar(instancia.id, instancia.tenant_id, "5511111111111")
    assert at.id == existing.id


@pytest.mark.asyncio
async def test_novo_apos_encerrado(db_session, setup, service):
    """Número com atendimento ENCERRADO gera novo atendimento."""
    tenant, instancia = setup
    encerrado = await _criar_atendimento(db_session, instancia.id, tenant.id, "5511111111111", "ENCERRADO")
    at = await service.criar_ou_retomar(instancia.id, instancia.tenant_id, "5511111111111")
    assert at.id != encerrado.id
    assert at.status == AtendimentoStatus.ATIVO


@pytest.mark.asyncio
async def test_salvar_mensagem(db_session, setup, service):
    """Salva mensagem com origem e conteúdo corretos."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)
    msg = await service.salvar_mensagem(atendimento.id, MensagemOrigem.CONTATO, "Olá!")
    assert msg.origem == MensagemOrigem.CONTATO
    assert msg.conteudo == "Olá!"
    assert msg.atendimento_id == atendimento.id


@pytest.mark.asyncio
async def test_assumir(db_session, setup, service):
    """Assumir muda status para HUMANO."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)
    at = await service.assumir(atendimento)
    assert at.status == AtendimentoStatus.HUMANO


@pytest.mark.asyncio
async def test_devolver(db_session, setup, service):
    """Devolver muda status para ATIVO."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id, status="HUMANO")
    at = await service.devolver(atendimento)
    assert at.status == AtendimentoStatus.ATIVO


@pytest.mark.asyncio
async def test_encerrar(db_session, setup, service):
    """Encerrar muda status para ENCERRADO."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)
    at = await service.encerrar(atendimento)
    assert at.status == AtendimentoStatus.ENCERRADO


@pytest.mark.asyncio
async def test_enviar_mensagem_operador_nao_humano_raises(db_session, setup, service):
    """Enviar mensagem de operador em atendimento não-HUMANO lança 400."""
    tenant, instancia = setup
    atendimento = await _criar_atendimento(db_session, instancia.id, tenant.id)  # status=ATIVO
    with pytest.raises(HTTPException) as exc:
        await service.enviar_mensagem_operador(atendimento, "texto")
    assert exc.value.status_code == 400
