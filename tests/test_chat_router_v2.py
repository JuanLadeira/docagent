"""
Testes TDD para as evolucoes do router de chat na Fase 6.

Cobre: agent_id no ChatRequest, selecao de agente por sessao,
e validacao do campo agent_id contra o AGENT_REGISTRY.
"""
import json
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient


def make_mock_service(answer="resposta mock"):
    service = MagicMock()
    service.stream.return_value = iter([
        f"data: {json.dumps({'type': 'answer', 'content': answer})}\n\n",
        f"data: {json.dumps({'type': 'done'})}\n\n",
    ])
    service.delete_session.return_value = True
    return service


@pytest.fixture
def client():
    from docagent.api import app
    from docagent.dependencies import get_chat_service

    mock_service = make_mock_service()
    app.dependency_overrides[get_chat_service] = lambda: mock_service

    yield TestClient(app), mock_service

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Schema ChatRequest — campo agent_id
# ---------------------------------------------------------------------------

class TestChatRequestAgentId:
    def test_default_agent_id_is_doc_analyst(self):
        from docagent.schemas.chat import ChatRequest
        req = ChatRequest(question="teste")
        assert req.agent_id == "doc-analyst"

    def test_accepts_custom_agent_id(self):
        from docagent.schemas.chat import ChatRequest
        req = ChatRequest(question="teste", agent_id="web-researcher")
        assert req.agent_id == "web-researcher"

    def test_unknown_agent_id_raises_validation_error(self):
        """agent_id deve ser validado contra o AGENT_REGISTRY."""
        from pydantic import ValidationError
        from docagent.schemas.chat import ChatRequest
        with pytest.raises(ValidationError):
            ChatRequest(question="teste", agent_id="agente-inexistente")


# ---------------------------------------------------------------------------
# Endpoint POST /chat com agent_id
# ---------------------------------------------------------------------------

class TestChatEndpointAgentId:
    def test_valid_agent_id_returns_200(self, client):
        tc, _ = client
        response = tc.post("/chat", json={
            "question": "pergunta",
            "agent_id": "doc-analyst",
        })
        assert response.status_code == 200

    def test_web_researcher_agent_returns_200(self, client):
        tc, _ = client
        response = tc.post("/chat", json={
            "question": "pergunta",
            "agent_id": "web-researcher",
        })
        assert response.status_code == 200

    def test_unknown_agent_id_returns_422(self, client):
        tc, _ = client
        response = tc.post("/chat", json={
            "question": "pergunta",
            "agent_id": "agente-que-nao-existe",
        })
        assert response.status_code == 422

    def test_missing_agent_id_uses_default(self, client):
        """Sem agent_id, deve usar doc-analyst e retornar 200."""
        tc, _ = client
        response = tc.post("/chat", json={"question": "pergunta"})
        assert response.status_code == 200

    def test_stream_still_works_with_agent_id(self, client):
        tc, _ = client
        response = tc.post("/chat", json={
            "question": "pergunta",
            "agent_id": "web-researcher",
        })
        assert "done" in response.text
