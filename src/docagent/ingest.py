from pathlib import Path
from dotenv import load_dotenv
import os

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from rich.console import Console
from rich.progress import track

load_dotenv()
console = Console()


def load_pdfs(pdf_dir: str) -> list:
    """Carrega todos os PDFs de um diretório."""
    docs = []
    pdf_path = Path(pdf_dir)
    pdf_files = list(pdf_path.glob("*.pdf"))

    if not pdf_files:
        console.print(f"[yellow]Nenhum PDF encontrado em {pdf_dir}[/yellow]")
        return docs

    for pdf_file in track(pdf_files, description="Carregando PDFs..."):
        loader = PyMuPDFLoader(str(pdf_file))
        loaded = loader.load()
        for doc in loaded:
            doc.metadata["source_file"] = pdf_file.name
        docs.extend(loaded)
        console.print(f"  [green]✓[/green] {pdf_file.name} — {len(loaded)} páginas")

    return docs


def split_documents(docs: list) -> list:
    """
    Divide os documentos em chunks.
    chunk_size=1000 e overlap=200 é um bom ponto de partida para RAG.
    O overlap garante que contexto não seja perdido nas bordas dos chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks = splitter.split_documents(docs)
    console.print(f"\n[blue]Total de chunks gerados:[/blue] {len(chunks)}")
    return chunks


def build_vectorstore(chunks: list, collection_name: str = "docagent") -> Chroma:
    """Cria embeddings e persiste no ChromaDB."""
    console.print("\n[blue]Gerando embeddings com nomic-embed-text...[/blue]")
    console.print("[dim]Isso pode demorar alguns minutos na primeira vez.[/dim]\n")

    embeddings = OllamaEmbeddings(
        model=os.getenv("EMBED_MODEL", "nomic-embed-text"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=os.getenv("CHROMA_PATH", "./data/chroma_db"),
        collection_name=collection_name,
    )

    console.print(f"[green]✓ Vectorstore criado com {len(chunks)} chunks![/green]")
    return vectorstore


def ingest(pdf_dir: str = "./data/pdfs"):
    console.print("[bold]DocAgent — Pipeline de Ingestão[/bold]\n")

    docs = load_pdfs(pdf_dir)
    if not docs:
        return

    chunks = split_documents(docs)
    vectorstore = build_vectorstore(chunks)

    console.print("\n[bold green]Ingestão concluída![/bold green]")
    console.print(f"Banco vetorial salvo em: {os.getenv('CHROMA_PATH')}")
    return vectorstore


if __name__ == "__main__":
    ingest()
