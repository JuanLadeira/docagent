"""
Nó 1 do pipeline de vagas: CV Analyzer.

Responsabilidade:
- Recebe cv_text + cv_filename do estado
- Trunca para 8000 chars antes de enviar ao LLM
- Usa structured output (json_mode) para extrair perfil do candidato
- Persiste Candidato no banco
- Emite SSE de progresso
- Fallback com perfil vazio se LLM falhar
- Sinaliza erro no estado se CV estiver vazio (scaneado/ilegível)
"""
import asyncio
import logging
from typing import Callable

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.vagas.models import PipelineStatus
from docagent.vagas.pipeline_state import PipelineVagasState
from docagent.vagas.services import CandidatoService, PipelineRunService
from docagent.vagas.sse import VagasPipelineSseManager

logger = logging.getLogger(__name__)

CV_MAX_CHARS = 8000

PERFIL_PROMPT = """Analise o currículo abaixo e extraia as informações do candidato em formato JSON.

CURRÍCULO:
{cv_text}

Retorne um JSON com os campos:
- nome: string (nome completo do candidato)
- email: string (e-mail de contato)
- telefone: string (telefone de contato)
- cargo_desejado: string (principal cargo ou área de atuação)
- skills: lista de strings (habilidades técnicas e ferramentas)
- experiencias: lista de objetos com {{"cargo": "", "empresa": "", "periodo": "", "descricao": ""}}
- formacao: lista de objetos com {{"grau": "", "curso": "", "instituicao": "", "ano": ""}}
- resumo: string (parágrafo curto sobre o perfil profissional)

Se uma informação não estiver disponível, use string vazia ou lista vazia.
"""


class PerfilExtraido(BaseModel):
    nome: str = ""
    email: str = ""
    telefone: str = ""
    cargo_desejado: str = ""
    skills: list = []
    experiencias: list = []
    formacao: list = []
    resumo: str = ""


def make_cv_analyzer_node(
    session: AsyncSession,
    sse_manager: VagasPipelineSseManager,
    llm=None,
) -> Callable:
    """Factory que retorna o nó cv_analyzer para o LangGraph pipeline."""

    async def cv_analyzer(state: PipelineVagasState) -> dict:
        tenant_id = state["tenant_id"]
        usuario_id = state["usuario_id"]
        pipeline_run_id = state["pipeline_run_id"]
        cv_text = state["cv_text"]
        cv_filename = state["cv_filename"]
        candidato_id_existente = state.get("candidato_id")

        run_service = PipelineRunService(session)
        candidato_service = CandidatoService(session)

        # ── Modo reuso: candidato_id já definido, sem CV novo ────────────────
        if candidato_id_existente and not cv_text.strip():
            candidato = await candidato_service.get_by_id(candidato_id_existente)
            if not candidato:
                await run_service.registrar_erro(pipeline_run_id, "Candidato não encontrado.")
                await sse_manager.broadcast(pipeline_run_id, {
                    "type": "ERRO", "mensagem": "Candidato não encontrado."
                })
                return {"erro": "Candidato não encontrado."}

            await run_service.atualizar_status(
                pipeline_run_id,
                status=PipelineStatus.ANALISANDO_CV,
                etapa_atual="Reutilizando perfil existente...",
                candidato_id=candidato.id,
            )
            await sse_manager.broadcast(pipeline_run_id, {
                "type": "PROGRESSO",
                "etapa": PipelineStatus.ANALISANDO_CV.value,
                "mensagem": f"Reutilizando perfil de {candidato.nome or 'candidato'}...",
            })
            return {
                "perfil": {
                    "nome": candidato.nome,
                    "email": candidato.email,
                    "telefone": candidato.telefone,
                    "cargo_desejado": candidato.cargo_desejado,
                    "skills": candidato.skills or [],
                    "experiencias": candidato.experiencias or [],
                    "formacao": candidato.formacao or [],
                    "resumo": candidato.resumo,
                },
                "candidato_id": candidato.id,
                "erro": None,
            }

        # Sinalizar CV vazio antes de tudo
        if not cv_text.strip():
            await run_service.registrar_erro(
                pipeline_run_id, "Texto do CV vazio — PDF pode estar scaneado ou ilegível."
            )
            await sse_manager.broadcast(pipeline_run_id, {
                "type": "ERRO",
                "mensagem": "Texto do CV vazio — PDF pode estar scaneado ou ilegível.",
            })
            return {"erro": "Texto do CV vazio — PDF pode estar scaneado ou ilegível."}

        # Atualizar status
        await run_service.atualizar_status(
            pipeline_run_id,
            status=PipelineStatus.ANALISANDO_CV,
            etapa_atual="Analisando currículo...",
        )
        await sse_manager.broadcast(pipeline_run_id, {
            "type": "PROGRESSO",
            "etapa": PipelineStatus.ANALISANDO_CV.value,
            "mensagem": "Analisando currículo...",
        })

        # Extrair perfil via LLM
        perfil = await _extrair_perfil(llm, cv_text)

        # Persistir Candidato (inclui texto bruto para geração do PDF adaptado)
        candidato = await candidato_service.criar(
            tenant_id=tenant_id,
            usuario_id=usuario_id,
            nome=perfil.nome,
            email=perfil.email,
            telefone=perfil.telefone,
            skills=perfil.skills,
            experiencias=perfil.experiencias,
            formacao=perfil.formacao,
            cargo_desejado=perfil.cargo_desejado,
            resumo=perfil.resumo,
            cv_filename=cv_filename,
            cv_texto=cv_text[:CV_MAX_CHARS],
        )

        # Vincular candidato ao run
        await run_service.atualizar_status(
            pipeline_run_id,
            status=PipelineStatus.ANALISANDO_CV,
            candidato_id=candidato.id,
        )

        return {
            "perfil": perfil.model_dump(),
            "candidato_id": candidato.id,
            "erro": None,
        }

    return cv_analyzer


async def _extrair_perfil(llm, cv_text: str) -> PerfilExtraido:
    """Chama o LLM com structured output. Retorna PerfilExtraido vazio em caso de falha."""
    cv_truncado = cv_text[:CV_MAX_CHARS]
    prompt = PERFIL_PROMPT.format(cv_text=cv_truncado)

    try:
        chain = llm.with_structured_output(PerfilExtraido, method="json_mode")
        perfil = await chain.ainvoke(prompt)
        return perfil
    except Exception as e:
        logger.warning("cv_analyzer: falha ao extrair perfil via LLM: %s", e)
        return PerfilExtraido()
