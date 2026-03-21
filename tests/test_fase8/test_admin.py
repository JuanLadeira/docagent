"""Testes de integracao para autenticacao e operacoes de admin."""
import pytest
from httpx import AsyncClient

from docagent.admin.models import Admin
from docagent.auth.security import get_password_hash


async def _create_admin(db_session, username="superadmin", password="admin123"):
    admin = Admin(
        username=username,
        email=f"{username}@admin.com",
        password=get_password_hash(password),
        nome="Super Admin",
        ativo=True,
    )
    db_session.add(admin)
    await db_session.flush()
    await db_session.refresh(admin)
    return admin


async def _admin_token(client: AsyncClient, username="superadmin", password="admin123") -> str:
    response = await client.post(
        "/api/admin/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, db_session):
    await _create_admin(db_session)

    response = await client.post(
        "/api/admin/login",
        data={"username": "superadmin", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_admin_login_wrong_password(client: AsyncClient, db_session):
    await _create_admin(db_session)

    response = await client.post(
        "/api/admin/login",
        data={"username": "superadmin", "password": "errada"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_me(client: AsyncClient, db_session):
    await _create_admin(db_session)
    token = await _admin_token(client)

    response = await client.get("/api/admin/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "superadmin"


@pytest.mark.asyncio
async def test_user_token_cannot_access_admin(client: AsyncClient, db_session):
    """Token de usuario comum nao deve acessar endpoints de admin."""
    from docagent.tenant.models import Tenant
    from docagent.usuario.models import Usuario, UsuarioRole

    tenant = Tenant(nome="Tenant")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)

    user = Usuario(
        username="comum",
        email="comum@test.com",
        password=get_password_hash("senha"),
        nome="Usuario Comum",
        tenant_id=tenant.id,
        role=UsuarioRole.OWNER,
    )
    db_session.add(user)
    await db_session.flush()

    login = await client.post(
        "/auth/login",
        data={"username": "comum", "password": "senha"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    user_token = login.json()["access_token"]

    response = await client.get(
        "/api/admin/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_create_tenant(client: AsyncClient, db_session):
    await _create_admin(db_session)
    token = await _admin_token(client)

    response = await client.post(
        "/api/admin/tenants",
        json={"nome": "Novo Tenant", "descricao": "Via admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["nome"] == "Novo Tenant"
