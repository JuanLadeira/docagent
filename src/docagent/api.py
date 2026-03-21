"""
Fase 5 — API FastAPI com arquitetura em camadas.

Assembly do app: registra routers e configura LangSmith.
A logica de negocio esta em services/, os endpoints em routers/.
"""
import os
from dotenv import load_dotenv
from fastapi import FastAPI

from docagent.routers.chat import router as chat_router

load_dotenv()

# Configura LangSmith automaticamente se a chave estiver presente.
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "docagent")

app = FastAPI(title="DocAgent API", version="2.0.0")
app.include_router(chat_router)
