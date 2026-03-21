"""
Registro global de skills disponíveis.

SKILL_REGISTRY mapeia nome → instância de skill.
Pode ser substituído em testes via patch("docagent.agents.configurable_agent.SKILL_REGISTRY").
"""
from docagent.skills.rag_search import RagSearchSkill
from docagent.skills.web_search import WebSearchSkill

SKILL_REGISTRY: dict = {
    "rag_search": RagSearchSkill(),
    "web_search": WebSearchSkill(),
}
