from contextlib import AsyncExitStack
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from docagent.database import AsyncDBSession
from docagent.mcp_server.models import McpServer, McpTool
from docagent.mcp_server.schemas import McpServerCreate, McpServerUpdate


class McpServerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[McpServer]:
        result = await self.session.execute(
            select(McpServer).options(selectinload(McpServer.tools)).order_by(McpServer.id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, server_id: int) -> McpServer | None:
        result = await self.session.execute(
            select(McpServer)
            .options(selectinload(McpServer.tools))
            .where(McpServer.id == server_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: McpServerCreate) -> McpServer:
        server = McpServer(**data.model_dump())
        self.session.add(server)
        await self.session.flush()
        await self.session.refresh(server, ["tools"])
        return server

    async def update(self, server_id: int, data: McpServerUpdate) -> McpServer | None:
        server = await self.get_by_id(server_id)
        if not server:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(server, field, value)
        await self.session.flush()
        await self.session.refresh(server, ["tools"])
        return server

    async def delete(self, server_id: int) -> bool:
        server = await self.get_by_id(server_id)
        if not server:
            return False
        await self.session.delete(server)
        await self.session.flush()
        return True

    async def descobrir_tools(self, server_id: int) -> list[McpTool]:
        """Conecta ao servidor MCP via stdio, descobre as tools e persiste no banco."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server = await self.get_by_id(server_id)
        if not server:
            raise ValueError(f"Servidor MCP {server_id} não encontrado")

        params = StdioServerParameters(
            command=server.command,
            args=server.args,
            env=server.env or None,
        )

        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(params))
            mcp_session = await stack.enter_async_context(ClientSession(read, write))
            await mcp_session.initialize()
            response = await mcp_session.list_tools()

        # Apaga tools antigas e substitui pelas descobertas
        await self.session.execute(
            select(McpTool).where(McpTool.server_id == server_id)
        )
        for tool in server.tools:
            await self.session.delete(tool)
        await self.session.flush()

        novas_tools = []
        for tool in response.tools:
            mt = McpTool(
                server_id=server_id,
                tool_name=tool.name,
                description=tool.description or "",
            )
            self.session.add(mt)
            novas_tools.append(mt)

        await self.session.flush()
        return novas_tools

    async def get_tools(self, server_id: int) -> list[McpTool]:
        result = await self.session.execute(
            select(McpTool).where(McpTool.server_id == server_id)
        )
        return list(result.scalars().all())


def get_mcp_service(session: AsyncDBSession) -> McpServerService:
    return McpServerService(session)


McpServiceDep = Annotated[McpServerService, Depends(get_mcp_service)]


async def load_mcp_tools_for_skills(
    skill_names: list[str],
    servers: list[McpServer],
    stack: AsyncExitStack,
) -> list:
    """
    Carrega as tools MCP necessárias para os skill_names que começam com 'mcp:'.
    Os subprocessos são mantidos vivos dentro do stack fornecido pelo caller.
    Retorna lista de LangChain tools prontas para uso no agente.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain_mcp_adapters.tools import load_mcp_tools

    # Agrupa tool_names por server_id
    by_server: dict[str, list[str]] = {}
    for name in skill_names:
        if not name.startswith("mcp:"):
            continue
        parts = name.split(":", 2)
        if len(parts) != 3:
            continue
        _, sid, tool_name = parts
        by_server.setdefault(sid, []).append(tool_name)

    tools = []
    for sid, tool_names in by_server.items():
        server = next((s for s in servers if str(s.id) == sid), None)
        if not server or not server.ativo:
            continue
        params = StdioServerParameters(
            command=server.command,
            args=server.args,
            env=server.env or None,
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        mcp_session = await stack.enter_async_context(ClientSession(read, write))
        await mcp_session.initialize()
        all_tools = await load_mcp_tools(mcp_session)
        tools += [t for t in all_tools if t.name in tool_names]

    return tools
