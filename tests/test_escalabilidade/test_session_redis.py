"""
Testes para RedisSessionManager e InMemorySessionManager (interface async).
"""
import pytest
from docagent.chat.session import InMemorySessionManager, RedisSessionManager, get_session_manager_instance


@pytest.mark.asyncio
async def test_in_memory_get_retorna_estado_vazio():
    mgr = InMemorySessionManager()
    state = await mgr.get_async("inexistente")
    assert state == {"messages": [], "summary": ""}


@pytest.mark.asyncio
async def test_in_memory_update_e_get():
    mgr = InMemorySessionManager()
    await mgr.update_async("sess1", {"messages": ["msg1"], "summary": "res"})
    state = await mgr.get_async("sess1")
    assert state["messages"] == ["msg1"]
    assert state["summary"] == "res"


@pytest.mark.asyncio
async def test_redis_get_retorna_estado_vazio(fake_redis):
    mgr = RedisSessionManager(fake_redis)
    state = await mgr.get_async("inexistente")
    assert state == {"messages": [], "summary": ""}


@pytest.mark.asyncio
async def test_redis_update_e_get(fake_redis):
    mgr = RedisSessionManager(fake_redis, ttl=60)
    payload = {"messages": [{"role": "user", "content": "oi"}], "summary": ""}
    await mgr.update_async("sess42", payload)
    retrieved = await mgr.get_async("sess42")
    assert retrieved["messages"][0]["content"] == "oi"


@pytest.mark.asyncio
async def test_redis_delete(fake_redis):
    mgr = RedisSessionManager(fake_redis)
    await mgr.update_async("del_sess", {"messages": [], "summary": "x"})
    deleted = await mgr.delete_async("del_sess")
    assert deleted is True
    state = await mgr.get_async("del_sess")
    assert state == {"messages": [], "summary": ""}


@pytest.mark.asyncio
async def test_factory_retorna_in_memory_sem_redis():
    mgr = get_session_manager_instance(redis=None)
    assert isinstance(mgr, InMemorySessionManager)


@pytest.mark.asyncio
async def test_factory_retorna_redis_com_redis(fake_redis):
    mgr = get_session_manager_instance(redis=fake_redis)
    assert isinstance(mgr, RedisSessionManager)
