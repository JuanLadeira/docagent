import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from docagent.api import app
from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole


@pytest_asyncio.fixture
async def tenant(db_session):
    t = Tenant(nome="Tenant Router")
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.mark.asyncio
async def test_config_public_sem_keycloak_retorna_disabled(client):
    with patch("docagent.keycloak.router.Settings") as mock_s:
        mock_s.return_value.KEYCLOAK_URL = ""
        resp = await client.get("/api/config/public")
    assert resp.status_code == 200
    data = resp.json()
    assert data["keycloak_enabled"] is False
    assert data["keycloak_url"] == ""


@pytest.mark.asyncio
async def test_config_public_com_keycloak_retorna_enabled(client):
    with patch("docagent.keycloak.router.Settings") as mock_s:
        mock_s.return_value.KEYCLOAK_URL = "http://keycloak:8080"
        mock_s.return_value.KEYCLOAK_REALM = "docagent"
        mock_s.return_value.KEYCLOAK_CLIENT_ID = "docagent-backend"
        resp = await client.get("/api/config/public")
    assert resp.status_code == 200
    data = resp.json()
    assert data["keycloak_enabled"] is True
    assert data["keycloak_realm"] == "docagent"


@pytest.mark.asyncio
async def test_login_sem_keycloak_configurado_retorna_404(client):
    with patch("docagent.keycloak.router.get_keycloak_client", return_value=None):
        resp = await client.get("/auth/keycloak/login", follow_redirects=False)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_login_redireciona_para_keycloak(client):
    mock_kc = MagicMock()
    mock_kc.get_authorization_url.return_value = "http://keycloak/auth?client_id=x"

    with patch("docagent.keycloak.router.get_keycloak_client", return_value=mock_kc):
        with patch("docagent.keycloak.router.Settings") as mock_s:
            mock_s.return_value.KEYCLOAK_REDIRECT_URI = "http://localhost:8000/auth/keycloak/callback"
            resp = await client.get("/auth/keycloak/login", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert "keycloak" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_state_invalido_retorna_400(client, tenant):
    mock_kc = MagicMock()

    with patch("docagent.keycloak.router.get_keycloak_client", return_value=mock_kc):
        resp = await client.get(
            "/auth/keycloak/callback",
            params={"code": "abc", "state": "estado-invalido"},
            follow_redirects=False,
        )

    assert resp.status_code == 400
    assert "state" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_callback_cria_usuario_e_redireciona(client, db_session, tenant):
    state_val = "estado-valido-xyz"
    # Access app.state.redis directly (the conftest sets it on app.state)
    await app.state.redis.set(f"keycloak:state:{state_val}", b"1", ex=300)

    mock_kc = MagicMock()
    mock_kc.exchange_code = AsyncMock(return_value={
        "access_token": "at-keycloak",
        "refresh_token": "rt-keycloak",
    })
    mock_kc.validate_jwt.return_value = {
        "sub": "kc-sub-callback",
        "email": "callback@teste.com",
        "name": "Callback User",
    }

    with patch("docagent.keycloak.router.get_keycloak_client", return_value=mock_kc):
        with patch("docagent.keycloak.router.Settings") as mock_s:
            mock_s.return_value.KEYCLOAK_REDIRECT_URI = "http://localhost:8000/auth/keycloak/callback"
            mock_s.return_value.FRONTEND_URL = "http://localhost:5173"
            mock_s.return_value.KEYCLOAK_DEFAULT_TENANT_ID = tenant.id
            with patch("docagent.keycloak.service.Settings") as mock_s2:
                mock_s2.return_value.KEYCLOAK_DEFAULT_TENANT_ID = tenant.id
                resp = await client.get(
                    "/auth/keycloak/callback",
                    params={"code": "code-xyz", "state": state_val},
                    follow_redirects=False,
                )

    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert "/auth/callback?token=" in location
