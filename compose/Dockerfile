FROM python:3.11-slim

WORKDIR /app

# Instala o uv e uvx (gerenciador de pacotes e executor de tools)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=ghcr.io/astral-sh/uv:latest /uvx /usr/local/bin/uvx

# Copia apenas os arquivos de dependencias primeiro (cache de camadas)
COPY pyproject.toml uv.lock ./

# Instala dependencias de producao (sem dev)
RUN uv sync --no-dev --frozen

# Copia o codigo fonte
COPY src/ ./src/

# Copia o entrypoint
COPY compose/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Cria o diretorio de dados (ChromaDB e PDFs sao montados via volume)
RUN mkdir -p data/pdfs data/chroma_db

EXPOSE 8000 8501

ENTRYPOINT ["/entrypoint.sh"]
