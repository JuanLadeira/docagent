"""
Testes unitários para o SseManager (Fase 12).

Testa subscribe/unsubscribe/broadcast em isolamento puro (sem banco, sem HTTP).
"""
import pytest

from docagent.whatsapp.ws_manager import SseManager


@pytest.mark.asyncio
async def test_subscribe_cria_fila():
    manager = SseManager()
    queue = await manager.subscribe(tenant_id=1)
    assert queue in manager._queues[1]


@pytest.mark.asyncio
async def test_unsubscribe_remove_fila():
    manager = SseManager()
    queue = await manager.subscribe(tenant_id=1)
    manager.unsubscribe(tenant_id=1, queue=queue)
    assert queue not in manager._queues[1]


@pytest.mark.asyncio
async def test_broadcast_entrega_evento():
    manager = SseManager()
    queue = await manager.subscribe(tenant_id=1)
    evento = {"type": "QRCODE_UPDATED", "qr_base64": "abc"}

    await manager.broadcast(tenant_id=1, event=evento)

    assert not queue.empty()
    recebido = await queue.get()
    assert recebido == evento


@pytest.mark.asyncio
async def test_broadcast_para_multiplos_subscribers():
    manager = SseManager()
    q1 = await manager.subscribe(tenant_id=1)
    q2 = await manager.subscribe(tenant_id=1)
    evento = {"type": "CONNECTION_UPDATE", "status": "CONECTADA"}

    await manager.broadcast(tenant_id=1, event=evento)

    assert (await q1.get()) == evento
    assert (await q2.get()) == evento


@pytest.mark.asyncio
async def test_broadcast_isolado_por_tenant():
    """Evento de tenant_id=1 nao deve chegar em subscriber de tenant_id=2."""
    manager = SseManager()
    q1 = await manager.subscribe(tenant_id=1)
    q2 = await manager.subscribe(tenant_id=2)

    await manager.broadcast(tenant_id=1, event={"type": "ping"})

    assert not q1.empty()
    assert q2.empty()


@pytest.mark.asyncio
async def test_unsubscribe_nao_afeta_outros():
    manager = SseManager()
    q1 = await manager.subscribe(tenant_id=1)
    q2 = await manager.subscribe(tenant_id=1)

    manager.unsubscribe(tenant_id=1, queue=q1)

    await manager.broadcast(tenant_id=1, event={"type": "test"})

    assert q1.empty()
    assert not q2.empty()
