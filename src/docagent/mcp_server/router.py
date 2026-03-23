from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload

from docagent.auth.current_user import CurrentOwner, CurrentUser
from docagent.mcp_server.schemas import (
    McpServerCreate,
    McpServerPublic,
    McpServerUpdate,
    McpToolPublic,
)
from docagent.mcp_server.services import McpServiceDep

router = APIRouter(prefix="/api/mcp-servidores", tags=["MCP"])


@router.get("", response_model=list[McpServerPublic])
async def listar_servidores(
    current_user: CurrentUser,
    service: McpServiceDep,
):
    return await service.get_all()


@router.post("", response_model=McpServerPublic, status_code=status.HTTP_201_CREATED)
async def criar_servidor(
    data: McpServerCreate,
    current_user: CurrentOwner,
    service: McpServiceDep,
):
    return await service.create(data)


@router.put("/{server_id}", response_model=McpServerPublic)
async def atualizar_servidor(
    server_id: int,
    data: McpServerUpdate,
    current_user: CurrentOwner,
    service: McpServiceDep,
):
    server = await service.update(server_id, data)
    if not server:
        raise HTTPException(status_code=404, detail="Servidor MCP não encontrado")
    return server


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_servidor(
    server_id: int,
    current_user: CurrentOwner,
    service: McpServiceDep,
):
    deleted = await service.delete(server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Servidor MCP não encontrado")


@router.post("/{server_id}/descobrir-tools", response_model=list[McpToolPublic])
async def descobrir_tools(
    server_id: int,
    current_user: CurrentOwner,
    service: McpServiceDep,
):
    try:
        tools = await service.descobrir_tools(server_id)
        return tools
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao conectar ao servidor MCP: {e}",
        )


@router.get("/{server_id}/tools", response_model=list[McpToolPublic])
async def listar_tools(
    server_id: int,
    current_user: CurrentUser,
    service: McpServiceDep,
):
    return await service.get_tools(server_id)
