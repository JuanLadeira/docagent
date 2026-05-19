# Decisão: Todo endpoint com ID de recurso deve verificar tenant_id

**Fase:** 21 (pentest + correção)
**Data:** 2026-04-12

---

## Problema

Durante o pentest interno, foram encontrados endpoints que recebiam IDs de recursos (usuários, documentos, etc.) sem verificar se o recurso pertencia ao tenant do usuário autenticado. Isso resultava em vulnerabilidades IDOR (Insecure Direct Object Reference).

## Regra

Todo endpoint que recebe um ID de recurso (usuário, agente, documento, atendimento, instância, etc.) **deve** verificar que o recurso pertence ao `current_user.tenant_id`.

**Padrão correto:**
```python
async def get_usuario(usuario_id: int, current_user: CurrentUser, service: UsuarioServiceDep):
    usuario = await service.get_by_id(usuario_id)
    if not usuario or usuario.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")  # 404, não 403
    return usuario
```

**Por que 404 e não 403?** Retornar 403 confirmaria que o recurso existe mas não pertence ao usuário. Retornar 404 não revela informação sobre a existência do recurso.

## Recursos com verificação de tenant

Para serviços que fazem a query diretamente com `tenant_id` no WHERE (ex: `AgentService.get_by_id(id, tenant_id=...)`), a verificação já está embutida. Para serviços que retornam o objeto sem filtro, a verificação deve ser feita no router.

## Vulnerabilidades encontradas e corrigidas

- `usuario/router.py`: GET e PUT sem verificação de tenant (2026-04-12)
- `agente/documento_service.py`: DELETE sem verificar que doc pertence ao agente (2026-04-12)
- `tenant/router.py`: CRUD completamente público sem autenticação (2026-04-12)
