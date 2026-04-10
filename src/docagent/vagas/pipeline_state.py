from typing import TypedDict


class PipelineVagasState(TypedDict):
    tenant_id: int
    usuario_id: int
    pipeline_run_id: int
    cv_text: str
    cv_filename: str
    perfil: dict | None
    candidato_id: int | None
    vagas: list[dict]
    candidaturas: list[dict]
    erro: str | None
    # Configurações do pipeline (max_vagas, max_personalizar, fontes, candidatura_simplificada)
    config: dict | None
    # URLs de vagas já encontradas em runs anteriores — job_searcher filtra essas
    excluir_urls: list[str] | None
