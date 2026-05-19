# Keycloak Auth Híbrida + MCP Token Forwarding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar Keycloak como provedor OIDC opcional ao login existente, com token forwarding dinâmico para MCP servers SSE/stdio que exijam autenticação Keycloak.

**Architecture:** Token exchange: o frontend redireciona para Keycloak → backend troca o `code` por tokens Keycloak → emite JWT docagent normal → armazena refresh_token Keycloak no Redis por usuário. A auth existente não muda. Para MCP tools com `auth_type="keycloak"`, o backend busca access_token fresco do Redis antes de conectar.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, PyJWT (JWKS RS256), httpx, cachetools TTLCache, Redis (fakeredis nos testes), Vue 3 + Pinia, Docker Compose + Keycloak 26.

---

## File Map

| Ação | Arquivo |
|------|---------|
| Create | `src/docagent/keycloak/__init__.py` |
| Create | `src/docagent/keycloak/client.py` |
| Create | `src/docagent/keycloak/service.py` |
| Create | `src/docagent/keycloak/router.py` |
| Create | `alembic/versions/s9t0u1v2w3x4_add_keycloak_sub_to_usuario.py` |
| Create | `alembic/versions/t0u1v2w3x4y5_add_auth_type_to_mcp_server.py` |
| Create | `tests/test_keycloak/__init__.py` |
| Create | `tests/test_keycloak/conftest.py` |
| Create | `tests/test_keycloak/test_keycloak_service.py` |
| Create | `tests/test_keycloak/test_keycloak_router.py` |
| Create | `tests/test_keycloak/test_mcp_token_forwarding.py` |
| Create | `keycloak/realm-docagent.json` |
| Create | `frontend/src/views/auth/KeycloakCallbackView.vue` |
| Modify | `src/docagent/usuario/models.py` — add `keycloak_sub` |
| Modify | `src/docagent/mcp_server/models.py` — add `auth_type` |
| Modify | `src/docagent/mcp_server/schemas.py` — add `auth_type` |
| Modify | `src/docagent/mcp_server/services.py` — `_build_mcp_headers` + novos params |
| Modify | `src/docagent/settings.py` — vars Keycloak |
| Modify | `src/docagent/api.py` — lifespan redis em `app.state`, registra routers |
| Modify | `src/docagent/chat/router.py` — propaga `usuario_id` + redis ao MCP |
| Modify | `frontend/src/views/McpServidoresView.vue` — campo `auth_type` no form |
| Modify | `frontend/src/api/client.ts` — `auth_type` nos tipos + `/api/config/public` |
| Modify | `frontend/src/stores/auth.ts` — `setTokenFromKeycloak()` |
| Modify | `frontend/src/views/auth/LoginView.vue` — botão SSO |
| Modify | `frontend/src/router/index.ts` — rota `/auth/callback` |
| Modify | `docker-compose.yml` — serviços `keycloak-db` + `keycloak` |
| Modify | `.env.example` — vars Keycloak |

---

## Task 0: Commitar mudanças pendentes do MCP SSE (fase-23)

**Files:** `src/docagent/mcp_server/models.py`, `schemas.py`, `services.py`, `alembic/versions/r8s9t0u1v2w3_add_transport_and_url_to_mcp_server.py`, `frontend/src/views/McpServidoresView.vue`, `frontend/src/api/client.ts`

- [ ] **Step 1: Verificar o que está pendente**

```bash
git status
git diff --stat
```

- [ ] **Step 2: Rodar testes para garantir que nada está quebrado**

```bash
uv run pytest tests/ -x -q 2>&1 | tail -20
```

Esperado: todos os testes passando (628+).

- [ ] **Step 3: Commitar as mudanças MCP**

```bash
git add src/docagent/mcp_server/models.py \
        src/docagent/mcp_server/schemas.py \
        src/docagent/mcp_server/services.py \
        alembic/versions/r8s9t0u1v2w3_add_transport_and_url_to_mcp_server.py \
        frontend/src/views/McpServidoresView.vue \
        frontend/src/api/client.ts

git commit -m "feat(fase23): MCP server SSE — transport + url + header auth"
```

- [ ] **Step 4: Criar branch da nova fase**

```bash
git checkout -b fase-keycloak
```

---

## Task 1: Settings + Modelos + Migrations

**Files:**
- Modify: `src/docagent/settings.py`
- Modify: `src/docagent/usuario/models.py`
- Modify: `src/docagent/mcp_server/models.py`
- Modify: `src/docagent/mcp_server/schemas.py`
- Create: `alembic/versions/s9t0u1v2w3x4_add_keycloak_sub_to_usuario.py`
- Create: `alembic/versions/t0u1v2w3x4y5_add_auth_type_to_mcp_server.py`

- [ ] **Step 1: Adicionar vars Keycloak ao Settings**

Em `src/docagent/settings.py`, adicionar ao final da classe `Settings`:

```python
    # Keycloak SSO (opcional — se KEYCLOAK_URL vazio, SSO desabilitado)
    KEYCLOAK_URL: str = os.getenv("KEYCLOAK_URL", "")
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "docagent")
    KEYCLOAK_CLIENT_ID: str = os.getenv("KEYCLOAK_CLIENT_ID", "docagent-backend")
    KEYCLOAK_CLIENT_SECRET: str = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
    KEYCLOAK_REDIRECT_URI: str = os.getenv(
        "KEYCLOAK_REDIRECT_URI", "http://localhost:8000/auth/keycloak/callback"
    )
    KEYCLOAK_DEFAULT_TENANT_ID: int = int(os.getenv("KEYCLOAK_DEFAULT_TENANT_ID", "1"))
```

- [ ] **Step 2: Adicionar `keycloak_sub` ao model Usuario**

Em `src/docagent/usuario/models.py`, adicionar após `role`:

```python
    keycloak_sub: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
```

- [ ] **Step 3: Adicionar `auth_type` ao model McpServer**

Em `src/docagent/mcp_server/models.py`, adicionar após `url`:

```python
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="none")
```

- [ ] **Step 4: Adicionar `auth_type` aos schemas MCP**

Em `src/docagent/mcp_server/schemas.py`:

No `McpServerCreate`, adicionar:
```python
    auth_type: str = "none"
```

No `McpServerUpdate`, adicionar:
```python
    auth_type: str | None = None
```

No `McpServerPublic`, adicionar:
```python
    auth_type: str
```

- [ ] **Step 5: Criar migration para `keycloak_sub`**

Criar `alembic/versions/s9t0u1v2w3x4_add_keycloak_sub_to_usuario.py`:

```python
"""add keycloak_sub to usuario

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.add_column(
            sa.Column("keycloak_sub", sa.String(255), nullable=True)
        )
        batch_op.create_unique_constraint("uq_usuario_keycloak_sub", ["keycloak_sub"])
        batch_op.create_index("ix_usuario_keycloak_sub", ["keycloak_sub"])


def downgrade() -> None:
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_index("ix_usuario_keycloak_sub")
        batch_op.drop_constraint("uq_usuario_keycloak_sub", type_="unique")
        batch_op.drop_column("keycloak_sub")
```

- [ ] **Step 6: Criar migration para `auth_type`**

Criar `alembic/versions/t0u1v2w3x4y5_add_auth_type_to_mcp_server.py`:

```python
"""add auth_type to mcp_server

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mcp_server") as batch_op:
        batch_op.add_column(
            sa.Column("auth_type", sa.String(20), nullable=False, server_default="none")
        )


def downgrade() -> None:
    with op.batch_alter_table("mcp_server") as batch_op:
        batch_op.drop_column("auth_type")
```

- [ ] **Step 7: Commit**

```bash
git add src/docagent/settings.py \
        src/docagent/usuario/models.py \
        src/docagent/mcp_server/models.py \
        src/docagent/mcp_server/schemas.py \
        alembic/versions/s9t0u1v2w3x4_add_keycloak_sub_to_usuario.py \
        alembic/versions/t0u1v2w3x4y5_add_auth_type_to_mcp_server.py

git commit -m "feat(keycloak): settings + migrations keycloak_sub e auth_type"
```

---

## Task 2: KeycloakClient

**Files:**
- Create: `src/docagent/keycloak/__init__.py`
- Create: `src/docagent/keycloak/client.py`

- [ ] **Step 1: Criar `__init__.py`**

```python
# src/docagent/keycloak/__init__.py
```

(arquivo vazio)

- [ ] **Step 2: Criar `client.py`**

Criar `src/docagent/keycloak/client.py`:

```python
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient


class KeycloakClient:
    def __init__(self, url: str, realm: str, client_id: str, client_secret: str):
        self.url = url.rstrip("/")
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self._token_url = f"{self.url}/realms/{realm}/protocol/openid-connect/token"
        self._auth_url = f"{self.url}/realms/{realm}/protocol/openid-connect/auth"
        self._jwks_uri = f"{self.url}/realms/{realm}/protocol/openid-connect/certs"
        # PyJWKClient faz cache das chaves por `lifespan` segundos
        self._jwks_client = PyJWKClient(self._jwks_uri, cache_keys=True, lifespan=600)

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{self._auth_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def refresh(self, refresh_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                },
            )
            resp.raise_for_status()
            return resp.json()

    def validate_jwt(self, token: str) -> dict:
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
```

- [ ] **Step 3: Commit**

```bash
git add src/docagent/keycloak/
git commit -m "feat(keycloak): KeycloakClient — exchange_code, refresh, validate_jwt"
```

---

## Task 3: TDD — KeycloakService (RED)

**Files:**
- Create: `tests/test_keycloak/__init__.py`
- Create: `tests/test_keycloak/conftest.py`
- Create: `tests/test_keycloak/test_keycloak_service.py`

- [ ] **Step 1: Criar `__init__.py`**

```python
# tests/test_keycloak/__init__.py
```

(arquivo vazio)

- [ ] **Step 2: Criar `conftest.py`**

Criar `tests/test_keycloak/conftest.py`:

```python
import pytest
import pytest_asyncio
import fakeredis.aioredis as fake_aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_redis():
    r = fake_aioredis.FakeRedis(decode_responses=False)
    yield r
    await r.aclose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: db_session
    # Injeta fake_redis no app.state para endpoints que usam request.app.state.redis
    app.state.redis = fake_aioredis.FakeRedis(decode_responses=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
    if hasattr(app.state, "redis"):
        await app.state.redis.aclose()
        del app.state.redis
```

- [ ] **Step 3: Criar `test_keycloak_service.py` (RED)**

Criar `tests/test_keycloak/test_keycloak_service.py`:

```python
import pytest
import pytest_asyncio
from unittest.mock import patch

from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole
from docagent.keycloak.service import KeycloakService


@pytest_asyncio.fixture
async def tenant(db_session):
    t = Tenant(nome="Tenant Teste", slug="tenant-teste")
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.mark.asyncio
async def test_criar_usuario_novo_via_keycloak(db_session, fake_redis, tenant):
    claims = {"sub": "kc-sub-001", "email": "novo@teste.com", "name": "Novo User"}

    with patch("docagent.keycloak.service.Settings") as mock_s:
        mock_s.return_value.KEYCLOAK_DEFAULT_TENANT_ID = tenant.id
        user = await KeycloakService.criar_ou_linkar_usuario(
            claims=claims,
            refresh_token="rt-abc",
            db=db_session,
            redis=fake_redis,
        )

    assert user.email == "novo@teste.com"
    assert user.keycloak_sub == "kc-sub-001"
    assert user.tenant_id == tenant.id
    assert user.password == "!keycloak"

    rt = await fake_redis.get(f"keycloak:rt:{user.id}")
    assert rt == b"rt-abc"


@pytest.mark.asyncio
async def test_linkar_por_email_usuario_existente(db_session, fake_redis, tenant):
    existing = Usuario(
        username="joao",
        email="joao@teste.com",
        password="hash",
        nome="João",
        role=UsuarioRole.OWNER,
        tenant_id=tenant.id,
    )
    db_session.add(existing)
    await db_session.flush()

    claims = {"sub": "kc-sub-002", "email": "joao@teste.com", "name": "João"}

    with patch("docagent.keycloak.service.Settings"):
        user = await KeycloakService.criar_ou_linkar_usuario(
            claims=claims,
            refresh_token="rt-joao",
            db=db_session,
            redis=fake_redis,
        )

    assert user.id == existing.id
    assert user.keycloak_sub == "kc-sub-002"
    rt = await fake_redis.get(f"keycloak:rt:{user.id}")
    assert rt == b"rt-joao"


@pytest.mark.asyncio
async def test_linkar_por_sub_ja_existente(db_session, fake_redis, tenant):
    existing = Usuario(
        username="maria",
        email="maria@teste.com",
        password="hash",
        nome="Maria",
        role=UsuarioRole.MEMBER,
        tenant_id=tenant.id,
        keycloak_sub="kc-sub-003",
    )
    db_session.add(existing)
    await db_session.flush()

    claims = {"sub": "kc-sub-003", "email": "maria@teste.com", "name": "Maria"}

    with patch("docagent.keycloak.service.Settings"):
        user = await KeycloakService.criar_ou_linkar_usuario(
            claims=claims,
            refresh_token="rt-maria-new",
            db=db_session,
            redis=fake_redis,
        )

    assert user.id == existing.id
    rt = await fake_redis.get(f"keycloak:rt:{user.id}")
    assert rt == b"rt-maria-new"


@pytest.mark.asyncio
async def test_get_access_token_com_refresh_valido(fake_redis, tenant):
    from unittest.mock import AsyncMock, patch

    await fake_redis.set("keycloak:rt:42", b"rt-valid", ex=3600)

    mock_client = AsyncMock()
    mock_client.refresh.return_value = {
        "access_token": "new-at",
        "refresh_token": "new-rt",
    }

    with patch("docagent.keycloak.service.get_keycloak_client", return_value=mock_client):
        token = await KeycloakService.get_access_token(usuario_id=42, redis=fake_redis)

    assert token == "new-at"
    # RT rotacionado deve ser salvo
    new_rt = await fake_redis.get("keycloak:rt:42")
    assert new_rt == b"new-rt"


@pytest.mark.asyncio
async def test_get_access_token_sem_rt_retorna_none(fake_redis):
    token = await KeycloakService.get_access_token(usuario_id=99, redis=fake_redis)
    assert token is None


@pytest.mark.asyncio
async def test_get_access_token_sem_redis_retorna_none():
    token = await KeycloakService.get_access_token(usuario_id=1, redis=None)
    assert token is None


@pytest.mark.asyncio
async def test_criar_usuario_sem_email_levanta_erro(db_session, fake_redis, tenant):
    claims = {"sub": "kc-sub-sem-email"}

    with pytest.raises(ValueError, match="email"):
        with patch("docagent.keycloak.service.Settings"):
            await KeycloakService.criar_ou_linkar_usuario(
                claims=claims,
                refresh_token="rt",
                db=db_session,
                redis=fake_redis,
            )
```

- [ ] **Step 4: Rodar testes — confirmar RED**

```bash
uv run pytest tests/test_keycloak/test_keycloak_service.py -v 2>&1 | tail -20
```

Esperado: `ImportError` ou `ModuleNotFoundError` em `docagent.keycloak.service`.

---

## Task 4: KeycloakService (GREEN)

**Files:**
- Create: `src/docagent/keycloak/service.py`

- [ ] **Step 1: Criar `service.py`**

Criar `src/docagent/keycloak/service.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.settings import Settings
from docagent.usuario.models import Usuario, UsuarioRole

_REDIS_RT_PREFIX = "keycloak:rt:{}"
_REDIS_RT_TTL = 60 * 60 * 24 * 7  # 7 dias


def get_keycloak_client():
    from docagent.keycloak.client import KeycloakClient
    s = Settings()
    if not s.KEYCLOAK_URL:
        return None
    return KeycloakClient(
        url=s.KEYCLOAK_URL,
        realm=s.KEYCLOAK_REALM,
        client_id=s.KEYCLOAK_CLIENT_ID,
        client_secret=s.KEYCLOAK_CLIENT_SECRET,
    )


class KeycloakService:
    @staticmethod
    async def criar_ou_linkar_usuario(
        claims: dict,
        refresh_token: str,
        db: AsyncSession,
        redis,
    ) -> Usuario:
        sub = claims["sub"]
        email = claims.get("email")
        if not email:
            raise ValueError("JWT Keycloak sem claim 'email'")

        # 1. Busca por keycloak_sub
        result = await db.execute(select(Usuario).where(Usuario.keycloak_sub == sub))
        user = result.scalar_one_or_none()

        # 2. Busca por email
        if not user:
            result = await db.execute(select(Usuario).where(Usuario.email == email))
            user = result.scalar_one_or_none()

        # 3. Cria novo usuário
        if not user:
            s = Settings()
            name = claims.get("name") or email.split("@")[0]
            username = email.split("@")[0] + "_" + str(uuid.uuid4())[:8]
            user = Usuario(
                username=username,
                email=email,
                nome=name,
                password="!keycloak",
                role=UsuarioRole.MEMBER,
                tenant_id=s.KEYCLOAK_DEFAULT_TENANT_ID,
                keycloak_sub=sub,
            )
            db.add(user)
            await db.flush()
        else:
            user.keycloak_sub = sub
            await db.flush()

        if redis:
            key = _REDIS_RT_PREFIX.format(user.id)
            await redis.set(key, refresh_token, ex=_REDIS_RT_TTL)

        return user

    @staticmethod
    async def get_access_token(usuario_id: int, redis) -> str | None:
        if not redis:
            return None
        key = _REDIS_RT_PREFIX.format(usuario_id)
        rt = await redis.get(key)
        if not rt:
            return None
        rt_str = rt.decode() if isinstance(rt, bytes) else rt
        kc = get_keycloak_client()
        if not kc:
            return None
        try:
            tokens = await kc.refresh(rt_str)
            new_rt = tokens.get("refresh_token", rt_str)
            await redis.set(key, new_rt, ex=_REDIS_RT_TTL)
            return tokens["access_token"]
        except Exception:
            return None
```

- [ ] **Step 2: Rodar testes — confirmar GREEN**

```bash
uv run pytest tests/test_keycloak/test_keycloak_service.py -v 2>&1 | tail -15
```

Esperado: todos os testes passando.

- [ ] **Step 3: Commit**

```bash
git add src/docagent/keycloak/service.py tests/test_keycloak/
git commit -m "feat(keycloak): KeycloakService — criar_ou_linkar_usuario + get_access_token (TDD)"
```

---

## Task 5: TDD — Keycloak Router + Config Public (RED)

**Files:**
- Create: `tests/test_keycloak/test_keycloak_router.py`

- [ ] **Step 1: Criar `test_keycloak_router.py`**

Criar `tests/test_keycloak/test_keycloak_router.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole


@pytest_asyncio_fixture_helper = None  # importado abaixo

import pytest_asyncio


@pytest_asyncio.fixture
async def tenant(db_session):
    t = Tenant(nome="Tenant Router", slug="tenant-router")
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.mark.asyncio
async def test_config_public_sem_keycloak_retorna_disabled(client):
    with patch("docagent.keycloak.router.Settings") as mock_s:
        mock_s.return_value.KEYCLOAK_URL = ""
        resp = await client.get("/api/config/public")
    assert resp.status_code == 200
    data = resp.json()
    assert data["keycloak_enabled"] is False
    assert data["keycloak_url"] == ""


@pytest.mark.asyncio
async def test_config_public_com_keycloak_retorna_enabled(client):
    with patch("docagent.keycloak.router.Settings") as mock_s:
        mock_s.return_value.KEYCLOAK_URL = "http://keycloak:8080"
        mock_s.return_value.KEYCLOAK_REALM = "docagent"
        mock_s.return_value.KEYCLOAK_CLIENT_ID = "docagent-backend"
        resp = await client.get("/api/config/public")
    assert resp.status_code == 200
    data = resp.json()
    assert data["keycloak_enabled"] is True
    assert data["keycloak_realm"] == "docagent"


@pytest.mark.asyncio
async def test_login_sem_keycloak_configurado_retorna_404(client):
    with patch("docagent.keycloak.router.get_keycloak_client", return_value=None):
        resp = await client.get("/auth/keycloak/login", follow_redirects=False)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_login_redireciona_para_keycloak(client):
    mock_kc = MagicMock()
    mock_kc.get_authorization_url.return_value = "http://keycloak/auth?client_id=x"

    with patch("docagent.keycloak.router.get_keycloak_client", return_value=mock_kc):
        with patch("docagent.keycloak.router.Settings") as mock_s:
            mock_s.return_value.KEYCLOAK_REDIRECT_URI = "http://localhost:8000/auth/keycloak/callback"
            resp = await client.get("/auth/keycloak/login", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert "keycloak" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_state_invalido_retorna_400(client, tenant):
    mock_kc = MagicMock()

    with patch("docagent.keycloak.router.get_keycloak_client", return_value=mock_kc):
        # Redis não tem a state key — simula state inválido/expirado
        resp = await client.get(
            "/auth/keycloak/callback",
            params={"code": "abc", "state": "estado-invalido"},
            follow_redirects=False,
        )

    assert resp.status_code == 400
    assert "state" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_callback_cria_usuario_e_redireciona(client, db_session, tenant):
    from docagent.settings import Settings

    # Salva a state no fake_redis do app
    state_val = "estado-valido-xyz"
    await client.app.state.redis.set(f"keycloak:state:{state_val}", b"1", ex=300)

    mock_kc = MagicMock()
    mock_kc.exchange_code = AsyncMock(return_value={
        "access_token": "at-keycloak",
        "refresh_token": "rt-keycloak",
    })
    mock_kc.validate_jwt.return_value = {
        "sub": "kc-sub-callback",
        "email": "callback@teste.com",
        "name": "Callback User",
    }

    with patch("docagent.keycloak.router.get_keycloak_client", return_value=mock_kc):
        with patch("docagent.keycloak.router.Settings") as mock_s:
            mock_s.return_value.KEYCLOAK_REDIRECT_URI = "http://localhost:8000/auth/keycloak/callback"
            mock_s.return_value.FRONTEND_URL = "http://localhost:5173"
            mock_s.return_value.KEYCLOAK_DEFAULT_TENANT_ID = tenant.id
            with patch("docagent.keycloak.service.Settings") as mock_s2:
                mock_s2.return_value.KEYCLOAK_DEFAULT_TENANT_ID = tenant.id
                resp = await client.get(
                    "/auth/keycloak/callback",
                    params={"code": "code-xyz", "state": state_val},
                    follow_redirects=False,
                )

    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert "/auth/callback?token=" in location
```

- [ ] **Step 2: Rodar — confirmar RED**

```bash
uv run pytest tests/test_keycloak/test_keycloak_router.py -v 2>&1 | tail -15
```

Esperado: `ImportError` em `docagent.keycloak.router`.

---

## Task 6: Keycloak Router + Config Public (GREEN)

**Files:**
- Create: `src/docagent/keycloak/router.py`
- Modify: `src/docagent/api.py`

- [ ] **Step 1: Criar `router.py`**

Criar `src/docagent/keycloak/router.py`:

```python
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from docagent.auth.security import create_access_token
from docagent.database import AsyncDBSession
from docagent.keycloak.service import KeycloakService, get_keycloak_client
from docagent.settings import Settings

router = APIRouter(prefix="/auth/keycloak", tags=["Keycloak SSO"])
config_router = APIRouter(tags=["Config"])


def _get_app_redis(request: Request):
    return getattr(request.app.state, "redis", None)


@router.get("/login")
async def keycloak_login(request: Request):
    kc = get_keycloak_client()
    if not kc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO Keycloak não configurado")

    state = str(uuid.uuid4())
    redis = _get_app_redis(request)
    if redis:
        await redis.set(f"keycloak:state:{state}", b"1", ex=300)

    s = Settings()
    url = kc.get_authorization_url(redirect_uri=s.KEYCLOAK_REDIRECT_URI, state=state)
    return RedirectResponse(url=url)


@router.get("/callback")
async def keycloak_callback(
    request: Request,
    code: str,
    state: str,
    db: AsyncDBSession,
):
    kc = get_keycloak_client()
    if not kc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSO Keycloak não configurado")

    redis = _get_app_redis(request)

    if redis:
        state_key = f"keycloak:state:{state}"
        exists = await redis.get(state_key)
        if not exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="state inválido ou expirado")
        await redis.delete(state_key)

    s = Settings()
    try:
        tokens = await kc.exchange_code(code=code, redirect_uri=s.KEYCLOAK_REDIRECT_URI)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Falha ao trocar code Keycloak")

    try:
        claims = kc.validate_jwt(tokens["access_token"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JWT Keycloak inválido")

    if not claims.get("email"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JWT Keycloak sem claim 'email'")

    user = await KeycloakService.criar_ou_linkar_usuario(
        claims=claims,
        refresh_token=tokens["refresh_token"],
        db=db,
        redis=redis,
    )

    access_token = create_access_token(data={"sub": user.username})
    frontend_url = s.FRONTEND_URL
    return RedirectResponse(url=f"{frontend_url}/auth/callback?token={access_token}")


@config_router.get("/api/config/public")
async def config_public():
    s = Settings()
    enabled = bool(s.KEYCLOAK_URL)
    return {
        "keycloak_enabled": enabled,
        "keycloak_url": s.KEYCLOAK_URL if enabled else "",
        "keycloak_realm": s.KEYCLOAK_REALM if enabled else "",
        "keycloak_client_id": s.KEYCLOAK_CLIENT_ID if enabled else "",
    }
```

- [ ] **Step 2: Registrar routers em `api.py`**

Em `src/docagent/api.py`, adicionar os imports:

```python
from docagent.keycloak.router import router as keycloak_router, config_router as keycloak_config_router
```

No lifespan, após `_deps._session_manager = RedisSessionManager(redis_client)`, adicionar:

```python
        app.state.redis = redis_client
```

E no `yield`, mudar o bloco de shutdown para também limpar `app.state`:

```python
    if redis_client is not None:
        await redis_client.aclose()
        if hasattr(app.state, "redis"):
            del app.state.redis
        print("[shutdown] Redis desconectado.")
```

No final do arquivo, antes do último `include_router`, adicionar:

```python
# Keycloak SSO (opcional)
app.include_router(keycloak_router)
app.include_router(keycloak_config_router)
```

- [ ] **Step 3: Rodar testes — confirmar GREEN**

```bash
uv run pytest tests/test_keycloak/test_keycloak_router.py -v 2>&1 | tail -15
```

Esperado: todos passando.

- [ ] **Step 4: Rodar suite completa — sem regressões**

```bash
uv run pytest tests/ -x -q 2>&1 | tail -10
```

Esperado: todos os testes existentes passando.

- [ ] **Step 5: Commit**

```bash
git add src/docagent/keycloak/router.py src/docagent/api.py \
        tests/test_keycloak/test_keycloak_router.py

git commit -m "feat(keycloak): router SSO login/callback + GET /api/config/public (TDD)"
```

---

## Task 7: TDD — MCP Token Forwarding (RED)

**Files:**
- Create: `tests/test_keycloak/test_mcp_token_forwarding.py`

- [ ] **Step 1: Criar `test_mcp_token_forwarding.py`**

Criar `tests/test_keycloak/test_mcp_token_forwarding.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

from docagent.mcp_server.models import McpServer
from docagent.mcp_server.services import _build_mcp_headers


def _make_server(auth_type: str, env: dict | None = None, url: str | None = None) -> McpServer:
    s = McpServer()
    s.auth_type = auth_type
    s.env = env or {}
    s.url = url
    s.transport = "sse" if url else "stdio"
    s.command = ""
    s.args = []
    return s


@pytest.mark.asyncio
async def test_build_headers_none_retorna_vazio(fake_redis):
    server = _make_server("none")
    headers = await _build_mcp_headers(server, usuario_id=1, redis=fake_redis)
    assert headers == {}


@pytest.mark.asyncio
async def test_build_headers_static_usa_env(fake_redis):
    server = _make_server("static", env={"Authorization": "Bearer token-estatico"})
    headers = await _build_mcp_headers(server, usuario_id=1, redis=fake_redis)
    assert headers == {"Authorization": "Bearer token-estatico"}


@pytest.mark.asyncio
async def test_build_headers_static_sem_env_retorna_vazio(fake_redis):
    server = _make_server("static", env={})
    headers = await _build_mcp_headers(server, usuario_id=1, redis=fake_redis)
    assert headers == {}


@pytest.mark.asyncio
async def test_build_headers_keycloak_com_token_valido(fake_redis):
    server = _make_server("keycloak")

    with patch(
        "docagent.mcp_server.services.KeycloakService.get_access_token",
        new_callable=AsyncMock,
        return_value="at-fresco",
    ):
        headers = await _build_mcp_headers(server, usuario_id=5, redis=fake_redis)

    assert headers == {"Authorization": "Bearer at-fresco"}


@pytest.mark.asyncio
async def test_build_headers_keycloak_sem_token_retorna_vazio(fake_redis):
    server = _make_server("keycloak")

    with patch(
        "docagent.mcp_server.services.KeycloakService.get_access_token",
        new_callable=AsyncMock,
        return_value=None,
    ):
        headers = await _build_mcp_headers(server, usuario_id=5, redis=fake_redis)

    assert headers == {}


@pytest.mark.asyncio
async def test_build_headers_keycloak_sem_redis_retorna_vazio():
    server = _make_server("keycloak")
    headers = await _build_mcp_headers(server, usuario_id=5, redis=None)
    assert headers == {}


@pytest.mark.asyncio
async def test_build_headers_keycloak_sem_usuario_id_retorna_vazio(fake_redis):
    server = _make_server("keycloak")
    headers = await _build_mcp_headers(server, usuario_id=None, redis=fake_redis)
    assert headers == {}
```

- [ ] **Step 2: Rodar — confirmar RED**

```bash
uv run pytest tests/test_keycloak/test_mcp_token_forwarding.py -v 2>&1 | tail -15
```

Esperado: `ImportError` — `_build_mcp_headers` não existe ainda.

---

## Task 8: MCP Token Forwarding + Chat Router (GREEN)

**Files:**
- Modify: `src/docagent/mcp_server/services.py`
- Modify: `src/docagent/chat/router.py`

- [ ] **Step 1: Adicionar `_build_mcp_headers` e atualizar `load_mcp_tools_for_skills`**

Em `src/docagent/mcp_server/services.py`, adicionar após os imports existentes:

```python
from docagent.keycloak.service import KeycloakService
```

Adicionar a função auxiliar logo antes de `load_mcp_tools_for_skills`:

```python
async def _build_mcp_headers(server: "McpServer", usuario_id: int | None, redis) -> dict:
    if server.auth_type == "keycloak":
        if not usuario_id or not redis:
            return {}
        token = await KeycloakService.get_access_token(usuario_id, redis)
        return {"Authorization": f"Bearer {token}"} if token else {}
    if server.auth_type == "static":
        auth = server.env.get("Authorization", "")
        return {"Authorization": auth} if auth else {}
    return {}
```

Alterar a assinatura de `load_mcp_tools_for_skills` para aceitar os novos parâmetros:

```python
async def load_mcp_tools_for_skills(
    skill_names: list[str],
    servers: list["McpServer"],
    stack: AsyncExitStack,
    usuario_id: int | None = None,
    redis=None,
) -> list:
```

Dentro do `for sid, tool_names in by_server.items():`, substituir o bloco de criação de `headers` existente. O bloco atual (que usa `server.env["Authorization"]` diretamente) deve ser substituído por:

```python
        if server.transport == "sse":
            from mcp.client.sse import sse_client
            headers = await _build_mcp_headers(server, usuario_id, redis)
            read, write = await stack.enter_async_context(
                sse_client(server.url, headers=headers or None)
            )
        else:
            env = dict(server.env or {})
            if server.auth_type == "keycloak" and usuario_id and redis:
                token = await KeycloakService.get_access_token(usuario_id, redis)
                if token:
                    env["KEYCLOAK_TOKEN"] = token
            params = StdioServerParameters(
                command=server.command,
                args=server.args,
                env=env or None,
            )
            read, write = await stack.enter_async_context(stdio_client(params))
```

Fazer o mesmo para o método `descobrir_tools` — substituir o bloco de headers SSE:

```python
            if server.transport == "sse":
                headers = await _build_mcp_headers(server, usuario_id=None, redis=None)
                read, write = await stack.enter_async_context(
                    sse_client(server.url, headers=headers or None)
                )
```

- [ ] **Step 2: Propagar `usuario_id` e `redis` no chat router**

Em `src/docagent/chat/router.py`, no endpoint `chat`, alterar a chamada a `load_mcp_tools_for_skills`:

```python
    if mcp_skills:
        servers = await mcp_service.get_all()
        redis = getattr(request.app.state, "redis", None)
        mcp_tools = await load_mcp_tools_for_skills(
            mcp_skills, servers, stack,
            usuario_id=current_user.id,
            redis=redis,
        )
```

No endpoint `chat_sync`, fazer o mesmo:

```python
        if mcp_skills:
            servers = await mcp_service.get_all()
            redis = getattr(request.app.state, "redis", None)
            mcp_tools = await load_mcp_tools_for_skills(
                mcp_skills, servers, stack,
                usuario_id=current_user.id,
                redis=redis,
            )
```

Adicionar `request: Request` como parâmetro em `chat_sync` se ainda não existir:

```python
async def chat_sync(
    request: Request,
    body: ChatRequest,
    current_user: CurrentUser,
    ...
```

- [ ] **Step 3: Rodar testes MCP forwarding — confirmar GREEN**

```bash
uv run pytest tests/test_keycloak/test_mcp_token_forwarding.py -v 2>&1 | tail -10
```

Esperado: todos passando.

- [ ] **Step 4: Rodar suite completa — sem regressões**

```bash
uv run pytest tests/ -x -q 2>&1 | tail -10
```

Esperado: todos os testes existentes passando.

- [ ] **Step 5: Commit**

```bash
git add src/docagent/mcp_server/services.py src/docagent/chat/router.py \
        tests/test_keycloak/test_mcp_token_forwarding.py

git commit -m "feat(keycloak): MCP token forwarding — _build_mcp_headers + propagação usuario_id (TDD)"
```

---

## Task 9: Docker Compose + Realm Keycloak

**Files:**
- Create: `keycloak/realm-docagent.json`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Criar diretório e realm JSON**

```bash
mkdir -p keycloak
```

Criar `keycloak/realm-docagent.json`:

```json
{
  "realm": "docagent",
  "enabled": true,
  "displayName": "DocAgent",
  "clients": [
    {
      "clientId": "docagent-backend",
      "enabled": true,
      "protocol": "openid-connect",
      "publicClient": false,
      "secret": "dev-secret-change-in-prod",
      "redirectUris": [
        "http://localhost:8000/auth/keycloak/callback",
        "http://api:8000/auth/keycloak/callback"
      ],
      "webOrigins": ["http://localhost:5173", "http://localhost:8000"],
      "standardFlowEnabled": true,
      "directAccessGrantsEnabled": false,
      "attributes": {
        "post.logout.redirect.uris": "+"
      }
    }
  ],
  "users": [
    {
      "username": "teste",
      "email": "teste@docagent.local",
      "firstName": "Usuário",
      "lastName": "Teste",
      "enabled": true,
      "emailVerified": true,
      "credentials": [
        {
          "type": "password",
          "value": "teste123",
          "temporary": false
        }
      ]
    }
  ],
  "requiredCredentials": ["password"],
  "defaultRoles": ["uma_authorization"],
  "smtpServer": {}
}
```

- [ ] **Step 2: Adicionar serviços ao `docker-compose.yml`**

No `docker-compose.yml`, adicionar antes do `volumes:` final:

```yaml
  keycloak-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: keycloak
      POSTGRES_USER: keycloak
      POSTGRES_PASSWORD: keycloak
    volumes:
      - keycloak_db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U keycloak"]
      interval: 10s
      timeout: 5s
      retries: 5

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

Na seção `volumes:`, adicionar:

```yaml
  keycloak_db_data:
```

- [ ] **Step 3: Atualizar `.env.example`**

Adicionar ao `.env.example`:

```env
# ── Keycloak SSO (opcional) ───────────────────────────────────────────────────
# Se KEYCLOAK_URL estiver vazio, o botão SSO não aparece no frontend.
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=docagent
KEYCLOAK_CLIENT_ID=docagent-backend
KEYCLOAK_CLIENT_SECRET=dev-secret-change-in-prod
KEYCLOAK_REDIRECT_URI=http://localhost:8000/auth/keycloak/callback
KEYCLOAK_DEFAULT_TENANT_ID=1
```

- [ ] **Step 4: Commit**

```bash
git add keycloak/ docker-compose.yml .env.example
git commit -m "feat(keycloak): docker-compose Keycloak 26 + realm-docagent.json"
```

---

## Task 10: Frontend

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/stores/auth.ts`
- Create: `frontend/src/views/auth/KeycloakCallbackView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/auth/LoginView.vue`
- Modify: `frontend/src/views/McpServidoresView.vue`

- [ ] **Step 1: Adicionar tipos e chamada de config em `client.ts`**

Em `frontend/src/api/client.ts`:

Adicionar o tipo `PublicConfig` e o campo `auth_type` nos tipos MCP. Localizar a interface `McpServerCreate` e adicionar:

```typescript
export interface PublicConfig {
  keycloak_enabled: boolean
  keycloak_url: string
  keycloak_realm: string
  keycloak_client_id: string
}
```

Na interface `McpServerCreate`, adicionar:
```typescript
  auth_type: string
```

Na interface `McpServer` (type de resposta), adicionar:
```typescript
  auth_type: string
```

No objeto `api`, adicionar o método:

```typescript
  getPublicConfig: () => axios.get<PublicConfig>('/api/config/public'),
```

- [ ] **Step 2: Adicionar `setTokenFromKeycloak` ao auth store**

Em `frontend/src/stores/auth.ts`, adicionar após a função `logout`:

```typescript
  async function setTokenFromKeycloak(accessToken: string) {
    token.value = accessToken
    sessionStorage.setItem('token', accessToken)
    const me = await api.getMe()
    tenantId.value = me.data.tenant_id
    userId.value = me.data.id
    role.value = me.data.role
    username.value = me.data.username
    sessionStorage.setItem('tenant_id', String(me.data.tenant_id))
    sessionStorage.setItem('user_id', String(me.data.id))
    sessionStorage.setItem('role', me.data.role)
    sessionStorage.setItem('username', me.data.username)
  }
```

Expor a função no `return`:

```typescript
  return { token, username, tenantId, userId, role, isAuthenticated, isOwner, login, logout, setTokenFromKeycloak }
```

- [ ] **Step 3: Criar `KeycloakCallbackView.vue`**

Criar `frontend/src/views/auth/KeycloakCallbackView.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const erro = ref('')

onMounted(async () => {
  const token = route.query.token as string | undefined
  if (!token) {
    erro.value = 'Token não encontrado na URL.'
    return
  }
  try {
    await auth.setTokenFromKeycloak(token)
    router.replace('/conversa')
  } catch {
    erro.value = 'Erro ao autenticar com Keycloak. Tente novamente.'
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-900">
    <div class="text-center">
      <div v-if="!erro" class="text-slate-400 text-sm">Autenticando via Keycloak...</div>
      <div v-else class="text-red-400 text-sm">{{ erro }}</div>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Adicionar rota em `router/index.ts`**

Em `frontend/src/router/index.ts`, adicionar à lista de rotas públicas, após `/reset-password`:

```typescript
    {
      path: '/auth/callback',
      name: 'keycloak-callback',
      component: () => import('@/views/auth/KeycloakCallbackView.vue'),
    },
```

- [ ] **Step 5: Adicionar botão Keycloak ao `LoginView.vue`**

Em `frontend/src/views/auth/LoginView.vue`, adicionar no `<script setup>`:

```typescript
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

const keycloakEnabled = ref(false)
const keycloakLoginUrl = '/auth/keycloak/login'

onMounted(async () => {
  try {
    const resp = await api.getPublicConfig()
    keycloakEnabled.value = resp.data.keycloak_enabled
  } catch {
    keycloakEnabled.value = false
  }
})
```

No template, após o link "Esqueceu a senha?" e antes do fechamento do card, adicionar:

```html
        <div v-if="keycloakEnabled" class="mt-4">
          <div class="relative">
            <div class="absolute inset-0 flex items-center">
              <div class="w-full border-t border-slate-600"></div>
            </div>
            <div class="relative flex justify-center text-xs">
              <span class="px-2 bg-slate-800 text-slate-500">ou</span>
            </div>
          </div>
          <a
            :href="keycloakLoginUrl"
            class="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border border-slate-600 px-4 py-3 text-sm text-slate-300 hover:bg-slate-700 transition-colors"
          >
            <span>🔑</span>
            Entrar com Keycloak
          </a>
        </div>
```

- [ ] **Step 6: Adicionar `auth_type` ao form MCP em `McpServidoresView.vue`**

Em `frontend/src/views/McpServidoresView.vue`, adicionar `auth_type: 'none'` ao objeto `form` inicial:

```typescript
const form = ref({
  nome: '',
  descricao: '',
  transport: 'stdio',
  command: '',
  args: '',
  env: '',
  url: '',
  auth_type: 'none',
  ativo: true,
})
```

Em `abrirEditar`, adicionar:
```typescript
    auth_type: server.auth_type ?? 'none',
```

No `payload` da função `salvar`, adicionar:
```typescript
      auth_type: form.value.auth_type,
```

No template, adicionar o campo após o campo "Transporte":

```html
          <div>
            <label class="block text-xs font-medium text-gray-600 dark:text-slate-300 mb-2">Autenticação</label>
            <div class="flex gap-3 flex-wrap">
              <label class="flex items-center gap-2 cursor-pointer">
                <input v-model="form.auth_type" type="radio" value="none" class="accent-indigo-600" />
                <span class="text-sm text-gray-700 dark:text-slate-200">Nenhuma</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input v-model="form.auth_type" type="radio" value="static" class="accent-indigo-600" />
                <span class="text-sm text-gray-700 dark:text-slate-200">Token estático</span>
                <span class="text-xs text-gray-400 dark:text-slate-500">(env Authorization=)</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input v-model="form.auth_type" type="radio" value="keycloak" class="accent-indigo-600" />
                <span class="text-sm text-gray-700 dark:text-slate-200">Keycloak</span>
                <span class="text-xs text-gray-400 dark:text-slate-500">(token do usuário logado)</span>
              </label>
            </div>
          </div>
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/client.ts \
        frontend/src/stores/auth.ts \
        frontend/src/views/auth/KeycloakCallbackView.vue \
        frontend/src/router/index.ts \
        frontend/src/views/auth/LoginView.vue \
        frontend/src/views/McpServidoresView.vue

git commit -m "feat(keycloak): frontend — botão SSO, callback view, auth_type no MCP"
```

---

## Task 11: Smoke Test End-to-End

**Goal:** Verificar o fluxo completo de login Keycloak + MCP forwarding com o docker-compose dev.

- [ ] **Step 1: Subir os serviços**

```bash
docker compose up -d
docker compose logs -f keycloak 2>&1 | grep -m1 "Keycloak.*started"
```

Aguardar até ver `Keycloak 26.x.x on` ou `started in`.

- [ ] **Step 2: Verificar realm importado**

Abrir `http://localhost:8180` → logar com `admin/admin` → confirmar realm `docagent` existe com o client `docagent-backend`.

- [ ] **Step 3: Testar `/api/config/public`**

```bash
curl http://localhost:8000/api/config/public | python3 -m json.tool
```

Esperado:
```json
{
  "keycloak_enabled": true,
  "keycloak_url": "http://keycloak:8080",
  "keycloak_realm": "docagent",
  "keycloak_client_id": "docagent-backend"
}
```

- [ ] **Step 4: Testar login via browser**

Acessar `http://localhost:5173/login` → confirmar botão "Entrar com Keycloak" visível → clicar → Keycloak login form → credenciais `teste` / `teste123` → confirmar redirecionamento para `/conversa` com sessão ativa.

- [ ] **Step 5: Testar MCP SSE com auth_type=keycloak**

Criar um MCP server SSE de teste com `auth_type=keycloak` na tela de servidores MCP. Iniciar uma conversa com um agente que usa esse servidor. Verificar nos logs da API que o `Authorization: Bearer <token>` está sendo injetado.

```bash
docker compose logs api | grep -i "keycloak"
```

- [ ] **Step 6: Rodar suite completa de testes**

```bash
uv run pytest tests/ -q 2>&1 | tail -10
```

Esperado: todos os testes passando.

- [ ] **Step 7: Commit final**

```bash
git add .
git commit -m "chore(keycloak): smoke test ok — fase Keycloak completa"
```

---

## Self-Review

**Spec coverage:**
- [x] Auth híbrida: login local + Keycloak coexistem → Task 6 (router) + Task 10 (frontend)
- [x] Toda middleware auth existente intacta → `current_user.py` não alterado
- [x] MCP servers ganham `auth_type` → Task 1 (model) + Task 10 (UI)
- [x] Token forwarding dinâmico → Task 7-8 (`_build_mcp_headers`)
- [x] Keycloak no docker-compose → Task 9
- [x] Identity por email → Task 3-4 (`criar_ou_linkar_usuario`)
- [x] Redis `keycloak:rt:{id}` → Task 4 (`service.py`)
- [x] state anti-CSRF → Task 6 (`router.py`)
- [x] JWKS cache via PyJWKClient → Task 2 (`client.py`)
- [x] `GET /api/config/public` → Task 6 (`config_router`)
- [x] Frontend botão SSO condicional → Task 10
- [x] Frontend rota `/auth/callback` → Task 10
- [x] stdio + keycloak via `KEYCLOAK_TOKEN` env var → Task 8
- [x] Refresh token rotacionado salvo de volta → Task 4 (`get_access_token`)
- [x] `descobrir_tools` não tem `usuario_id` → usa `_build_mcp_headers(usuario_id=None)` → retorna `{}` → usa `auth_type="static"` como workaround documentado

**Gaps encontrados:** Nenhum.

**Type consistency:** `_build_mcp_headers` definida em Task 7 com assinatura `(server, usuario_id, redis) -> dict` e importada em `test_mcp_token_forwarding.py` com o mesmo nome. `KeycloakService.get_access_token` definida em Task 4 e mockada em Task 7 com o mesmo path `docagent.mcp_server.services.KeycloakService.get_access_token` ✓.
