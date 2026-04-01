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

REGRAS:
- Use as ferramentas apenas quando a pergunta do usuario exigir informacoes externas, busca ou dados em tempo real.
- Para perguntas de conversa, instrucoes gerais ou que voce ja sabe responder, responda diretamente sem usar ferramentas.
- Quando a ferramenta retornar URLs ou links, cite-os explicitamente na resposta como fonte.
- Se os resultados contiverem um campo "link" ou "🔗 Fonte", inclua esse link na sua resposta.
- Nunca invente ou suponha URLs. Se nao houver link nos resultados, diga de onde veio a informacao sem inventar endereco.\
"""

TOOLS_SUFFIX = """\

Voce tem acesso as seguintes ferramentas (use apenas quando a pergunta exigir):
{tools}
- Quando ferramentas retornarem URLs, cite-as como fonte. Nunca invente URLs.\
"""


class ConfigurableAgent(BaseAgent):
    """Agente cujas tools e prompt sao definidos pelo AgentConfig injetado."""

    def __init__(
        self,
        config: AgentConfig,
        session_collection: str | None = None,
        system_prompt_override: str | None = None,
        extra_tools: list | None = None,
        llm=None,
    ):
        super().__init__()
        self._config = config
        self._session_collection = session_collection
        self._system_prompt_override = system_prompt_override
        self._extra_tools = extra_tools or []
        self._llm = llm

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
        tool_lines = "\n".join(
            f"- {SKILL_REGISTRY[name].name}: {SKILL_REGISTRY[name].description}"
            for name in self._config.skill_names
            if name in SKILL_REGISTRY
        )
        mcp_lines = "\n".join(
            f"- {t.name}: {t.description or ''}"
            for t in self._extra_tools
        )
        all_tool_lines = "\n".join(filter(None, [tool_lines, mcp_lines]))

        if self._system_prompt_override:
            if all_tool_lines:
                return self._system_prompt_override + TOOLS_SUFFIX.format(tools=all_tool_lines)
            return self._system_prompt_override
        return BASE_SYSTEM_PROMPT.format(tools=all_tool_lines or "(nenhuma)")

    def build(self, llm=None) -> "ConfigurableAgent":
        return super().build(llm=self._llm or llm)
