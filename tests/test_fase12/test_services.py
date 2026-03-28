"""
Testes unitários para WhatsappService (Fase 12).

Testa a camada de serviço diretamente, com mock do Evolution API client.
"""
import pytest
from unittest.mock import MagicMock
from httpx import Response

from docagent.whatsapp.models import ConexaoStatus, WhatsappInstancia
from docagent.whatsapp.schemas import InstanciaCreate, MensagemTextoRequest
from docagent.whatsapp.services import WhatsappService

from tests.test_fase12.conftest import _criar_tenant_e_owner, _criar_instancia


def _mock_response(status_code=200, json_data=None):
    r = MagicMock(spec=Response)
    r.status_code = status_code
    r.json.return_value = json_data or {}
    r.raise_for_status = MagicMock()
    return r


@pytest.mark.asyncio
async def test_criar_instancia(db_session, mock_evolution):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    mock_evolution.post.return_value = _mock_response(200, {"instance": {"instanceName": "nova"}})

    service = WhatsappService(mock_evolution, db_session)
    data = InstanciaCreate(instance_name="nova", agente_id=None)
    instancia = await service.criar_instancia(tenant.id, data, "http://localhost/webhook")

    assert instancia.instance_name == "nova"
    assert instancia.status == ConexaoStatus.CRIADA
    assert instancia.tenant_id == tenant.id
    mock_evolution.post.assert_called_once()


@pytest.mark.asyncio
async def test_listar_instancias(db_session, mock_evolution):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    await _criar_instancia(db_session, tenant.id)

    service = WhatsappService(mock_evolution, db_session)
    instancias = await service.listar_instancias(tenant.id)

    assert len(instancias) == 1
    assert instancias[0].instance_name == "instancia-teste"


@pytest.mark.asyncio
async def test_listar_instancias_isolamento_por_tenant(db_session, mock_evolution):
    """Instancias de outro tenant nao devem aparecer."""
    tenant1, _, _ = await _criar_tenant_e_owner(db_session, username="owner1")
    tenant2, _, _ = await _criar_tenant_e_owner(db_session, username="owner2")

    inst2 = WhatsappInstancia(
        instance_name="inst-outro-tenant",
        status=ConexaoStatus.CRIADA,
        tenant_id=tenant2.id,
    )
    db_session.add(inst2)
    await db_session.flush()

    service = WhatsappService(mock_evolution, db_session)
    instancias = await service.listar_instancias(tenant1.id)

    assert len(instancias) == 0


@pytest.mark.asyncio
async def test_obter_qrcode_atualiza_status(db_session, mock_evolution):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    mock_evolution.get.return_value = _mock_response(200, {"base64": "abc123"})

    service = WhatsappService(mock_evolution, db_session)
    result = await service.obter_qrcode(instancia)

    assert instancia.status == ConexaoStatus.CONECTANDO
    assert result["base64"] == "data:image/png;base64,abc123"
    assert result["status"] == "CONECTANDO"


@pytest.mark.asyncio
async def test_sincronizar_status_open(db_session, mock_evolution):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    mock_evolution.get.return_value = _mock_response(200, {"state": "open"})

    service = WhatsappService(mock_evolution, db_session)
    resultado = await service.sincronizar_status(instancia)

    assert resultado.status == ConexaoStatus.CONECTADA


@pytest.mark.asyncio
async def test_sincronizar_status_close(db_session, mock_evolution):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    mock_evolution.get.return_value = _mock_response(200, {"state": "close"})

    service = WhatsappService(mock_evolution, db_session)
    resultado = await service.sincronizar_status(instancia)

    assert resultado.status == ConexaoStatus.DESCONECTADA


@pytest.mark.asyncio
async def test_deletar_instancia(db_session, mock_evolution):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)

    service = WhatsappService(mock_evolution, db_session)
    await service.deletar_instancia(instancia)

    instancias = await service.listar_instancias(tenant.id)
    assert len(instancias) == 0


@pytest.mark.asyncio
async def test_enviar_texto(db_session, mock_evolution):
    tenant, _, _ = await _criar_tenant_e_owner(db_session)
    instancia = await _criar_instancia(db_session, tenant.id)
    mock_evolution.post.return_value = _mock_response(200, {"key": {"id": "msg123"}, "status": "PENDING"})

    service = WhatsappService(mock_evolution, db_session)
    data = MensagemTextoRequest(number="5511999999999", text="Ola!")
    result = await service.enviar_texto(instancia, data)

    assert result["status"] == "PENDING"
    mock_evolution.post.assert_called_once()
