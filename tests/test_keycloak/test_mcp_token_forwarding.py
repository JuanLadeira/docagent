import pytest
from unittest.mock import AsyncMock, patch

from docagent.mcp_server.models import McpServer
from docagent.mcp_server.services import _build_mcp_headers


def _make_server(auth_type: str, env: dict | None = None, url: str | None = None) -> McpServer:
    s = McpServer()
    s.auth_type = auth_type
    s.env = env or {}
    s.url = url
    s.transport = "sse" if url else "stdio"
    s.command = ""
    s.args = []
    return s


@pytest.mark.asyncio
async def test_build_headers_none_retorna_vazio(fake_redis):
    server = _make_server("none")
    headers = await _build_mcp_headers(server, usuario_id=1, redis=fake_redis)
    assert headers == {}


@pytest.mark.asyncio
async def test_build_headers_static_usa_env(fake_redis):
    server = _make_server("static", env={"Authorization": "Bearer token-estatico"})
    headers = await _build_mcp_headers(server, usuario_id=1, redis=fake_redis)
    assert headers == {"Authorization": "Bearer token-estatico"}


@pytest.mark.asyncio
async def test_build_headers_static_sem_env_retorna_vazio(fake_redis):
    server = _make_server("static", env={})
    headers = await _build_mcp_headers(server, usuario_id=1, redis=fake_redis)
    assert headers == {}


@pytest.mark.asyncio
async def test_build_headers_keycloak_com_token_valido(fake_redis):
    server = _make_server("keycloak")

    with patch(
        "docagent.mcp_server.services.KeycloakService.get_access_token",
        new_callable=AsyncMock,
        return_value="at-fresco",
    ):
        headers = await _build_mcp_headers(server, usuario_id=5, redis=fake_redis)

    assert headers == {"Authorization": "Bearer at-fresco"}


@pytest.mark.asyncio
async def test_build_headers_keycloak_sem_token_retorna_vazio(fake_redis):
    server = _make_server("keycloak")

    with patch(
        "docagent.mcp_server.services.KeycloakService.get_access_token",
        new_callable=AsyncMock,
        return_value=None,
    ):
        headers = await _build_mcp_headers(server, usuario_id=5, redis=fake_redis)

    assert headers == {}


@pytest.mark.asyncio
async def test_build_headers_keycloak_sem_redis_retorna_vazio():
    server = _make_server("keycloak")
    headers = await _build_mcp_headers(server, usuario_id=5, redis=None)
    assert headers == {}


@pytest.mark.asyncio
async def test_build_headers_keycloak_sem_usuario_id_retorna_vazio(fake_redis):
    server = _make_server("keycloak")
    headers = await _build_mcp_headers(server, usuario_id=None, redis=fake_redis)
    assert headers == {}
