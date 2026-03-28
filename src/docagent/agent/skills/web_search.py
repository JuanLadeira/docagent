"""
Fase 6 — WebSearchSkill: busca na internet via DuckDuckGo.
"""
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.tools import BaseTool


class WebSearchSkill:
    name = "web_search"
    label = "Busca na Web"
    icon = "🌐"
    description = "Busca informações atuais na internet via DuckDuckGo"

    def as_tool(self) -> BaseTool:
        return DuckDuckGoSearchResults(name="web_search", num_results=4)
