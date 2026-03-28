"""
Testes TDD para POST /documents/upload (routers/documents.py).

Valida upload de PDF com delegacao ao IngestService via dependency_overrides.
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

FAKE_PDF = b"%PDF-1.4 fake content"


def make_mock_ingest_service(filename="test.pdf", chunks=5, collection_id="s-1"):
    service = MagicMock()
    service.ingest.return_value = {
        "filename": filename,
        "chunks": chunks,
        "collection_id": collection_id,
    }
    return service


@pytest.fixture
def client():
    from docagent.api import app
    from docagent.dependencies import get_ingest_service

    mock_service = make_mock_ingest_service()
    app.dependency_overrides[get_ingest_service] = lambda: mock_service

    yield TestClient(app), mock_service

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Endpoint basico
# ---------------------------------------------------------------------------

class TestUploadEndpoint:
    def test_upload_returns_200(self, client):
        tc, _ = client
        response = tc.post(
            "/documents/upload",
            files={"file": ("test.pdf", FAKE_PDF, "application/pdf")},
        )
        assert response.status_code == 200

    def test_upload_without_file_returns_422(self, client):
        tc, _ = client
        assert tc.post("/documents/upload").status_code == 422

    def test_upload_returns_filename(self, client):
        tc, _ = client
        response = tc.post(
            "/documents/upload",
            files={"file": ("meu-doc.pdf", FAKE_PDF, "application/pdf")},
        )
        assert response.json()["filename"] == "test.pdf"  # mock retorna "test.pdf"

    def test_upload_returns_chunk_count(self, client):
        tc, _ = client
        response = tc.post(
            "/documents/upload",
            files={"file": ("test.pdf", FAKE_PDF, "application/pdf")},
        )
        assert response.json()["chunks"] == 5

    def test_upload_returns_collection_id(self, client):
        tc, _ = client
        response = tc.post(
            "/documents/upload",
            files={"file": ("test.pdf", FAKE_PDF, "application/pdf")},
            params={"session_id": "s-1"},
        )
        assert "collection_id" in response.json()


# ---------------------------------------------------------------------------
# Delegacao ao IngestService
# ---------------------------------------------------------------------------

class TestUploadDelegation:
    def test_delegates_to_ingest_service(self, client):
        tc, mock_service = client
        tc.post(
            "/documents/upload",
            files={"file": ("doc.pdf", FAKE_PDF, "application/pdf")},
        )
        mock_service.ingest.assert_called_once()

    def test_passes_filename_to_service(self, client):
        tc, mock_service = client
        tc.post(
            "/documents/upload",
            files={"file": ("relatorio.pdf", FAKE_PDF, "application/pdf")},
        )
        call_args = mock_service.ingest.call_args[0]
        assert call_args[0] == "relatorio.pdf"

    def test_passes_content_bytes_to_service(self, client):
        tc, mock_service = client
        tc.post(
            "/documents/upload",
            files={"file": ("doc.pdf", FAKE_PDF, "application/pdf")},
        )
        call_args = mock_service.ingest.call_args[0]
        assert isinstance(call_args[1], bytes)
        assert len(call_args[1]) > 0

    def test_passes_session_id_to_service(self, client):
        """session_id é lido do Form body (não query param)."""
        tc, mock_service = client
        tc.post(
            "/documents/upload",
            files={"file": ("doc.pdf", FAKE_PDF, "application/pdf")},
            data={"session_id": "minha-sessao"},
        )
        call_args = mock_service.ingest.call_args[0]
        assert call_args[2] == "minha-sessao"

    def test_default_session_id_is_default(self, client):
        tc, mock_service = client
        tc.post(
            "/documents/upload",
            files={"file": ("doc.pdf", FAKE_PDF, "application/pdf")},
        )
        call_args = mock_service.ingest.call_args[0]
        assert call_args[2] == "default"
