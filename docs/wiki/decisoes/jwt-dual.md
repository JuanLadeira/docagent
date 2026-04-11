---
name: jwt-dual
description: Sistema JWT com dois tipos de token distinguidos pelo prefixo "admin:" no campo sub
type: project
---

# Decisão: JWT Dual (user vs admin)

**Regra:** Tokens de usuário têm `sub=username`. Tokens de admin têm `sub=admin:username`. A dependency `current_user` rejeita tokens admin; `current_admin` rejeita tokens user.

**Why:** A separação foi necessária para ter endpoints `/sys-mgmt/*` e `/api/admin/*` completamente isolados dos endpoints de usuário regular, sem depender de roles no banco. O admin pode gerenciar todos os tenants; o user só acessa o seu tenant. Ter o prefixo no `sub` permite distinguir sem round-trip ao banco para checar role.

**How to apply:** Nunca usar o token de admin para testar endpoints de usuário e vice-versa. Ao escrever testes, usar `login_admin()` para admin e `login_user()` para user — eles geram tokens diferentes.
