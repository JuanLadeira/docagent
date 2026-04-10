"""
Nó 2 do pipeline de vagas: Job Searcher.

Responsabilidade:
- Busca vagas em paralelo via múltiplas fontes (Gupy, DDG, LinkedIn, Indeed)
- Cada fonte contribui até max_vagas_por_fonte resultados (limite por fonte, não global)
- Fontes com falha retornam [] — nunca derrubam o pipeline
- Calcula match_score por keyword matching (skills vs descrição) — sem LLM
- Persiste Vaga[] no banco
- Emite SSE de progresso com contagem por fonte
"""
import asyncio
import logging
from collections import defaultdict
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from docagent.vagas.models import FonteVaga, PipelineStatus
from docagent.vagas.pipeline_state import PipelineVagasState
from docagent.vagas.services import PipelineRunService, VagaService
from docagent.vagas.sse import VagasPipelineSseManager

logger = logging.getLogger(__name__)

MAX_POR_FONTE = 10  # default

# Palavras-chave para detecção de modalidade nas vagas
_MODALIDADE_KEYWORDS: dict[str, list[str]] = {
    "HOMEOFFICE": [
        "home office", "homeoffice", "remoto", "remote", "trabalho remoto",
        "100% remoto", "full remote", "anywhere", "trabalhe de casa",
    ],
    "PRESENCIAL": [
        "presencial", "on-site", "onsite", "no escritório", "in loco",
        "local de trabalho", "trabalho presencial",
    ],
    "HIBRIDO": [
        "híbrido", "hibrido", "hybrid", "flexível", "flex",
        "modelo híbrido", "modelo hibrido", "parcialmente remoto",
    ],
}


def make_job_searcher_node(
    session: AsyncSession,
    sse_manager: VagasPipelineSseManager,
    sources: list | None = None,
) -> Callable:
    """Factory que retorna o nó job_searcher para o LangGraph pipeline.

    sources: lista de JobSource injetável (testes). Se None, instancia as fontes conforme config.
    """

    def _get_sources(fontes_ativas: list[str] | None = None) -> list:
        if sources is not None:
            return sources
        from docagent.vagas.sources.gupy import GupySource
        from docagent.vagas.sources.duckduckgo import DuckDuckGoSource
        from docagent.vagas.sources.linkedin import LinkedInSource
        from docagent.vagas.sources.indeed import IndeedSource
        all_sources = {
            "GUPY": GupySource(),
            "DUCKDUCKGO": DuckDuckGoSource(),
            "LINKEDIN": LinkedInSource(),
            "INDEED": IndeedSource(),
        }
        if fontes_ativas is None:
            return list(all_sources.values())
        return [v for k, v in all_sources.items() if k in fontes_ativas]

    async def job_searcher(state: PipelineVagasState) -> dict:
        tenant_id = state["tenant_id"]
        pipeline_run_id = state["pipeline_run_id"]
        perfil = state.get("perfil") or {}
        cfg = state.get("config") or {}

        limite_por_fonte = cfg.get("max_vagas_por_fonte", MAX_POR_FONTE)
        fontes_ativas = cfg.get("fontes") or None
        apenas_simplificadas = cfg.get("apenas_simplificadas", False)
        modalidade_filtro: str | None = cfg.get("modalidade")
        excluir_urls: set[str] = set(state.get("excluir_urls") or [])

        run_service = PipelineRunService(session)
        vaga_service = VagaService(session)

        await run_service.atualizar_status(
            pipeline_run_id,
            status=PipelineStatus.BUSCANDO_VAGAS,
            etapa_atual="Buscando vagas...",
        )
        await sse_manager.broadcast(pipeline_run_id, {
            "type": "PROGRESSO",
            "etapa": PipelineStatus.BUSCANDO_VAGAS.value,
            "mensagem": "Buscando vagas em paralelo...",
        })

        # ── Busca paralela ────────────────────────────────────────────────────
        todas_sources = _get_sources(fontes_ativas)
        # Passa modalidade via perfil para fontes que a suportam (chave privada _modalidade)
        perfil_busca = {**perfil, "_modalidade": modalidade_filtro} if modalidade_filtro else perfil
        tasks = [_buscar_safe(source, perfil_busca) for source in todas_sources]
        resultados = await asyncio.gather(*tasks)

        # ── Agrupa por fonte, aplica limite por fonte ─────────────────────────
        skills = perfil.get("skills", [])
        por_fonte: dict[str, list[dict]] = defaultdict(list)
        urls_vistos: set[str] = set()

        for lote in resultados:
            for vaga in lote:
                url = vaga.get("url", "")
                if not url or url in urls_vistos or url in excluir_urls:
                    continue
                urls_vistos.add(url)
                # Calcula score aqui antes de agrupar
                texto = f"{vaga.get('descricao', '')} {vaga.get('requisitos', '')}"
                vaga["match_score"] = _calcular_match_score(skills, texto)
                por_fonte[vaga.get("fonte", "OUTRO")].append(vaga)

        # Log + SSE com contagem por fonte
        resumo_fontes = []
        top_vagas: list[dict] = []

        for fonte_nome, vagas_da_fonte in sorted(por_fonte.items()):
            # Ordena por score e aplica limite por fonte
            vagas_da_fonte.sort(key=lambda v: v["match_score"], reverse=True)

            if apenas_simplificadas:
                vagas_da_fonte = [v for v in vagas_da_fonte if v.get("candidatura_simplificada", False)]

            if modalidade_filtro:
                vagas_da_fonte = [v for v in vagas_da_fonte if _tem_modalidade(v, modalidade_filtro)]

            selecionadas = vagas_da_fonte[:limite_por_fonte]
            top_vagas.extend(selecionadas)
            resumo_fontes.append(f"{fonte_nome}: {len(selecionadas)}")
            logger.info("job_searcher: %s → %d encontradas, %d selecionadas", fonte_nome, len(vagas_da_fonte), len(selecionadas))

        resumo_msg = " | ".join(resumo_fontes) if resumo_fontes else "nenhuma vaga encontrada"
        await sse_manager.broadcast(pipeline_run_id, {
            "type": "PROGRESSO",
            "etapa": PipelineStatus.BUSCANDO_VAGAS.value,
            "mensagem": f"Vagas encontradas — {resumo_msg}",
        })

        # Ordena o conjunto final por score (melhor match primeiro)
        top_vagas.sort(key=lambda v: v["match_score"], reverse=True)

        # ── Persiste no banco ─────────────────────────────────────────────────
        vagas_persistidas = []
        for v in top_vagas:
            try:
                fonte = FonteVaga(v.get("fonte", FonteVaga.DUCKDUCKGO.value))
                vaga_db = await vaga_service.criar(
                    tenant_id=tenant_id,
                    pipeline_run_id=pipeline_run_id,
                    titulo=v.get("titulo", ""),
                    empresa=v.get("empresa", ""),
                    localizacao=v.get("localizacao", ""),
                    descricao=v.get("descricao", ""),
                    requisitos=v.get("requisitos", ""),
                    url=v.get("url", ""),
                    fonte=fonte,
                    match_score=v.get("match_score", 0.0),
                    raw_data=v.get("raw_data", {}),
                    candidatura_simplificada=v.get("candidatura_simplificada", False),
                )
                vagas_persistidas.append({
                    "id": vaga_db.id,
                    "titulo": vaga_db.titulo,
                    "empresa": vaga_db.empresa,
                    "url": vaga_db.url,
                    "match_score": vaga_db.match_score,
                })
            except Exception as e:
                logger.warning("job_searcher: erro ao persistir vaga: %s", e)

        return {
            "vagas": vagas_persistidas,
            "erro": None,
        }

    return job_searcher


async def _buscar_safe(source, perfil: dict) -> list[dict]:
    """Executa busca na source capturando qualquer exceção."""
    try:
        return await source.buscar(perfil)
    except Exception as e:
        logger.warning("job_searcher: source %s falhou: %s", type(source).__name__, e)
        return []


def _calcular_match_score(skills: list[str], descricao: str) -> float:
    """Conta quantas skills do candidato aparecem no texto da vaga (case-insensitive)."""
    if not skills:
        return 0.0
    descricao_lower = descricao.lower()
    matches = sum(1 for skill in skills if skill.lower() in descricao_lower)
    return matches / len(skills)


def _tem_modalidade(vaga: dict, modalidade: str) -> bool:
    """Retorna True se o texto da vaga contém pelo menos uma keyword da modalidade desejada.

    Vagas sem qualquer sinal de modalidade retornam False — são descartadas quando
    um filtro de modalidade está ativo.
    """
    texto = " ".join([
        vaga.get("titulo", ""),
        vaga.get("localizacao", ""),
        vaga.get("descricao", ""),
        vaga.get("requisitos", ""),
    ]).lower()
    keywords = _MODALIDADE_KEYWORDS.get(modalidade, [])
    return any(kw in texto for kw in keywords)
