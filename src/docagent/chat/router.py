"""
Router FastAPI para chat, health e session.

O agente e carregado do banco de dados a partir do agent_id da requisicao.
Agentes com skills MCP (prefixo mcp:) carregam ferramentas via AsyncExitStack.
"""
from contextlib import AsyncExitStack

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage

from docagent.agente.services import AgenteServiceDep
from docagent.agent.configurable import ConfigurableAgent
from docagent.agent.llm_factory import get_tenant_llm
from docagent.agent.registry import AgentConfig
from docagent.auth.current_user import CurrentUser
from docagent.database import AsyncSessionLocal
from docagent.dependencies import get_session_manager
from docagent.mcp_server.services import McpServiceDep, load_mcp_tools_for_skills
from docagent.chat.schemas import ChatRequest, HealthResponse
from docagent.chat.service import ChatService
from docagent.chat.session import SessionManager

router = APIRouter()

# Cache de agentes construídos, keyed por (agente_id, skill_names, system_prompt).
# Invalida automaticamente quando a configuração do agente muda.
# Agentes com skills mcp:* NÃO são cacheados — precisam de conexão ativa por requisição.
_agent_cache: dict[tuple, object] = {}


def _mcp_skill_names(skill_names: list[str]) -> list[str]:
    return [n for n in skill_names if n.startswith("mcp:")]


def _build_agent(agente, extra_tools: list | None = None, llm=None):
    config = AgentConfig(
        id=str(agente.id),
        name=agente.nome,
        description=agente.descricao,
        skill_names=agente.skill_names,
    )
    return ConfigurableAgent(
        config,
        session_collection=f"agente_{agente.id}",
        system_prompt_override=agente.system_prompt or None,
        extra_tools=extra_tools,
        llm=llm,
    ).build()


def _get_or_build_agent(agente, llm=None, llm_provider: str = "", llm_model: str = ""):
    """Retorna agente cacheado ou constrói novo se a config mudou.
    Agentes com skills MCP nunca são cacheados."""
    cache_key = (
        agente.id,
        tuple(agente.skill_names),
        agente.system_prompt or "",
        llm_provider,
        llm_model,
    )
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = _build_agent(agente, llm=llm)
    return _agent_cache[cache_key]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: CurrentUser,
    agente_service: AgenteServiceDep,
    mcp_service: McpServiceDep,
    sessions: SessionManager = Depends(get_session_manager),
) -> StreamingResponse:
    try:
        agente_id = int(request.agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="agent_id deve ser um numero inteiro")

    agente = await agente_service.get_by_id(agente_id, tenant_id=current_user.tenant_id)
    if not agente or not agente.ativo:
        raise HTTPException(status_code=404, detail=f"Agente '{request.agent_id}' nao encontrado")

    async with AsyncSessionLocal() as llm_db:
        tenant_llm = await get_tenant_llm(current_user.tenant_id, llm_db)
    llm_provider = getattr(tenant_llm, "model_name", "") or getattr(tenant_llm, "model", "") or ""

    mcp_skills = _mcp_skill_names(agente.skill_names)
    stack = AsyncExitStack()
    mcp_tools = []

    if mcp_skills:
        servers = await mcp_service.get_all()
        mcp_tools = await load_mcp_tools_for_skills(mcp_skills, servers, stack)
        agent = _build_agent(agente, extra_tools=mcp_tools, llm=tenant_llm)
    else:
        agent = _get_or_build_agent(agente, llm=tenant_llm, llm_provider=llm_provider)

    service = ChatService(agent, sessions)

    async def managed_stream():
        async with stack:
            for chunk in service.stream(request.question, request.session_id):
                yield chunk

    return StreamingResponse(
        managed_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/sync")
async def chat_sync(
    request: ChatRequest,
    current_user: CurrentUser,
    agente_service: AgenteServiceDep,
    mcp_service: McpServiceDep,
    sessions: SessionManager = Depends(get_session_manager),
) -> dict:
    """Endpoint síncrono para integrações externas (n8n, Evolution API, etc).
    Aguarda a resposta completa e retorna JSON."""
    try:
        agente_id = int(request.agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="agent_id deve ser um numero inteiro")

    agente = await agente_service.get_by_id(agente_id, tenant_id=current_user.tenant_id)
    if not agente or not agente.ativo:
        raise HTTPException(status_code=404, detail=f"Agente '{request.agent_id}' nao encontrado")

    async with AsyncSessionLocal() as llm_db2:
        tenant_llm2 = await get_tenant_llm(current_user.tenant_id, llm_db2)
    llm_provider2 = getattr(tenant_llm2, "model_name", "") or getattr(tenant_llm2, "model", "") or ""

    mcp_skills = _mcp_skill_names(agente.skill_names)
    async with AsyncExitStack() as stack:
        mcp_tools = []
        if mcp_skills:
            servers = await mcp_service.get_all()
            mcp_tools = await load_mcp_tools_for_skills(mcp_skills, servers, stack)
            agent = _build_agent(agente, extra_tools=mcp_tools, llm=tenant_llm2)
        else:
            agent = _get_or_build_agent(agente, llm=tenant_llm2, llm_provider=llm_provider2)
        state = sessions.get(request.session_id)
        final_state = agent.run(request.question, state)

    if agent.last_state is not None:
        sessions.update(request.session_id, agent.last_state)

    answer = ""
    if final_state and final_state.get("messages"):
        last_msg = final_state["messages"][-1]
        if isinstance(last_msg, AIMessage):
            answer = last_msg.content or ""

    return {
        "answer": answer,
        "session_id": request.session_id,
        "agent_id": request.agent_id,
    }


@router.delete("/session/{session_id}")
def delete_session(
    session_id: str,
    sessions: SessionManager = Depends(get_session_manager),
) -> dict:
    if not sessions.delete(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"Sessao '{session_id}' nao encontrada.",
        )
    return {"status": "cleared", "session_id": session_id}
