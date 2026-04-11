"""
Router de configuração de áudio (STT + TTS) por tenant e por agente.

Endpoints:
  GET    /api/audio-config/default          → config padrão do tenant
  PUT    /api/audio-config/default          → criar/atualizar config padrão
  GET    /api/agentes/{id}/audio-config     → config efetiva do agente (cascata)
  PUT    /api/agentes/{id}/audio-config     → criar/atualizar config do agente
  DELETE /api/agentes/{id}/audio-config     → remove config específica do agente
"""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from docagent.audio.models import AudioConfig
from docagent.audio.schemas import AudioConfigCreate, AudioConfigPublic, AudioConfigUpdate
from docagent.audio.services import AudioService
from docagent.auth.current_user import CurrentUser
from docagent.database import AsyncDBSession

router = APIRouter(tags=["Áudio"])


# ── Config padrão do tenant ───────────────────────────────────────────────────

@router.get("/api/audio-config/default", response_model=AudioConfigPublic)
async def get_default_config(current_user: CurrentUser, session: AsyncDBSession):
    """Retorna a config padrão do tenant. Se não existir, retorna system defaults."""
    cfg = await AudioService.resolver_config(None, current_user.tenant_id, session)
    return _to_public(cfg, current_user.tenant_id, agente_id=None)


@router.put("/api/audio-config/default", response_model=AudioConfigPublic)
async def upsert_default_config(
    data: AudioConfigCreate,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    """Cria ou atualiza a config padrão do tenant (agente_id IS NULL)."""
    result = await session.execute(
        select(AudioConfig).where(
            AudioConfig.tenant_id == current_user.tenant_id,
            AudioConfig.agente_id.is_(None),
        )
    )
    cfg = result.scalar_one_or_none()

    if cfg is None:
        cfg = AudioConfig(tenant_id=current_user.tenant_id, agente_id=None)
        session.add(cfg)

    _aplicar_dados(cfg, data)
    await session.flush()
    await session.refresh(cfg)
    return cfg


# ── Config por agente ─────────────────────────────────────────────────────────

@router.get("/api/agentes/{agente_id}/audio-config", response_model=AudioConfigPublic)
async def get_agente_config(
    agente_id: int,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    """Retorna a config efetiva do agente (própria → padrão tenant → system defaults).
    Retorna 404 se o agente não pertencer ao tenant.
    """
    await _verificar_agente_tenant(agente_id, current_user.tenant_id, session)
    cfg = await AudioService.resolver_config(agente_id, current_user.tenant_id, session)
    return _to_public(cfg, current_user.tenant_id, agente_id=agente_id)


@router.put("/api/agentes/{agente_id}/audio-config", response_model=AudioConfigPublic)
async def upsert_agente_config(
    agente_id: int,
    data: AudioConfigUpdate,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    """Cria ou atualiza a config específica do agente."""
    await _verificar_agente_tenant(agente_id, current_user.tenant_id, session)

    result = await session.execute(
        select(AudioConfig).where(
            AudioConfig.tenant_id == current_user.tenant_id,
            AudioConfig.agente_id == agente_id,
        )
    )
    cfg = result.scalar_one_or_none()

    if cfg is None:
        cfg = AudioConfig(tenant_id=current_user.tenant_id, agente_id=agente_id)
        session.add(cfg)

    _aplicar_dados(cfg, data)
    await session.flush()
    await session.refresh(cfg)
    return cfg


@router.delete(
    "/api/agentes/{agente_id}/audio-config",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_agente_config(
    agente_id: int,
    current_user: CurrentUser,
    session: AsyncDBSession,
):
    """Remove a config específica do agente (volta a usar a padrão do tenant)."""
    await _verificar_agente_tenant(agente_id, current_user.tenant_id, session)

    result = await session.execute(
        select(AudioConfig).where(
            AudioConfig.tenant_id == current_user.tenant_id,
            AudioConfig.agente_id == agente_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="Config de áudio não encontrada para este agente.")

    await session.delete(cfg)
    await session.flush()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _verificar_agente_tenant(agente_id: int, tenant_id: int, session: AsyncDBSession):
    from docagent.agente.models import Agente
    result = await session.execute(
        select(Agente).where(Agente.id == agente_id, Agente.tenant_id == tenant_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")


def _aplicar_dados(cfg: AudioConfig, data: AudioConfigCreate | AudioConfigUpdate):
    cfg.stt_habilitado = data.stt_habilitado
    cfg.stt_provider = data.stt_provider.value
    cfg.stt_modelo = data.stt_modelo
    cfg.tts_habilitado = data.tts_habilitado
    cfg.tts_provider = data.tts_provider.value
    cfg.piper_voz = data.piper_voz
    cfg.openai_tts_voz = data.openai_tts_voz
    cfg.elevenlabs_voice_id = data.elevenlabs_voice_id
    cfg.elevenlabs_api_key = data.elevenlabs_api_key
    cfg.modo_resposta = data.modo_resposta.value


def _to_public(cfg, tenant_id: int, agente_id: int | None) -> AudioConfigPublic:
    """Converte AudioConfig ou SimpleNamespace para AudioConfigPublic."""
    return AudioConfigPublic(
        id=getattr(cfg, "id", None) or 0,
        tenant_id=getattr(cfg, "tenant_id", tenant_id),
        agente_id=getattr(cfg, "agente_id", agente_id),
        stt_habilitado=cfg.stt_habilitado,
        stt_provider=cfg.stt_provider,
        stt_modelo=cfg.stt_modelo,
        tts_habilitado=cfg.tts_habilitado,
        tts_provider=cfg.tts_provider,
        piper_voz=cfg.piper_voz,
        openai_tts_voz=cfg.openai_tts_voz,
        elevenlabs_voice_id=cfg.elevenlabs_voice_id,
        elevenlabs_api_key=None,  # nunca expor a key na resposta
        modo_resposta=cfg.modo_resposta,
    )
