"""
Fase 6 — ConfigurableAgent: agente montado dinamicamente a partir de skills.

Substitui DocAgent como agente principal do sistema.
Subclasse de BaseAgent — herda build(), run() e stream().
"""
from docagent.base_agent import BaseAgent
from docagent.agents.registry import AgentConfig
from docagent.skills import SKILL_REGISTRY

BASE_SYSTEM_PROMPT = """\
Voce e um assistente especializado. Responda SEMPRE em portugues.

Voce tem acesso as seguintes ferramentas:
{tools}

IMPORTANTE: sempre use uma das ferramentas antes de responder. \
Nunca responda apenas com seu conhecimento pre-treinado.\
"""


class ConfigurableAgent(BaseAgent):
    """Agente cujas tools e prompt sao definidos pelo AgentConfig injetado."""

    def __init__(self, config: AgentConfig, session_collection: str | None = None):
        super().__init__()
        self._config = config
        self._session_collection = session_collection

    @property
    def tools(self) -> list:
        return [
            SKILL_REGISTRY[name].as_tool()
            for name in self._config.skill_names
            if name in SKILL_REGISTRY
        ]

    @property
    def system_prompt(self) -> str:
        tool_lines = "\n".join(
            f"- {SKILL_REGISTRY[name].name}: {SKILL_REGISTRY[name].description}"
            for name in self._config.skill_names
            if name in SKILL_REGISTRY
        )
        return BASE_SYSTEM_PROMPT.format(tools=tool_lines)
