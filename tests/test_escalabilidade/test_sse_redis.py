"""
Testes para AtendimentoSseManager e AtendimentoListaSseManager com Redis.
"""
import asyncio
import json
import pytest
from docagent.atendimento.sse import AtendimentoSseManager, AtendimentoListaSseManager


@pytest.mark.asyncio
async def test_broadcast_in_memory_entrega_evento():
    mgr = AtendimentoSseManager(redis=None)
    q = await mgr.subscribe(1)
    await mgr.broadcast(1, {"type": "teste", "dados": "ok"})
    evento = q.get_nowait()
    assert evento["type"] == "teste"
    mgr.unsubscribe(1, q)


@pytest.mark.asyncio
async def test_lista_broadcast_in_memory_entrega_evento():
    mgr = AtendimentoListaSseManager(redis=None)
    q = await mgr.subscribe(tenant_id=10)
    await mgr.broadcast(10, {"type": "NOVO_ATENDIMENTO"})
    evento = q.get_nowait()
    assert evento["type"] == "NOVO_ATENDIMENTO"
    mgr.unsubscribe(10, q)


@pytest.mark.asyncio
async def test_unsubscribe_cancela_bridge(fake_redis):
    """
    Verifica que cancelar a subscrição cancela a bridge task sem exceção.
    """
    mgr = AtendimentoSseManager(redis=fake_redis)
    q = await mgr.subscribe(99)
    assert q in mgr._bridge_tasks
    mgr.unsubscribe(99, q)
    # Task deve ter sido cancelada
    assert q not in mgr._bridge_tasks
