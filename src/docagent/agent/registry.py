"""
Fase 6 — Registry de agentes disponíveis.

AGENT_REGISTRY mapeia agent_id → AgentConfig.
Adicionar um novo agente = adicionar uma entrada aqui.
"""
from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    id: str
    name: str
    description: str
    skill_names: list[str] = field(default_factory=list)


AGENT_REGISTRY: dict[str, AgentConfig] = {
    "doc-analyst": AgentConfig(
        id="doc-analyst",
        name="Analista de Documentos",
        description="Especializado em analisar PDFs carregados pelo usuário.",
        skill_names=["rag_search", "web_search"],
    ),
    "web-researcher": AgentConfig(
        id="web-researcher",
        name="Pesquisador Web",
        description="Busca informações atuais na internet sem depender de documentos.",
        skill_names=["web_search"],
    ),
}
