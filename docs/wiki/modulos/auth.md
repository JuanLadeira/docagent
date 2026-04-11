# Módulo: auth/

**Path:** `src/docagent/auth/`
**Fase:** 8

---

## JWT Dual

Dois tipos de token com `sub` diferente:

| Tipo | `sub` | Endpoints |
|------|-------|-----------|
| User | `username` | `/chat`, `/api/*` |
| Admin | `admin:username` | `/sys-mgmt/*`, `/api/admin/*` |

`current_user` dependency detecta pelo prefixo `admin:` e rejeita tokens de admin em rotas de user e vice-versa.

Ver [decisao: jwt-dual](../decisoes/jwt-dual.md).

---

## Dependências FastAPI

```python
get_current_user   # → Usuario ORM (user token)
get_current_admin  # → AdminUser (admin token)
require_owner      # → Usuario com role=OWNER
```

---

## Roles

```python
class UsuarioRole(str, Enum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"
```

- **OWNER:** acesso total ao tenant (configurações, agentes, WhatsApp, etc.)
- **MEMBER:** acesso limitado (chat, atendimentos)

---

## Segurança Pendente (Fase 21)

- [ ] Rate limiting com `slowapi` nos endpoints críticos
- [ ] Fernet encryption para `llm_api_key`, `elevenlabs_api_key`, `bot_token`
- [ ] TOTP 2FA para admin
- [ ] `audit_log` de ações administrativas
- [ ] Validação de origem dos webhooks WhatsApp/Telegram
- [ ] `rate limiting` backend Redis (quando escalar — Fase 23)
