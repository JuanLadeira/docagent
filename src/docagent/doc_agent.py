"""
Fase 5 — DocAgent: subclasse concreta de BaseAgent para RAG + web search.

Implementa as propriedades abstratas `tools` e `system_prompt`.
"""
from docagent.base_agent import BaseAgent
from docagent.tools import TOOLS

SYSTEM_PROMPT = """\
Voce e um assistente especializado em analise de documentos. Responda SEMPRE em portugues.

Voce tem acesso a duas ferramentas:
- rag_search: use para responder perguntas sobre os documentos PDF carregados no sistema
- web_search: use para buscar informacoes atuais ou externas que nao estao nos documentos

IMPORTANTE: sempre use uma das ferramentas antes de responder. Nunca responda apenas com \
seu conhecimento pre-treinado.\
"""


class DocAgent(BaseAgent):
    """Agente especializado em documentos com rag_search e web_search."""

    @property
    def tools(self) -> list:
        return TOOLS

    @property
    def system_prompt(self) -> str:
        return SYSTEM_PROMPT
