"""
Fase 2 — Tools do agente.

Cada tool é uma função Python decorada com @tool do LangChain.
O LLM decide qual tool usar baseado na descrição de cada uma —
a qualidade da descrição é o fator mais importante para o agente
tomar a decisão certa.

Tools disponíveis:
- rag_search: busca semântica nos documentos PDF indexados
- web_search: busca na internet via DuckDuckGo
"""
import os
from dotenv import load_dotenv

from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_community.tools import DuckDuckGoSearchRun

load_dotenv()

# O vectorstore é inicializado uma vez quando o módulo é carregado.
# Isso evita reconectar ao ChromaDB a cada chamada da tool.
_embeddings = OllamaEmbeddings(
    model=os.getenv("EMBED_MODEL", "nomic-embed-text"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
)

_vectorstore = Chroma(
    persist_directory=os.getenv("CHROMA_PATH", "./data/chroma_db"),
    embedding_function=_embeddings,
    collection_name="docagent",
)

_retriever = _vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 4},
)

_web_search = DuckDuckGoSearchRun()


@tool
def rag_search(query: str) -> str:
    """
    Busca informações nos documentos PDF carregados no sistema.
    Use esta ferramenta quando a pergunta for sobre o conteúdo dos
    documentos indexados, como conceitos, definições, procedimentos
    ou qualquer informação que possa estar nos PDFs.
    Retorna trechos relevantes com indicação de fonte e página.
    """
    docs = _retriever.invoke(query)

    if not docs:
        return "Nenhum trecho relevante encontrado nos documentos."

    parts = []
    for doc in docs:
        meta = doc.metadata
        source = meta.get("source_file", "desconhecido")
        page = meta.get("page", 0)
        parts.append(f"[{source}, p.{page + 1}]\n{doc.page_content}")

    return "\n\n---\n\n".join(parts)


@tool
def web_search(query: str) -> str:
    """
    Busca informações atuais na internet via DuckDuckGo.
    Use esta ferramenta quando precisar de informações recentes,
    notícias, dados que mudam com frequência, ou qualquer assunto
    que provavelmente não está nos documentos carregados.
    """
    return _web_search.invoke(query)


# Lista de tools disponíveis para o agente — importada pelo agent.py
TOOLS = [rag_search, web_search]
