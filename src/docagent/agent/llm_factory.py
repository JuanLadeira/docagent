"""Factory para instanciar o LLM correto conforme a configuração do tenant."""
import os
from typing import TYPE_CHECKING

from langchain_core.language_models.chat_models import BaseChatModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

PROVIDERS = ("ollama", "openai", "groq", "anthropic", "gemini")


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> BaseChatModel:
    """Retorna o chat model LangChain para o provider configurado.

    Ordem de resolução:
    1. Parâmetros explícitos (config do tenant)
    2. Variáveis de ambiente LLM_PROVIDER / LLM_MODEL
    3. Fallback: Ollama local

    Providers suportados: ollama, openai, groq, anthropic, gemini
    """
    provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=api_key or os.getenv("OPENAI_API_KEY") or "",
            temperature=0,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            api_key=api_key or os.getenv("GROQ_API_KEY") or "",
            temperature=0,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY") or "",
            temperature=0,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            google_api_key=api_key or os.getenv("GOOGLE_API_KEY") or "",
            temperature=0,
        )

    # Ollama (padrão)
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=model or os.getenv("LLM_MODEL", "qwen2.5:7b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
        keep_alive=-1,
    )


async def get_tenant_llm(tenant_id: int, db: "AsyncSession") -> BaseChatModel:
    """Retorna o LLM correto para um tenant respeitando o modo global do sistema.

    - llm_mode = 'local'  → sempre Ollama (ignora config do tenant)
    - llm_mode = 'api'    → usa provider/model/key configurados pelo tenant;
                            se o tenant não configurou, cai em Ollama
    """
    from docagent.system_config.services import SystemConfigService

    mode = await SystemConfigService(db).get_llm_mode()
    if mode == "api":
        from docagent.tenant.models import Tenant
        tenant = await db.get(Tenant, tenant_id)
        if tenant and tenant.llm_provider and tenant.llm_api_key:
            return get_llm(tenant.llm_provider, tenant.llm_model, tenant.llm_api_key)
    return get_llm()
