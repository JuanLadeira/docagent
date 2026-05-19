"""
Fixtures para testes de escalabilidade (Redis / Celery).

Usa fakeredis — sem container necessário.
"""
import pytest
import pytest_asyncio
import fakeredis.aioredis as fake_aioredis


@pytest_asyncio.fixture
async def fake_redis():
    """Instância de fakeredis async, isolada por teste."""
    r = fake_aioredis.FakeRedis()
    yield r
    await r.aclose()
