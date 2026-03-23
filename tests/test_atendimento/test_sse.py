"""Testes para AtendimentoSseManager."""
import pytest
from docagent.atendimento.sse import AtendimentoSseManager


@pytest.mark.asyncio
async def test_subscribe_e_broadcast():
    mgr = AtendimentoSseManager()
    q = await mgr.subscribe(1)
    await mgr.broadcast(1, {"type": "NOVA_MENSAGEM", "conteudo": "Olá"})
    event = q.get_nowait()
    assert event["type"] == "NOVA_MENSAGEM"
    assert event["conteudo"] == "Olá"


@pytest.mark.asyncio
async def test_broadcast_multiplos_subscribers():
    mgr = AtendimentoSseManager()
    q1 = await mgr.subscribe(1)
    q2 = await mgr.subscribe(1)
    await mgr.broadcast(1, {"type": "NOVA_MENSAGEM"})
    assert not q1.empty()
    assert not q2.empty()


@pytest.mark.asyncio
async def test_unsubscribe_nao_recebe():
    mgr = AtendimentoSseManager()
    q = await mgr.subscribe(1)
    mgr.unsubscribe(1, q)
    await mgr.broadcast(1, {"type": "NOVA_MENSAGEM"})
    assert q.empty()


@pytest.mark.asyncio
async def test_isolamento_por_atendimento_id():
    mgr = AtendimentoSseManager()
    q1 = await mgr.subscribe(1)
    q2 = await mgr.subscribe(2)
    await mgr.broadcast(1, {"type": "NOVA_MENSAGEM"})
    assert not q1.empty()
    assert q2.empty()
