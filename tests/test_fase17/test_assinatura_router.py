"""
Testes TDD para o router /api/assinaturas (Fase 17).
Cobre: GET /me, GET /me/uso, POST / (criar/atualizar), admin list.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_fase17.conftest import (
    _criar_tenant,
    _criar_owner,
    _criar_plano,
    _criar_assinatura,
    _get_token,
)


# ---------------------------------------------------------------------------
# GET /api/assinaturas/me
# ---------------------------------------------------------------------------

class TestGetMinhaAssinatura:
    @pytest.mark.asyncio
    async def test_sem_assinatura_retorna_none(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        token = await _get_token(client)

        response = await client.get(
            "/api/assinaturas/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["assinatura"] is None

    @pytest.mark.asyncio
    async def test_com_assinatura_retorna_dados(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, nome="Pro")
        await _criar_assinatura(db_session, tenant, plano)
        token = await _get_token(client)

        response = await client.get(
            "/api/assinaturas/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["assinatura"] is not None
        assert data["assinatura"]["plano_nome"] == "Pro"

    @pytest.mark.asyncio
    async def test_retorna_401_sem_token(self, client: AsyncClient, db_session: AsyncSession):
        await _criar_tenant(db_session)
        response = await client.get("/api/assinaturas/me")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/assinaturas/me/uso
# ---------------------------------------------------------------------------

class TestGetUso:
    @pytest.mark.asyncio
    async def test_retorna_uso_atual(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, limite_agentes=3, limite_documentos=10)
        await _criar_assinatura(db_session, tenant, plano)
        token = await _get_token(client)

        response = await client.get(
            "/api/assinaturas/me/uso",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "agentes_atual" in data
        assert "agentes_limite" in data
        assert "documentos_atual" in data
        assert "documentos_limite" in data

    @pytest.mark.asyncio
    async def test_limites_refletem_plano(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, limite_agentes=7, limite_documentos=42)
        await _criar_assinatura(db_session, tenant, plano)
        token = await _get_token(client)

        response = await client.get(
            "/api/assinaturas/me/uso",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = response.json()
        assert data["agentes_limite"] == 7
        assert data["documentos_limite"] == 42


# ---------------------------------------------------------------------------
# POST /api/assinaturas — criar/atualizar
# ---------------------------------------------------------------------------

class TestCriarAssinatura:
    @pytest.mark.asyncio
    async def test_cria_nova_assinatura(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, nome="Starter")
        token = await _get_token(client)

        response = await client.post(
            "/api/assinaturas/",
            json={"plano_id": plano.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_retorna_plano_nome_na_resposta(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, nome="Starter")
        token = await _get_token(client)

        response = await client.post(
            "/api/assinaturas/",
            json={"plano_id": plano.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.json()["plano_nome"] == "Starter"

    @pytest.mark.asyncio
    async def test_plano_inexistente_retorna_404(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        token = await _get_token(client)

        response = await client.post(
            "/api/assinaturas/",
            json={"plano_id": 9999},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_atualiza_assinatura_existente(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano_free = await _criar_plano(db_session, nome="Free")
        plano_pro = await _criar_plano(db_session, nome="Pro")
        await _criar_assinatura(db_session, tenant, plano_free)
        token = await _get_token(client)

        response = await client.post(
            "/api/assinaturas/",
            json={"plano_id": plano_pro.id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["plano_nome"] == "Pro"
