# Fase Keycloak — Auth Híbrida + MCP Token Forwarding

**Data:** 2026-05-18  
**Status:** Aprovado  
**Pré-requisito:** Fase 23 mergeada (Redis disponível no stack)

---

## Objetivo

Adicionar Keycloak como provedor OIDC opcional ao lado da auth local existente. Usuários podem logar via Keycloak SSO; o token Keycloak é reutilizado para autenticar MCP servers (SSE e stdio) que exijam a mesma identidade.

---

## Escopo

- Auth híbrida: login local (username/senha) + login Keycloak coexistem sem conflito
- Toda middleware de auth existente permanece intacta
- MCP servers ganham campo `auth_type` (none | static | keycloak)
- Token forwarding dinâmico: backend busca access_token Keycloak fresco do Redis ao conectar MCP
- Keycloak sobe via docker-compose com realm pré-configurado (dev)
- Identidade: email do JWT Keycloak → busca usuário local; cria se não existir

---

## Fora do escopo

- Substituição da auth local por Keycloak (migração completa)
- PKCE flow no frontend (fica para evolução futura)
- Multi-realm por tenant (um realm global para todos os tenants nesta fase)

---

## Arquitetura

### Fluxo de login Keycloak

```
Frontend                  Backend                    Keycloak
   │                         │                           │
   │  clica "Entrar com KC"  │                           │
   │──────────────────────→  │                           │
   │  GET /auth/keycloak/login                           │
   │  ←── redirect 302 ──────│                           │
   │                         │                           │
   │  ──── redirect ─────────────────────────────────→  │
   │  ←── code + state ──────────────────────────────── │
   │                         │                           │
   │  GET /auth/keycloak/callback?code=...&state=...     │
   │──────────────────────→  │                           │
   │                         │── POST /token (code) ──→ │
   │                         │← access_token + rt ───── │
   │                         │                           │
   │                         │ valida JWT via JWKS       │
   │                         │ cria/linka usuário        │
   │                         │ salva rt no Redis         │
   │                         │ emite docagent JWT        │
   │  ←── redirect + JWT ────│                           │
   │  (frontend armazena)    │                           │
```

A partir daqui o frontend usa o JWT docagent normalmente. Nenhum endpoint existente precisa mudar.

### Token forwarding para MCP

```
POST /chat (com current_user)
  └─ load_mcp_tools_for_skills(skill_names, servers, stack, usuario_id, redis)
       └─ para cada server com auth_type="keycloak":
            KeycloakService.get_access_token(usuario_id, redis)
              └─ Redis.get("keycloak:rt:{usuario_id}")
              └─ POST Keycloak /token (grant_type=refresh_token)
              └─ retorna access_token fresco
            injeta como header Authorization: Bearer <token>   (SSE)
            injeta como env KEYCLOAK_TOKEN=<token>             (stdio)
```

---

## Banco de dados

### Migração: `usuario`

```python
keycloak_sub: Mapped[str | None] = mapped_column(
    String(255), nullable=True, unique=True, index=True
)
```

### Migração: `mcp_server`

```python
auth_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="none")
# "none"     → sem auth extra
# "static"   → usa env["Authorization"] (comportamento anterior, retrocompatível)
# "keycloak" → forwarda token Keycloak do usuário atual
```

O campo `env["Authorization"]` existente continua funcionando para `auth_type="static"`. Servidores criados antes desta fase ficam com `auth_type="none"` por padrão — o admin atualiza se quiser.

---

## Módulos novos

### `src/docagent/keycloak/`

```
keycloak/
├── __init__.py
├── client.py      # KeycloakClient: HTTP calls para Keycloak
├── router.py      # endpoints /auth/keycloak/*
└── service.py     # criar_ou_linkar_usuario(), get_access_token()
```

**`client.py`**
```python
class KeycloakClient:
    def __init__(self, url, realm, client_id, client_secret): ...

    async def exchange_code(self, code, redirect_uri) -> dict:
        # POST {url}/realms/{realm}/protocol/openid-connect/token
        # grant_type=authorization_code

    async def refresh(self, refresh_token) -> dict:
        # POST {url}/realms/{realm}/protocol/openid-connect/token
        # grant_type=refresh_token

    async def get_jwks(self) -> dict:
        # GET {url}/realms/{realm}/protocol/openid-connect/certs
        # cached localmente por 10 minutos (TTLCache)

    def validate_jwt(self, token: str) -> dict:
        # verifica assinatura via JWKS em cache
        # retorna claims: sub, email, name
```

**`service.py`**
```python
class KeycloakService:
    async def criar_ou_linkar_usuario(claims: dict, db, redis) -> Usuario:
        # busca por keycloak_sub; se não achar, busca por email
        # se não existir: cria usuário com role MEMBER no tenant padrão
        # em todos os casos: seta keycloak_sub e salva refresh_token no Redis

    async def get_access_token(usuario_id: int, redis) -> str | None:
        # Redis.get("keycloak:rt:{usuario_id}")
        # se existe: KeycloakClient.refresh(rt) → retorna access_token
        # se expirado ou ausente: retorna None (MCP usa auth_type="none" como fallback)
```

**`router.py`**
```python
GET /auth/keycloak/login
    # gera state (uuid), salva no Redis 5min
    # redireciona para Keycloak authorization_endpoint

GET /auth/keycloak/callback
    # valida state anti-CSRF
    # exchange code → tokens
    # valida JWT Keycloak
    # criar_ou_linkar_usuario()
    # emite docagent JWT
    # redireciona para FRONTEND_URL/auth/callback?token=<jwt>
```

---

## Endpoint público de configuração

```python
GET /api/config/public   # sem autenticação

# resposta:
{
  "keycloak_enabled": true,
  "keycloak_url": "http://localhost:8180",
  "keycloak_realm": "docagent",
  "keycloak_client_id": "docagent-backend"
}
```

Se `KEYCLOAK_URL` não estiver definido nas envs, `keycloak_enabled: false`. O frontend só exibe o botão SSO quando `keycloak_enabled: true`.

---

## Mudanças no MCP service

`load_mcp_tools_for_skills` recebe dois novos parâmetros opcionais:

```python
async def load_mcp_tools_for_skills(
    skill_names: list[str],
    servers: list[McpServer],
    stack: AsyncExitStack,
    usuario_id: int | None = None,   # novo
    redis=None,                       # novo
) -> list
```

Função auxiliar interna:

```python
async def _build_mcp_headers(server: McpServer, usuario_id, redis) -> dict:
    if server.auth_type == "keycloak" and usuario_id and redis:
        token = await KeycloakService.get_access_token(usuario_id, redis)
        return {"Authorization": f"Bearer {token}"} if token else {}
    if server.auth_type == "static":
        auth = server.env.get("Authorization", "")
        return {"Authorization": auth} if auth else {}
    return {}
```

Para `auth_type="keycloak"` em servidores **stdio**: token injetado em `env["KEYCLOAK_TOKEN"]` ao criar `StdioServerParameters`.

O router de chat (`routers/chat.py`) já recebe `current_user` — basta propagar `current_user.id` e o `redis` (disponível via lifespan) para `load_mcp_tools_for_skills`.

---

## Frontend

### LoginView.vue

```
┌──────────────────────────────────┐
│         DocAgent                 │
│                                  │
│  Usuário  [________________]     │
│  Senha    [________________]     │
│                                  │
│  [       Entrar       ]          │
│                                  │
│  ──────── ou ────────            │
│                                  │
│  [  🔑  Entrar com Keycloak  ]   │  ← visível só se keycloak_enabled
│                                  │
└──────────────────────────────────┘
```

### Nova rota: `/auth/callback`

Página mínima que:
1. Lê `?token=` da query string
2. Salva no mesmo store de auth (Pinia) que o login local usa
3. Redireciona para `/`

Nenhuma outra view muda.

---

## Docker-compose (dev)

```yaml
keycloak-db:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: keycloak
    POSTGRES_USER: keycloak
    POSTGRES_PASSWORD: keycloak
  volumes:
    - keycloak_db_data:/var/lib/postgresql/data

keycloak:
  image: quay.io/keycloak/keycloak:26
  command: start-dev --import-realm
  environment:
    KC_DB: postgres
    KC_DB_URL: jdbc:postgresql://keycloak-db/keycloak
    KC_DB_USERNAME: keycloak
    KC_DB_PASSWORD: keycloak
    KEYCLOAK_ADMIN: admin
    KEYCLOAK_ADMIN_PASSWORD: admin
  volumes:
    - ./keycloak/realm-docagent.json:/opt/keycloak/data/import/realm.json
  ports:
    - "8180:8080"
  depends_on:
    keycloak-db:
      condition: service_healthy
```

`keycloak/realm-docagent.json` — realm com:
- Client `docagent-backend` (confidential, redirect URI: `http://localhost:8000/auth/keycloak/callback`)
- Mapper de email como claim obrigatório
- Usuário de teste: `teste@docagent.local` / `teste123`

---

## Variáveis de ambiente

```env
# Keycloak (opcional — se ausente, SSO desabilitado)
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=docagent
KEYCLOAK_CLIENT_ID=docagent-backend
KEYCLOAK_CLIENT_SECRET=<gerado no realm>
KEYCLOAK_DEFAULT_TENANT_ID=1
KEYCLOAK_REDIRECT_URI=http://localhost:8000/auth/keycloak/callback
```

---

## Testes

```
tests/test_keycloak/
├── conftest.py           # mock KeycloakClient, mock Redis
├── test_keycloak_service.py
│   ├── test_criar_usuario_novo_via_keycloak
│   ├── test_linkar_por_email_usuario_existente
│   ├── test_linkar_por_sub_ja_existente
│   ├── test_get_access_token_com_refresh_valido
│   └── test_get_access_token_sem_rt_retorna_none
├── test_keycloak_router.py
│   ├── test_login_redireciona_para_keycloak
│   ├── test_callback_state_invalido_retorna_400
│   ├── test_callback_cria_usuario_e_retorna_jwt
│   └── test_config_public_sem_keycloak_retorna_disabled
└── test_mcp_token_forwarding.py
    ├── test_build_headers_keycloak_com_token_valido
    ├── test_build_headers_static_usa_env
    ├── test_build_headers_none_retorna_vazio
    └── test_build_headers_keycloak_sem_redis_retorna_vazio
```

---

## Ordem de implementação

```
1.  Branch: fase-keycloak (ou fase-24, a definir no roadmap)
2.  Alembic: add keycloak_sub em usuario + auth_type em mcp_server
3.  keycloak/client.py (KeycloakClient + JWKS cache)
4.  🔴 RED: test_keycloak_service.py
5.  🟢 GREEN: keycloak/service.py
6.  🔴 RED: test_keycloak_router.py
7.  🟢 GREEN: keycloak/router.py
8.  GET /api/config/public
9.  🔴 RED: test_mcp_token_forwarding.py
10. 🟢 GREEN: _build_mcp_headers() + propagação de usuario_id no chat router
11. keycloak/realm-docagent.json + docker-compose.yml
12. Frontend: LoginView.vue + /auth/callback route
13. .env.example com vars Keycloak
14. Smoke test end-to-end: login Keycloak → chat com MCP SSE Keycloak
```

---

## Gotchas

- **Refresh token rotacionado:** Keycloak por padrão rotaciona o refresh token a cada uso. Sempre atualizar o Redis com o novo RT retornado.
- **TTL do refresh token:** configurar no realm Keycloak (padrão: 30 dias offline, 30min online). Usar TTL correspondente no Redis.
- **JWKS cache:** não buscar JWKS a cada request. TTLCache de 10min é suficiente. Se validação falhar por key rotacionada, invalidar cache e tentar uma vez.
- **state anti-CSRF:** guardar no Redis com TTL de 5min, deletar após uso. Não usar sessão de servidor.
- **Keycloak start-dev:** apenas para desenvolvimento. Em produção usar `start` com configuração TLS adequada.
- **Usuário sem email no Keycloak:** exigir email como claim obrigatório no realm. Rejeitar callback com 400 se claim ausente.
- **MCP stdio + token:** token via env var `KEYCLOAK_TOKEN` — o servidor MCP precisa ler essa var. Documentar a convenção.
- **`descobrir_tools` com auth_type="keycloak":** esta operação é chamada pelo admin, que pode não ter RT Keycloak no Redis. Solução: para `descobrir_tools`, usar `auth_type="static"` com um token de service account Keycloak no `env["Authorization"]`, ou aceitar que a descoberta falhe sem token e o admin use `auth_type="none"` temporariamente. Não bloquear a feature por este edge case.
