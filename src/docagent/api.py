"""
Fase 8 — API FastAPI com arquitetura em camadas.

Assembly do app: registra routers e configura LangSmith.
A logica de negocio esta em services/, os endpoints em routers/.
"""
import os
from dotenv import load_dotenv
from fastapi import FastAPI

from docagent.routers.chat import router as chat_router
from docagent.routers.agents import router as agents_router
from docagent.routers.documents import router as documents_router
from docagent.auth.router import router as auth_router
from docagent.tenant.router import router as tenant_router
from docagent.usuario.router import router as usuario_router
from docagent.admin.router import router as admin_router
from docagent.agente.router import router as agente_router

load_dotenv()

# Configura LangSmith automaticamente se a chave estiver presente.
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "docagent")

app = FastAPI(title="DocAgent API", version="3.0.0")

# RAG + Agentes
app.include_router(chat_router)
app.include_router(agents_router)
app.include_router(documents_router)

# Auth + Multi-tenant SaaS
app.include_router(auth_router)
app.include_router(tenant_router)
app.include_router(usuario_router)
app.include_router(admin_router)
app.include_router(agente_router)
