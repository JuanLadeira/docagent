"""
Nó 4 do pipeline de vagas: Registrar.

Responsabilidade:
- Finaliza o PipelineRun com contagens finais
- Emite SSE CONCLUIDO (ou ERRO se há erro no estado)
- Último nó do pipeline — sempre executado
"""
import logging
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from docagent.vagas.models import PipelineStatus
from docagent.vagas.pipeline_state import PipelineVagasState
from docagent.vagas.services import PipelineRunService
from docagent.vagas.sse import VagasPipelineSseManager

logger = logging.getLogger(__name__)


def make_registrar_node(
    session: AsyncSession,
    sse_manager: VagasPipelineSseManager,
) -> Callable:
    """Factory que retorna o nó registrar para o LangGraph pipeline."""

    async def registrar(state: PipelineVagasState) -> dict:
        pipeline_run_id = state["pipeline_run_id"]
        vagas = state.get("vagas") or []
        candidaturas = state.get("candidaturas") or []
        erro = state.get("erro")

        run_service = PipelineRunService(session)

        if erro:
            await run_service.registrar_erro(pipeline_run_id, erro)
            await sse_manager.broadcast(pipeline_run_id, {
                "type": "ERRO",
                "mensagem": erro,
            })
            return {}

        await run_service.finalizar(
            pipeline_run_id,
            vagas_encontradas=len(vagas),
            candidaturas_criadas=len(candidaturas),
        )
        await sse_manager.broadcast(pipeline_run_id, {
            "type": "CONCLUIDO",
            "vagas_encontradas": len(vagas),
            "candidaturas_criadas": len(candidaturas),
        })

        logger.info(
            "registrar: pipeline %s concluído — %d vagas, %d candidaturas",
            pipeline_run_id, len(vagas), len(candidaturas),
        )
        return {}

    return registrar
