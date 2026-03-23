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

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from sqlalchemy import select

from docagent.agente.models import Agente
from docagent.agents.configurable_agent import ConfigurableAgent
from docagent.agents.registry import AgentConfig
from docagent.atendimento.models import Atendimento, AtendimentoStatus, MensagemAtendimento, MensagemOrigem
from docagent.atendimento.sse import atendimento_sse_manager
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
                            "url": webhook_url,
                            "webhook_by_events": False,
                            "webhook_base64": True,
                            "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE", "QRCODE_UPDATED"],
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


async def _processar_mensagem_recebida(evento: WebhookEvento) -> None:
    """Recebe mensagem do WhatsApp, gerencia atendimento e executa o agente se ATIVO."""
    try:
        data = evento.data
        key = data.get("key", {})
        if key.get("fromMe"):
            return

        remote_jid = key.get("remoteJid", "")
        if "@g.us" in remote_jid:
            return  # ignorar grupos

        # LID = WhatsApp privacy mode (newer accounts): sem número de telefone disponível.
        # Não é possível enviar para @lid via Evolution API v1.8.x.
        # Criamos o atendimento mas não acionamos o agente.
        is_lid = "@lid" in remote_jid

        conteudo = (
            data.get("message", {}).get("conversation")
            or data.get("message", {}).get("extendedTextMessage", {}).get("text")
            or ""
        )
        if not conteudo:
            return

        numero = remote_jid.replace("@s.whatsapp.net", "").replace("@lid", "")
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

            # Upsert atendimento
            at_result = await db.execute(
                select(Atendimento).where(
                    Atendimento.instancia_id == instancia.id,
                    Atendimento.numero == numero,
                    Atendimento.status != AtendimentoStatus.ENCERRADO,
                )
            )
            atendimento = at_result.scalar_one_or_none()
            if not atendimento:
                atendimento = Atendimento(
                    numero=numero,
                    instancia_id=instancia.id,
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
            agente_obj = agente  # mantém referência antes do commit
            await db.commit()

        # Broadcast mensagem do contato via SSE
        await atendimento_sse_manager.broadcast(atendimento_id, {
            "type": "NOVA_MENSAGEM",
            "origem": "CONTATO",
            "conteudo": conteudo,
        })

        # Se operador assumiu, não há agente configurado, ou é contato LID (não é possível
        # enviar via Evolution API v1.8.x para @lid JIDs), não acionar o agente.
        if atendimento_status == AtendimentoStatus.HUMANO or not agente or is_lid:
            return

        # Executar agente
        config = AgentConfig(
            id=str(agente_obj.id),
            name=agente_obj.nome,
            description=agente_obj.descricao,
            skill_names=agente_obj.skill_names,
        )
        agent = ConfigurableAgent(
            config,
            system_prompt_override=agente_obj.system_prompt or None,
        ).build()

        sessions = get_session_manager()
        state = sessions.get(session_id)
        final_state = agent.run(conteudo, state)
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
    except Exception:
        pass  # Webhook must always return 200
