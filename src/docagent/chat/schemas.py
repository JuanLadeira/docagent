"""
Fase 5/6 — Schemas Pydantic para a camada de API.

Define os contratos de entrada e saida sem logica de negocio.
"""
from pydantic import BaseModel, field_validator


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    agent_id: str = "1"
    conversa_id: int | None = None

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be empty")
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
