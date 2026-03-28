"""
Fase 1 — RAG Pipeline: busca e QA com citações de página.

Conceitos ensinados neste arquivo:
- Como reconectar a um vectorstore persistido (ChromaDB)
- Como construir uma chain LCEL (LangChain Expression Language)
- Como retornar citações de fonte junto com a resposta
- temperature=0 para respostas determinísticas em QA
"""
from dotenv import load_dotenv
import os

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

load_dotenv()
console = Console()


def load_vectorstore() -> Chroma:
    """Reconecta ao ChromaDB já populado pelo ingest.py."""
    embeddings = OllamaEmbeddings(
        model=os.getenv("EMBED_MODEL", "nomic-embed-text"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
    vectorstore = Chroma(
        persist_directory=os.getenv("CHROMA_PATH", "./data/chroma_db"),
        embedding_function=embeddings,
        collection_name="docagent",
    )
    return vectorstore


def format_docs_with_citations(docs: list) -> str:
    """
    Formata os chunks recuperados incluindo metadados de fonte e página.
    Esses metadados foram salvos pelo ingest.py e ficam no ChromaDB.
    """
    parts = []
    for doc in docs:
        meta = doc.metadata
        source = meta.get("source_file", "desconhecido")
        # PyMuPDFLoader usa índice 0; somamos 1 para exibição humana
        page = meta.get("page", 0)
        parts.append(f"[Fonte: {source}, p.{page + 1}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


PROMPT_TEMPLATE = """\
Você é um assistente especializado em análise de documentos.
Use apenas os trechos abaixo para responder à pergunta.
Se a resposta não estiver nos trechos, diga que não encontrou a informação no documento.
Ao final da resposta, liste as fontes utilizadas (arquivo e página).

Trechos do documento:
{context}

Pergunta: {question}

Resposta:"""


def build_chain(vectorstore: Chroma):
    """
    Monta a chain LCEL de RAG.

    Fluxo:
      pergunta → retriever (busca semântica) → formatar chunks com fontes
              → prompt → LLM → parser de string
    """
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4},  # recupera os 4 chunks mais relevantes
    )

    llm = ChatOllama(
        model=os.getenv("LLM_MODEL", "qwen2.5:7b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,  # 0 = respostas determinísticas, ideal para QA factual
    )

    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)

    # LCEL: cada "|" passa a saída de um passo como entrada do próximo.
    # RunnablePassthrough() deixa a pergunta original passar sem alteração.
    chain = (
        {
            "context": retriever | format_docs_with_citations,
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain, retriever


def ask(question: str, chain, retriever) -> None:
    """Executa uma pergunta e exibe a resposta com as fontes."""
    console.print(f"\n[bold cyan]Pergunta:[/bold cyan] {question}\n")

    # Recupera os docs para exibir as fontes separadamente
    docs = retriever.invoke(question)

    # Roda a chain completa (retriever + prompt + LLM)
    answer = chain.invoke(question)

    console.print(Panel(Markdown(answer), title="Resposta", border_style="green"))

    # Exibe fontes dedupliacadas
    console.print("\n[bold yellow]Fontes recuperadas:[/bold yellow]")
    seen = set()
    for doc in docs:
        meta = doc.metadata
        source = meta.get("source_file", "desconhecido")
        page = meta.get("page", 0)
        key = (source, page)
        if key not in seen:
            seen.add(key)
            console.print(f"  • {source} — página {page + 1}")


def main():
    console.print("[bold]DocAgent — RAG QA com citações de página[/bold]\n")

    vectorstore = load_vectorstore()
    chain, retriever = build_chain(vectorstore)

    console.print(
        "[green]Vectorstore carregado. "
        "Digite sua pergunta (ou 'sair' para encerrar).[/green]\n"
    )

    while True:
        try:
            question = input("Pergunta: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not question or question.lower() in {"sair", "exit", "quit"}:
            break

        ask(question, chain, retriever)

    console.print("\n[dim]Encerrando DocAgent.[/dim]")


if __name__ == "__main__":
    main()
