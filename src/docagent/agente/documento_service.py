"""
Fase 15 — DocumentoService: gerencia documentos PDF indexados por agente.

Cada agente tem sua própria collection ChromaDB: agente_{agente_id}.
O registro no banco (tabela Documento) rastreia quais arquivos foram indexados.
"""
import asyncio
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.agente.models import Documento
from docagent.database import AsyncDBSession
from docagent.rag.ingest import delete_document_from_vectorstore
from docagent.rag.ingest_service import IngestService


class DocumentoService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_agente(self, agente_id: int) -> list[Documento]:
        """Lista todos os documentos indexados de um agente."""
        r = await self.session.execute(
            select(Documento)
            .where(Documento.agente_id == agente_id)
            .order_by(Documento.id)
        )
        return list(r.scalars().all())

    async def get_by_id(self, doc_id: int) -> Documento | None:
        """Busca um documento por ID."""
        return await self.session.get(Documento, doc_id)

    async def create(self, agente_id: int, filename: str, content: bytes) -> Documento:
        """
        Ingere o PDF no ChromaDB (collection agente_{agente_id}) e persiste o registro.

        Raises:
            ValueError: se já existe um documento com o mesmo filename para o agente.
        """
        existing = await self.session.execute(
            select(Documento).where(
                Documento.agente_id == agente_id,
                Documento.filename == filename,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Documento '{filename}' já indexado para este agente")

        collection_name = f"agente_{agente_id}"
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: IngestService().ingest(filename, content, collection_name),
        )

        doc = Documento(agente_id=agente_id, filename=filename, chunks=result["chunks"])
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def delete(self, doc_id: int, agente_id: int | None = None) -> bool:
        """
        Remove os chunks do ChromaDB e o registro do banco.

        Args:
            doc_id: ID do documento a remover.
            agente_id: Se fornecido, verifica que o documento pertence a este agente
                       antes de deletar (previne IDOR cross-agente).

        Returns:
            True se deletado, False se não encontrado.
        """
        doc = await self.get_by_id(doc_id)
        if not doc:
            return False

        # Verificação de ownership: impede que um agente delete documentos de outro
        if agente_id is not None and doc.agente_id != agente_id:
            return False

        collection_name = f"agente_{doc.agente_id}"
        filename = doc.filename
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: delete_document_from_vectorstore(filename, collection_name),
        )

        await self.session.delete(doc)
        await self.session.flush()
        return True


def get_documento_service(session: AsyncDBSession) -> "DocumentoService":
    return DocumentoService(session)


DocumentoServiceDep = Annotated[DocumentoService, Depends(get_documento_service)]
