"""
Fase 5 — Dependencias FastAPI.

Usa lru_cache para garantir instancias unicas por processo (singleton).
get_chat_service e criado por request para receber as dependencias injetadas.
"""
from functools import lru_cache

from fastapi import Depends

from docagent.doc_agent import DocAgent
from docagent.session import SessionManager
from docagent.services.chat_service import ChatService
from docagent.services.ingest_service import IngestService


@lru_cache(maxsize=1)
def get_agent() -> DocAgent:
    return DocAgent().build()


@lru_cache(maxsize=1)
def get_session_manager() -> SessionManager:
    return SessionManager()


def get_chat_service(
    agent: DocAgent = Depends(get_agent),
    sessions: SessionManager = Depends(get_session_manager),
) -> ChatService:
    return ChatService(agent, sessions)


def get_ingest_service() -> IngestService:
    return IngestService()
