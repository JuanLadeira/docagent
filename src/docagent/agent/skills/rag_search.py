"""
Fase 6 — RagSearchSkill: busca semantica em documentos PDF via ChromaDB.
"""
import os
from langchain_core.tools import tool, BaseTool
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()


class RagSearchSkill:
    name = "rag_search"
    label = "Busca em Documentos"
    icon = "🔍"
    description = "Busca semântica nos documentos PDF carregados no sistema"

    def __init__(self, collection: str = "docagent"):
        self._collection = collection

    def as_tool(self) -> BaseTool:
        """
        Cria e retorna a tool de busca RAG.

        OllamaEmbeddings e Chroma sao instanciados dentro do corpo da tool
        (execucao lazy) — as_tool() apenas define e devolve o objeto sem
        fazer chamadas de rede.
        """
        collection_name = self._collection

        @tool
        def rag_search(query: str) -> str:
            """
            Busca informacoes nos documentos PDF carregados no sistema.
            Use quando a pergunta for sobre conteudo dos documentos indexados.
            Retorna trechos relevantes com indicacao de fonte e pagina.
            """
            embeddings = OllamaEmbeddings(
                model=os.getenv("EMBED_MODEL", "nomic-embed-text"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            )
            vectorstore = Chroma(
                persist_directory=os.getenv("CHROMA_PATH", "./data/chroma_db"),
                embedding_function=embeddings,
                collection_name=collection_name,
            )
            docs = vectorstore.similarity_search(query, k=4)

            if not docs:
                return "Nenhum trecho relevante encontrado nos documentos."

            parts = []
            for doc in docs:
                source = doc.metadata.get("source_file", "desconhecido")
                page = doc.metadata.get("page", 0)
                parts.append(f"[{source}, p.{page + 1}]\n{doc.page_content}")

            return "\n\n---\n\n".join(parts)

        return rag_search
