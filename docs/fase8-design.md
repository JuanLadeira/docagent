# Fase 8 — Auth, Tenant e Usuario: Integração SaaS

## Objetivo

Integrar os apps existentes (`auth/`, `tenant/`, `usuario/`, `admin/`) ao DocAgent,
adaptando o namespace de importações de `app.*` para `docagent.*`, criando o setup
de banco de dados SQLAlchemy async e registrando os routers na API.

Ao final desta fase, o DocAgent terá:
- Autenticação JWT para usuários multi-tenant
- CRUD completo de tenants e usuários
- Login separado para admins globais
- Migrações Alembic

---

## Estrutura de arquivos

```
src/docagent/
├── database.py                  ← NOVO: engine + Base + get_db
├── auth/
│   ├── router.py                ← adaptar imports de app.* → docagent.*
│   ├── security.py              ← adaptar imports
│   ├── schemas.py               ← adaptar imports
│   └── current_user.py          ← adaptar imports
├── tenant/
│   ├── models.py                ← adaptar Base import
│   ├── router.py                ← adaptar imports
│   ├── services.py              ← adaptar imports
│   └── schemas.py               ← adaptar imports
├── usuario/
│   ├── models.py                ← adaptar Base import
│   ├── router.py                ← adaptar imports
│   ├── services.py              ← adaptar imports
│   └── schemas.py               ← adaptar imports
├── admin/
│   ├── models.py                ← adaptar Base import
│   ├── router.py                ← remover rotas WhatsApp, adaptar imports
│   └── security.py              ← NOVO: get_current_admin() separado
├── api.py                       ← incluir novos routers
└── dependencies.py              ← adicionar get_db

alembic/                         ← NOVO: configuração de migrações
  env.py
  versions/
    0001_initial.py
```

---

## `database.py` — novo

```python
"""
Setup SQLAlchemy async para o DocAgent.
DATABASE_URL deve ser definida em .env:
  DOCAGENT_DB_URL=postgresql+asyncpg://user:pass@localhost/docagent
  ou para SQLite em dev:
  DOCAGENT_DB_URL=sqlite+aiosqlite:///./docagent.db
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


DATABASE_URL = os.getenv("DOCAGENT_DB_URL", "sqlite+aiosqlite:///./docagent.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI dependency — injeta sessão async por request."""
    async with AsyncSessionLocal() as session:
        yield session
```

---

## Adaptação de imports

Todo arquivo que contiver `from app.` deve ser atualizado:

| Import antigo | Import novo |
|---|---|
| `from app.database.base import Base` | `from docagent.database import Base` |
| `from app.auth.security import ...` | `from docagent.auth.security import ...` |
| `from app.auth.current_user import ...` | `from docagent.auth.current_user import ...` |
| `from app.tenant.services import ...` | `from docagent.tenant.services import ...` |
| `from app.tenant.models import ...` | `from docagent.tenant.models import ...` |
| `from app.usuario.models import ...` | `from docagent.usuario.models import ...` |

Script de verificação rápida:
```bash
grep -r "from app\." src/docagent/{auth,tenant,usuario,admin}/
# Saída deve ser vazia após a adaptação
```

---

## `admin/security.py` — novo

Auth JWT separado para admins (não conflita com o auth de usuários).

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from docagent.admin.models import Admin
from docagent.database import get_db

admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login")

async def get_current_admin(
    token: str = Depends(admin_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """Valida JWT de admin. Lança 401 se inválido."""
    ...

CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]
```

---

## `admin/router.py` — limpeza

Remover rotas que não se aplicam ao DocAgent:
- `POST /api/admin/whatsapp/...` — remover
- `GET /api/admin/whatsapp-instancias` — remover

Manter:
- `POST /api/admin/login`
- `GET/POST/PUT/DELETE /api/admin/tenants`
- `GET/POST/PUT/DELETE /api/admin/planos` ← implementado na Fase 9
- `GET /api/admin/me`
- `POST /api/admin/admins`

---

## `api.py` — integração

```python
from docagent.auth.router import router as auth_router
from docagent.tenant.router import router as tenant_router
from docagent.usuario.router import router as usuario_router
from docagent.admin.router import router as admin_router

app.include_router(auth_router)           # /auth/login, /auth/forgot-password, ...
app.include_router(tenant_router)         # /api/tenants
app.include_router(usuario_router)        # /api/usuarios, /api/usuarios/me
app.include_router(admin_router)          # /api/admin/*
```

---

## Alembic

```bash
# Inicializar
uv run alembic init alembic

# alembic/env.py — configurar target_metadata
from docagent.database import Base
from docagent.tenant.models import Tenant      # importar todos os modelos
from docagent.usuario.models import Usuario
from docagent.admin.models import Admin
target_metadata = Base.metadata

# Gerar migration inicial
uv run alembic revision --autogenerate -m "initial"

# Aplicar
uv run alembic upgrade head
```

---

## Variáveis de ambiente — `.env`

```
DOCAGENT_DB_URL=sqlite+aiosqlite:///./docagent.db
SECRET_KEY=<chave_jwt_forte>
ADMIN_SECRET_KEY=<chave_jwt_admin_separada>
```

---

## Plano TDD

| Arquivo de teste | O que valida |
|---|---|
| `tests/test_auth.py` | Login retorna JWT; token inválido → 401; forgot-password → email enviado |
| `tests/test_tenant.py` | CRUD completo; admin pode criar; usuário comum não pode |
| `tests/test_usuario.py` | GET /me retorna usuário logado; OWNER cria membro; MEMBER não cria |
| `tests/test_admin_auth.py` | Login admin retorna JWT admin; JWT user não acessa /api/admin |

Cada test module usa `pytest-asyncio` com banco SQLite in-memory:

```python
@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal(engine) as session:
        yield session
```

---

## Plano de verificação

```bash
# Aplicar migrações
uv run alembic upgrade head

# Rodar testes
uv run pytest tests/test_auth.py tests/test_tenant.py tests/test_usuario.py -v

# Smoke test manual
curl -X POST http://localhost:8000/auth/login \
  -d "username=owner&password=senha123" -H "Content-Type: application/x-www-form-urlencoded"
# → { "access_token": "...", "token_type": "bearer" }

curl http://localhost:8000/api/usuarios/me \
  -H "Authorization: Bearer <token>"
# → { "id": 1, "username": "owner", "role": "OWNER", ... }
```

---

## Princípios aplicados

| Princípio | Onde |
|---|---|
| **Separation of concerns** | Auth de admin separado do auth de usuário (tokens diferentes) |
| **DIP** | Routers dependem de `get_db` via Depends, não instanciam sessões diretamente |
| **Migration-first** | Alembic garante schema em sync com models em todos os ambientes |
| **Test isolation** | Banco SQLite in-memory por fixture, sem estado compartilhado entre testes |
