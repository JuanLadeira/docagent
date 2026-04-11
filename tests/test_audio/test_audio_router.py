"""
TDD — audio/router.py

Endpoints:
  GET    /api/audio-config/default          → config padrão do tenant
  PUT    /api/audio-config/default          → criar/atualizar config padrão
  GET    /api/agentes/{id}/audio-config     → config do agente (ou padrão)
  PUT    /api/agentes/{id}/audio-config     → criar/atualizar config do agente
  DELETE /api/agentes/{id}/audio-config     → remove config específica do agente
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from docagent.api import app
from docagent.database import Base, get_db
from docagent.auth.security import create_access_token, get_password_hash

import docagent.tenant.models          # noqa: F401
import docagent.usuario.models         # noqa: F401
import docagent.agente.models          # noqa: F401
import docagent.audio.models           # noqa: F401
import docagent.system_config.models   # noqa: F401

from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole
from docagent.agente.models import Agente

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


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
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def setup(db_session):
    tenant = Tenant(nome="Tenant Audio")
    db_session.add(tenant)
    await db_session.flush()

    user = Usuario(
        username="audio_owner",
        email="audio@test.com",
        password=get_password_hash("senha123"),
        nome="Owner Audio",
        tenant_id=tenant.id,
        role=UsuarioRole.OWNER,
    )
    db_session.add(user)
    await db_session.flush()

    agente = Agente(
        nome="Agente Audio",
        descricao="desc",
        skill_names=[],
        ativo=True,
        tenant_id=tenant.id,
    )
    db_session.add(agente)
    await db_session.flush()
    await db_session.commit()

    token = create_access_token({"sub": user.username})
    headers = {"Authorization": f"Bearer {token}"}
    return {"tenant": tenant, "user": user, "agente": agente, "headers": headers}


@pytest_asyncio.fixture
async def client(db_session, db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db():
        async with factory() as s:
            async with s.begin():
                yield s

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── GET /api/audio-config/default ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_default_sem_config_retorna_system_defaults(client, setup):
    r = await client.get("/api/audio-config/default", headers=setup["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["stt_habilitado"] is False
    assert data["tts_habilitado"] is False
    assert data["stt_provider"] == "faster_whisper"
    assert data["tts_provider"] == "piper"


@pytest.mark.asyncio
async def test_get_default_com_config_retorna_config_banco(client, setup, db_session):
    from docagent.audio.models import AudioConfig
    cfg = AudioConfig(
        tenant_id=setup["tenant"].id,
        agente_id=None,
        stt_habilitado=True,
        tts_habilitado=True,
    )
    db_session.add(cfg)
    await db_session.commit()

    r = await client.get("/api/audio-config/default", headers=setup["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["stt_habilitado"] is True
    assert data["tts_habilitado"] is True
    assert data["agente_id"] is None


# ── PUT /api/audio-config/default ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_put_default_cria_config(client, setup):
    payload = {"stt_habilitado": True, "stt_provider": "faster_whisper", "stt_modelo": "small",
               "tts_habilitado": False, "tts_provider": "piper", "piper_voz": "pt_BR-faber-medium",
               "openai_tts_voz": "nova", "modo_resposta": "audio_e_texto"}
    r = await client.put("/api/audio-config/default", json=payload, headers=setup["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["stt_habilitado"] is True
    assert data["stt_modelo"] == "small"
    assert data["agente_id"] is None
    assert data["tenant_id"] == setup["tenant"].id


@pytest.mark.asyncio
async def test_put_default_atualiza_config_existente(client, setup, db_session):
    from docagent.audio.models import AudioConfig
    cfg = AudioConfig(tenant_id=setup["tenant"].id, agente_id=None, stt_habilitado=False)
    db_session.add(cfg)
    await db_session.commit()

    payload = {"stt_habilitado": True, "stt_provider": "faster_whisper", "stt_modelo": "base",
               "tts_habilitado": False, "tts_provider": "piper", "piper_voz": "pt_BR-faber-medium",
               "openai_tts_voz": "nova", "modo_resposta": "audio_e_texto"}
    r = await client.put("/api/audio-config/default", json=payload, headers=setup["headers"])
    assert r.status_code == 200
    assert r.json()["stt_habilitado"] is True


# ── GET /api/agentes/{id}/audio-config ───────────────────────────────────────

@pytest.mark.asyncio
async def test_get_agente_config_sem_config_retorna_defaults(client, setup):
    agente_id = setup["agente"].id
    r = await client.get(f"/api/agentes/{agente_id}/audio-config", headers=setup["headers"])
    assert r.status_code == 200
    assert r.json()["stt_habilitado"] is False


@pytest.mark.asyncio
async def test_get_agente_config_usa_config_propria(client, setup, db_session):
    from docagent.audio.models import AudioConfig
    agente_id = setup["agente"].id
    cfg = AudioConfig(
        tenant_id=setup["tenant"].id,
        agente_id=agente_id,
        stt_habilitado=True,
        tts_habilitado=True,
        modo_resposta="audio_apenas",
    )
    db_session.add(cfg)
    await db_session.commit()

    r = await client.get(f"/api/agentes/{agente_id}/audio-config", headers=setup["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["stt_habilitado"] is True
    assert data["modo_resposta"] == "audio_apenas"
    assert data["agente_id"] == agente_id


@pytest.mark.asyncio
async def test_get_agente_config_isolamento_tenant(client, setup, db_session):
    """Agente de outro tenant → 404."""
    outro_tenant = Tenant(nome="Outro Tenant")
    db_session.add(outro_tenant)
    await db_session.flush()
    agente_outro = Agente(nome="Agente Outro", descricao="x", skill_names=[], tenant_id=outro_tenant.id)
    db_session.add(agente_outro)
    await db_session.commit()

    r = await client.get(f"/api/agentes/{agente_outro.id}/audio-config", headers=setup["headers"])
    assert r.status_code == 404


# ── PUT /api/agentes/{id}/audio-config ───────────────────────────────────────

@pytest.mark.asyncio
async def test_put_agente_config_cria_config(client, setup):
    agente_id = setup["agente"].id
    payload = {"stt_habilitado": True, "stt_provider": "faster_whisper", "stt_modelo": "base",
               "tts_habilitado": True, "tts_provider": "piper", "piper_voz": "pt_BR-faber-medium",
               "openai_tts_voz": "nova", "modo_resposta": "audio_apenas"}
    r = await client.put(f"/api/agentes/{agente_id}/audio-config", json=payload, headers=setup["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["agente_id"] == agente_id
    assert data["tts_habilitado"] is True
    assert data["modo_resposta"] == "audio_apenas"


# ── DELETE /api/agentes/{id}/audio-config ────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_agente_config_remove_config(client, setup, db_session):
    from docagent.audio.models import AudioConfig
    agente_id = setup["agente"].id
    cfg = AudioConfig(tenant_id=setup["tenant"].id, agente_id=agente_id, stt_habilitado=True)
    db_session.add(cfg)
    await db_session.commit()

    r = await client.delete(f"/api/agentes/{agente_id}/audio-config", headers=setup["headers"])
    assert r.status_code == 204

    # Agora deve retornar defaults
    r2 = await client.get(f"/api/agentes/{agente_id}/audio-config", headers=setup["headers"])
    assert r2.json()["stt_habilitado"] is False


@pytest.mark.asyncio
async def test_delete_agente_config_sem_config_retorna_404(client, setup):
    agente_id = setup["agente"].id
    r = await client.delete(f"/api/agentes/{agente_id}/audio-config", headers=setup["headers"])
    assert r.status_code == 404
