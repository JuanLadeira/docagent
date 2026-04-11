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
import base64
import json
import logging
import re
from contextlib import AsyncExitStack

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from sqlalchemy import select

from docagent.agente.models import Agente
from docagent.agent.configurable import ConfigurableAgent
from docagent.agent.registry import AgentConfig
from docagent.agent.base import BaseAgent
from docagent.atendimento.models import Atendimento, AtendimentoStatus, Contato, MensagemAtendimento, MensagemOrigem, MensagemTipo
from docagent.atendimento.sse import atendimento_lista_sse_manager, atendimento_sse_manager
from docagent.auth.current_user import CurrentUser
from docagent.database import AsyncSessionLocal
from docagent.dependencies import get_session_manager
from docagent.settings import Settings
from docagent.whatsapp.models import ConexaoStatus, WhatsappInstancia
from docagent.whatsapp.schemas import (
    InstanciaCreate,
    InstanciaPublic,
    InstanciaUpdate,
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


def _build_agent_obj(agente_obj: Agente, extra_tools: list | None = None, llm=None) -> BaseAgent:
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
        llm=llm,
    ).build()


def _get_or_build_agent(agente_obj: Agente, llm=None, llm_provider: str = "", llm_model: str = "") -> BaseAgent:
    """Retorna o agente cacheado ou constrói um novo se a config mudou.
    Agentes com skills MCP nunca são cacheados — use _build_agent_obj diretamente."""
    cache_key = (
        agente_obj.id,
        tuple(agente_obj.skill_names),
        agente_obj.system_prompt or "",
        llm_provider,
        llm_model,
    )
    if cache_key not in _agent_cache:
        _agent_cache[cache_key] = _build_agent_obj(agente_obj, llm=llm)
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


@router.patch("/instancias/{instancia_id}", response_model=InstanciaPublic)
async def atualizar_instancia(
    instancia_id: int,
    data: InstanciaUpdate,
    current_user: CurrentUser,
    service: WhatsappServiceDep,
):
    instancia = await _get_instancia_or_404(instancia_id, current_user, service)
    return await service.atualizar_instancia(instancia, data)


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


_log = logging.getLogger("docagent.webhook")


async def _baixar_midia_evolution(instance_name: str, key: dict) -> bytes:
    """Baixa mídia de uma mensagem WhatsApp via Evolution API e retorna bytes brutos."""
    settings = Settings()
    async with httpx.AsyncClient(
        base_url=settings.EVOLUTION_API_URL,
        headers={"apikey": settings.EVOLUTION_API_KEY},
        timeout=30.0,
    ) as client:
        r = await client.post(
            f"/chat/getBase64FromMediaMessage/{instance_name}",
            json={"key": key, "convertToMp4": False},
        )
        r.raise_for_status()
        b64 = r.json().get("base64", "")
        return base64.b64decode(b64) if b64 else b""


async def _executar_agente_whatsapp(
    instancia: "WhatsappInstancia",
    agente_obj: "Agente",
    conteudo: str,
    session_id: str,
    tenant_id: int,
    atendimento_id: int,
) -> str:
    """Executa o agente LangGraph para o caminho de áudio e retorna a resposta em texto."""
    sessions = get_session_manager()
    state = sessions.get(session_id)
    loop = asyncio.get_event_loop()

    from docagent.agent.llm_factory import get_tenant_llm
    async with AsyncSessionLocal() as llm_db:
        tenant_llm = await get_tenant_llm(tenant_id, llm_db)
    llm_provider = getattr(tenant_llm, "model_name", "") or getattr(tenant_llm, "model", "") or ""

    handoff_flag: dict = {"requested": False}
    handoff_extra: list = []
    if "human_handoff" in agente_obj.skill_names:
        from docagent.agent.skills.human_handoff import HumanHandoffSkill
        handoff_extra = [HumanHandoffSkill(flag=handoff_flag).as_tool()]

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
            agent = _build_agent_obj(agente_obj, extra_tools=mcp_tools + handoff_extra, llm=tenant_llm)
            final_state = await loop.run_in_executor(None, agent.run, conteudo, state)
    else:
        extra = handoff_extra or None
        if extra:
            agent = _build_agent_obj(agente_obj, extra_tools=extra, llm=tenant_llm)
        else:
            agent = _get_or_build_agent(agente_obj, llm=tenant_llm, llm_provider=llm_provider, llm_model="")
        final_state = await loop.run_in_executor(None, agent.run, conteudo, state)

    if agent.last_state:
        sessions.update(session_id, agent.last_state)

    if handoff_flag["requested"]:
        async with AsyncSessionLocal() as db:
            from docagent.atendimento.services import AtendimentoService
            _at = await db.get(Atendimento, atendimento_id)
            if _at:
                await AtendimentoService(db).sinalizar_humano(_at)
                await db.commit()

    answer = ""
    if final_state and final_state.get("messages"):
        last_msg = final_state["messages"][-1]
        if isinstance(last_msg, AIMessage):
            from docagent.utils import strip_emojis
            answer = strip_emojis(last_msg.content or "")
    return answer


async def _enviar_resposta_whatsapp(
    instance_name: str,
    numero: str,
    answer: str,
    audio_config,
) -> None:
    """Envia a resposta do agente via WhatsApp: áudio, texto ou ambos, conforme config."""
    from docagent.audio.models import ModoResposta, TtsProvider
    from docagent.audio.services import AudioService

    settings = Settings()

    if audio_config is not None and audio_config.tts_habilitado:
        try:
            audio_bytes = await AudioService.sintetizar(answer, audio_config)
            b64_audio = base64.b64encode(audio_bytes).decode()
            async with httpx.AsyncClient(
                base_url=settings.EVOLUTION_API_URL,
                headers={"apikey": settings.EVOLUTION_API_KEY},
                timeout=60.0,
            ) as client:
                await client.post(
                    f"/message/sendWhatsAppAudio/{instance_name}",
                    json={"number": numero, "audio": b64_audio, "encoding": True},
                )
            if audio_config.modo_resposta != ModoResposta.AUDIO_APENAS.value:
                async with httpx.AsyncClient(
                    base_url=settings.EVOLUTION_API_URL,
                    headers={"apikey": settings.EVOLUTION_API_KEY},
                    timeout=60.0,
                ) as client:
                    await client.post(
                        f"/message/sendText/{instance_name}",
                        json={"number": numero, "text": answer},
                    )
        except Exception:
            _log.exception("Erro ao sintetizar/enviar áudio — enviando texto como fallback")
            await _enviar_texto_evolution(instance_name, numero, answer, settings)
    else:
        await _enviar_texto_evolution(instance_name, numero, answer, settings)


async def _enviar_audio_bytes_whatsapp(
    instance_name: str,
    numero: str,
    audio_bytes: bytes,
    answer: str,
    audio_config,
) -> None:
    """Envia bytes de áudio já gerados para o WhatsApp, evitando sintetizar duas vezes."""
    from docagent.audio.models import ModoResposta
    settings = Settings()
    b64_audio = base64.b64encode(audio_bytes).decode()
    async with httpx.AsyncClient(
        base_url=settings.EVOLUTION_API_URL,
        headers={"apikey": settings.EVOLUTION_API_KEY},
        timeout=60.0,
    ) as client:
        await client.post(
            f"/message/sendWhatsAppAudio/{instance_name}",
            json={"number": numero, "audio": b64_audio, "encoding": True},
        )
    if audio_config and audio_config.modo_resposta != ModoResposta.AUDIO_APENAS.value:
        await _enviar_texto_evolution(instance_name, numero, answer, settings)


async def _enviar_texto_evolution(instance_name: str, numero: str, answer: str, settings: Settings) -> None:
    typing_delay_ms = max(1500, min(5000, len(answer) * 30))
    async with httpx.AsyncClient(
        base_url=settings.EVOLUTION_API_URL,
        headers={"apikey": settings.EVOLUTION_API_KEY},
        timeout=60.0,
    ) as client:
        await client.post(
            f"/message/sendText/{instance_name}",
            json={
                "number": numero,
                "text": answer,
                "options": {"delay": typing_delay_ms, "presence": "composing"},
            },
        )


async def _processar_mensagem_recebida(evento: WebhookEvento) -> None:
    """Recebe mensagem do WhatsApp, gerencia atendimento e executa o agente se ATIVO."""
    log = _log
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

        message_content = data.get("message", {})
        conteudo = (
            message_content.get("conversation")
            or message_content.get("extendedTextMessage", {}).get("text")
            or ""
        )
        audio_message = message_content.get("audioMessage")

        # Se não há texto nem áudio, nada a processar
        if not conteudo and not audio_message:
            return

        # ── Caminho de áudio: STT antes de seguir ────────────────────────────
        audio_config = None
        media_ref_contato: str | None = None
        if audio_message and not conteudo:
            async with AsyncSessionLocal() as db_audio:
                inst_result = await db_audio.execute(
                    select(WhatsappInstancia).where(WhatsappInstancia.instance_name == evento.instance)
                )
                inst_audio = inst_result.scalar_one_or_none()
                if not inst_audio:
                    return
                from docagent.audio.services import AudioService
                audio_config = await AudioService.resolver_config(
                    inst_audio.agente_id, inst_audio.tenant_id, db_audio
                )

            if not audio_config.stt_habilitado:
                return  # áudio ignorado quando STT desabilitado

            try:
                audio_bytes = await _baixar_midia_evolution(evento.instance, key)
                from docagent.audio.services import AudioService
                conteudo = await AudioService.transcrever(audio_bytes, audio_config)
            except Exception:
                log.exception("Erro ao transcrever áudio instance=%s", evento.instance)
                return

            if not conteudo.strip():
                return

            # Salva áudio recebido em disco para o player da UI
            from docagent.telegram.router import _salvar_audio_local
            try:
                media_ref_contato = await _salvar_audio_local(audio_bytes)
            except Exception:
                log.warning("Não foi possível salvar áudio WhatsApp em disco")
        # ─────────────────────────────────────────────────────────────────────

        # Buscar instância, agente e gerenciar atendimento
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(WhatsappInstancia).where(WhatsappInstancia.instance_name == evento.instance)
            )
            instancia = result.scalar_one_or_none()
            if not instancia:
                return

            session_id = f"whatsapp:{instancia.tenant_id}:{numero}"

            agente = None
            if instancia.agente_id:
                agente_result = await db.execute(
                    select(Agente).where(Agente.id == instancia.agente_id, Agente.ativo.is_(True))
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
            is_audio_msg = audio_message is not None
            conteudo_salvo = f"[Áudio] {conteudo}" if is_audio_msg else conteudo
            msg_contato = MensagemAtendimento(
                atendimento_id=atendimento.id,
                origem=MensagemOrigem.CONTATO,
                conteudo=conteudo_salvo,
                tipo=MensagemTipo.AUDIO.value if is_audio_msg else MensagemTipo.TEXT.value,
                media_ref=media_ref_contato,
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
                "assumido_por_id": atendimento.assumido_por_id,
                "assumido_por_nome": atendimento.assumido_por_nome,
                "contato_id": atendimento.contato_id,
                "created_at": atendimento.created_at.isoformat() if atendimento.created_at else None,
                "updated_at": atendimento.updated_at.isoformat() if atendimento.updated_at else None,
            }
            await db.commit()

        # Broadcast mensagem do contato via SSE
        await atendimento_sse_manager.broadcast(atendimento_id, {
            "type": "NOVA_MENSAGEM",
            "origem": "CONTATO",
            "conteudo": conteudo_salvo,
            "tipo": MensagemTipo.AUDIO.value if is_audio_msg else MensagemTipo.TEXT.value,
            "media_ref": media_ref_contato,
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

        # ── Caminho de áudio: usa funções extraídas ───────────────────────────
        if audio_message:
            answer = await _executar_agente_whatsapp(
                instancia=None,  # não usado internamente — agente_obj passado diretamente
                agente_obj=agente_obj,
                conteudo=conteudo,
                session_id=session_id,
                tenant_id=atendimento_tenant_id,
                atendimento_id=atendimento_id,
            )
            if not answer:
                return

            # Gerar TTS e salvar em disco para o player
            tts_media_ref: str | None = None
            if audio_config is not None and audio_config.tts_habilitado:
                try:
                    from docagent.audio.services import AudioService
                    from docagent.telegram.router import _salvar_audio_local
                    tts_bytes = await AudioService.sintetizar(answer, audio_config)
                    tts_media_ref = await _salvar_audio_local(tts_bytes)
                except Exception:
                    log.exception("Erro ao gerar TTS WhatsApp para media_ref")

            async with AsyncSessionLocal() as db:
                db.add(MensagemAtendimento(
                    atendimento_id=atendimento_id,
                    origem=MensagemOrigem.AGENTE,
                    conteudo=answer,
                    tipo=MensagemTipo.AUDIO.value if tts_media_ref else MensagemTipo.TEXT.value,
                    media_ref=tts_media_ref,
                ))
                await db.commit()

            await atendimento_sse_manager.broadcast(atendimento_id, {
                "type": "NOVA_MENSAGEM",
                "origem": "AGENTE",
                "conteudo": answer,
                "tipo": MensagemTipo.AUDIO.value if tts_media_ref else MensagemTipo.TEXT.value,
                "media_ref": tts_media_ref,
            })

            # Envia para WhatsApp (reutiliza bytes do TTS se já gerados)
            if tts_media_ref:
                import os
                filename = tts_media_ref.split(":", 1)[1]
                filepath = os.path.join(os.getcwd(), "data", "audio", filename)
                with open(filepath, "rb") as f:
                    cached_bytes = f.read()
                await _enviar_audio_bytes_whatsapp(evento.instance, numero, cached_bytes, answer, audio_config)
            else:
                await _enviar_resposta_whatsapp(evento.instance, numero, answer, audio_config)
            return
        # ─────────────────────────────────────────────────────────────────────

        # Caminho de texto — lógica original preservada
        sessions = get_session_manager()
        state = sessions.get(session_id)
        loop = asyncio.get_event_loop()

        from docagent.agent.llm_factory import get_tenant_llm
        async with AsyncSessionLocal() as llm_db:
            tenant_llm = await get_tenant_llm(atendimento_tenant_id, llm_db)
        llm_provider = getattr(tenant_llm, "model_name", "") or getattr(tenant_llm, "model", "") or ""
        llm_model = ""

        handoff_flag: dict = {'requested': False}
        handoff_extra: list = []
        if 'human_handoff' in agente_obj.skill_names:
            from docagent.agent.skills.human_handoff import HumanHandoffSkill
            handoff_extra = [HumanHandoffSkill(flag=handoff_flag).as_tool()]

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
                agent = _build_agent_obj(agente_obj, extra_tools=mcp_tools + handoff_extra, llm=tenant_llm)
                final_state = await loop.run_in_executor(None, agent.run, conteudo, state)
        else:
            extra = handoff_extra or None
            if extra:
                agent = _build_agent_obj(agente_obj, extra_tools=extra, llm=tenant_llm)
            else:
                agent = _get_or_build_agent(agente_obj, llm=tenant_llm, llm_provider=llm_provider, llm_model=llm_model)
            final_state = await loop.run_in_executor(None, agent.run, conteudo, state)
        if agent.last_state:
            sessions.update(session_id, agent.last_state)

        if handoff_flag['requested']:
            async with AsyncSessionLocal() as db:
                from docagent.atendimento.services import AtendimentoService
                _at = await db.get(Atendimento, atendimento_id)
                if _at:
                    await AtendimentoService(db).sinalizar_humano(_at)
                    await db.commit()

        answer = ""
        if final_state and final_state.get("messages"):
            last_msg = final_state["messages"][-1]
            if isinstance(last_msg, AIMessage):
                from docagent.utils import strip_emojis
                answer = strip_emojis(last_msg.content or "")
        if not answer:
            return

        if "[PEDIDO_CONFIRMADO]" in answer:
            answer = answer.replace("[PEDIDO_CONFIRMADO]", "").strip()
            if not handoff_flag['requested']:
                async with AsyncSessionLocal() as db:
                    from docagent.atendimento.services import AtendimentoService
                    _at = await db.get(Atendimento, atendimento_id)
                    if _at:
                        await AtendimentoService(db).sinalizar_humano(_at)
                        await db.commit()

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

        # Envio texto com typing delay (caminho original)
        typing_delay_ms = max(1500, min(5000, len(answer) * 30))
        settings = Settings()
        async with httpx.AsyncClient(
            base_url=settings.EVOLUTION_API_URL,
            headers={"apikey": settings.EVOLUTION_API_KEY},
            timeout=60.0,
        ) as client:
            await client.post(
                f"/message/sendText/{evento.instance}",
                json={
                    "number": numero,
                    "text": answer,
                    "options": {"delay": typing_delay_ms, "presence": "composing"},
                },
            )
    except Exception as e:
        log.exception("Erro em _processar_mensagem_recebida instance=%s: %s", evento.instance, e)
