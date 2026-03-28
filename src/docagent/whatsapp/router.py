"""
Router WhatsApp — integração com Evolution API via SSE (sem WebSocket).

Fluxo de mensagens recebidas:
  Evolution API → POST /api/whatsapp/webhook
    → busca instancia no banco
    → busca agente vinculado
    → executa ChatService.run()
    → responde via Evolution API

Notificações em tempo real (QR code, status):
  Frontend → GET /api/whatsapp/instancias/{id}/eventos (SSE)
  Webhook → sse_manager.broadcast()
"""
import asyncio
import json
import re
from contextlib import AsyncExitStack

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from sqlalchemy import select

from docagent.agente.models import Agente
from docagent.agents.configurable_agent import ConfigurableAgent
from docagent.agents.registry import AgentConfig
from docagent.base_agent import BaseAgent
from docagent.atendimento.models import Atendimento, AtendimentoStatus, Contato, MensagemAtendimento, MensagemOrigem
from docagent.atendimento.sse import atendimento_lista_sse_manager, atendimento_sse_manager
from docagent.auth.current_user import CurrentUser
from docagent.database import AsyncSessionLocal
from docagent.dependencies import get_session_manager
from docagent.settings import Settings
from docagent.whatsapp.models import ConexaoStatus, WhatsappInstancia
from docagent.whatsapp.schemas import (
    InstanciaCreate,
    InstanciaPublic,
    MensagemMidiaRequest,
    MensagemTextoRequest,
    WebhookEvento,
)
from docagent.whatsapp.services import WhatsappServiceDep
from docagent.whatsapp.ws_manager import sse_manager

router = APIRouter(
    prefix="/api/whatsapp",
    tags=["WhatsApp"],
)

# Cache de agentes construídos, keyed por (agente_id, skill_names, system_prompt).
# Invalida automaticamente quando a configuração do agente muda.
# Agentes com skills mcp:* NÃO são cacheados — precisam de conexão ativa por requisição.
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
    """Retorna o agente cacheado ou constrói um novo se a config mudou.
    Agentes com skills MCP nunca são cacheados — use _build_agent_obj diretamente."""
    cache_key = (
        agente_obj.id,
        tuple(agente_obj.skill_names),
        agente_obj.system_prompt or "",
    )
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = _build_agent_obj(agente_obj)
    return _agent_cache[cache_key]


async def _get_instancia_or_404(instancia_id: int, current_user: CurrentUser, service: WhatsappServiceDep):
    instancia = await service.obter_instancia(instancia_id, current_user.tenant_id)
    if not instancia:
        raise HTTPException(status_code=404, detail="Instância não encontrada")
    return instancia


# ── CRUD de instâncias ────────────────────────────────────────────────────────

@router.get("/instancias", response_model=list[InstanciaPublic])
async def listar_instancias(current_user: CurrentUser, service: WhatsappServiceDep):
    return await service.listar_instancias(current_user.tenant_id)


@router.post("/instancias", response_model=InstanciaPublic, status_code=status.HTTP_201_CREATED)
async def criar_instancia(
    data: InstanciaCreate,
    request: Request,
    current_user: CurrentUser,
    service: WhatsappServiceDep,
):
    settings = Settings()
    webhook_url = f"{settings.WEBHOOK_BASE_URL}/api/whatsapp/webhook"
    return await service.criar_instancia(current_user.tenant_id, data, webhook_url)


@router.get("/instancias/{instancia_id}/qrcode")
async def obter_qrcode(
    instancia_id: int,
    current_user: CurrentUser,
    service: WhatsappServiceDep,
):
    instancia = await _get_instancia_or_404(instancia_id, current_user, service)
    return await service.obter_qrcode(instancia)


@router.get("/instancias/{instancia_id}/status", response_model=InstanciaPublic)
async def sincronizar_status(
    instancia_id: int,
    current_user: CurrentUser,
    service: WhatsappServiceDep,
):
    instancia = await _get_instancia_or_404(instancia_id, current_user, service)
    return await service.sincronizar_status(instancia)


@router.delete("/instancias/{instancia_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_instancia(
    instancia_id: int,
    current_user: CurrentUser,
    service: WhatsappServiceDep,
):
    instancia = await _get_instancia_or_404(instancia_id, current_user, service)
    await service.deletar_instancia(instancia)


# ── Envio de mensagens ────────────────────────────────────────────────────────

@router.post("/instancias/{instancia_id}/mensagens/texto")
async def enviar_texto(
    instancia_id: int,
    data: MensagemTextoRequest,
    current_user: CurrentUser,
    service: WhatsappServiceDep,
):
    instancia = await _get_instancia_or_404(instancia_id, current_user, service)
    return await service.enviar_texto(instancia, data)


@router.post("/instancias/{instancia_id}/mensagens/midia")
async def enviar_midia(
    instancia_id: int,
    data: MensagemMidiaRequest,
    current_user: CurrentUser,
    service: WhatsappServiceDep,
):
    instancia = await _get_instancia_or_404(instancia_id, current_user, service)
    return await service.enviar_midia(instancia, data)


# ── SSE: eventos em tempo real (QR code, status) ─────────────────────────────

@router.get("/instancias/{instancia_id}/eventos")
async def eventos_instancia(
    instancia_id: int,
    current_user: CurrentUser,
    service: WhatsappServiceDep,
):
    """Stream SSE de eventos da instância (QRCODE_UPDATED, CONNECTION_UPDATE).
    O cliente se inscreve aqui e recebe eventos conforme chegam via webhook."""
    instancia = await _get_instancia_or_404(instancia_id, current_user, service)

    async def generate():
        queue = await sse_manager.subscribe(instancia.tenant_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield 'data: {"type":"ping"}\n\n'
        finally:
            sse_manager.unsubscribe(instancia.tenant_id, queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Webhook (recebe eventos da Evolution API) ─────────────────────────────────

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receber_webhook(evento: WebhookEvento):
    # Evolution API v1 usa maiúsculo+underscore; v2 usa minúsculo+ponto
    event_normalized = evento.event.upper().replace(".", "_")
    if event_normalized == "QRCODE_UPDATED":
        await _processar_qrcode(evento)
    elif event_normalized == "CONNECTION_UPDATE":
        await _processar_connection_update(evento)
    elif event_normalized == "MESSAGES_UPSERT":
        await _processar_mensagem_recebida(evento)
    return {"received": True, "event": evento.event, "instance": evento.instance}


async def _processar_qrcode(evento: WebhookEvento) -> None:
    """Recebe QR Code da Evolution API e faz broadcast via SSE."""
    try:
        raw = evento.data.get("qrcode", {}).get("base64") or evento.data.get("base64") or ""
        if not raw:
            return

        qr_base64 = raw if raw.startswith("data:") else f"data:image/png;base64,{raw}"

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(WhatsappInstancia).where(WhatsappInstancia.instance_name == evento.instance)
            )
            instancia = result.scalar_one_or_none()
            if not instancia:
                return

        await sse_manager.broadcast(instancia.tenant_id, {
            "type": "QRCODE_UPDATED",
            "instance_name": evento.instance,
            "qr_base64": qr_base64,
        })
    except Exception:
        pass


async def _processar_connection_update(evento: WebhookEvento) -> None:
    """Atualiza status da instância no banco e faz broadcast via SSE."""
    try:
        state = evento.data.get("state") or evento.data.get("instance", {}).get("state") or ""

        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(WhatsappInstancia).where(WhatsappInstancia.instance_name == evento.instance)
                )
                instancia = result.scalar_one_or_none()
                if not instancia:
                    return

                novo_status = {
                    "open": ConexaoStatus.CONECTADA,
                    "connecting": ConexaoStatus.CONECTANDO,
                    "close": ConexaoStatus.DESCONECTADA,
                }.get(state)

                if novo_status and instancia.status != novo_status:
                    instancia.status = novo_status

                tenant_id = instancia.tenant_id
                status_val = instancia.status.value

        # Ao conectar, reconfigura webhook (pode ter sido perdido após restart)
        if state == "open":
            settings = Settings()
            webhook_url = f"{settings.WEBHOOK_BASE_URL}/api/whatsapp/webhook"
            try:
                async with httpx.AsyncClient(
                    base_url=settings.EVOLUTION_API_URL,
                    headers={"apikey": settings.EVOLUTION_API_KEY},
                    timeout=10.0,
                ) as client:
                    await client.post(
                        f"/webhook/set/{evento.instance}",
                        json={
                            "webhook": {
                                "url": webhook_url,
                                "enabled": True,
                                "byEvents": False,
                                "base64": False,
                                "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE", "QRCODE_UPDATED"],
                            }
                        },
                    )
            except Exception:
                pass

        await sse_manager.broadcast(tenant_id, {
            "type": "CONNECTION_UPDATE",
            "instance_name": evento.instance,
            "status": status_val,
        })
    except Exception:
        pass


async def _resolver_lid_para_numero(instance_name: str, lid_jid: str) -> str | None:
    """Tenta resolver um @lid JID para número de telefone via Evolution API.

    Usa fetchProfilePictureUrl que internamente resolve o JID e retorna o wuid
    no formato 5511999999@s.whatsapp.net, do qual extraímos o telefone.
    Retorna None se não conseguir resolver.
    """
    try:
        settings = Settings()
        async with httpx.AsyncClient(
            base_url=settings.EVOLUTION_API_URL,
            headers={"apikey": settings.EVOLUTION_API_KEY},
            timeout=10.0,
        ) as client:
            r = await client.post(
                f"/chat/fetchProfilePictureUrl/{instance_name}",
                json={"number": lid_jid},
            )
            if r.status_code == 200:
                wuid = r.json().get("wuid", "")
                if wuid and "@s.whatsapp.net" in wuid:
                    return wuid.replace("@s.whatsapp.net", "")
    except Exception:
        pass
    return None


async def _processar_mensagem_recebida(evento: WebhookEvento) -> None:
    """Recebe mensagem do WhatsApp, gerencia atendimento e executa o agente se ATIVO."""
    import logging
    log = logging.getLogger("docagent.webhook")
    try:
        data = evento.data
        key = data.get("key", {})
        if key.get("fromMe"):
            return

        remote_jid = key.get("remoteJid", "")
        if "@g.us" in remote_jid:
            return  # ignorar grupos

        # LID = WhatsApp privacy mode (newer accounts): sem número de telefone real disponível.
        # Tentamos resolver via Evolution API. Se resolver, tratamos como número normal.
        # Se não resolver, criamos o atendimento mas não acionamos o agente.
        is_lid = "@lid" in remote_jid
        if is_lid:
            numero_resolvido = await _resolver_lid_para_numero(evento.instance, remote_jid)
            if numero_resolvido:
                numero = re.sub(r"[^\d]", "", numero_resolvido)
                is_lid = False
            else:
                numero = re.sub(r"[^\d]", "", remote_jid.replace("@lid", ""))
        else:
            numero = re.sub(r"[^\d]", "", remote_jid.replace("@s.whatsapp.net", ""))

        conteudo = (
            data.get("message", {}).get("conversation")
            or data.get("message", {}).get("extendedTextMessage", {}).get("text")
            or ""
        )
        if not conteudo:
            return

        session_id = f"whatsapp:{numero}"

        # Buscar instância, agente e gerenciar atendimento
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(WhatsappInstancia).where(WhatsappInstancia.instance_name == evento.instance)
            )
            instancia = result.scalar_one_or_none()
            if not instancia:
                return

            agente = None
            if instancia.agente_id:
                agente_result = await db.execute(
                    select(Agente).where(Agente.id == instancia.agente_id, Agente.ativo == True)
                )
                agente = agente_result.scalar_one_or_none()

            # Buscar contato vinculado ao número
            contato_result = await db.execute(
                select(Contato).where(
                    Contato.numero == numero,
                    Contato.tenant_id == instancia.tenant_id,
                    Contato.instancia_id == instancia.id,
                )
            )
            contato = contato_result.scalar_one_or_none()

            # Upsert atendimento
            at_result = await db.execute(
                select(Atendimento).where(
                    Atendimento.instancia_id == instancia.id,
                    Atendimento.numero == numero,
                    Atendimento.status != AtendimentoStatus.ENCERRADO,
                )
            )
            atendimento = at_result.scalar_one_or_none()
            is_novo = atendimento is None
            if not atendimento:
                atendimento = Atendimento(
                    numero=numero,
                    instancia_id=instancia.id,
                    tenant_id=instancia.tenant_id,
                    status=AtendimentoStatus.ATIVO,
                    contato_id=contato.id if contato else None,
                    nome_contato=contato.nome if contato else None,
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
            atendimento_tenant_id = instancia.tenant_id
            agente_obj = agente  # mantém referência antes do commit
            # Capturar dados para SSE antes do commit
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

        # Broadcast mensagem do contato via SSE
        await atendimento_sse_manager.broadcast(atendimento_id, {
            "type": "NOVA_MENSAGEM",
            "origem": "CONTATO",
            "conteudo": conteudo,
        })

        # Broadcast lista SSE (novo ou atualizado)
        event_type = "NOVO_ATENDIMENTO" if is_novo else "ATENDIMENTO_ATUALIZADO"
        await atendimento_lista_sse_manager.broadcast(atendimento_tenant_id, {
            "type": event_type,
            "atendimento": at_data,
        })

        # Se operador assumiu, não há agente configurado, ou @lid não resolvido, não acionar o agente.
        if atendimento_status == AtendimentoStatus.HUMANO or not agente or is_lid:
            return

        # Executar agente — executor libera o event loop durante a inferência LLM.
        # Agentes com skills MCP carregam tools via AsyncExitStack (conexão ativa durante run).
        sessions = get_session_manager()
        state = sessions.get(session_id)
        loop = asyncio.get_event_loop()

        if _tem_skills_mcp(agente_obj):
            from docagent.mcp_server.models import McpServer
            from docagent.mcp_server.services import load_mcp_tools_for_skills
            async with AsyncExitStack() as stack:
                async with AsyncSessionLocal() as mcp_db:
                    from sqlalchemy.orm import selectinload
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

        # Broadcast resposta do agente via SSE
        await atendimento_sse_manager.broadcast(atendimento_id, {
            "type": "NOVA_MENSAGEM",
            "origem": "AGENTE",
            "conteudo": answer,
        })

        # Enviar resposta via Evolution API
        settings = Settings()
        async with httpx.AsyncClient(
            base_url=settings.EVOLUTION_API_URL,
            headers={"apikey": settings.EVOLUTION_API_KEY},
            timeout=60.0,
        ) as client:
            await client.post(
                f"/message/sendText/{evento.instance}",
                json={"number": numero, "text": answer},
            )
    except Exception as e:
        log.exception("Erro em _processar_mensagem_recebida instance=%s: %s", evento.instance, e)
