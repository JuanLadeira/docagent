from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class TenantBase(BaseModel):
    nome: str
    descricao: str | None = None


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    nome: str | None = None
    descricao: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None


class TenantPublic(TenantBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key_set: bool = False

    @model_validator(mode="before")
    @classmethod
    def _compute_api_key_set(cls, data: Any) -> Any:
        """Converte llm_api_key (do modelo SQLAlchemy) em llm_api_key_set (bool)."""
        if hasattr(data, "llm_api_key"):
            # SQLAlchemy model — não podemos setar atributos, então passamos como dict
            return {
                "nome": data.nome,
                "descricao": data.descricao,
                "id": data.id,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
                "llm_provider": data.llm_provider,
                "llm_model": data.llm_model,
                "llm_api_key_set": bool(data.llm_api_key),
            }
        return data


class TenantLlmConfigUpdate(BaseModel):
    """Usado pelo tenant owner para configurar seu próprio LLM."""
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
