# Módulo: Segurança

**Fase:** 21
**Status:** ✅ Implementado

---

## Componentes

### `src/docagent/rate_limit.py`

Singleton `Limiter` do `slowapi`. Backend configurável via `REDIS_URL` (padrão: memória local).

```python
limiter = Limiter(key_func=get_remote_address, storage_uri=REDIS_URL or "memory://")
```

**`get_tenant_key(request)`:** extrai `tenant_id` do JWT sem verificar assinatura para usar como chave de rate limit no `/chat`. A auth real continua verificando a assinatura normalmente.

**Uso nos routers:**
```python
@limiter.limit("20/minute", key_func=get_tenant_key)
async def chat(request: Request, body: ChatRequest, ...):
```

---

### `src/docagent/crypto.py`

Criptografia simétrica Fernet (AES-128-CBC + HMAC-SHA256) para secrets em repouso.

**`EncryptedString(TypeDecorator)`:** SQLAlchemy type decorator — cifra no `process_bind_param`, decifra no `process_result_value`. Transparente para o código que usa os models.

```python
# Model com campo cifrado:
bot_token: Mapped[str] = mapped_column(EncryptedString(700))
```

**Graceful degradation:** se `ENCRYPTION_KEY` não estiver setada, funciona como `String` normal (com log de warning).

**Gotcha:** Fernet é não-determinístico (IV aleatório). Campos com `unique=True` + `EncryptedString` falham em queries de lookup em produção. Ver [fases/21.md](../fases/21.md#gotcha-crítico).

---

### `src/docagent/audit/`

```
audit/
├── models.py   — AuditLog
├── services.py — AuditService
└── router.py   — GET /api/admin/audit-logs
```

**`AuditLog`:** `actor_tipo` (USER/ADMIN), `actor_id`, `actor_username`, `tenant_id`, `acao`, `recurso_tipo`, `recurso_id`, `ip_origem`, `dados_antes` (JSON), `dados_depois` (JSON).

**`AuditService.registrar()`:** sempre silencioso (`try/except`). Nunca comita — o commit fica a cargo da sessão da request.

---

### `src/docagent/auth/totp.py`

TOTP para admin 2FA usando `pyotp`.

```python
gerar_secret()             → str (base32)
gerar_qr_uri(secret, ...)  → str (otpauth:// URI)
verificar_codigo(secret, codigo, valid_window=1)  → bool
```

---

### `src/docagent/auth/security.py` (adições Fase 21)

```python
create_temp_token(admin_id: int) → str   # JWT 5min, type=temp_2fa
verify_temp_token(token: str) → int | None  # retorna admin_id ou None
```

---

## Variáveis de Ambiente

| Var | Descrição | Default |
|-----|-----------|---------|
| `ENCRYPTION_KEY` | Chave Fernet (base64url 32 bytes) | `""` (plaintext) |
| `REDIS_URL` | Backend de rate limit | `""` (memória) |

**Gerar ENCRYPTION_KEY:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
