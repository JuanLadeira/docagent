"""
Testes TDD para quota enforcement nos routers (Fase 17).
Verifica que POST /api/agentes retorna 402 quando limite_agentes excedido,
e POST /api/agentes/{id}/documentos retorna 402 quando limite_documentos excedido.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.agente.models import Agente, Documento

from tests.test_fase17.conftest import (
    _criar_tenant,
    _criar_owner,
    _criar_plano,
    _criar_assinatura,
    _get_token,
)


# ---------------------------------------------------------------------------
# POST /api/agentes — quota de agentes
# ---------------------------------------------------------------------------

class TestQuotaAgentesRouter:
    @pytest.mark.asyncio
    async def test_cria_agente_dentro_do_limite_retorna_201(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """limite_agentes=2, 0 agentes criados → 201."""
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, limite_agentes=2, limite_documentos=10)
        await _criar_assinatura(db_session, tenant, plano)
        token = await _get_token(client)

        response = await client.post(
            "/api/agentes/",
            json={"nome": "Agente Novo", "descricao": "desc", "skill_names": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_cria_agente_no_limite_retorna_402(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """limite_agentes=1, 1 agente existente → 402."""
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, nome="Free", limite_agentes=1)
        await _criar_assinatura(db_session, tenant, plano)
        db_session.add(Agente(
            nome="Existente", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
        ))
        await db_session.flush()
        token = await _get_token(client)

        response = await client.post(
            "/api/agentes/",
            json={"nome": "Novo", "descricao": "", "skill_names": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 402

    @pytest.mark.asyncio
    async def test_erro_402_mensagem_informativa(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Resposta 402 deve incluir mensagem sobre limite."""
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, nome="Free", limite_agentes=1)
        await _criar_assinatura(db_session, tenant, plano)
        db_session.add(Agente(
            nome="Existente", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
        ))
        await db_session.flush()
        token = await _get_token(client)

        response = await client.post(
            "/api/agentes/",
            json={"nome": "Novo", "descricao": "", "skill_names": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert "agentes" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_sem_assinatura_cria_agente_normalmente(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Tenant sem assinatura não é bloqueado (modo demo)."""
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        token = await _get_token(client)

        response = await client.post(
            "/api/agentes/",
            json={"nome": "Agente Demo", "descricao": "", "skill_names": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# POST /api/agentes/{id}/documentos — quota de documentos
# ---------------------------------------------------------------------------

class TestQuotaDocumentosRouter:
    @pytest.mark.asyncio
    async def test_upload_dentro_do_limite_retorna_201(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """limite_documentos=5, 0 docs → 201."""
        from unittest.mock import patch
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, limite_agentes=5, limite_documentos=5)
        await _criar_assinatura(db_session, tenant, plano)
        agente = Agente(
            nome="Ag", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
        )
        db_session.add(agente)
        await db_session.flush()
        await db_session.refresh(agente)
        token = await _get_token(client)

        with patch("docagent.agente.documento_service.IngestService") as MockIngest:
            inst = MockIngest.return_value
            inst.ingest.return_value = {
                "filename": "doc.pdf", "chunks": 3, "collection_id": f"agente_{agente.id}"
            }
            response = await client.post(
                f"/api/agentes/{agente.id}/documentos",
                files={"file": ("doc.pdf", b"fake pdf", "application/pdf")},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_upload_no_limite_retorna_402(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """limite_documentos=2, 2 docs existentes → 402."""
        tenant = await _criar_tenant(db_session)
        await _criar_owner(db_session, tenant)
        plano = await _criar_plano(db_session, limite_agentes=5, limite_documentos=2)
        await _criar_assinatura(db_session, tenant, plano)
        agente = Agente(
            nome="Ag", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
        )
        db_session.add(agente)
        await db_session.flush()
        await db_session.refresh(agente)
        for i in range(2):
            db_session.add(Documento(agente_id=agente.id, filename=f"d{i}.pdf", chunks=2))
        await db_session.flush()
        token = await _get_token(client)

        response = await client.post(
            f"/api/agentes/{agente.id}/documentos",
            files={"file": ("novo.pdf", b"fake pdf", "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 402
