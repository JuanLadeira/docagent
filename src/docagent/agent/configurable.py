"""
Fase 6 — ConfigurableAgent: agente montado dinamicamente a partir de skills.

Substitui DocAgent como agente principal do sistema.
Subclasse de BaseAgent — herda build(), run() e stream().
"""
from docagent.agent.base import BaseAgent
from docagent.agent.registry import AgentConfig
from docagent.agent.skills import SKILL_REGISTRY

BASE_SYSTEM_PROMPT = """\
Voce e um assistente especializado. Responda SEMPRE em portugues.

Voce tem acesso as seguintes ferramentas:
{tools}

IMPORTANTE: sempre use uma das ferramentas antes de responder. \
Nunca responda apenas com seu conhecimento pre-treinado.\
"""


class ConfigurableAgent(BaseAgent):
    """Agente cujas tools e prompt sao definidos pelo AgentConfig injetado."""

    def __init__(
        self,
        config: AgentConfig,
        session_collection: str | None = None,
        system_prompt_override: str | None = None,
        extra_tools: list | None = None,
    ):
        super().__init__()
        self._config = config
        self._session_collection = session_collection
        self._system_prompt_override = system_prompt_override
        self._extra_tools = extra_tools or []

    @property
    def tools(self) -> list:
        built_in = []
        for name in self._config.skill_names:
            if name not in SKILL_REGISTRY:
                continue
            skill = SKILL_REGISTRY[name]
            if name == "rag_search" and self._session_collection:
                from docagent.agent.skills.rag_search import RagSearchSkill
                skill = RagSearchSkill(collection=self._session_collection)
            built_in.append(skill.as_tool())
        return built_in + self._extra_tools

    @property
    def system_prompt(self) -> str:
        if self._system_prompt_override:
            return self._system_prompt_override
        tool_lines = "\n".join(
            f"- {SKILL_REGISTRY[name].name}: {SKILL_REGISTRY[name].description}"
            for name in self._config.skill_names
            if name in SKILL_REGISTRY
        )
        return BASE_SYSTEM_PROMPT.format(tools=tool_lines)
