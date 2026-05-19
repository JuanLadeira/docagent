import pytest
import pytest_asyncio
from unittest.mock import patch

from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole
from docagent.keycloak.service import KeycloakService


@pytest_asyncio.fixture
async def tenant(db_session):
    t = Tenant(nome="Tenant Teste")
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.mark.asyncio
async def test_criar_usuario_novo_via_keycloak(db_session, fake_redis, tenant):
    claims = {"sub": "kc-sub-001", "email": "novo@teste.com", "name": "Novo User"}

    with patch("docagent.keycloak.service.Settings") as mock_s:
        mock_s.return_value.KEYCLOAK_DEFAULT_TENANT_ID = tenant.id
        user = await KeycloakService.criar_ou_linkar_usuario(
            claims=claims,
            refresh_token="rt-abc",
            db=db_session,
            redis=fake_redis,
        )

    assert user.email == "novo@teste.com"
    assert user.keycloak_sub == "kc-sub-001"
    assert user.tenant_id == tenant.id
    assert user.password == "!keycloak"

    rt = await fake_redis.get(f"keycloak:rt:{user.id}")
    assert rt == b"rt-abc"


@pytest.mark.asyncio
async def test_linkar_por_email_usuario_existente(db_session, fake_redis, tenant):
    existing = Usuario(
        username="joao",
        email="joao@teste.com",
        password="hash",
        nome="João",
        role=UsuarioRole.OWNER,
        tenant_id=tenant.id,
    )
    db_session.add(existing)
    await db_session.flush()

    claims = {"sub": "kc-sub-002", "email": "joao@teste.com", "name": "João"}

    with patch("docagent.keycloak.service.Settings"):
        user = await KeycloakService.criar_ou_linkar_usuario(
            claims=claims,
            refresh_token="rt-joao",
            db=db_session,
            redis=fake_redis,
        )

    assert user.id == existing.id
    assert user.keycloak_sub == "kc-sub-002"
    rt = await fake_redis.get(f"keycloak:rt:{user.id}")
    assert rt == b"rt-joao"


@pytest.mark.asyncio
async def test_linkar_por_sub_ja_existente(db_session, fake_redis, tenant):
    existing = Usuario(
        username="maria",
        email="maria@teste.com",
        password="hash",
        nome="Maria",
        role=UsuarioRole.MEMBER,
        tenant_id=tenant.id,
        keycloak_sub="kc-sub-003",
    )
    db_session.add(existing)
    await db_session.flush()

    claims = {"sub": "kc-sub-003", "email": "maria@teste.com", "name": "Maria"}

    with patch("docagent.keycloak.service.Settings"):
        user = await KeycloakService.criar_ou_linkar_usuario(
            claims=claims,
            refresh_token="rt-maria-new",
            db=db_session,
            redis=fake_redis,
        )

    assert user.id == existing.id
    rt = await fake_redis.get(f"keycloak:rt:{user.id}")
    assert rt == b"rt-maria-new"


@pytest.mark.asyncio
async def test_get_access_token_com_refresh_valido(fake_redis):
    from unittest.mock import AsyncMock, patch

    await fake_redis.set("keycloak:rt:42", b"rt-valid", ex=3600)

    mock_client = AsyncMock()
    mock_client.refresh.return_value = {
        "access_token": "new-at",
        "refresh_token": "new-rt",
    }

    with patch("docagent.keycloak.service.get_keycloak_client", return_value=mock_client):
        token = await KeycloakService.get_access_token(usuario_id=42, redis=fake_redis)

    assert token == "new-at"
    new_rt = await fake_redis.get("keycloak:rt:42")
    assert new_rt == b"new-rt"


@pytest.mark.asyncio
async def test_get_access_token_sem_rt_retorna_none(fake_redis):
    token = await KeycloakService.get_access_token(usuario_id=99, redis=fake_redis)
    assert token is None


@pytest.mark.asyncio
async def test_get_access_token_sem_redis_retorna_none():
    token = await KeycloakService.get_access_token(usuario_id=1, redis=None)
    assert token is None


@pytest.mark.asyncio
async def test_criar_usuario_sem_email_levanta_erro(db_session, fake_redis, tenant):
    claims = {"sub": "kc-sub-sem-email"}

    with pytest.raises(ValueError, match="email"):
        with patch("docagent.keycloak.service.Settings"):
            await KeycloakService.criar_ou_linkar_usuario(
                claims=claims,
                refresh_token="rt",
                db=db_session,
                redis=fake_redis,
            )
