from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from docagent.audit.models import ActorTipo
from docagent.audit.services import AuditService
from docagent.rate_limit import limiter

from docagent.admin.current_admin import CurrentAdmin
from docagent.admin.schemas import AdminCreate, AdminPublic, Token
from docagent.admin.services import AdminServiceDep
from docagent.auth.security import create_access_token, verify_password
from docagent.agente.defaults import AGENTES_PADRAO
from docagent.agente.schemas import AgenteCreate
from docagent.agente.services import AgenteServiceDep
from docagent.assinatura.schemas import AssinaturaPublic
from docagent.assinatura.services import AssinaturaServiceDep
from docagent.database import AsyncDBSession
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
@limiter.limit("5/minute")
async def admin_login(
    request: Request,
    service: AdminServiceDep,
    db: AsyncDBSession,
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

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=admin.id,
        actor_username=admin.username,
        acao="login_admin",
        ip_origem=request.client.host if request.client else None,
    )

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
    current_admin: CurrentAdmin,
    data: TenantCreate,
    db: AsyncDBSession,
    service: TenantServiceDep,
    agente_service: AgenteServiceDep,
):
    tenant = await service.create(data)
    for dados in AGENTES_PADRAO:
        await agente_service.create(AgenteCreate(**dados), tenant_id=tenant.id)

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="criar_tenant",
        recurso_tipo="tenant",
        recurso_id=tenant.id,
        dados_depois={"nome": tenant.nome},
    )

    return tenant


@router.put("/tenants/{tenant_id}", response_model=TenantPublic)
async def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
    service: TenantServiceDep,
):
    tenant = await service.update(tenant_id, data)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="atualizar_tenant",
        recurso_tipo="tenant",
        recurso_id=tenant_id,
        dados_depois=data.model_dump(exclude_none=True),
    )

    return tenant


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: int,
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
    service: TenantServiceDep,
):
    deleted = await service.delete(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="deletar_tenant",
        recurso_tipo="tenant",
        recurso_id=tenant_id,
    )


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
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
    service: UsuarioServiceDep,
):
    existing = await service.get_by_username(data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username já existe")
    create_data = UsuarioCreate(tenant_id=tenant_id, **data.model_dump())
    usuario = await service.create(create_data)

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="criar_usuario",
        tenant_id=tenant_id,
        recurso_tipo="usuario",
        recurso_id=usuario.id,
        dados_depois={"username": usuario.username, "email": usuario.email},
    )

    return usuario


@router.put("/usuarios/{usuario_id}", response_model=UsuarioPublic)
async def update_usuario(
    usuario_id: int,
    data: UsuarioUpdate,
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
    service: UsuarioServiceDep,
):
    usuario = await service.update(usuario_id, data)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="atualizar_usuario",
        recurso_tipo="usuario",
        recurso_id=usuario_id,
        dados_depois=data.model_dump(exclude_none=True),
    )

    return usuario


@router.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_usuario(
    usuario_id: int,
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
    service: UsuarioServiceDep,
):
    deleted = await service.delete(usuario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="deletar_usuario",
        recurso_tipo="usuario",
        recurso_id=usuario_id,
    )


# ─── System Config ────────────────────────────────────────────────────────────

@router.get("/system-config")
async def get_system_config(_: CurrentAdmin, svc: SystemConfigServiceDep):
    return await svc.get_all()


@router.put("/system-config")
async def update_system_config(
    data: dict,
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
    svc: SystemConfigServiceDep,
):
    for key, value in data.items():
        await svc.set(key, str(value) if value is not None else None)

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="atualizar_system_config",
        dados_depois=data,
    )

    return await svc.get_all()


# ─── Planos ───────────────────────────────────────────────────────────────────

@router.get("/planos", response_model=list[PlanoPublic])
async def list_planos(_: CurrentAdmin, service: PlanoServiceDep):
    return await service.get_all()


@router.post("/planos", response_model=PlanoPublic, status_code=status.HTTP_201_CREATED)
async def create_plano(
    current_admin: CurrentAdmin,
    data: PlanoCreate,
    db: AsyncDBSession,
    service: PlanoServiceDep,
):
    plano = await service.create(data)

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="criar_plano",
        recurso_tipo="plano",
        recurso_id=plano.id,
        dados_depois={"nome": plano.nome},
    )

    return plano


@router.put("/planos/{plano_id}", response_model=PlanoPublic)
async def update_plano(
    plano_id: int,
    data: PlanoUpdate,
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
    service: PlanoServiceDep,
):
    plano = await service.update(plano_id, data)
    if not plano:
        raise HTTPException(status_code=404, detail="Plano não encontrado")

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="atualizar_plano",
        recurso_tipo="plano",
        recurso_id=plano_id,
        dados_depois=data.model_dump(exclude_none=True),
    )

    return plano


@router.delete("/planos/{plano_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plano(
    plano_id: int,
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
    service: PlanoServiceDep,
):
    deleted = await service.delete(plano_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plano não encontrado")

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="deletar_plano",
        recurso_tipo="plano",
        recurso_id=plano_id,
    )


# ─── Assinaturas (admin) ──────────────────────────────────────────────────────

@router.get("/assinaturas", response_model=list[AssinaturaPublic])
async def list_assinaturas(_: CurrentAdmin, service: AssinaturaServiceDep):
    assinaturas = await service.get_all()
    return [AssinaturaPublic.from_orm_with_plano(a) for a in assinaturas]


@router.post("/tenants/{tenant_id}/assinatura", response_model=AssinaturaPublic, status_code=status.HTTP_201_CREATED)
async def assign_assinatura(
    tenant_id: int,
    data: dict,
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
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

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="atribuir_assinatura",
        tenant_id=tenant_id,
        recurso_tipo="assinatura",
        recurso_id=assinatura.id,
        dados_depois={"plano_id": plano_id},
    )

    return AssinaturaPublic.from_orm_with_plano(assinatura)


# ─── Admin management ────────────────────────────────────────────────────────

@router.post("/admins", response_model=AdminPublic, status_code=status.HTTP_201_CREATED)
async def create_admin(
    data: AdminCreate,
    current_admin: CurrentAdmin,
    db: AsyncDBSession,
    service: AdminServiceDep,
):
    existing = await service.get_by_username(data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username já existe")
    novo_admin = await service.create(data)

    await AuditService.registrar(
        db,
        actor_tipo=ActorTipo.ADMIN,
        actor_id=current_admin.id,
        actor_username=current_admin.username,
        acao="criar_admin",
        recurso_tipo="admin",
        recurso_id=novo_admin.id,
        dados_depois={"username": novo_admin.username},
    )

    return novo_admin
