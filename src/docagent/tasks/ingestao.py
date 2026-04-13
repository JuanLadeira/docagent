"""
Fase 23 — Celery task para ingestão assíncrona de documentos PDF.

Remove o processo de ingestão do request path do uvicorn:
o endpoint de upload retorna 202 Accepted imediatamente e despacha esta task.
"""
import asyncio
import base64
import logging

from docagent.celery_app import celery

log = logging.getLogger(__name__)


async def _ingerir(agente_id: int, filename: str, content: bytes) -> None:
    """Executa o pipeline de ingestão no banco e no ChromaDB."""
    from docagent.database import AsyncSessionLocal
    from docagent.agente.documento_service import DocumentoService

    async with AsyncSessionLocal() as db:
        svc = DocumentoService(db)
        await svc.create(agente_id, filename, content)


@celery.task(bind=True, max_retries=3, default_retry_delay=30, name="docagent.tasks.ingerir_documento")
def ingerir_documento_task(self, agente_id: int, filename: str, content_b64: str) -> dict:
    """
    Ingest a PDF document for an agent asynchronously.

    Args:
        agente_id: ID do agente dono do documento.
        filename: Nome do arquivo original.
        content_b64: Conteúdo do PDF em base64.

    Returns:
        dict com 'status' e 'agente_id'.
    """
    try:
        content = base64.b64decode(content_b64)
        asyncio.run(_ingerir(agente_id, filename, content))
        log.info("Documento '%s' ingerido para agente %d", filename, agente_id)
        return {"status": "ok", "agente_id": agente_id, "filename": filename}
    except Exception as exc:
        log.error("Falha ao ingerir '%s' para agente %d: %s", filename, agente_id, exc)
        raise self.retry(exc=exc)
