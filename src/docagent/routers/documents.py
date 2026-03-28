"""
Fase 6 — Router de documentos: upload de PDFs para ingestão no RAG.
"""
from fastapi import APIRouter, Depends, Form, UploadFile, File

from docagent.schemas.chat import UploadResponse
from docagent.services.ingest_service import IngestService
from docagent.dependencies import get_ingest_service

router = APIRouter()


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form("default"),
    service: IngestService = Depends(get_ingest_service),
) -> UploadResponse:
    """Recebe um PDF e o ingere no ChromaDB da sessão."""
    content = await file.read()
    result = service.ingest(file.filename, content, session_id)
    return UploadResponse(**result)
