"""
Fase 5/6 — Schemas Pydantic para a camada de API.

Define os contratos de entrada e saida sem logica de negocio.
"""
from pydantic import BaseModel, field_validator


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    agent_id: str = "doc-analyst"

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be empty")
        return v

    @field_validator("agent_id")
    @classmethod
    def agent_must_exist(cls, v: str) -> str:
        from docagent.agents.registry import AGENT_REGISTRY
        if v not in AGENT_REGISTRY:
            raise ValueError(
                f"Agente '{v}' nao encontrado. "
                f"Disponiveis: {list(AGENT_REGISTRY.keys())}"
            )
        return v


class HealthResponse(BaseModel):
    status: str


class SkillInfo(BaseModel):
    name: str
    label: str
    icon: str
    description: str


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    skills: list[SkillInfo]


class UploadResponse(BaseModel):
    filename: str
    chunks: int
    collection_id: str
