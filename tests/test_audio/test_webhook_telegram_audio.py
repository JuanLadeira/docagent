"""
TDD — Integração de áudio no webhook Telegram

Testa o fluxo de voice/audio no _processar_update:
  - Mensagem de voz transcrita e processada quando STT habilitado
  - Mensagem de voz ignorada quando STT desabilitado
  - Regressão: mensagens de texto normais não são afetadas
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db
from docagent.tenant.models import Tenant
from docagent.agente.models import Agente
from docagent.telegram.models import TelegramInstancia, TelegramBotStatus
from docagent.audio.models import AudioConfig

import docagent.tenant.models          # noqa: F401
import docagent.usuario.models         # noqa: F401
import docagent.agente.models          # noqa: F401
import docagent.audio.models           # noqa: F401
import docagent.atendimento.models     # noqa: F401
import docagent.telegram.models        # noqa: F401
import docagent.whatsapp.models        # noqa: F401
import docagent.system_config.models   # noqa: F401

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
BOT_TOKEN = "123456:TEST_TOKEN_TELEGRAM"
CHAT_ID = 987654321


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory):
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def setup(db_session):
    tenant = Tenant(nome="Tenant Audio TG")
    db_session.add(tenant)
    await db_session.flush()

    agente = Agente(
        nome="Agente TG Audio", descricao="desc",
        skill_names=[], ativo=True, tenant_id=tenant.id,
    )
    db_session.add(agente)
    await db_session.flush()

    instancia = TelegramInstancia(
        bot_token=BOT_TOKEN,
        tenant_id=tenant.id,
        agente_id=agente.id,
        cria_atendimentos=False,  # modo direto: mais simples para testar
        status=TelegramBotStatus.ATIVA,
    )
    db_session.add(instancia)
    await db_session.commit()
    return {"tenant": tenant, "agente": agente, "instancia": instancia}


@pytest_asyncio.fixture
async def client(db_session, session_factory):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db

    import docagent.telegram.router as _tg
    _tg._agent_cache.clear()

    with patch("docagent.telegram.router.AsyncSessionLocal", session_factory):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


def _voice_update(chat_id: int = CHAT_ID, file_id: str = "FILE123") -> dict:
    """Payload de update Telegram com mensagem de voz (voice)."""
    return {
        "update_id": 1001,
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "first_name": "Teste", "is_bot": False},
            "voice": {
                "file_id": file_id,
                "duration": 5,
                "mime_type": "audio/ogg",
                "file_size": 8000,
            },
        },
    }


def _audio_update(chat_id: int = CHAT_ID, file_id: str = "FILE456") -> dict:
    """Payload de update Telegram com arquivo de áudio (audio)."""
    return {
        "update_id": 1002,
        "message": {
            "message_id": 2,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "first_name": "Teste", "is_bot": False},
            "audio": {
                "file_id": file_id,
                "duration": 30,
                "mime_type": "audio/mpeg",
                "file_size": 50000,
            },
        },
    }


def _texto_update(chat_id: int = CHAT_ID, texto: str = "oi") -> dict:
    """Payload de update Telegram com mensagem de texto."""
    return {
        "update_id": 1003,
        "message": {
            "message_id": 3,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "first_name": "Teste", "is_bot": False},
            "text": texto,
        },
    }


# ── Testes ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_ignorado_se_stt_desabilitado(client, setup):
    """Sem STT habilitado (system defaults) → mensagem de voz ignorada silenciosamente."""
    r = await client.post(f"/api/telegram/webhook/{BOT_TOKEN}", json=_voice_update())
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_voice_transcrito_e_processado_quando_stt_habilitado(client, setup, session_factory):
    """Com STT habilitado: baixa arquivo, transcreve, executa agente e responde."""
    async with session_factory() as s:
        cfg = AudioConfig(
            tenant_id=setup["tenant"].id, agente_id=None,
            stt_habilitado=True, tts_habilitado=False,
        )
        s.add(cfg)
        await s.commit()

    with (
        patch("docagent.telegram.router._baixar_audio_telegram", new_callable=AsyncMock, return_value=b"OGG_BYTES") as mock_dl,
        patch("docagent.audio.services.AudioService.transcrever", new_callable=AsyncMock, return_value="Olá Telegram") as mock_stt,
        patch("docagent.telegram.router._executar_agente_telegram", new_callable=AsyncMock, return_value="Resposta TG") as mock_agent,
        patch("docagent.telegram.router._enviar_resposta_telegram", new_callable=AsyncMock) as mock_send,
    ):
        r = await client.post(f"/api/telegram/webhook/{BOT_TOKEN}", json=_voice_update())

    assert r.status_code == 200
    mock_dl.assert_called_once()
    mock_stt.assert_called_once()
    mock_agent.assert_called_once()
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_audio_file_transcrito_quando_stt_habilitado(client, setup, session_factory):
    """Arquivo de áudio (não ptt) também deve ser transcrito quando STT habilitado."""
    async with session_factory() as s:
        cfg = AudioConfig(
            tenant_id=setup["tenant"].id, agente_id=None,
            stt_habilitado=True, tts_habilitado=False,
        )
        s.add(cfg)
        await s.commit()

    with (
        patch("docagent.telegram.router._baixar_audio_telegram", new_callable=AsyncMock, return_value=b"MP3_BYTES"),
        patch("docagent.audio.services.AudioService.transcrever", new_callable=AsyncMock, return_value="texto do áudio"),
        patch("docagent.telegram.router._executar_agente_telegram", new_callable=AsyncMock, return_value="Resposta"),
        patch("docagent.telegram.router._enviar_resposta_telegram", new_callable=AsyncMock),
    ):
        r = await client.post(f"/api/telegram/webhook/{BOT_TOKEN}", json=_audio_update())

    assert r.status_code == 200


@pytest.mark.asyncio
async def test_texto_nao_afetado_por_audio(client, setup):
    """Regressão: mensagens de texto devem retornar 200 sem interferência do áudio."""
    # O agente vai tentar executar mas pode falhar (Ollama offline em testes)
    # O importante é que o webhook retorne 200 e não tente processar como áudio
    with patch("docagent.telegram.router._executar_agente_telegram", new_callable=AsyncMock, return_value="") as mock_agent:
        r = await client.post(f"/api/telegram/webhook/{BOT_TOKEN}", json=_texto_update())

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # _executar_agente_telegram NÃO deve ser chamado (caminho de texto usa lógica inline)
    mock_agent.assert_not_called()


@pytest.mark.asyncio
async def test_schema_telegram_aceita_voice_e_audio():
    """TelegramMessage deve deserializar voice e audio corretamente."""
    from docagent.telegram.schemas import TelegramMessage

    msg_voice = TelegramMessage.model_validate({
        "message_id": 1,
        "chat": {"id": 123, "type": "private"},
        "voice": {"file_id": "FILE1", "duration": 5, "mime_type": "audio/ogg", "file_size": 100},
    })
    assert msg_voice.voice is not None
    assert msg_voice.voice.file_id == "FILE1"
    assert msg_voice.text is None

    msg_audio = TelegramMessage.model_validate({
        "message_id": 2,
        "chat": {"id": 123, "type": "private"},
        "audio": {"file_id": "FILE2", "duration": 30, "mime_type": "audio/mpeg", "file_size": 5000},
    })
    assert msg_audio.audio is not None
    assert msg_audio.audio.file_id == "FILE2"
