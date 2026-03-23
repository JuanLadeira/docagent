"""
Testes de integração para os endpoints /api/mcp-servidores.

Valida CRUD, autenticação e controle de acesso (OWNER only).
"""
import pytest
from httpx import AsyncClient

from docagent.mcp_server.models import McpServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SERVER_PAYLOAD = {
    "nome": "Filesystem",
    "descricao": "Acesso a arquivos locais",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    "env": {},
    "ativo": True,
}


async def _create_server(client: AsyncClient, headers: dict) -> dict:
    r = await client.post("/api/mcp-servidores", json=_SERVER_PAYLOAD, headers=headers)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# GET /api/mcp-servidores
# ---------------------------------------------------------------------------

class TestListarServidores:
    @pytest.mark.asyncio
    async def test_sem_auth_retorna_401(self, client: AsyncClient):
        r = await client.get("/api/mcp-servidores")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_com_auth_retorna_200(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/mcp-servidores", headers=auth_headers)
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_retorna_lista_vazia_inicialmente(self, client: AsyncClient, auth_headers: dict):
        r = await client.get("/api/mcp-servidores", headers=auth_headers)
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_retorna_servidor_criado(self, client: AsyncClient, auth_headers: dict):
        await _create_server(client, auth_headers)
        r = await client.get("/api/mcp-servidores", headers=auth_headers)
        assert len(r.json()) == 1
        assert r.json()[0]["nome"] == "Filesystem"


# ---------------------------------------------------------------------------
# POST /api/mcp-servidores
# ---------------------------------------------------------------------------

class TestCriarServidor:
    @pytest.mark.asyncio
    async def test_sem_auth_retorna_401(self, client: AsyncClient):
        r = await client.post("/api/mcp-servidores", json=_SERVER_PAYLOAD)
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_owner_pode_criar(self, client: AsyncClient, auth_headers: dict):
        r = await client.post("/api/mcp-servidores", json=_SERVER_PAYLOAD, headers=auth_headers)
        assert r.status_code == 201

    @pytest.mark.asyncio
    async def test_resposta_contem_id(self, client: AsyncClient, auth_headers: dict):
        r = await client.post("/api/mcp-servidores", json=_SERVER_PAYLOAD, headers=auth_headers)
        assert "id" in r.json()

    @pytest.mark.asyncio
    async def test_resposta_contem_tools_vazia(self, client: AsyncClient, auth_headers: dict):
        r = await client.post("/api/mcp-servidores", json=_SERVER_PAYLOAD, headers=auth_headers)
        assert r.json()["tools"] == []

    @pytest.mark.asyncio
    async def test_persiste_command_e_args(self, client: AsyncClient, auth_headers: dict):
        r = await client.post("/api/mcp-servidores", json=_SERVER_PAYLOAD, headers=auth_headers)
        data = r.json()
        assert data["command"] == "npx"
        assert "-y" in data["args"]


# ---------------------------------------------------------------------------
# PUT /api/mcp-servidores/{id}
# ---------------------------------------------------------------------------

class TestAtualizarServidor:
    @pytest.mark.asyncio
    async def test_owner_pode_atualizar(self, client: AsyncClient, auth_headers: dict):
        server = await _create_server(client, auth_headers)
        r = await client.put(
            f"/api/mcp-servidores/{server['id']}",
            json={"nome": "Novo Nome"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["nome"] == "Novo Nome"

    @pytest.mark.asyncio
    async def test_servidor_inexistente_retorna_404(self, client: AsyncClient, auth_headers: dict):
        r = await client.put(
            "/api/mcp-servidores/99999",
            json={"nome": "X"},
            headers=auth_headers,
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_sem_auth_retorna_401(self, client: AsyncClient):
        r = await client.put("/api/mcp-servidores/1", json={"nome": "X"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/mcp-servidores/{id}
# ---------------------------------------------------------------------------

class TestDeletarServidor:
    @pytest.mark.asyncio
    async def test_owner_pode_deletar(self, client: AsyncClient, auth_headers: dict):
        server = await _create_server(client, auth_headers)
        r = await client.delete(f"/api/mcp-servidores/{server['id']}", headers=auth_headers)
        assert r.status_code == 204

    @pytest.mark.asyncio
    async def test_servidor_removido_nao_aparece_na_lista(self, client: AsyncClient, auth_headers: dict):
        server = await _create_server(client, auth_headers)
        await client.delete(f"/api/mcp-servidores/{server['id']}", headers=auth_headers)
        r = await client.get("/api/mcp-servidores", headers=auth_headers)
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_servidor_inexistente_retorna_404(self, client: AsyncClient, auth_headers: dict):
        r = await client.delete("/api/mcp-servidores/99999", headers=auth_headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_sem_auth_retorna_401(self, client: AsyncClient):
        r = await client.delete("/api/mcp-servidores/1")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/mcp-servidores/{id}/descobrir-tools
# ---------------------------------------------------------------------------

class TestDescobrirTools:
    @pytest.mark.asyncio
    async def test_servidor_inexistente_retorna_404(self, client: AsyncClient, auth_headers: dict):
        r = await client.post("/api/mcp-servidores/99999/descobrir-tools", headers=auth_headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_sem_auth_retorna_401(self, client: AsyncClient):
        r = await client.post("/api/mcp-servidores/1/descobrir-tools")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_falha_subprocess_retorna_502(self, client: AsyncClient, auth_headers: dict):
        """Quando o comando MCP não existe, o endpoint retorna 502."""
        from unittest.mock import patch, AsyncMock

        payload = {**_SERVER_PAYLOAD, "command": "comando-que-nao-existe-xyz", "args": []}
        r = await client.post("/api/mcp-servidores", json=payload, headers=auth_headers)
        server_id = r.json()["id"]

        r2 = await client.post(
            f"/api/mcp-servidores/{server_id}/descobrir-tools",
            headers=auth_headers,
        )
        assert r2.status_code == 502


# ---------------------------------------------------------------------------
# GET /api/mcp-servidores/{id}/tools
# ---------------------------------------------------------------------------

class TestListarTools:
    @pytest.mark.asyncio
    async def test_sem_tools_retorna_lista_vazia(self, client: AsyncClient, auth_headers: dict):
        server = await _create_server(client, auth_headers)
        r = await client.get(f"/api/mcp-servidores/{server['id']}/tools", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_sem_auth_retorna_401(self, client: AsyncClient):
        r = await client.get("/api/mcp-servidores/1/tools")
        assert r.status_code == 401
