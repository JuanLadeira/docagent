"""
Fase 21d — 2FA para Admin (TOTP).

Testa o fluxo completo: setup, confirmação, login com 2FA, código inválido.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

from docagent.admin.models import Admin
from docagent.auth.security import get_password_hash, create_temp_token
from docagent.auth.totp import gerar_secret, verificar_codigo


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def admin(db_session) -> Admin:
    a = Admin(
        username="admin2fa",
        email="2fa@test.com",
        password=get_password_hash("senha123"),
        nome="Admin 2FA",
        ativo=True,
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, admin: Admin) -> dict:
    r = await client.post(
        "/api/admin/login",
        data={"username": "admin2fa", "password": "senha123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── unit tests — totp.py ──────────────────────────────────────────────────────

def test_gerar_secret_retorna_base32():
    secret = gerar_secret()
    assert len(secret) >= 16
    # base32 usa apenas A-Z e 2-7
    import re
    assert re.match(r"^[A-Z2-7]+=*$", secret)


def test_verificar_codigo_valido():
    import pyotp
    secret = gerar_secret()
    codigo_atual = pyotp.TOTP(secret).now()
    assert verificar_codigo(secret, codigo_atual) is True


def test_verificar_codigo_invalido():
    secret = gerar_secret()
    assert verificar_codigo(secret, "000000") is False


# ── fluxo HTTP ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_sem_2fa_retorna_jwt_direto(client: AsyncClient, admin: Admin):
    """Sem 2FA configurado, login retorna access_token diretamente."""
    r = await client.post(
        "/api/admin/login",
        data={"username": "admin2fa", "password": "senha123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["requires_2fa"] is False
    assert data["access_token"] is not None
    assert data["temp_token"] is None


@pytest.mark.asyncio
async def test_setup_2fa_retorna_qr_uri(client: AsyncClient, auth_headers: dict):
    r = await client.get("/api/admin/2fa/setup", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "qr_uri" in data
    assert data["qr_uri"].startswith("otpauth://totp/")
    assert "secret" in data


@pytest.mark.asyncio
async def test_confirmar_2fa_com_codigo_valido(
    client: AsyncClient, auth_headers: dict, admin: Admin, db_session
):
    # Setup
    r = await client.get("/api/admin/2fa/setup", headers=auth_headers)
    assert r.status_code == 200
    secret = r.json()["secret"]

    # Gera código válido
    import pyotp
    codigo = pyotp.TOTP(secret).now()

    # Confirma
    r = await client.post(
        "/api/admin/2fa/confirmar",
        json={"codigo": codigo},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["totp_habilitado"] is True


@pytest.mark.asyncio
async def test_confirmar_2fa_com_codigo_invalido(
    client: AsyncClient, auth_headers: dict
):
    await client.get("/api/admin/2fa/setup", headers=auth_headers)
    r = await client.post(
        "/api/admin/2fa/confirmar",
        json={"codigo": "000000"},
        headers=auth_headers,
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_com_2fa_ativo_requer_segundo_passo(
    client: AsyncClient, admin: Admin, db_session
):
    """Após ativar 2FA, login retorna requires_2fa=True e temp_token."""
    import pyotp

    # Ativa 2FA diretamente no banco
    secret = gerar_secret()
    admin.totp_secret = secret
    admin.totp_habilitado = True
    await db_session.flush()

    r = await client.post(
        "/api/admin/login",
        data={"username": "admin2fa", "password": "senha123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["requires_2fa"] is True
    assert data["temp_token"] is not None
    assert data["access_token"] is None


@pytest.mark.asyncio
async def test_login_2fa_com_codigo_valido_retorna_jwt(
    client: AsyncClient, admin: Admin, db_session
):
    import pyotp

    secret = gerar_secret()
    admin.totp_secret = secret
    admin.totp_habilitado = True
    await db_session.flush()

    # Passo 1
    r = await client.post(
        "/api/admin/login",
        data={"username": "admin2fa", "password": "senha123"},
    )
    temp_token = r.json()["temp_token"]

    # Passo 2
    codigo = pyotp.TOTP(secret).now()
    r = await client.post(
        "/api/admin/login/2fa",
        json={"temp_token": temp_token, "codigo": codigo},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["access_token"] is not None
    assert data["requires_2fa"] is False


@pytest.mark.asyncio
async def test_login_2fa_com_codigo_invalido_retorna_401(
    client: AsyncClient, admin: Admin, db_session
):
    secret = gerar_secret()
    admin.totp_secret = secret
    admin.totp_habilitado = True
    await db_session.flush()

    r = await client.post(
        "/api/admin/login",
        data={"username": "admin2fa", "password": "senha123"},
    )
    temp_token = r.json()["temp_token"]

    r = await client.post(
        "/api/admin/login/2fa",
        json={"temp_token": temp_token, "codigo": "000000"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_2fa_com_temp_token_invalido_retorna_401(client: AsyncClient):
    r = await client.post(
        "/api/admin/login/2fa",
        json={"temp_token": "token_invalido", "codigo": "123456"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_desativar_2fa(
    client: AsyncClient, admin: Admin, db_session
):
    import pyotp

    secret = gerar_secret()
    admin.totp_secret = secret
    admin.totp_habilitado = True
    await db_session.flush()

    # Login com 2FA ativo
    r = await client.post(
        "/api/admin/login",
        data={"username": "admin2fa", "password": "senha123"},
    )
    temp_token = r.json()["temp_token"]
    codigo = pyotp.TOTP(secret).now()
    r = await client.post(
        "/api/admin/login/2fa",
        json={"temp_token": temp_token, "codigo": codigo},
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Desativa
    r = await client.delete("/api/admin/2fa/desativar", headers=headers)
    assert r.status_code == 200
    assert r.json()["totp_habilitado"] is False

    # Login agora deve ser direto (sem 2FA)
    r = await client.post(
        "/api/admin/login",
        data={"username": "admin2fa", "password": "senha123"},
    )
    assert r.json()["requires_2fa"] is False
    assert r.json()["access_token"] is not None
