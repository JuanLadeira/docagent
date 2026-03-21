"""
Fase 5 — Schemas Pydantic para a camada de API.

Define os contratos de entrada e saida sem logica de negocio.
"""
from pydantic import BaseModel, field_validator


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("question must not be empty")
        return v


class HealthResponse(BaseModel):
    status: str
