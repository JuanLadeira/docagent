from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from docagent.admin.current_admin import CurrentAdmin
from docagent.admin.schemas import AdminCreate, AdminPublic, Token
from docagent.admin.services import AdminServiceDep
from docagent.auth.security import create_access_token, verify_password
from docagent.agente.defaults import AGENTES_PADRAO
from docagent.agente.schemas import AgenteCreate
from docagent.agente.services import AgenteServiceDep
from docagent.assinatura.schemas import AssinaturaPublic
from docagent.assinatura.services import AssinaturaServiceDep
from docagent.plano.schemas import PlanoCreate, PlanoPublic, PlanoUpdate
from docagent.plano.services import PlanoServiceDep
from docagent.system_config.services import SystemConfigServiceDep, LLM_MODE_KEY
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
async def create_tenant(
    _: CurrentAdmin,
    data: TenantCreate,
    service: TenantServiceDep,
    agente_service: AgenteServiceDep,
):
    tenant = await service.create(data)
    for dados in AGENTES_PADRAO:
        await agente_service.create(AgenteCreate(**dados), tenant_id=tenant.id)
    return tenant


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


# ─── System Config ────────────────────────────────────────────────────────────

@router.get("/system-config")
async def get_system_config(_: CurrentAdmin, svc: SystemConfigServiceDep):
    """Retorna as configurações globais do sistema."""
    return await svc.get_all()


@router.put("/system-config")
async def update_system_config(
    data: dict,
    _: CurrentAdmin,
    svc: SystemConfigServiceDep,
):
    """Atualiza configurações globais do sistema (chave-valor)."""
    for key, value in data.items():
        await svc.set(key, str(value) if value is not None else None)
    return await svc.get_all()


# ─── Planos ───────────────────────────────────────────────────────────────────

@router.get("/planos", response_model=list[PlanoPublic])
async def list_planos(_: CurrentAdmin, service: PlanoServiceDep):
    return await service.get_all()


@router.post("/planos", response_model=PlanoPublic, status_code=status.HTTP_201_CREATED)
async def create_plano(_: CurrentAdmin, data: PlanoCreate, service: PlanoServiceDep):
    return await service.create(data)


@router.put("/planos/{plano_id}", response_model=PlanoPublic)
async def update_plano(plano_id: int, data: PlanoUpdate, _: CurrentAdmin, service: PlanoServiceDep):
    plano = await service.update(plano_id, data)
    if not plano:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return plano


@router.delete("/planos/{plano_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plano(plano_id: int, _: CurrentAdmin, service: PlanoServiceDep):
    deleted = await service.delete(plano_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plano não encontrado")


# ─── Assinaturas (admin) ──────────────────────────────────────────────────────

@router.get("/assinaturas", response_model=list[AssinaturaPublic])
async def list_assinaturas(_: CurrentAdmin, service: AssinaturaServiceDep):
    assinaturas = await service.get_all()
    return [AssinaturaPublic.from_orm_with_plano(a) for a in assinaturas]


@router.post("/tenants/{tenant_id}/assinatura", response_model=AssinaturaPublic, status_code=status.HTTP_201_CREATED)
async def assign_assinatura(
    tenant_id: int,
    data: dict,
    _: CurrentAdmin,
    service: AssinaturaServiceDep,
    tenant_service: TenantServiceDep,
    plano_service: PlanoServiceDep,
):
    tenant = await tenant_service.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    plano_id = data.get("plano_id")
    if not plano_id:
        raise HTTPException(status_code=422, detail="plano_id é obrigatório")
    plano = await plano_service.get_by_id(plano_id)
    if not plano:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    assinatura = await service.criar(tenant_id, plano_id)
    return AssinaturaPublic.from_orm_with_plano(assinatura)


# ─── Admin management (bootstrap) ────────────────────────────────────────────

@router.post("/admins", response_model=AdminPublic, status_code=status.HTTP_201_CREATED)
async def create_admin(
    data: AdminCreate, _: CurrentAdmin, service: AdminServiceDep
):
    existing = await service.get_by_username(data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username já existe")
    return await service.create(data)
