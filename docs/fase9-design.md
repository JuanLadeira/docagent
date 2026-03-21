# Fase 9 — SaaS: Planos, Assinaturas e Admin Panel

## Objetivo

Completar o modelo de negócio SaaS com entidades `Plano` e `Assinatura`,
expor o admin panel completo via API, e aplicar limites de uso baseados
no plano contratado pelo tenant.

Pré-requisito: **Fase 8 concluída** (database.py, auth, tenant, usuario integrados).

---

## Estrutura de arquivos

```
src/docagent/
├── plano/
│   ├── __init__.py
│   ├── models.py               ← NOVO: Plano
│   ├── schemas.py              ← NOVO: PlanoCreate, PlanoResponse
│   ├── services.py             ← NOVO: PlanoService
│   └── router.py               ← NOVO: /api/admin/planos (via admin router)
├── assinatura/
│   ├── __init__.py
│   ├── models.py               ← NOVO: Assinatura
│   ├── schemas.py              ← NOVO: AssinaturaCreate, AssinaturaResponse
│   ├── services.py             ← NOVO: AssinaturaService
│   └── router.py               ← NOVO: /api/admin/assinaturas
├── admin/
│   └── router.py               ← incluir routers de plano e assinatura
└── api.py                      ← sem mudanças (admin_router já registrado)

alembic/versions/
└── 0002_planos_assinaturas.py  ← NOVA migration
```

---

## `plano/models.py`

```python
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from docagent.database import Base


class Plano(Base):
    __tablename__ = "planos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(unique=True)
    descricao: Mapped[str] = mapped_column(default="")
    limite_documentos: Mapped[int] = mapped_column(default=10)
    limite_sessoes: Mapped[int] = mapped_column(default=5)
    preco_mensal: Mapped[Decimal] = mapped_column(default=Decimal("0.00"))
    ativo: Mapped[bool] = mapped_column(default=True)

    assinaturas: Mapped[list["Assinatura"]] = relationship(
        back_populates="plano", cascade="all, delete-orphan"
    )
```

---

## `assinatura/models.py`

```python
import enum
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Enum
from docagent.database import Base


class AssinaturaStatus(str, enum.Enum):
    ATIVA = "ativa"
    CANCELADA = "cancelada"
    SUSPENSA = "suspensa"


class Assinatura(Base):
    __tablename__ = "assinaturas"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    plano_id: Mapped[int] = mapped_column(ForeignKey("planos.id", ondelete="RESTRICT"))
    status: Mapped[AssinaturaStatus] = mapped_column(
        Enum(AssinaturaStatus, name="assinaturastatus"),
        default=AssinaturaStatus.ATIVA,
    )
    data_inicio: Mapped[date]
    data_fim: Mapped[date | None] = mapped_column(default=None)

    tenant: Mapped["Tenant"] = relationship(back_populates="assinaturas")
    plano: Mapped["Plano"] = relationship(back_populates="assinaturas")
```

---

## Schemas

### `plano/schemas.py`

```python
from decimal import Decimal
from pydantic import BaseModel

class PlanoCreate(BaseModel):
    nome: str
    descricao: str = ""
    limite_documentos: int = 10
    limite_sessoes: int = 5
    preco_mensal: Decimal = Decimal("0.00")
    ativo: bool = True

class PlanoResponse(PlanoCreate):
    id: int
    model_config = {"from_attributes": True}
```

### `assinatura/schemas.py`

```python
from datetime import date
from pydantic import BaseModel
from docagent.assinatura.models import AssinaturaStatus

class AssinaturaCreate(BaseModel):
    tenant_id: int
    plano_id: int
    data_inicio: date
    data_fim: date | None = None

class AssinaturaResponse(AssinaturaCreate):
    id: int
    status: AssinaturaStatus
    model_config = {"from_attributes": True}

class AssinaturaUpdate(BaseModel):
    status: AssinaturaStatus
    data_fim: date | None = None
```

---

## Endpoints Admin

Todos protegidos por `CurrentAdmin` (definido na Fase 8).

### Planos — `plano/router.py`

```python
router = APIRouter(prefix="/api/admin/planos", tags=["admin-planos"])

GET    /api/admin/planos          → list[PlanoResponse]   # listar todos
POST   /api/admin/planos          → PlanoResponse          # criar
GET    /api/admin/planos/{id}     → PlanoResponse          # detalhar
PUT    /api/admin/planos/{id}     → PlanoResponse          # atualizar
DELETE /api/admin/planos/{id}     → 204                    # remover (se sem assinaturas ativas)
```

### Assinaturas — `assinatura/router.py`

```python
router = APIRouter(prefix="/api/admin/assinaturas", tags=["admin-assinaturas"])

GET    /api/admin/assinaturas            → list[AssinaturaResponse]
POST   /api/admin/assinaturas            → AssinaturaResponse
GET    /api/admin/assinaturas/{id}       → AssinaturaResponse
PUT    /api/admin/assinaturas/{id}       → AssinaturaResponse  # atualizar status/data_fim
```

---

## Limites de uso por plano

Dependência que verifica se o tenant pode fazer upload de documento:

```python
async def check_document_limit(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Lança 403 se tenant atingiu o limite de documentos do plano."""
    assinatura = await get_assinatura_ativa(db, current_user.tenant_id)
    if assinatura is None:
        raise HTTPException(403, "Sem assinatura ativa")
    count = await count_documents(db, current_user.tenant_id)
    if count >= assinatura.plano.limite_documentos:
        raise HTTPException(
            403,
            f"Limite de {assinatura.plano.limite_documentos} documentos atingido"
        )
```

Aplicar em `routers/documents.py`:

```python
@router.post("/documents/upload", dependencies=[Depends(check_document_limit)])
async def upload_document(...):
    ...
```

---

## Migration

```bash
# Após criar os models
uv run alembic revision --autogenerate -m "planos_assinaturas"
uv run alembic upgrade head
```

---

## Plano TDD

| Arquivo de teste | O que valida |
|---|---|
| `tests/test_plano.py` | CRUD planos; delete falha se há assinatura ativa |
| `tests/test_assinatura.py` | Criar assinatura, atualizar status, listar por tenant |
| `tests/test_limites.py` | Upload bloqueado quando sem assinatura; upload bloqueado ao atingir limite |
| `tests/test_admin_planos.py` | Admin acessa /api/admin/planos; usuário comum → 401 |

---

## Plano de verificação

```bash
# Migrations
uv run alembic upgrade head

# Testes
uv run pytest tests/test_plano.py tests/test_assinatura.py tests/test_limites.py -v

# Smoke test — criar plano
curl -X POST http://localhost:8000/api/admin/planos \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"nome": "Starter", "limite_documentos": 5, "preco_mensal": "29.90"}'

# Smoke test — criar assinatura
curl -X POST http://localhost:8000/api/admin/assinaturas \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": 1, "plano_id": 1, "data_inicio": "2026-03-21"}'
```

---

## Princípios aplicados

| Princípio | Onde |
|---|---|
| **SRP** | `PlanoService` cuida só de planos; `AssinaturaService` cuida só de assinaturas |
| **Guard dependency** | `check_document_limit` é uma dep FastAPI reutilizável, não lógica espalhada no router |
| **Integridade referencial** | `RESTRICT` no FK plano_id impede deletar plano com assinaturas ativas |
| **Status explícito** | `AssinaturaStatus` enum evita strings mágicas no banco |
