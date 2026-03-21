"""Testes de integracao para autenticacao de usuarios."""
import pytest
from httpx import AsyncClient

from docagent.auth.security import get_password_hash
from docagent.usuario.models import Usuario, UsuarioRole
from docagent.tenant.models import Tenant


async def _create_user(db_session, username="owner", password="senha123", role=UsuarioRole.OWNER):
    tenant = Tenant(nome="Tenant Teste")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    user = Usuario(
        username=username,
        email=f"{username}@test.com",
        password=get_password_hash(password),
        nome="Usuario Teste",
        tenant_id=tenant.id,
        role=role,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session):
    await _create_user(db_session, username="owner", password="senha123")

    response = await client.post(
        "/auth/login",
        data={"username": "owner", "password": "senha123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session):
    await _create_user(db_session, username="user2", password="correta")

    response = await client.post(
        "/auth/login",
        data={"username": "user2", "password": "errada"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient):
    response = await client.post(
        "/auth/login",
        data={"username": "naoexiste", "password": "qualquer"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, db_session):
    await _create_user(db_session, username="meuser", password="senha123")

    login = await client.post(
        "/auth/login",
        data={"username": "meuser", "password": "senha123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = login.json()["access_token"]

    response = await client.get(
        "/api/usuarios/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "meuser"


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/usuarios/me",
        headers={"Authorization": "Bearer token_invalido"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_forgot_password_safe_enumeration(client: AsyncClient):
    """Deve retornar 200 mesmo se o email nao existir (evita enumeracao)."""
    response = await client.post(
        "/auth/forgot-password",
        json={"email": "naoexiste@test.com"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient):
    response = await client.post(
        "/auth/reset-password",
        json={"token": "token_invalido", "new_password": "nova_senha"},
    )
    assert response.status_code == 400
