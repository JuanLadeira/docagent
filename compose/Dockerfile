FROM python:3.11-slim

WORKDIR /app

# Instala Node.js (necessário para servidores MCP via npx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Instala o uv e uvx (gerenciador de pacotes e executor de tools)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=ghcr.io/astral-sh/uv:latest /uvx /usr/local/bin/uvx

# Copia apenas os arquivos de dependencias primeiro (cache de camadas)
COPY pyproject.toml uv.lock ./

# Instala dependencias de producao (sem dev)
RUN uv sync --no-dev --frozen

# Copia o codigo fonte
COPY src/ ./src/

# Copia os entrypoints (dev e prod)
COPY compose/entrypoint.sh /entrypoint.sh
COPY compose/entrypoint.prod.sh /entrypoint.prod.sh
RUN chmod +x /entrypoint.sh /entrypoint.prod.sh

# Cria o diretorio de dados (ChromaDB e PDFs sao montados via volume)
RUN mkdir -p data/pdfs data/chroma_db

EXPOSE 8000 8501

ENTRYPOINT ["/entrypoint.sh"]
