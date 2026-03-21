from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from docagent.admin.current_admin import CurrentAdmin
from docagent.admin.schemas import AdminCreate, AdminPublic, Token
from docagent.admin.services import AdminServiceDep
from docagent.auth.security import create_access_token, verify_password
from docagent.tenant.schemas import TenantCreate, TenantPublic, TenantUpdate
from docagent.tenant.services import TenantServiceDep
from docagent.usuario.schemas import UsuarioCreate, UsuarioCreateAdmin, UsuarioPublic, UsuarioUpdate
from docagent.usuario.services import UsuarioServiceDep

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
)


@router.post("/login", response_model=Token)
async def admin_login(
    service: AdminServiceDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    admin = await service.get_by_username(form_data.username)
    if not admin or not verify_password(form_data.password, admin.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not admin.ativo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin inativo")

    access_token = create_access_token(data={"sub": f"admin:{admin.username}"})
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=AdminPublic)
async def admin_me(current_admin: CurrentAdmin):
    return current_admin


# ─── Tenants ──────────────────────────────────────────────────────────────────

@router.get("/tenants", response_model=list[TenantPublic])
async def list_tenants(_: CurrentAdmin, service: TenantServiceDep):
    return await service.get_all()


@router.post("/tenants", response_model=TenantPublic, status_code=status.HTTP_201_CREATED)
async def create_tenant(_: CurrentAdmin, data: TenantCreate, service: TenantServiceDep):
    return await service.create(data)


@router.put("/tenants/{tenant_id}", response_model=TenantPublic)
async def update_tenant(
    tenant_id: int, data: TenantUpdate, _: CurrentAdmin, service: TenantServiceDep
):
    tenant = await service.update(tenant_id, data)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: int, _: CurrentAdmin, service: TenantServiceDep):
    deleted = await service.delete(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")


# ─── Tenant → Usuários ────────────────────────────────────────────────────────

@router.get("/tenants/{tenant_id}/usuarios", response_model=list[UsuarioPublic])
async def list_tenant_usuarios(
    tenant_id: int, _: CurrentAdmin, service: UsuarioServiceDep
):
    return await service.get_all(tenant_id=tenant_id)


@router.post(
    "/tenants/{tenant_id}/usuarios",
    response_model=UsuarioPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_tenant_usuario(
    tenant_id: int,
    data: UsuarioCreateAdmin,
    _: CurrentAdmin,
    service: UsuarioServiceDep,
):
    existing = await service.get_by_username(data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username já existe")
    create_data = UsuarioCreate(tenant_id=tenant_id, **data.model_dump())
    return await service.create(create_data)


@router.put("/usuarios/{usuario_id}", response_model=UsuarioPublic)
async def update_usuario(
    usuario_id: int, data: UsuarioUpdate, _: CurrentAdmin, service: UsuarioServiceDep
):
    usuario = await service.update(usuario_id, data)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return usuario


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_usuario(usuario_id: int, _: CurrentAdmin, service: UsuarioServiceDep):
    deleted = await service.delete(usuario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")


# ─── Admin management (bootstrap) ────────────────────────────────────────────

@router.post("/admins", response_model=AdminPublic, status_code=status.HTTP_201_CREATED)
async def create_admin(
    data: AdminCreate, _: CurrentAdmin, service: AdminServiceDep
):
    existing = await service.get_by_username(data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username já existe")
    return await service.create(data)
