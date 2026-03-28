"""
Router Telegram — integração com Telegram Bot API.

Fluxo de mensagens recebidas:
  Telegram → POST /api/telegram/webhook/{bot_token}
    → busca TelegramInstancia pelo token
    → se cria_atendimentos=True: cria/retoma Atendimento
    → executa agente vinculado
    → responde via sendMessage
"""
import asyncio
from contextlib import AsyncExitStack

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage
from sqlalchemy import select

from docagent.agente.models import Agente
from docagent.agent.configurable import ConfigurableAgent
from docagent.agent.registry import AgentConfig
from docagent.atendimento.models import (
    Atendimento,
    AtendimentoStatus,
    CanalAtendimento,
    MensagemAtendimento,
    MensagemOrigem,
)
from docagent.atendimento.sse import atendimento_lista_sse_manager, atendimento_sse_manager
from docagent.auth.current_user import CurrentUser
from docagent.agent.base import BaseAgent
from docagent.database import AsyncSessionLocal
from docagent.dependencies import get_session_manager
from docagent.telegram.client import get_telegram_client
from docagent.telegram.models import TelegramInstancia
from docagent.telegram.schemas import (
    TelegramInstanciaCreate,
    TelegramInstanciaPublic,
    TelegramUpdate,
)
from docagent.telegram.services import TelegramServiceDep
from docagent.settings import Settings

router = APIRouter(
    prefix="/api/telegram",
    tags=["Telegram"],
)

# Cache de agentes construídos — mesma estratégia do whatsapp/router.py
_agent_cache: dict[tuple, BaseAgent] = {}


def _tem_skills_mcp(agente_obj: Agente) -> bool:
    return any(s.startswith("mcp:") for s in agente_obj.skill_names)


def _build_agent_obj(agente_obj: Agente, extra_tools: list | None = None) -> BaseAgent:
    config = AgentConfig(
        id=str(agente_obj.id),
        name=agente_obj.nome,
        description=agente_obj.descricao,
        skill_names=agente_obj.skill_names,
    )
    return ConfigurableAgent(
        config,
        system_prompt_override=agente_obj.system_prompt or None,
        extra_tools=extra_tools,
    ).build()


def _get_or_build_agent(agente_obj: Agente) -> BaseAgent:
    cache_key = (agente_obj.id, tuple(agente_obj.skill_names), agente_obj.system_prompt or "")
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = _build_agent_obj(agente_obj)
    return _agent_cache[cache_key]


# ── CRUD de instâncias ────────────────────────────────────────────────────────

@router.get("/instancias", response_model=list[TelegramInstanciaPublic])
async def listar_instancias(current_user: CurrentUser, service: TelegramServiceDep):
    return await service.listar_instancias(current_user.tenant_id)


@router.post("/instancias", response_model=TelegramInstanciaPublic, status_code=201)
async def criar_instancia(
    data: TelegramInstanciaCreate,
    current_user: CurrentUser,
    service: TelegramServiceDep,
):
    settings = Settings()
    webhook_url = (
        f"{settings.WEBHOOK_BASE_URL}/api/telegram/webhook/{data.bot_token}"
    )
    return await service.criar_instancia(current_user.tenant_id, data, webhook_url)


@router.delete("/instancias/{instancia_id}", status_code=204)
async def deletar_instancia(
    instancia_id: int,
    current_user: CurrentUser,
    service: TelegramServiceDep,
):
    instancia = await service.obter_instancia(instancia_id, current_user.tenant_id)
    if not instancia:
        raise HTTPException(status_code=404, detail="Instância não encontrada")
    await service.deletar_instancia(instancia)


@router.post("/instancias/{instancia_id}/webhook/configurar", response_model=TelegramInstanciaPublic)
async def configurar_webhook(
    instancia_id: int,
    current_user: CurrentUser,
    service: TelegramServiceDep,
):
    instancia = await service.obter_instancia(instancia_id, current_user.tenant_id)
    if not instancia:
        raise HTTPException(status_code=404, detail="Instância não encontrada")
    settings = Settings()
    webhook_url = (
        f"{settings.WEBHOOK_BASE_URL}/api/telegram/webhook/{instancia.bot_token}"
    )
    return await service.configurar_webhook(instancia, webhook_url)


# ── Webhook público ───────────────────────────────────────────────────────────

@router.post("/webhook/{bot_token}", status_code=200)
async def receber_update(bot_token: str, update: TelegramUpdate):
    """Endpoint público chamado pelo Telegram. Sempre retorna 200."""
    await _processar_update(bot_token, update)
    return {"ok": True}


async def _processar_update(bot_token: str, update: TelegramUpdate) -> None:
    msg = update.message
    if not msg or not msg.text:
        return
    if msg.chat.type != "private":
        return
    if msg.from_ and msg.from_.is_bot:
        return

    numero = str(msg.chat.id)
    nome_contato = msg.from_.first_name if msg.from_ else None
    conteudo = msg.text
    session_id = f"telegram:{numero}"

    async with AsyncSessionLocal() as db:
        # Buscar instância pelo token
        result = await db.execute(
            select(TelegramInstancia).where(TelegramInstancia.bot_token == bot_token)
        )
        instancia = result.scalar_one_or_none()
        if not instancia:
            return

        # Buscar agente vinculado
        agente = None
        if instancia.agente_id:
            ag_result = await db.execute(
                select(Agente).where(Agente.id == instancia.agente_id, Agente.ativo == True)
            )
            agente = ag_result.scalar_one_or_none()

        if not instancia.cria_atendimentos:
            # Modo direto: responde sem criar atendimento na fila
            await db.commit()
            if agente:
                await _executar_e_responder_direto(instancia, agente, conteudo, session_id)
            return

        # Upsert atendimento
        at_result = await db.execute(
            select(Atendimento).where(
                Atendimento.telegram_instancia_id == instancia.id,
                Atendimento.numero == numero,
                Atendimento.status != AtendimentoStatus.ENCERRADO,
            )
        )
        atendimento = at_result.scalar_one_or_none()
        is_novo = atendimento is None
        if not atendimento:
            atendimento = Atendimento(
                numero=numero,
                nome_contato=nome_contato,
                canal=CanalAtendimento.TELEGRAM,
                telegram_instancia_id=instancia.id,
                instancia_id=None,
                tenant_id=instancia.tenant_id,
                status=AtendimentoStatus.ATIVO,
            )
            db.add(atendimento)
            await db.flush()
            await db.refresh(atendimento)

        # Salvar mensagem do contato
        msg_contato = MensagemAtendimento(
            atendimento_id=atendimento.id,
            origem=MensagemOrigem.CONTATO,
            conteudo=conteudo,
        )
        db.add(msg_contato)

        atendimento_id = atendimento.id
        atendimento_status = atendimento.status
        tenant_id = instancia.tenant_id
        agente_obj = agente

        at_data = {
            "id": atendimento.id,
            "numero": atendimento.numero,
            "nome_contato": atendimento.nome_contato,
            "canal": atendimento.canal.value,
            "instancia_id": atendimento.instancia_id,
            "telegram_instancia_id": atendimento.telegram_instancia_id,
            "tenant_id": atendimento.tenant_id,
            "status": atendimento.status.value,
            "prioridade": atendimento.prioridade.value,
            "contato_id": atendimento.contato_id,
            "created_at": atendimento.created_at.isoformat() if atendimento.created_at else None,
            "updated_at": atendimento.updated_at.isoformat() if atendimento.updated_at else None,
        }
        await db.commit()

    # Broadcasts SSE
    await atendimento_sse_manager.broadcast(atendimento_id, {
        "type": "NOVA_MENSAGEM",
        "origem": "CONTATO",
        "conteudo": conteudo,
    })
    event_type = "NOVO_ATENDIMENTO" if is_novo else "ATENDIMENTO_ATUALIZADO"
    await atendimento_lista_sse_manager.broadcast(tenant_id, {
        "type": event_type,
        "atendimento": at_data,
    })

    if atendimento_status == AtendimentoStatus.HUMANO or not agente_obj:
        return

    await _executar_agente_e_salvar(instancia, agente_obj, conteudo, session_id, atendimento_id, numero)


async def _executar_agente_e_salvar(
    instancia: TelegramInstancia,
    agente_obj: Agente,
    conteudo: str,
    session_id: str,
    atendimento_id: int,
    numero: str,
) -> None:
    sessions = get_session_manager()
    state = sessions.get(session_id)
    loop = asyncio.get_event_loop()

    if _tem_skills_mcp(agente_obj):
        from docagent.mcp_server.models import McpServer
        from docagent.mcp_server.services import load_mcp_tools_for_skills
        from sqlalchemy.orm import selectinload
        async with AsyncExitStack() as stack:
            async with AsyncSessionLocal() as mcp_db:
                result = await mcp_db.execute(
                    select(McpServer).options(selectinload(McpServer.tools))
                )
                servers = list(result.scalars().all())
            mcp_skills = [n for n in agente_obj.skill_names if n.startswith("mcp:")]
            mcp_tools = await load_mcp_tools_for_skills(mcp_skills, servers, stack)
            agent = _build_agent_obj(agente_obj, extra_tools=mcp_tools)
            final_state = await loop.run_in_executor(None, agent.run, conteudo, state)
    else:
        agent = _get_or_build_agent(agente_obj)
        final_state = await loop.run_in_executor(None, agent.run, conteudo, state)

    if agent.last_state:
        sessions.update(session_id, agent.last_state)

    answer = ""
    if final_state and final_state.get("messages"):
        last_msg = final_state["messages"][-1]
        if isinstance(last_msg, AIMessage):
            answer = last_msg.content or ""
    if not answer:
        return

    # Salvar resposta do agente
    async with AsyncSessionLocal() as db:
        msg_agente = MensagemAtendimento(
            atendimento_id=atendimento_id,
            origem=MensagemOrigem.AGENTE,
            conteudo=answer,
        )
        db.add(msg_agente)
        await db.commit()

    await atendimento_sse_manager.broadcast(atendimento_id, {
        "type": "NOVA_MENSAGEM",
        "origem": "AGENTE",
        "conteudo": answer,
    })

    # Enviar resposta via Telegram Bot API
    try:
        chat_id = int(numero)
        async with get_telegram_client(instancia.bot_token) as client:
            await client.post("/sendMessage", json={"chat_id": chat_id, "text": answer})
    except (ValueError, Exception):
        pass


async def _executar_e_responder_direto(
    instancia: TelegramInstancia,
    agente_obj: Agente,
    conteudo: str,
    session_id: str,
) -> None:
    """Executa agente e responde diretamente sem criar atendimento."""
    sessions = get_session_manager()
    state = sessions.get(session_id)
    loop = asyncio.get_event_loop()

    agent = _get_or_build_agent(agente_obj)
    final_state = await loop.run_in_executor(None, agent.run, conteudo, state)

    if agent.last_state:
        sessions.update(session_id, agent.last_state)

    answer = ""
    if final_state and final_state.get("messages"):
        last_msg = final_state["messages"][-1]
        if isinstance(last_msg, AIMessage):
            answer = last_msg.content or ""
    if not answer:
        return

    try:
        chat_id = int(session_id.replace("telegram:", ""))
        async with get_telegram_client(instancia.bot_token) as client:
            await client.post("/sendMessage", json={"chat_id": chat_id, "text": answer})
    except (ValueError, Exception):
        pass
