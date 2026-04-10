"""
Fase 8 — API FastAPI com arquitetura em camadas.

Assembly do app: registra routers e configura LangSmith.
A logica de negocio esta em services/, os endpoints em routers/.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_core.messages import HumanMessage

from docagent.chat.router import router as chat_router
from docagent.rag.router import router as documents_router
from docagent.auth.router import router as auth_router
from docagent.tenant.router import router as tenant_router
from docagent.usuario.router import router as usuario_router
from docagent.admin.router import router as admin_router
from docagent.agente.router import router as agente_router, legacy_router as agents_legacy_router
from docagent.whatsapp.router import router as whatsapp_router
from docagent.telegram.router import router as telegram_router
from docagent.atendimento.router import router as atendimento_router
from docagent.mcp_server.router import router as mcp_router
from docagent.assinatura.router import router as assinatura_router
from docagent.vagas.router import router as vagas_router
from docagent.audio.router import router as audio_router

load_dotenv()

# Configura LangSmith automaticamente se a chave estiver presente.
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "docagent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Aquece o modelo Ollama no startup (somente quando llm_mode=local)."""
    if os.getenv("LLM_PROVIDER", "ollama") == "ollama":
        try:
            from docagent.agent.llm_factory import get_llm
            llm = get_llm()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, llm.invoke, [HumanMessage(content="olá")])
            print("[startup] Modelo aquecido.")
        except Exception as e:
            print(f"[startup] Warmup falhou (Ollama offline?): {e}")
    yield


app = FastAPI(title="DocAgent API", version="3.0.0", lifespan=lifespan)

# RAG + Agentes
app.include_router(chat_router)
app.include_router(documents_router)

# Auth + Multi-tenant SaaS
app.include_router(auth_router)
app.include_router(tenant_router)
app.include_router(usuario_router)
app.include_router(admin_router)
app.include_router(agente_router)
app.include_router(agents_legacy_router)

# Canais de atendimento
app.include_router(whatsapp_router)
app.include_router(telegram_router)
app.include_router(atendimento_router)

# MCP — skills dinâmicas
app.include_router(mcp_router)

# Billing & Quotas
app.include_router(assinatura_router)

# Vagas — pipeline multi-agente de busca de emprego
app.include_router(vagas_router)

# Áudio — STT + TTS por tenant/agente
app.include_router(audio_router)
