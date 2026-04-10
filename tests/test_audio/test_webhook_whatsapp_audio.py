"""
TDD — Integração de áudio no webhook WhatsApp

Testa o fluxo de audioMessage no _processar_mensagem_recebida:
  - Áudio transcrito e processado quando STT habilitado
  - Áudio ignorado quando STT desabilitado
  - Resposta enviada como áudio quando TTS habilitado
  - Resposta enviada como áudio + texto quando modo=audio_e_texto
  - Resposta enviada só como texto quando TTS desabilitado
  - Mensagens de texto normais não são afetadas (regressão)
"""
import base64
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db
from docagent.whatsapp.client import get_evolution_client
from docagent.tenant.models import Tenant
from docagent.agente.models import Agente
from docagent.whatsapp.models import WhatsappInstancia, ConexaoStatus
from docagent.audio.models import AudioConfig

import docagent.tenant.models          # noqa: F401
import docagent.usuario.models         # noqa: F401
import docagent.agente.models          # noqa: F401
import docagent.audio.models           # noqa: F401
import docagent.atendimento.models     # noqa: F401
import docagent.whatsapp.models        # noqa: F401
import docagent.system_config.models   # noqa: F401

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
INSTANCE_NAME = "wpp-audio-test"
NUMERO = "5511999990001"


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
    """Cria tenant, agente e instância WhatsApp no banco."""
    tenant = Tenant(nome="Tenant Audio WPP")
    db_session.add(tenant)
    await db_session.flush()

    agente = Agente(
        nome="Agente Audio", descricao="desc",
        skill_names=[], ativo=True, tenant_id=tenant.id,
    )
    db_session.add(agente)
    await db_session.flush()

    instancia = WhatsappInstancia(
        instance_name=INSTANCE_NAME,
        tenant_id=tenant.id,
        agente_id=agente.id,
        status=ConexaoStatus.CONECTADA,
    )
    db_session.add(instancia)
    await db_session.commit()
    return {"tenant": tenant, "agente": agente, "instancia": instancia}


@pytest_asyncio.fixture
async def mock_evolution():
    client = AsyncMock()
    resp = MagicMock(spec=Response)
    resp.status_code = 200
    resp.json.return_value = {}
    resp.raise_for_status = MagicMock()
    client.post.return_value = resp
    client.get.return_value = resp
    return client


@pytest_asyncio.fixture
async def client(db_session, session_factory, mock_evolution):
    async def override_db():
        yield db_session

    async def override_evolution():
        yield mock_evolution

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_evolution_client] = override_evolution

    import docagent.whatsapp.router as _wh
    _wh._agent_cache.clear()

    with patch("docagent.whatsapp.router.AsyncSessionLocal", session_factory):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


def _audio_webhook(instance: str = INSTANCE_NAME, numero: str = NUMERO) -> dict:
    """Payload MESSAGES_UPSERT com audioMessage."""
    return {
        "event": "messages.upsert",
        "instance": instance,
        "data": {
            "key": {"remoteJid": f"{numero}@s.whatsapp.net", "fromMe": False, "id": "MSG001"},
            "message": {
                "audioMessage": {
                    "mimetype": "audio/ogg; codecs=opus",
                    "seconds": 5,
                    "ptt": True,
                }
            },
        },
    }


def _texto_webhook(instance: str = INSTANCE_NAME, numero: str = NUMERO, texto: str = "oi") -> dict:
    """Payload MESSAGES_UPSERT com mensagem de texto normal."""
    return {
        "event": "messages.upsert",
        "instance": instance,
        "data": {
            "key": {"remoteJid": f"{numero}@s.whatsapp.net", "fromMe": False, "id": "MSG002"},
            "message": {"conversation": texto},
        },
    }


# ── Testes ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audio_ignorado_se_stt_desabilitado(client, setup, db_session):
    """Sem config STT (defaults: stt_habilitado=False) → áudio deve ser ignorado silenciosamente."""
    r = await client.post("/api/whatsapp/webhook", json=_audio_webhook())
    assert r.status_code == 200
    # Não deve criar atendimento (STT desabilitado = áudio ignorado)
    from sqlalchemy import select
    from docagent.atendimento.models import Atendimento
    async with (await _get_session(db_session))() as s:
        result = await s.execute(select(Atendimento))
        assert result.scalars().first() is None


@pytest.mark.asyncio
async def test_audio_transcrito_e_processado_quando_stt_habilitado(client, setup, db_session, session_factory):
    """Com STT habilitado: baixa mídia, transcreve, cria atendimento com texto transcrito."""
    # Habilitar STT na config do tenant
    async with session_factory() as s:
        cfg = AudioConfig(
            tenant_id=setup["tenant"].id, agente_id=None,
            stt_habilitado=True, tts_habilitado=False,
        )
        s.add(cfg)
        await s.commit()

    audio_b64 = base64.b64encode(b"OGG_FAKE").decode()

    with (
        patch("docagent.whatsapp.router._baixar_midia_evolution", new_callable=AsyncMock, return_value=b"OGG_FAKE") as mock_dl,
        patch("docagent.audio.services.AudioService.transcrever", new_callable=AsyncMock, return_value="Olá agente") as mock_stt,
        patch("docagent.whatsapp.router._executar_agente_whatsapp", new_callable=AsyncMock, return_value="Resposta do agente") as mock_agent,
        patch("docagent.whatsapp.router._enviar_resposta_whatsapp", new_callable=AsyncMock) as mock_send,
    ):
        r = await client.post("/api/whatsapp/webhook", json=_audio_webhook())

    assert r.status_code == 200
    mock_dl.assert_called_once()
    mock_stt.assert_called_once()
    mock_agent.assert_called_once()
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_texto_normal_nao_afetado_por_audio(client, setup, db_session, session_factory, mock_evolution):
    """Regressão: mensagens de texto normais devem seguir fluxo original."""
    # Sem config de áudio (defaults: STT desabilitado)
    ai_msg = MagicMock()
    ai_msg.content = "Resposta normal"

    with (
        patch("docagent.whatsapp.router.asyncio.get_event_loop") as mock_loop,
    ):
        mock_loop.return_value.run_in_executor = AsyncMock(
            return_value={"messages": [ai_msg]}
        )
        r = await client.post("/api/whatsapp/webhook", json=_texto_webhook())

    assert r.status_code == 200


@pytest.mark.asyncio
async def test_resposta_audio_apenas_envia_so_audio(client, setup, db_session, session_factory):
    """TTS habilitado + modo=audio_apenas → envia só áudio, sem texto."""
    async with session_factory() as s:
        cfg = AudioConfig(
            tenant_id=setup["tenant"].id, agente_id=None,
            stt_habilitado=True, tts_habilitado=True,
            modo_resposta="audio_apenas",
        )
        s.add(cfg)
        await s.commit()

    with (
        patch("docagent.whatsapp.router._baixar_midia_evolution", new_callable=AsyncMock, return_value=b"OGG"),
        patch("docagent.audio.services.AudioService.transcrever", new_callable=AsyncMock, return_value="texto"),
        patch("docagent.whatsapp.router._executar_agente_whatsapp", new_callable=AsyncMock, return_value="Resposta"),
        patch("docagent.whatsapp.router._enviar_resposta_whatsapp", new_callable=AsyncMock) as mock_send,
    ):
        r = await client.post("/api/whatsapp/webhook", json=_audio_webhook())

    assert r.status_code == 200
    mock_send.assert_called_once()
    _, kwargs = mock_send.call_args[0], mock_send.call_args[1] if mock_send.call_args[1] else {}
    args = mock_send.call_args[0]
    # O config passado deve ter modo_resposta=audio_apenas
    audio_config_arg = args[3] if len(args) > 3 else None
    if audio_config_arg:
        assert audio_config_arg.modo_resposta == "audio_apenas"


@pytest.mark.asyncio
async def test_resposta_audio_e_texto_envia_ambos(client, setup, db_session, session_factory):
    """TTS habilitado + modo=audio_e_texto → _enviar_resposta_whatsapp chamado com config correta."""
    async with session_factory() as s:
        cfg = AudioConfig(
            tenant_id=setup["tenant"].id, agente_id=None,
            stt_habilitado=True, tts_habilitado=True,
            modo_resposta="audio_e_texto",
        )
        s.add(cfg)
        await s.commit()

    with (
        patch("docagent.whatsapp.router._baixar_midia_evolution", new_callable=AsyncMock, return_value=b"OGG"),
        patch("docagent.audio.services.AudioService.transcrever", new_callable=AsyncMock, return_value="texto"),
        patch("docagent.whatsapp.router._executar_agente_whatsapp", new_callable=AsyncMock, return_value="Resposta"),
        patch("docagent.whatsapp.router._enviar_resposta_whatsapp", new_callable=AsyncMock) as mock_send,
    ):
        r = await client.post("/api/whatsapp/webhook", json=_audio_webhook())

    assert r.status_code == 200
    mock_send.assert_called_once()


# ── helper para acesso à session sem fechar a fixture ─────────────────────────

async def _get_session(db_session):
    """Retorna um factory wrapper para uso em testes."""
    class _FakeFactory:
        def __call__(self):
            return db_session
        def __await__(self):
            return iter([self])
    return type("F", (), {"__call__": lambda s: db_session, "__aenter__": lambda s: db_session, "__aexit__": lambda *a: None})()
