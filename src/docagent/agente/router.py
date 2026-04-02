from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from docagent.agente.documento_service import DocumentoServiceDep
from docagent.agente.schemas import (
    AgenteCreate,
    AgentePublic,
    AgenteUpdate,
    DocumentoPublic,
    DocumentoUploadResponse,
)
from docagent.agente.services import AgenteServiceDep
from docagent.agent.skills import SKILL_REGISTRY
from docagent.auth.current_user import CurrentOwner, CurrentUser
from docagent.chat.schemas import AgentInfo, SkillInfo
from docagent.dependencies import require_quota

router = APIRouter(
    prefix="/api/agentes",
    tags=["Agentes"],
)

legacy_router = APIRouter(tags=["Agentes"])


@legacy_router.get("/agents", response_model=list[AgentInfo])
async def list_agents(current_user: CurrentUser, service: AgenteServiceDep) -> list[AgentInfo]:
    """Lista agentes ativos do tenant com suas skills."""
    agentes = await service.get_all(tenant_id=current_user.tenant_id, apenas_ativos=True)
    result = []
    for agente in agentes:
        skills = [
            SkillInfo(
                name=SKILL_REGISTRY[name].name,
                label=SKILL_REGISTRY[name].label,
                icon=SKILL_REGISTRY[name].icon,
                description=SKILL_REGISTRY[name].description,
            )
            for name in agente.skill_names
            if name in SKILL_REGISTRY
        ]
        result.append(AgentInfo(
            id=str(agente.id),
            name=agente.nome,
            description=agente.descricao,
            skills=skills,
        ))
    return result


@router.get("/", response_model=list[AgentePublic])
async def list_agentes(current_user: CurrentUser, service: AgenteServiceDep):
    return await service.get_all(tenant_id=current_user.tenant_id)


@router.get("/{agente_id}", response_model=AgentePublic)
async def get_agente(agente_id: int, current_user: CurrentUser, service: AgenteServiceDep):
    agente = await service.get_by_id(agente_id, tenant_id=current_user.tenant_id)
    if not agente:
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
    return agente


@router.post(
    "/",
    response_model=AgentePublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_quota("agentes")],
)
async def create_agente(data: AgenteCreate, current_user: CurrentOwner, service: AgenteServiceDep):
    return await service.create(data, tenant_id=current_user.tenant_id)


@router.put("/{agente_id}", response_model=AgentePublic)
async def update_agente(
    agente_id: int, data: AgenteUpdate, current_user: CurrentOwner, service: AgenteServiceDep
):
    agente = await service.update(agente_id, data, tenant_id=current_user.tenant_id)
    if not agente:
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
    return agente


@router.delete("/{agente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agente(agente_id: int, current_user: CurrentOwner, service: AgenteServiceDep):
    deleted = await service.delete(agente_id, tenant_id=current_user.tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agente nao encontrado")


# --- Documentos ---


@router.get("/{agente_id}/documentos", response_model=list[DocumentoPublic])
async def listar_documentos(
    agente_id: int,
    current_user: CurrentUser,
    service: AgenteServiceDep,
    doc_service: DocumentoServiceDep,
):
    if not await service.get_by_id(agente_id, tenant_id=current_user.tenant_id):
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
    return await doc_service.get_by_agente(agente_id)


@router.post(
    "/{agente_id}/documentos",
    response_model=DocumentoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_quota("documentos")],
)
async def upload_documento(
    agente_id: int,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    service: AgenteServiceDep = None,
    doc_service: DocumentoServiceDep = None,
):
    if not await service.get_by_id(agente_id, tenant_id=current_user.tenant_id):
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
    content = await file.read()
    try:
        doc = await doc_service.create(agente_id, file.filename, content)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return DocumentoUploadResponse(
        id=doc.id,
        agente_id=doc.agente_id,
        filename=doc.filename,
        chunks=doc.chunks,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        collection_id=f"agente_{agente_id}",
    )


@router.delete(
    "/{agente_id}/documentos/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remover_documento(
    agente_id: int,
    doc_id: int,
    current_user: CurrentUser,
    doc_service: DocumentoServiceDep,
    service: AgenteServiceDep,
):
    if not await service.get_by_id(agente_id, tenant_id=current_user.tenant_id):
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
    if not await doc_service.delete(doc_id):
        raise HTTPException(status_code=404, detail="Documento nao encontrado")
