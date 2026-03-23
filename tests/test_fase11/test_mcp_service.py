"""
Testes unitários para McpServerService (mcp_server/services.py).

Valida CRUD e a função load_mcp_tools_for_skills sem subir subprocessos MCP.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import AsyncExitStack
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from docagent.database import Base
from docagent.mcp_server.models import McpServer, McpTool
from docagent.mcp_server.schemas import McpServerCreate, McpServerUpdate
from docagent.mcp_server.services import McpServerService, load_mcp_tools_for_skills

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        async with s.begin():
            yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def service(session):
    return McpServerService(session)


@pytest_asyncio.fixture
async def servidor_base(service):
    data = McpServerCreate(
        nome="Filesystem",
        descricao="Acesso a arquivos",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        env={},
        ativo=True,
    )
    return await service.create(data)


# ---------------------------------------------------------------------------
# CRUD — create
# ---------------------------------------------------------------------------

class TestMcpServerCreate:
    @pytest.mark.asyncio
    async def test_create_returns_server(self, service):
        data = McpServerCreate(
            nome="Teste", descricao="desc", command="npx", args=[], env={}, ativo=True
        )
        server = await service.create(data)
        assert server.id is not None

    @pytest.mark.asyncio
    async def test_create_persists_nome(self, service):
        data = McpServerCreate(
            nome="Meu Servidor", descricao="", command="python", args=[], env={}, ativo=True
        )
        server = await service.create(data)
        assert server.nome == "Meu Servidor"

    @pytest.mark.asyncio
    async def test_create_persists_command_and_args(self, service):
        data = McpServerCreate(
            nome="X", descricao="", command="uv", args=["run", "server.py"], env={}, ativo=True
        )
        server = await service.create(data)
        assert server.command == "uv"
        assert server.args == ["run", "server.py"]

    @pytest.mark.asyncio
    async def test_create_starts_with_empty_tools(self, service):
        data = McpServerCreate(
            nome="X", descricao="", command="npx", args=[], env={}, ativo=True
        )
        server = await service.create(data)
        assert server.tools == []


# ---------------------------------------------------------------------------
# CRUD — get_all / get_by_id
# ---------------------------------------------------------------------------

class TestMcpServerRead:
    @pytest.mark.asyncio
    async def test_get_all_returns_list(self, service):
        result = await service.get_all()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_all_includes_created_server(self, service, servidor_base):
        all_servers = await service.get_all()
        ids = [s.id for s in all_servers]
        assert servidor_base.id in ids

    @pytest.mark.asyncio
    async def test_get_by_id_returns_server(self, service, servidor_base):
        found = await service.get_by_id(servidor_base.id)
        assert found is not None
        assert found.id == servidor_base.id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_missing(self, service):
        found = await service.get_by_id(99999)
        assert found is None


# ---------------------------------------------------------------------------
# CRUD — update
# ---------------------------------------------------------------------------

class TestMcpServerUpdate:
    @pytest.mark.asyncio
    async def test_update_changes_nome(self, service, servidor_base):
        updated = await service.update(servidor_base.id, McpServerUpdate(nome="Novo Nome"))
        assert updated.nome == "Novo Nome"

    @pytest.mark.asyncio
    async def test_update_returns_none_for_missing(self, service):
        result = await service.update(99999, McpServerUpdate(nome="X"))
        assert result is None

    @pytest.mark.asyncio
    async def test_update_partial_keeps_other_fields(self, service, servidor_base):
        original_command = servidor_base.command
        await service.update(servidor_base.id, McpServerUpdate(nome="Alterado"))
        found = await service.get_by_id(servidor_base.id)
        assert found.command == original_command


# ---------------------------------------------------------------------------
# CRUD — delete
# ---------------------------------------------------------------------------

class TestMcpServerDelete:
    @pytest.mark.asyncio
    async def test_delete_returns_true(self, service, servidor_base):
        result = await service.delete(servidor_base.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_removes_server(self, service, servidor_base):
        await service.delete(servidor_base.id)
        found = await service.get_by_id(servidor_base.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_missing(self, service):
        result = await service.delete(99999)
        assert result is False


# ---------------------------------------------------------------------------
# load_mcp_tools_for_skills — sem subprocesso real
# ---------------------------------------------------------------------------

def _make_mock_server(server_id: int, tool_names: list[str]) -> McpServer:
    server = MagicMock(spec=McpServer)
    server.id = server_id
    server.command = "npx"
    server.args = []
    server.env = {}
    server.ativo = True
    return server


def _make_mock_lc_tool(name: str):
    tool = MagicMock()
    tool.name = name
    return tool


class TestLoadMcpToolsForSkills:
    @pytest.mark.asyncio
    async def test_returns_empty_for_no_mcp_skills(self):
        async with AsyncExitStack() as stack:
            tools = await load_mcp_tools_for_skills(["rag_search", "web_search"], [], stack)
        assert tools == []

    @pytest.mark.asyncio
    async def test_ignores_non_mcp_skills(self):
        async with AsyncExitStack() as stack:
            tools = await load_mcp_tools_for_skills(["rag_search"], [], stack)
        assert tools == []

    @pytest.mark.asyncio
    async def test_skips_inactive_server(self):
        server = _make_mock_server(1, ["read_file"])
        server.ativo = False

        async with AsyncExitStack() as stack:
            tools = await load_mcp_tools_for_skills(["mcp:1:read_file"], [server], stack)

        assert tools == []

    @pytest.mark.asyncio
    async def test_skips_unknown_server_id(self):
        async with AsyncExitStack() as stack:
            tools = await load_mcp_tools_for_skills(["mcp:999:read_file"], [], stack)
        assert tools == []

    @pytest.mark.asyncio
    async def test_filters_to_requested_tools_only(self):
        server = _make_mock_server(1, [])
        lc_read = _make_mock_lc_tool("read_file")
        lc_write = _make_mock_lc_tool("write_file")

        mock_session = AsyncMock()

        with (
            patch("mcp.client.stdio.stdio_client") as mock_stdio,
            patch("mcp.ClientSession") as mock_client_session,
            patch("langchain_mcp_adapters.tools.load_mcp_tools", return_value=[lc_read, lc_write]),
        ):
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_client_session.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session.initialize = AsyncMock()

            async with AsyncExitStack() as stack:
                tools = await load_mcp_tools_for_skills(
                    ["mcp:1:read_file"],  # apenas read_file, não write_file
                    [server],
                    stack,
                )

        assert len(tools) == 1
        assert tools[0].name == "read_file"

    @pytest.mark.asyncio
    async def test_returns_all_requested_tools_from_server(self):
        server = _make_mock_server(1, [])
        lc_read = _make_mock_lc_tool("read_file")
        lc_write = _make_mock_lc_tool("write_file")

        mock_session = AsyncMock()

        with (
            patch("mcp.client.stdio.stdio_client") as mock_stdio,
            patch("mcp.ClientSession") as mock_client_session,
            patch("langchain_mcp_adapters.tools.load_mcp_tools", return_value=[lc_read, lc_write]),
        ):
            mock_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
            mock_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_client_session.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session.initialize = AsyncMock()

            async with AsyncExitStack() as stack:
                tools = await load_mcp_tools_for_skills(
                    ["mcp:1:read_file", "mcp:1:write_file"],
                    [server],
                    stack,
                )

        assert len(tools) == 2
