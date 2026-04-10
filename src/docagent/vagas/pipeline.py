"""
Pipeline LangGraph — 4 nós sequenciais para o módulo de vagas.

Fluxo:
  START → cv_analyzer → job_searcher → personalizer → registrar → END

Roda como asyncio.create_task() — cada nó cria suas próprias sessões de banco.
"""
import asyncio
import logging

from langgraph.graph import END, START, StateGraph

from docagent.database import AsyncSessionLocal
from docagent.vagas.pipeline_state import PipelineVagasState
from docagent.vagas.sse import VagasPipelineSseManager, vagas_sse_manager

logger = logging.getLogger(__name__)


def build_pipeline_graph(llm=None, sources=None, sse_manager: VagasPipelineSseManager | None = None):
    """Constrói e compila o StateGraph do pipeline de vagas.

    Params:
        llm: LangChain chat model (injetável em testes). Se None, usa get_llm().
        sources: lista de JobSource (injetável em testes). Se None, usa as 4 fontes padrão.
        sse_manager: SSE manager (injetável em testes). Se None, usa o singleton global.
    """
    _sse = sse_manager or vagas_sse_manager

    if llm is None:
        from docagent.agent.llm_factory import get_llm
        llm = get_llm()

    # Cada nó cria sua própria sessão — o pipeline roda em background
    async def _cv_analyzer_node(state: PipelineVagasState) -> dict:
        from docagent.vagas.nodes.cv_analyzer import make_cv_analyzer_node
        async with AsyncSessionLocal() as session:
            async with session.begin():
                node = make_cv_analyzer_node(session, _sse, llm=llm)
                return await node(state)

    async def _job_searcher_node(state: PipelineVagasState) -> dict:
        from docagent.vagas.nodes.job_searcher import make_job_searcher_node
        async with AsyncSessionLocal() as session:
            async with session.begin():
                node = make_job_searcher_node(session, _sse, sources=sources)
                return await node(state)

    async def _personalizer_node(state: PipelineVagasState) -> dict:
        from docagent.vagas.nodes.personalizer import make_personalizer_node
        async with AsyncSessionLocal() as session:
            async with session.begin():
                node = make_personalizer_node(session, _sse, llm=llm)
                return await node(state)

    async def _registrar_node(state: PipelineVagasState) -> dict:
        from docagent.vagas.nodes.registrar import make_registrar_node
        async with AsyncSessionLocal() as session:
            async with session.begin():
                node = make_registrar_node(session, _sse)
                return await node(state)

    graph = StateGraph(PipelineVagasState)
    graph.add_node("cv_analyzer", _cv_analyzer_node)
    graph.add_node("job_searcher", _job_searcher_node)
    graph.add_node("personalizer", _personalizer_node)
    graph.add_node("registrar", _registrar_node)

    graph.add_edge(START, "cv_analyzer")
    graph.add_edge("cv_analyzer", "job_searcher")
    graph.add_edge("job_searcher", "personalizer")
    graph.add_edge("personalizer", "registrar")
    graph.add_edge("registrar", END)

    return graph.compile()


async def executar_pipeline(
    tenant_id: int,
    usuario_id: int,
    pipeline_run_id: int,
    cv_text: str,
    cv_filename: str,
    llm=None,
    sources=None,
    config: dict | None = None,
) -> None:
    """Executa o pipeline completo. Destinado a ser chamado via asyncio.create_task()."""
    pipeline = build_pipeline_graph(llm=llm, sources=sources)

    initial_state: PipelineVagasState = {
        "tenant_id": tenant_id,
        "usuario_id": usuario_id,
        "pipeline_run_id": pipeline_run_id,
        "cv_text": cv_text,
        "cv_filename": cv_filename,
        "perfil": None,
        "candidato_id": None,
        "vagas": [],
        "candidaturas": [],
        "erro": None,
        "config": config,
        "excluir_urls": None,
    }

    try:
        await pipeline.ainvoke(initial_state)
    except Exception as e:
        logger.error("pipeline %s: erro não tratado: %s", pipeline_run_id, e)
        # Garante que o run não fique preso em status intermediário
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    from docagent.vagas.services import PipelineRunService
                    await PipelineRunService(session).registrar_erro(
                        pipeline_run_id, str(e)
                    )
            await vagas_sse_manager.broadcast(pipeline_run_id, {
                "type": "ERRO",
                "mensagem": str(e),
            })
        except Exception:
            pass


async def executar_pipeline_reuso(
    tenant_id: int,
    usuario_id: int,
    pipeline_run_id: int,
    candidato_id: int,
    excluir_urls: list[str],
    llm=None,
    sources=None,
    config: dict | None = None,
) -> None:
    """Reutiliza um Candidato existente — pula extração de CV e exclui URLs já vistas."""
    pipeline = build_pipeline_graph(llm=llm, sources=sources)

    initial_state: PipelineVagasState = {
        "tenant_id": tenant_id,
        "usuario_id": usuario_id,
        "pipeline_run_id": pipeline_run_id,
        "cv_text": "",          # sem CV — cv_analyzer entra em modo reuso
        "cv_filename": "",
        "perfil": None,
        "candidato_id": candidato_id,   # sinaliza cv_analyzer para reutilizar
        "vagas": [],
        "candidaturas": [],
        "erro": None,
        "config": config,
        "excluir_urls": excluir_urls,
    }

    try:
        await pipeline.ainvoke(initial_state)
    except Exception as e:
        logger.error("pipeline_reuso %s: erro não tratado: %s", pipeline_run_id, e)
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    from docagent.vagas.services import PipelineRunService
                    await PipelineRunService(session).registrar_erro(pipeline_run_id, str(e))
            await vagas_sse_manager.broadcast(pipeline_run_id, {"type": "ERRO", "mensagem": str(e)})
        except Exception:
            pass
