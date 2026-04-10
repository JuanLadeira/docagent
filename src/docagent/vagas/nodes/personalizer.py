"""
Nó 3 do pipeline de vagas: Personalizer.

Responsabilidade:
- Recebe top vagas do estado (max 10)
- Para cada vaga, chama LLM para gerar resumo personalizado + carta de apresentação
- Processa em SEQUÊNCIA (não paralelo) para evitar rate limiting
- Persiste cada Candidatura individualmente ao gerar
- Emite SSE de progresso incremental (N/total)
- Falha em uma vaga não para o restante
"""
import json
import logging
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from docagent.vagas.models import PipelineStatus
from docagent.vagas.pipeline_state import PipelineVagasState
from docagent.vagas.services import CandidaturaService, PipelineRunService
from docagent.vagas.sse import VagasPipelineSseManager

logger = logging.getLogger(__name__)

TOP_PERSONALIZAR = 10

PERSONALIZER_PROMPT = """Você é um especialista em recrutamento. Personalize o currículo e a carta de apresentação do candidato para a vaga abaixo.

PERFIL DO CANDIDATO:
Nome: {nome}
Cargo desejado: {cargo_desejado}
Skills: {skills}
Resumo: {resumo}

VAGA:
Título: {titulo}
Empresa: {empresa}
Descrição: {descricao}
Requisitos: {requisitos}

Retorne um JSON com:
- resumo: string (resumo do candidato adaptado para esta vaga específica, 2-3 parágrafos)
- carta: string (carta de apresentação completa e personalizada para esta vaga)

Seja específico, mencione a empresa e o cargo. Use as skills do candidato que são relevantes para esta vaga."""

PERSONALIZER_PROMPT_SIMPLIFICADO = """Gere uma candidatura simplificada para a vaga abaixo.

CANDIDATO:
Nome: {nome}
Skills: {skills}

VAGA:
{titulo} na {empresa}
Requisitos: {requisitos}

Retorne um JSON com:
- resumo: string (1 parágrafo conciso, máx 120 palavras, destaque as 3 skills mais relevantes para esta vaga)
- carta: string (exatamente 3 frases: 1ª interesse na vaga, 2ª principal diferencial do candidato, 3ª call to action)"""


class PersonalizacaoOutput:
    def __init__(self, resumo: str = "", carta: str = ""):
        self.resumo = resumo
        self.carta = carta


def make_personalizer_node(
    session: AsyncSession,
    sse_manager: VagasPipelineSseManager,
    llm=None,
) -> Callable:
    """Factory que retorna o nó personalizer para o LangGraph pipeline."""

    async def personalizer(state: PipelineVagasState) -> dict:
        tenant_id = state["tenant_id"]
        pipeline_run_id = state["pipeline_run_id"]
        candidato_id = state.get("candidato_id")
        perfil = state.get("perfil") or {}
        vagas = state.get("vagas") or []
        cfg = state.get("config") or {}
        top_n = cfg.get("max_personalizar", TOP_PERSONALIZAR)
        simplificada = cfg.get("candidatura_simplificada", False)

        run_service = PipelineRunService(session)
        cand_service = CandidaturaService(session)

        await run_service.atualizar_status(
            pipeline_run_id,
            status=PipelineStatus.PERSONALIZANDO,
            etapa_atual="Personalizando candidaturas...",
        )

        vagas_para_personalizar = vagas[:top_n]
        total = len(vagas_para_personalizar)
        candidaturas_criadas = []

        for i, vaga_dict in enumerate(vagas_para_personalizar, start=1):
            await sse_manager.broadcast(pipeline_run_id, {
                "type": "PROGRESSO",
                "etapa": PipelineStatus.PERSONALIZANDO.value,
                "mensagem": f"Personalizando {i}/{total}...",
            })

            vaga_id = vaga_dict.get("id")
            if not vaga_id:
                continue

            try:
                resultado = await _personalizar_vaga(llm, perfil, vaga_dict, simplificada=simplificada)

                candidatura = await cand_service.criar(
                    tenant_id=tenant_id,
                    pipeline_run_id=pipeline_run_id,
                    vaga_id=vaga_id,
                    candidato_id=candidato_id,
                    resumo_personalizado=resultado.resumo,
                    carta_apresentacao=resultado.carta,
                    simplificada=simplificada,
                )
                candidaturas_criadas.append({
                    "id": candidatura.id,
                    "vaga_id": vaga_id,
                    "status": candidatura.status,
                })

            except Exception as e:
                logger.warning("personalizer: erro ao personalizar vaga %s: %s", vaga_id, e)
                # Continua para a próxima vaga

        return {
            "candidaturas": candidaturas_criadas,
            "erro": None,
        }

    return personalizer


async def _personalizar_vaga(llm, perfil: dict, vaga: dict, simplificada: bool = False) -> PersonalizacaoOutput:
    """Chama LLM para gerar resumo + carta para uma vaga. Retorna vazio em caso de falha."""
    template = PERSONALIZER_PROMPT_SIMPLIFICADO if simplificada else PERSONALIZER_PROMPT
    prompt = template.format(
        nome=perfil.get("nome", ""),
        cargo_desejado=perfil.get("cargo_desejado", ""),
        skills=", ".join(perfil.get("skills", [])),
        resumo=perfil.get("resumo", ""),
        titulo=vaga.get("titulo", ""),
        empresa=vaga.get("empresa", ""),
        descricao=(vaga.get("descricao", "") or "")[:2000],
        requisitos=(vaga.get("requisitos", "") or "")[:500],
    )

    try:
        chain = llm.with_structured_output(None, method="json_mode")
        resp = await chain.ainvoke(prompt)

        # resp pode ser um objeto com .content (ChatMessage) ou um dict
        if hasattr(resp, "content"):
            data = json.loads(resp.content)
        elif isinstance(resp, dict):
            data = resp
        else:
            data = {}

        return PersonalizacaoOutput(
            resumo=data.get("resumo", ""),
            carta=data.get("carta", ""),
        )
    except Exception as e:
        logger.warning("personalizer: falha ao chamar LLM para vaga '%s': %s", vaga.get("titulo"), e)
        return PersonalizacaoOutput()
