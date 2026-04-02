"""
Testes TDD para GET /agents (routers/agents.py).

Valida a listagem de agentes ativos com suas skills.
Agentes agora vêm do banco de dados (ID numérico como string).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient


def _make_mock_agentes():
    """Dois agentes fake simulando o que viria do banco."""
    a1 = MagicMock(id=1, nome="Analista de Documentos", descricao="Analisa PDFs", skill_names=["rag_search", "web_search"], ativo=True)
    a2 = MagicMock(id=2, nome="Pesquisador Web", descricao="Busca na web", skill_names=["web_search"], ativo=True)
    return [a1, a2]


@pytest.fixture
def client():
    from docagent.api import app
    from docagent.agente.services import get_agente_service
    from docagent.auth.current_user import get_current_user

    mock_user = MagicMock(id=1, tenant_id=1, username="owner")
    svc = MagicMock()
    svc.get_all = AsyncMock(return_value=_make_mock_agentes())
    app.dependency_overrides[get_agente_service] = lambda: svc
    app.dependency_overrides[get_current_user] = lambda: mock_user

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestListAgents:
    def test_returns_200(self, client):
        assert client.get("/agents").status_code == 200

    def test_returns_list(self, client):
        response = client.get("/agents")
        assert isinstance(response.json(), list)

    def test_list_is_not_empty(self, client):
        response = client.get("/agents")
        assert len(response.json()) >= 1

    def test_returns_two_agents(self, client):
        response = client.get("/agents")
        assert len(response.json()) == 2

    def test_ids_are_numeric_strings(self, client):
        """IDs agora são numéricos (string do id do banco)."""
        response = client.get("/agents")
        ids = [a["id"] for a in response.json()]
        assert "1" in ids
        assert "2" in ids


class TestAgentInfoShape:
    def test_agent_has_id(self, client):
        agent = client.get("/agents").json()[0]
        assert "id" in agent

    def test_agent_has_name(self, client):
        agent = client.get("/agents").json()[0]
        assert "name" in agent

    def test_agent_has_description(self, client):
        agent = client.get("/agents").json()[0]
        assert "description" in agent

    def test_agent_has_skills_list(self, client):
        agent = client.get("/agents").json()[0]
        assert "skills" in agent
        assert isinstance(agent["skills"], list)

    def test_skill_has_name(self, client):
        skill = client.get("/agents").json()[0]["skills"][0]
        assert "name" in skill

    def test_skill_has_label(self, client):
        skill = client.get("/agents").json()[0]["skills"][0]
        assert "label" in skill

    def test_skill_has_icon(self, client):
        skill = client.get("/agents").json()[0]["skills"][0]
        assert "icon" in skill

    def test_skill_has_description(self, client):
        skill = client.get("/agents").json()[0]["skills"][0]
        assert "description" in skill


class TestAgentSkills:
    def test_doc_analyst_has_two_skills(self, client):
        agents = client.get("/agents").json()
        doc_analyst = next(a for a in agents if a["id"] == "1")
        assert len(doc_analyst["skills"]) == 2

    def test_doc_analyst_has_rag_search_skill(self, client):
        agents = client.get("/agents").json()
        doc_analyst = next(a for a in agents if a["id"] == "1")
        skill_names = [s["name"] for s in doc_analyst["skills"]]
        assert "rag_search" in skill_names

    def test_doc_analyst_has_web_search_skill(self, client):
        agents = client.get("/agents").json()
        doc_analyst = next(a for a in agents if a["id"] == "1")
        skill_names = [s["name"] for s in doc_analyst["skills"]]
        assert "web_search" in skill_names

    def test_web_researcher_has_one_skill(self, client):
        agents = client.get("/agents").json()
        researcher = next(a for a in agents if a["id"] == "2")
        assert len(researcher["skills"]) == 1
