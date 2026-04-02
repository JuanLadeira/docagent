"""
Testes TDD para AssinaturaService (Fase 17).
Cobre: criar, get_by_tenant, checar_quota, uso_atual.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.assinatura.services import AssinaturaService
from docagent.agente.models import Agente

from tests.test_fase17.conftest import (
    _criar_tenant,
    _criar_plano,
    _criar_assinatura,
)


@pytest_asyncio.fixture
async def service(db_session: AsyncSession) -> AssinaturaService:
    return AssinaturaService(db_session)


@pytest_asyncio.fixture
async def tenant(db_session):
    return await _criar_tenant(db_session)


@pytest_asyncio.fixture
async def plano_free(db_session):
    return await _criar_plano(
        db_session, nome="Free", limite_agentes=1, limite_documentos=5
    )


@pytest_asyncio.fixture
async def plano_pro(db_session):
    return await _criar_plano(
        db_session, nome="Pro", limite_agentes=5, limite_documentos=50
    )


# ---------------------------------------------------------------------------
# get_by_tenant
# ---------------------------------------------------------------------------

class TestGetByTenant:
    @pytest.mark.asyncio
    async def test_retorna_none_sem_assinatura(self, service, tenant):
        result = await service.get_by_tenant(tenant.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_retorna_assinatura_existente(self, service, db_session, tenant, plano_free):
        await _criar_assinatura(db_session, tenant, plano_free)
        result = await service.get_by_tenant(tenant.id)
        assert result is not None
        assert result.tenant_id == tenant.id

    @pytest.mark.asyncio
    async def test_retorna_assinatura_com_plano_carregado(self, service, db_session, tenant, plano_free):
        await _criar_assinatura(db_session, tenant, plano_free)
        result = await service.get_by_tenant(tenant.id)
        assert result.plano is not None
        assert result.plano.nome == "Free"


# ---------------------------------------------------------------------------
# criar
# ---------------------------------------------------------------------------

class TestCriar:
    @pytest.mark.asyncio
    async def test_cria_assinatura(self, service, tenant, plano_free):
        assinatura = await service.criar(tenant.id, plano_free.id)
        assert assinatura.id is not None

    @pytest.mark.asyncio
    async def test_assinatura_ativo_por_padrao(self, service, tenant, plano_free):
        assinatura = await service.criar(tenant.id, plano_free.id)
        assert assinatura.ativo is True

    @pytest.mark.asyncio
    async def test_data_proxima_renovacao_calculada(self, service, tenant, plano_free):
        assinatura = await service.criar(tenant.id, plano_free.id)
        delta = assinatura.data_proxima_renovacao - assinatura.data_inicio
        assert delta.days == plano_free.ciclo_dias

    @pytest.mark.asyncio
    async def test_atualiza_assinatura_existente(self, service, db_session, tenant, plano_free, plano_pro):
        """Se tenant já tem assinatura, criar() atualiza o plano."""
        await _criar_assinatura(db_session, tenant, plano_free)
        assinatura = await service.criar(tenant.id, plano_pro.id)
        assert assinatura.plano_id == plano_pro.id

    @pytest.mark.asyncio
    async def test_retorna_objeto_assinatura(self, service, tenant, plano_free):
        from docagent.assinatura.models import Assinatura
        assinatura = await service.criar(tenant.id, plano_free.id)
        assert isinstance(assinatura, Assinatura)


# ---------------------------------------------------------------------------
# checar_quota — agentes
# ---------------------------------------------------------------------------

class TestChecarQuotaAgentes:
    @pytest.mark.asyncio
    async def test_sem_assinatura_retorna_true(self, service, tenant):
        """Tenant sem assinatura não é bloqueado (acesso livre/demo)."""
        result = await service.checar_quota(tenant.id, "agentes")
        assert result is True

    @pytest.mark.asyncio
    async def test_dentro_do_limite_retorna_true(self, service, db_session, tenant, plano_free):
        """limite_agentes=1, 0 agentes criados → OK."""
        await _criar_assinatura(db_session, tenant, plano_free)
        result = await service.checar_quota(tenant.id, "agentes")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_limite_retorna_false(self, service, db_session, tenant, plano_free):
        """limite_agentes=1, 1 agente criado → BLOQUEADO."""
        await _criar_assinatura(db_session, tenant, plano_free)
        agente = Agente(
            nome="Agente 1", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
        )
        db_session.add(agente)
        await db_session.flush()

        result = await service.checar_quota(tenant.id, "agentes")
        assert result is False

    @pytest.mark.asyncio
    async def test_acima_do_limite_retorna_false(self, service, db_session, tenant, plano_free):
        """limite_agentes=1, 2 agentes criados → BLOQUEADO."""
        await _criar_assinatura(db_session, tenant, plano_free)
        for i in range(2):
            db_session.add(Agente(
                nome=f"Agente {i}", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
            ))
        await db_session.flush()

        result = await service.checar_quota(tenant.id, "agentes")
        assert result is False

    @pytest.mark.asyncio
    async def test_plano_pro_permite_mais_agentes(self, service, db_session, tenant, plano_pro):
        """limite_agentes=5, 3 agentes → ainda OK."""
        await _criar_assinatura(db_session, tenant, plano_pro)
        for i in range(3):
            db_session.add(Agente(
                nome=f"Agente {i}", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
            ))
        await db_session.flush()

        result = await service.checar_quota(tenant.id, "agentes")
        assert result is True


# ---------------------------------------------------------------------------
# checar_quota — documentos
# ---------------------------------------------------------------------------

class TestChecarQuotaDocumentos:
    @pytest.mark.asyncio
    async def test_sem_assinatura_retorna_true(self, service, tenant):
        result = await service.checar_quota(tenant.id, "documentos")
        assert result is True

    @pytest.mark.asyncio
    async def test_dentro_do_limite_retorna_true(self, service, db_session, tenant, plano_free):
        """limite_documentos=5, agente com 3 docs → OK."""
        await _criar_assinatura(db_session, tenant, plano_free)
        agente = Agente(
            nome="Agente 1", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
        )
        db_session.add(agente)
        await db_session.flush()
        await db_session.refresh(agente)

        from docagent.agente.models import Documento
        for i in range(3):
            db_session.add(Documento(
                agente_id=agente.id, filename=f"doc{i}.pdf", chunks=5
            ))
        await db_session.flush()

        result = await service.checar_quota(tenant.id, "documentos")
        assert result is True

    @pytest.mark.asyncio
    async def test_no_limite_retorna_false(self, service, db_session, tenant, plano_free):
        """limite_documentos=5, agente com 5 docs → BLOQUEADO."""
        await _criar_assinatura(db_session, tenant, plano_free)
        agente = Agente(
            nome="Agente 1", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
        )
        db_session.add(agente)
        await db_session.flush()
        await db_session.refresh(agente)

        from docagent.agente.models import Documento
        for i in range(5):
            db_session.add(Documento(
                agente_id=agente.id, filename=f"doc{i}.pdf", chunks=5
            ))
        await db_session.flush()

        result = await service.checar_quota(tenant.id, "documentos")
        assert result is False


# ---------------------------------------------------------------------------
# uso_atual
# ---------------------------------------------------------------------------

class TestUsoAtual:
    @pytest.mark.asyncio
    async def test_sem_assinatura_retorna_zeros(self, service, tenant):
        uso = await service.uso_atual(tenant.id)
        assert uso["agentes_atual"] == 0
        assert uso["documentos_atual"] == 0

    @pytest.mark.asyncio
    async def test_conta_agentes_corretamente(self, service, db_session, tenant, plano_free):
        await _criar_assinatura(db_session, tenant, plano_free)
        for i in range(2):
            db_session.add(Agente(
                nome=f"Agente {i}", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
            ))
        await db_session.flush()

        uso = await service.uso_atual(tenant.id)
        assert uso["agentes_atual"] == 2
        assert uso["agentes_limite"] == plano_free.limite_agentes

    @pytest.mark.asyncio
    async def test_conta_documentos_corretamente(self, service, db_session, tenant, plano_free):
        await _criar_assinatura(db_session, tenant, plano_free)
        agente = Agente(
            nome="Ag", descricao="", skill_names=[], ativo=True, tenant_id=tenant.id
        )
        db_session.add(agente)
        await db_session.flush()
        await db_session.refresh(agente)

        from docagent.agente.models import Documento
        for i in range(3):
            db_session.add(Documento(agente_id=agente.id, filename=f"d{i}.pdf", chunks=2))
        await db_session.flush()

        uso = await service.uso_atual(tenant.id)
        assert uso["documentos_atual"] == 3
        assert uso["documentos_limite"] == plano_free.limite_documentos

    @pytest.mark.asyncio
    async def test_retorna_nome_plano(self, service, db_session, tenant, plano_free):
        await _criar_assinatura(db_session, tenant, plano_free)
        uso = await service.uso_atual(tenant.id)
        assert uso["plano"] == "Free"

    @pytest.mark.asyncio
    async def test_sem_assinatura_plano_none(self, service, tenant):
        uso = await service.uso_atual(tenant.id)
        assert uso["plano"] is None
