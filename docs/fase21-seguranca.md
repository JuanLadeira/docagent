# Fase 21 — Segurança & Rate Limiting

## Objetivo

Fechar as lacunas de segurança antes de crescer a base de usuários. Esta fase não adiciona features visíveis ao tenant, mas é obrigatória antes de qualquer crescimento real: criptografia de secrets, rate limiting em endpoints críticos, 2FA para admin e audit log de todas as ações importantes.

---

## 1. Rate Limiting

Usar `slowapi` (wrapper FastAPI do `limits`).

### Limites por endpoint

```python
# Endpoints críticos
POST /auth/token              → 5 req / minuto / IP        (brute force login)
POST /auth/register           → 3 req / hora / IP          (spam de contas)
POST /auth/password-reset     → 3 req / hora / IP
POST /api/admin/login         → 5 req / minuto / IP
POST /chat                    → 20 req / minuto / tenant   (custo LLM)
POST /api/*/webhook           → 100 req / minuto / IP      (flood de webhooks)
POST /api/fine-tuning/jobs    → 2 req / hora / tenant      (treino é pesado)
```

### Implementação

```python
# main.py / api.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# nos routers:
@router.post("/token")
@limiter.limit("5/minute")
async def login(request: Request, ...): ...
```

Para limites por tenant (não por IP):

```python
def get_tenant_key(request: Request) -> str:
    # extrai tenant_id do JWT
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = decode_access_token(token)
    return f"tenant:{payload.get('tenant_id', 'anon')}"

@router.post("/chat")
@limiter.limit("20/minute", key_func=get_tenant_key)
async def chat(...): ...
```

---

## 2. Criptografia de Secrets

Campos sensíveis atualmente em plaintext no banco:
- `Tenant.llm_api_key`
- `AudioConfig.elevenlabs_api_key`
- `TelegramInstancia.bot_token` (write-only, mas no banco em plaintext)

### Solução: Fernet (cryptography lib)

```python
# src/docagent/crypto.py
from cryptography.fernet import Fernet
from docagent.settings import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()

def decrypt(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
```

```env
# .env
ENCRYPTION_KEY=<gerar com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
```

### Campos a criptografar

```python
# No SQLAlchemy: usar TypeDecorator
class EncryptedString(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return decrypt(value)
        return value

# Uso nos models:
class Tenant(Base):
    llm_api_key: Mapped[str | None] = mapped_column(EncryptedString(500))
```

### Migração de dados existentes

```python
# Script de migração one-time: re-encripta valores existentes em plaintext
# Roda como task do entrypoint.sh na primeira vez
async def migrar_criptografia(db):
    tenants = await db.execute(select(Tenant))
    for t in tenants.scalars():
        if t.llm_api_key and not t.llm_api_key.startswith("gAA"):  # prefixo Fernet
            t.llm_api_key = encrypt(t.llm_api_key)
    await db.commit()
```

---

## 3. 2FA para Admin

Usar TOTP (Time-based One-Time Password) — compatível com Google Authenticator, Authy, etc.

### Fluxo

```
1. Admin acessa /sys-mgmt/setup-2fa
   → Backend gera secret TOTP → exibe QR code para escanear no app
   → Admin confirma com código gerado → backend salva secret (criptografado)

2. Login normal: POST /api/admin/login (username + password)
   → Retorna {requires_2fa: true, temp_token: "..."}

3. POST /api/admin/login/2fa (temp_token + totp_code)
   → Valida código → retorna JWT admin definitivo
```

### Schema

```python
class Admin(Base):
    # campos existentes...
    totp_secret: str | None = None  # EncryptedString — null se 2FA não configurado
    totp_habilitado: bool = False
```

### Implementação

```python
import pyotp

class AdminAuthService:
    def gerar_totp_secret(self) -> str:
        return pyotp.random_base32()

    def gerar_qr_uri(self, secret: str, username: str) -> str:
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(username, issuer_name="z3ndocs Admin")

    def verificar_totp(self, secret: str, codigo: str) -> bool:
        totp = pyotp.TOTP(secret)
        return totp.verify(codigo, valid_window=1)  # ±30s de tolerância
```

---

## 4. Audit Log

Toda ação administrativa registrada — quem fez o quê, quando e em qual recurso.

### Tabela: `audit_log`

```python
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: int (PK)
    # Quem fez
    actor_tipo: ActorTipo          # admin | usuario
    actor_id: int
    actor_username: str            # denormalizado para preservar histórico
    tenant_id: int | None          # null para ações de admin global
    # O que fez
    acao: str                      # ex: "criar_agente", "deletar_usuario", "login_admin"
    recurso_tipo: str | None       # ex: "agente", "usuario", "plano"
    recurso_id: int | None
    # Detalhes
    dados_antes: dict | None (JSON)   # estado antes da mudança
    dados_depois: dict | None (JSON)  # estado depois da mudança
    ip_origem: str | None
    created_at: datetime

class ActorTipo(str, Enum):
    ADMIN = "admin"
    USUARIO = "usuario"
```

### AuditService

```python
class AuditService:
    @staticmethod
    async def registrar(
        db: AsyncSession,
        actor_tipo: ActorTipo,
        actor_id: int,
        actor_username: str,
        acao: str,
        tenant_id: int | None = None,
        recurso_tipo: str | None = None,
        recurso_id: int | None = None,
        dados_antes: dict | None = None,
        dados_depois: dict | None = None,
        ip_origem: str | None = None,
    ) -> None:
        log = AuditLog(...)
        db.add(log)
        # Não faz commit aqui — deixa o commit da operação principal levar junto
```

### Ações auditadas (exemplos)

```python
# Em admin/router.py:
await AuditService.registrar(db, ActorTipo.ADMIN, admin.id, admin.username,
    acao="criar_tenant", recurso_tipo="tenant", recurso_id=novo_tenant.id,
    dados_depois=novo_tenant.dict())

await AuditService.registrar(db, ActorTipo.ADMIN, admin.id, admin.username,
    acao="deletar_usuario", recurso_tipo="usuario", recurso_id=usuario.id,
    dados_antes=usuario.dict())

# Em auth/router.py:
await AuditService.registrar(db, ActorTipo.USUARIO, usuario.id, usuario.username,
    acao="login", tenant_id=usuario.tenant_id, ip_origem=request.client.host)
```

### Endpoint de audit log (admin only)

```
GET /api/admin/audit-logs
    → Params: actor_id, acao, recurso_tipo, tenant_id, data_inicio, data_fim, page
    → Retorna lista paginada de AuditLog
```

---

## 5. Validação de Origem de Webhooks

### WhatsApp (Evolution API)

A Evolution API envia um header `apikey` nos webhooks. Validar:

```python
async def validar_webhook_evolution(request: Request, instancia: WhatsappInstancia):
    apikey = request.headers.get("apikey")
    if apikey != settings.EVOLUTION_API_KEY:
        raise HTTPException(401, "Webhook não autorizado")
```

### Telegram

Adicionar suporte ao header `X-Telegram-Bot-Api-Secret-Token` (opcional no Telegram, mas recomendado):

```python
# No create da instância: gerar um secret_token aleatório e salvar
# No setWebhook: passar secret_token
# No webhook handler: validar X-Telegram-Bot-Api-Secret-Token
```

---

## 6. CORS Restritivo

Hoje o CORS provavelmente aceita `*` em dev. Em produção:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,       # ex: https://z3ndocs.uk
        "http://localhost:5173",      # dev
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

## Dependências

```toml
dependencies = [
    "slowapi>=0.1.9",
    "cryptography>=42.0.0",
    "pyotp>=2.9.0",
]
```

---

## Estrutura de Arquivos

```
src/docagent/
├── crypto.py               — encrypt/decrypt (Fernet), EncryptedString TypeDecorator
├── audit/
│   ├── __init__.py
│   ├── models.py           — AuditLog, ActorTipo
│   ├── schemas.py          — AuditLogPublic
│   └── services.py         — AuditService.registrar()
└── auth/
    ├── router.py           — + /login/2fa, rate limiting
    └── totp.py             — gerar_secret, gerar_qr_uri, verificar_totp
```

---

## Testes

```
tests/test_seguranca/
├── test_rate_limiting.py
│   ├── test_login_bloqueado_apos_5_tentativas
│   ├── test_chat_bloqueado_apos_20_req
│   └── test_rate_limit_reset_apos_janela
├── test_crypto.py
│   ├── test_encrypt_decrypt_roundtrip
│   ├── test_campo_salvo_criptografado_no_banco
│   └── test_campo_retornado_descriptografado
├── test_2fa.py
│   ├── test_setup_2fa_gera_qr
│   ├── test_login_sem_2fa_retorna_jwt_direto
│   ├── test_login_com_2fa_requer_codigo
│   ├── test_codigo_invalido_retorna_401
│   └── test_codigo_valido_retorna_jwt
└── test_audit_log.py
    ├── test_criar_tenant_registra_audit
    ├── test_deletar_usuario_registra_audit
    ├── test_login_registra_audit
    └── test_listar_audit_logs_paginado
```

---

## Ordem de Implementação

```
1.  Branch: fase-21
2.  crypto.py + EncryptedString TypeDecorator
3.  Alembic: alterar colunas para usar EncryptedString
4.  Script de migração de dados existentes
5.  slowapi: instalar + configurar + aplicar nos endpoints críticos
6.  🔴 RED: test_rate_limiting.py
7.  🟢 GREEN: decorators @limiter.limit nos routers
8.  Alembic: tabela audit_log
9.  audit/models.py + audit/services.py
10. 🔴 RED: test_audit_log.py
11. 🟢 GREEN: AuditService.registrar() nos endpoints admin + auth
12. 🔴 RED: test_2fa.py
13. 🟢 GREEN: auth/totp.py + /login/2fa endpoint
14. 🔴 RED: test_crypto.py
15. CORS: ajustar allow_origins para produção
16. Validação de origem de webhooks (Evolution + Telegram)
```

---

## Gotchas

- **ENCRYPTION_KEY é crítica:** perder a chave = perder todos os secrets criptografados. Fazer backup seguro. Rotação de chave requer re-criptografar todos os registros.
- **Rate limiting com múltiplos workers:** `slowapi` usa memória local por padrão — com múltiplas réplicas, os contadores não são compartilhados. Usar backend Redis: `Limiter(storage_uri="redis://redis:6379")`.
- **2FA é opcional inicialmente:** não forçar 2FA para todos os admins imediatamente — primeiro implementar opt-in, depois considerar obrigatoriedade.
- **Audit log não falha a operação:** se o `AuditService.registrar` lançar exceção, não deve cancelar a operação principal — usar `try/except` silencioso com log de erro.
