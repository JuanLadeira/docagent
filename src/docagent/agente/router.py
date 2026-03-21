from fastapi import APIRouter, HTTPException, status

from docagent.agente.schemas import AgenteCreate, AgentePublic, AgenteUpdate
from docagent.agente.services import AgenteServiceDep
from docagent.auth.current_user import CurrentOwner, CurrentUser

router = APIRouter(
    prefix="/api/agentes",
    tags=["Agentes"],
)


@router.get("/", response_model=list[AgentePublic])
async def list_agentes(_: CurrentUser, service: AgenteServiceDep):
    return await service.get_all()


@router.get("/{agente_id}", response_model=AgentePublic)
async def get_agente(agente_id: int, _: CurrentUser, service: AgenteServiceDep):
    agente = await service.get_by_id(agente_id)
    if not agente:
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
    return agente


@router.post("/", response_model=AgentePublic, status_code=status.HTTP_201_CREATED)
async def create_agente(data: AgenteCreate, _: CurrentOwner, service: AgenteServiceDep):
    return await service.create(data)


@router.put("/{agente_id}", response_model=AgentePublic)
async def update_agente(
    agente_id: int, data: AgenteUpdate, _: CurrentOwner, service: AgenteServiceDep
):
    agente = await service.update(agente_id, data)
    if not agente:
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
    return agente


@router.delete("/{agente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agente(agente_id: int, _: CurrentOwner, service: AgenteServiceDep):
    deleted = await service.delete(agente_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agente nao encontrado")
