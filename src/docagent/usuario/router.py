from fastapi import APIRouter, HTTPException, status

from docagent.auth.current_user import CurrentOwner, CurrentUser
from docagent.usuario.schemas import UsuarioCreate, UsuarioPublic, UsuarioUpdate
from docagent.usuario.services import UsuarioServiceDep

router = APIRouter(
    prefix="/api/usuarios",
    tags=["Usuarios"],
    responses={404: {"description": "Nao encontrado"}},
)


@router.get("/me", response_model=UsuarioPublic)
async def get_me(current_user: CurrentUser):
    return current_user


@router.get("/", response_model=list[UsuarioPublic])
async def list_usuarios(current_user: CurrentUser, service: UsuarioServiceDep):
    return await service.get_all(tenant_id=current_user.tenant_id)


@router.get("/{usuario_id}", response_model=UsuarioPublic)
async def get_usuario(
    usuario_id: int,
    current_user: CurrentUser,
    service: UsuarioServiceDep,
):
    usuario = await service.get_by_id(usuario_id)
    if not usuario or usuario.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return usuario


@router.post("/", response_model=UsuarioPublic, status_code=status.HTTP_201_CREATED)
async def create_usuario(data: UsuarioCreate, _: CurrentOwner, service: UsuarioServiceDep):
    existing = await service.get_by_username(data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username ja existe")

    existing = await service.get_by_email(data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email ja existe")

    return await service.create(data)


@router.put("/{usuario_id}", response_model=UsuarioPublic)
async def update_usuario(
    usuario_id: int,
    data: UsuarioUpdate,
    current_user: CurrentOwner,
    service: UsuarioServiceDep,
):
    usuario = await service.get_by_id(usuario_id)
    if not usuario or usuario.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    updated = await service.update(usuario_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return updated


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_usuario(
    usuario_id: int,
    current_user: CurrentOwner,
    service: UsuarioServiceDep,
):
    usuario = await service.get_by_id(usuario_id)
    if not usuario or usuario.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    deleted = await service.delete(usuario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
