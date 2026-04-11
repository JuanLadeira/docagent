"""
TDD — AudioService.resolver_config()

Testa a cascata de resolução de configuração de áudio:
  1. Agente com config própria → usa ela
  2. Agente sem config → usa config padrão do tenant (agente_id IS NULL)
  3. Nenhuma config no banco → retorna system defaults (AudioConfig sintético)
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.audio.models import AudioConfig, ModoResposta, SttProvider, TtsProvider


# ── helpers ───────────────────────────────────────────────────────────────────

async def _criar_config(
    db: AsyncSession,
    tenant_id: int,
    agente_id: int | None = None,
    stt_habilitado: bool = False,
    tts_habilitado: bool = False,
    stt_provider: str = SttProvider.FASTER_WHISPER.value,
    tts_provider: str = TtsProvider.PIPER.value,
    modo_resposta: str = ModoResposta.AUDIO_E_TEXTO.value,
) -> AudioConfig:
    cfg = AudioConfig(
        tenant_id=tenant_id,
        agente_id=agente_id,
        stt_habilitado=stt_habilitado,
        tts_habilitado=tts_habilitado,
        stt_provider=stt_provider,
        tts_provider=tts_provider,
        modo_resposta=modo_resposta,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


# ── testes ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolver_config_agente_proprio(db_session, tenant, agente):
    """Agente com config própria → retorna config do agente."""
    from docagent.audio.services import AudioService

    # config padrão do tenant (deve ser ignorada)
    await _criar_config(db_session, tenant.id, agente_id=None, stt_habilitado=False)
    # config específica do agente
    await _criar_config(db_session, tenant.id, agente_id=agente.id, stt_habilitado=True)

    cfg = await AudioService.resolver_config(agente.id, tenant.id, db_session)

    assert cfg.stt_habilitado is True
    assert cfg.agente_id == agente.id


@pytest.mark.asyncio
async def test_resolver_config_fallback_tenant(db_session, tenant, agente):
    """Agente sem config → usa config padrão do tenant."""
    from docagent.audio.services import AudioService

    await _criar_config(db_session, tenant.id, agente_id=None, tts_habilitado=True)

    cfg = await AudioService.resolver_config(agente.id, tenant.id, db_session)

    assert cfg.tts_habilitado is True
    assert cfg.agente_id is None


@pytest.mark.asyncio
async def test_resolver_config_system_default(db_session, tenant, agente):
    """Sem nenhuma config no banco → retorna system defaults."""
    from docagent.audio.services import AudioService

    cfg = await AudioService.resolver_config(agente.id, tenant.id, db_session)

    # System defaults: STT e TTS desabilitados
    assert cfg.stt_habilitado is False
    assert cfg.tts_habilitado is False
    assert cfg.stt_provider == SttProvider.FASTER_WHISPER.value
    assert cfg.tts_provider == TtsProvider.PIPER.value
    assert cfg.modo_resposta == ModoResposta.AUDIO_E_TEXTO.value
    # Não persiste no banco (é um objeto sintético)
    assert cfg.id is None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_resolver_config_agente_none(db_session, tenant):
    """agente_id=None → pula busca por agente, vai direto ao tenant."""
    from docagent.audio.services import AudioService

    await _criar_config(db_session, tenant.id, agente_id=None, stt_habilitado=True)

    cfg = await AudioService.resolver_config(None, tenant.id, db_session)

    assert cfg.stt_habilitado is True
    assert cfg.agente_id is None


@pytest.mark.asyncio
async def test_resolver_config_prioridade_agente_sobre_tenant(db_session, tenant, agente):
    """Config do agente deve ter prioridade mesmo quando ambas existem."""
    from docagent.audio.services import AudioService

    await _criar_config(
        db_session, tenant.id, agente_id=None,
        stt_habilitado=False, modo_resposta=ModoResposta.TEXTO_APENAS.value,
    )
    await _criar_config(
        db_session, tenant.id, agente_id=agente.id,
        stt_habilitado=True, modo_resposta=ModoResposta.AUDIO_APENAS.value,
    )

    cfg = await AudioService.resolver_config(agente.id, tenant.id, db_session)

    assert cfg.stt_habilitado is True
    assert cfg.modo_resposta == ModoResposta.AUDIO_APENAS.value
