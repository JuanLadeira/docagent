from fastapi import APIRouter, HTTPException

from docagent.auth.current_user import CurrentUser
from docagent.tenant.schemas import TenantLlmConfigUpdate, TenantPublic
from docagent.tenant.services import TenantServiceDep
from docagent.usuario.models import UsuarioRole

router = APIRouter(
    prefix="/api/tenants",
    tags=["Tenants"],
    responses={404: {"description": "Nao encontrado"}},
)

# Nota: CRUD completo de tenants (criar, listar, editar, deletar) está protegido
# em /api/admin/tenants/* com autenticação de admin.
# Este router expõe apenas operações do próprio tenant autenticado.


# ── Configuração de LLM pelo tenant owner ─────────────────────────────────────

class _LlmConfigResponse(TenantLlmConfigUpdate):
    llm_api_key_set: bool = False
    llm_api_key: str | None = None  # nunca retorna o valor real


@router.get("/me/llm-config")
async def get_my_llm_config(current_user: CurrentUser, service: TenantServiceDep):
    """Retorna a configuração LLM do tenant atual (owner apenas)."""
    if current_user.role != UsuarioRole.OWNER:
        raise HTTPException(status_code=403, detail="Apenas owners podem acessar esta configuração")
    tenant = await service.get_by_id(current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return {
        "llm_provider": tenant.llm_provider,
        "llm_model": tenant.llm_model,
        "llm_api_key": None,
        "llm_api_key_set": bool(tenant.llm_api_key),
    }


@router.put("/me/llm-config")
async def update_my_llm_config(
    data: TenantLlmConfigUpdate,
    current_user: CurrentUser,
    service: TenantServiceDep,
):
    """Atualiza a configuração LLM do tenant atual (owner apenas)."""
    if current_user.role != UsuarioRole.OWNER:
        raise HTTPException(status_code=403, detail="Apenas owners podem alterar esta configuração")
    tenant = await service.get_by_id(current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    await service.update_llm_config(tenant, data)
    return {
        "llm_provider": tenant.llm_provider,
        "llm_model": tenant.llm_model,
        "llm_api_key": None,
        "llm_api_key_set": bool(tenant.llm_api_key),
    }
