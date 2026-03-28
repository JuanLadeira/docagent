"""
Fase 5 — Dependencias FastAPI.

Usa lru_cache para garantir instancias unicas por processo (singleton).
get_chat_service e criado por request para receber as dependencias injetadas.
"""
from functools import lru_cache

from docagent.chat.session import SessionManager
from docagent.rag.ingest_service import IngestService


@lru_cache(maxsize=1)
def get_session_manager() -> SessionManager:
    return SessionManager()


def get_ingest_service() -> IngestService:
    return IngestService()
