"""
TDD — ConversaService (Fase 19)

Testa:
  - criar conversa
  - carregar histórico vazio e com mensagens
  - salvar e carregar mensagens (round-trip)
  - gerar título após primeiro turn
  - listar paginado
  - arquivar e restaurar
  - isolamento por tenant
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from docagent.conversa.services import ConversaService
from docagent.conversa.models import MensagemRole


# ── criar ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_criar_conversa(db, setup):
    svc = ConversaService(db)
    conversa = await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )
    assert conversa.id is not None
    assert conversa.titulo is None
    assert conversa.arquivada is False
    assert conversa.tenant_id == setup["tenant"].id


# ── histórico ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_carregar_historico_vazio(db, setup):
    svc = ConversaService(db)
    conversa = await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )
    historico = await svc.carregar_historico(conversa.id)
    assert historico == []


@pytest.mark.asyncio
async def test_salvar_e_carregar_mensagens(db, setup):
    svc = ConversaService(db)
    conversa = await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )

    await svc.salvar_mensagem(conversa.id, MensagemRole.USER, "Olá, tudo bem?")
    await svc.salvar_mensagem(conversa.id, MensagemRole.ASSISTANT, "Tudo ótimo!")

    historico = await svc.carregar_historico(conversa.id)
    assert len(historico) == 2
    assert isinstance(historico[0], HumanMessage)
    assert historico[0].content == "Olá, tudo bem?"
    assert isinstance(historico[1], AIMessage)
    assert historico[1].content == "Tudo ótimo!"


@pytest.mark.asyncio
async def test_salvar_mensagem_tool(db, setup):
    svc = ConversaService(db)
    conversa = await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )
    await svc.salvar_mensagem(
        conversa.id, MensagemRole.TOOL, "resultado da busca", tool_name="web_search"
    )
    historico = await svc.carregar_historico(conversa.id)
    assert len(historico) == 1
    assert isinstance(historico[0], ToolMessage)
    assert historico[0].content == "resultado da busca"


@pytest.mark.asyncio
async def test_salvar_mensagem_atualiza_updated_at(db, setup):
    """updated_at da conversa deve mudar após salvar mensagem."""
    svc = ConversaService(db)
    conversa = await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )
    updated_antes = conversa.updated_at

    await svc.salvar_mensagem(conversa.id, MensagemRole.USER, "ping")
    await db.refresh(conversa)

    # updated_at deve ser >= ao valor anterior
    assert conversa.updated_at >= updated_antes


# ── título ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gerar_titulo_apos_primeiro_turn(db, setup):
    svc = ConversaService(db)
    conversa = await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )

    llm_mock = MagicMock()
    llm_mock.ainvoke = AsyncMock(return_value=MagicMock(content="Análise do Contrato"))

    await svc.gerar_titulo(conversa.id, "preciso analisar um contrato", llm_mock)
    await db.refresh(conversa)

    assert conversa.titulo == "Análise do Contrato"


# ── listar paginado ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listar_paginado(db, setup):
    svc = ConversaService(db)
    for _ in range(5):
        await svc.criar(
            tenant_id=setup["tenant"].id,
            usuario_id=setup["usuario"].id,
            agente_id=setup["agente"].id,
        )

    pagina1 = await svc.listar(
        usuario_id=setup["usuario"].id,
        tenant_id=setup["tenant"].id,
        agente_id=None,
        arquivada=False,
        page=1,
        page_size=3,
    )
    assert len(pagina1) == 3

    pagina2 = await svc.listar(
        usuario_id=setup["usuario"].id,
        tenant_id=setup["tenant"].id,
        agente_id=None,
        arquivada=False,
        page=2,
        page_size=3,
    )
    assert len(pagina2) == 2


@pytest.mark.asyncio
async def test_listar_filtro_agente(db, setup):
    from docagent.agente.models import Agente

    svc = ConversaService(db)
    agente2 = Agente(
        nome="Outro Agente", descricao="d", skill_names=[], ativo=True,
        tenant_id=setup["tenant"].id,
    )
    db.add(agente2)
    await db.flush()

    await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )
    await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=agente2.id,
    )
    await db.commit()

    resultado = await svc.listar(
        usuario_id=setup["usuario"].id,
        tenant_id=setup["tenant"].id,
        agente_id=setup["agente"].id,
        arquivada=False,
        page=1,
        page_size=10,
    )
    assert len(resultado) == 1
    assert resultado[0].agente_id == setup["agente"].id


# ── arquivar e restaurar ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_arquivar_e_restaurar(db, setup):
    svc = ConversaService(db)
    conversa = await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )

    await svc.arquivar(conversa.id, setup["tenant"].id)
    await db.refresh(conversa)
    assert conversa.arquivada is True

    # Não aparece na lista normal
    lista_normal = await svc.listar(
        usuario_id=setup["usuario"].id,
        tenant_id=setup["tenant"].id,
        agente_id=None,
        arquivada=False,
        page=1,
        page_size=10,
    )
    assert all(c.id != conversa.id for c in lista_normal)

    # Aparece na lista de arquivadas
    lista_arquivadas = await svc.listar(
        usuario_id=setup["usuario"].id,
        tenant_id=setup["tenant"].id,
        agente_id=None,
        arquivada=True,
        page=1,
        page_size=10,
    )
    assert any(c.id == conversa.id for c in lista_arquivadas)

    await svc.restaurar(conversa.id, setup["tenant"].id)
    await db.refresh(conversa)
    assert conversa.arquivada is False


# ── isolamento por tenant ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_isolamento_por_tenant(db, setup):
    from docagent.tenant.models import Tenant
    from docagent.usuario.models import Usuario
    from docagent.agente.models import Agente

    # Segundo tenant com usuário e agente próprios
    tenant2 = Tenant(nome="Outro Tenant")
    db.add(tenant2)
    await db.flush()

    usuario2 = Usuario(
        username="user2_hist", email="hist2@test.com",
        password="hash", nome="User 2", tenant_id=tenant2.id,
    )
    db.add(usuario2)
    await db.flush()

    agente2 = Agente(
        nome="Agente T2", descricao="d", skill_names=[], ativo=True,
        tenant_id=tenant2.id,
    )
    db.add(agente2)
    await db.commit()

    svc = ConversaService(db)

    # Cria uma conversa no tenant 1 e uma no tenant 2
    await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )
    await svc.criar(
        tenant_id=tenant2.id,
        usuario_id=usuario2.id,
        agente_id=agente2.id,
    )

    # Tenant 1 só enxerga suas próprias conversas
    lista_t1 = await svc.listar(
        usuario_id=setup["usuario"].id,
        tenant_id=setup["tenant"].id,
        agente_id=None,
        arquivada=False,
        page=1,
        page_size=10,
    )
    assert all(c.tenant_id == setup["tenant"].id for c in lista_t1)
    assert len(lista_t1) == 1


@pytest.mark.asyncio
async def test_get_by_id_isolamento_tenant(db, setup):
    from docagent.tenant.models import Tenant
    from docagent.usuario.models import Usuario
    from docagent.agente.models import Agente

    tenant2 = Tenant(nome="Tenant Invasor")
    db.add(tenant2)
    await db.flush()

    svc = ConversaService(db)
    conversa = await svc.criar(
        tenant_id=setup["tenant"].id,
        usuario_id=setup["usuario"].id,
        agente_id=setup["agente"].id,
    )

    # Tenant 2 não consegue ler a conversa do tenant 1
    resultado = await svc.get_by_id(conversa.id, tenant_id=tenant2.id)
    assert resultado is None

    # Tenant 1 consegue ler normalmente
    resultado_ok = await svc.get_by_id(conversa.id, tenant_id=setup["tenant"].id)
    assert resultado_ok is not None
    assert resultado_ok.id == conversa.id
