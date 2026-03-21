"""
Fase 6 — IngestService: encapsula o pipeline de ingestao de PDFs.

Recebe bytes do upload HTTP, salva em arquivo temporario, executa o
pipeline ingest.py e retorna metadados da ingestao.
"""
import tempfile
from pathlib import Path

from docagent.ingest import load_pdfs, split_documents, build_vectorstore


class IngestService:
    def ingest(self, filename: str, content: bytes, session_id: str) -> dict:
        """
        Ingere um PDF e persiste no ChromaDB com a collection da sessao.

        Parametros:
            filename:   nome original do arquivo
            content:    conteudo binario do PDF
            session_id: identificador da sessao — vira o collection_name

        Retorna:
            {"filename": ..., "chunks": ..., "collection_id": session_id}
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / filename
            file_path.write_bytes(content)

            docs = load_pdfs(tmp_dir)
            chunks = split_documents(docs)
            build_vectorstore(chunks, collection_name=session_id)

        return {
            "filename": filename,
            "chunks": len(chunks),
            "collection_id": session_id,
        }
