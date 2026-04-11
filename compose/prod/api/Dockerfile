FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema:
#   nodejs/npm → servidores MCP via npx
#   ffmpeg     → conversão WAV→OGG/OPUS para TTS (Piper)
#   libgomp1   → requerido pelo faster-whisper (OpenMP)
#   wget       → download de modelos Piper no build
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    npm \
    ffmpeg \
    libgomp1 \
    wget \
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

# Copia os servidores MCP customizados
COPY mcp_servers/ ./mcp_servers/

# Copia o entrypoint de prod (roda Alembic + seed)
COPY compose/prod/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Cria diretorios de dados e modelos
RUN mkdir -p data/pdfs data/chroma_db models/piper

# ── Pré-download: modelo Whisper base ────────────────────────────────────────
# HF_HOME aponta para dentro do container (persistido via volume se necessário)
ENV HF_HOME=/app/models/huggingface
RUN uv run python -c "\
from faster_whisper import WhisperModel; \
print('Baixando modelo Whisper base...'); \
WhisperModel('base', device='cpu', compute_type='int8'); \
print('Whisper base OK')"

# ── Pré-download: modelo Piper pt_BR-faber-medium ────────────────────────────
ENV PIPER_MODELS_DIR=/app/models/piper
RUN wget -q \
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx" \
    -O /app/models/piper/pt_BR-faber-medium.onnx && \
    wget -q \
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json" \
    -O /app/models/piper/pt_BR-faber-medium.onnx.json && \
    echo "Piper pt_BR-faber-medium OK"

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
