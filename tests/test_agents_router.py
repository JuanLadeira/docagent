"""
Testes TDD para GET /agents (routers/agents.py).

Valida a listagem de agentes disponiveis com suas skills.
Sem mocks de servico — o endpoint e puramente baseado no registry estatico.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from docagent.api import app
    return TestClient(app)


class TestListAgents:
    def test_returns_200(self, client):
        assert client.get("/agents").status_code == 200

    def test_returns_list(self, client):
        response = client.get("/agents")
        assert isinstance(response.json(), list)

    def test_list_is_not_empty(self, client):
        response = client.get("/agents")
        assert len(response.json()) >= 1

    def test_contains_doc_analyst(self, client):
        response = client.get("/agents")
        ids = [a["id"] for a in response.json()]
        assert "doc-analyst" in ids

    def test_contains_web_researcher(self, client):
        response = client.get("/agents")
        ids = [a["id"] for a in response.json()]
        assert "web-researcher" in ids


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


class TestDocAnalystAgent:
    def test_doc_analyst_has_two_skills(self, client):
        agents = client.get("/agents").json()
        doc_analyst = next(a for a in agents if a["id"] == "doc-analyst")
        assert len(doc_analyst["skills"]) == 2

    def test_doc_analyst_has_rag_search_skill(self, client):
        agents = client.get("/agents").json()
        doc_analyst = next(a for a in agents if a["id"] == "doc-analyst")
        skill_names = [s["name"] for s in doc_analyst["skills"]]
        assert "rag_search" in skill_names

    def test_doc_analyst_has_web_search_skill(self, client):
        agents = client.get("/agents").json()
        doc_analyst = next(a for a in agents if a["id"] == "doc-analyst")
        skill_names = [s["name"] for s in doc_analyst["skills"]]
        assert "web_search" in skill_names

    def test_web_researcher_has_one_skill(self, client):
        agents = client.get("/agents").json()
        researcher = next(a for a in agents if a["id"] == "web-researcher")
        assert len(researcher["skills"]) == 1
