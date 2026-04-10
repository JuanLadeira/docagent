"""
Source de vagas via DuckDuckGo.
Reutiliza DuckDuckGoSearchResults de langchain_community.

O output do DuckDuckGoSearchResults pode vir em dois formatos:
  - lista Python (formato antigo): '[{"snippet":..., "title":..., "link":...}, ...]'
  - string flat (formato novo): 'snippet: ..., title: ..., link: ..., snippet: ...'

Estratégia:
- 6 queries distintas em paralelo (site-specific + variações de cargo)
- num_results=20 por query
- Parser robusto para ambos os formatos
- Deduplicação por URL após aggregate
"""
import asyncio
import ast
import logging
import re

from docagent.vagas.models import FonteVaga

logger = logging.getLogger(__name__)

_QUERY_TEMPLATES: dict[str | None, list[str]] = {
    None: [
        "{cargo} vaga emprego site:gupy.io",
        "{cargo} vaga emprego site:linkedin.com/jobs",
        "{cargo} vaga emprego site:indeed.com.br",
        "{cargo} vaga remoto brasil",
        "{cargo} oportunidade emprego",
        "{cargo} emprego brasil 2025",
    ],
    "HOMEOFFICE": [
        "{cargo} vaga remoto site:gupy.io",
        "{cargo} home office site:linkedin.com/jobs",
        "{cargo} remote site:indeed.com.br",
        "{cargo} vaga remoto brasil",
        "{cargo} home office brasil 2025",
        "{cargo} trabalho remoto oportunidade",
    ],
    "PRESENCIAL": [
        "{cargo} vaga presencial site:gupy.io",
        "{cargo} presencial site:linkedin.com/jobs",
        "{cargo} presencial site:indeed.com.br",
        "{cargo} vaga presencial brasil",
        "{cargo} emprego presencial brasil 2025",
        "{cargo} vaga on-site brasil",
    ],
    "HIBRIDO": [
        "{cargo} vaga híbrido site:gupy.io",
        "{cargo} hibrido site:linkedin.com/jobs",
        "{cargo} modelo híbrido site:indeed.com.br",
        "{cargo} vaga hibrido brasil",
        "{cargo} hybrid emprego brasil 2025",
        "{cargo} modelo híbrido oportunidade",
    ],
}


class DuckDuckGoSource:
    def __init__(self, tool=None):
        if tool is not None:
            self._tool = tool
        else:
            from langchain_community.tools import DuckDuckGoSearchResults
            self._tool = DuckDuckGoSearchResults(name="vagas_search", num_results=20)

    async def buscar(self, perfil: dict) -> list[dict]:
        cargo = perfil.get("cargo_desejado", "")
        if not cargo:
            return []

        try:
            modalidade = perfil.get("_modalidade")
            templates = _QUERY_TEMPLATES.get(modalidade) or _QUERY_TEMPLATES[None]
            queries = [tmpl.format(cargo=cargo) for tmpl in templates]
            resultados = await asyncio.gather(
                *[self._buscar_safe(q) for q in queries],
                return_exceptions=True,
            )

            vagas: list[dict] = []
            urls_vistos: set[str] = set()
            for lote in resultados:
                if isinstance(lote, list):
                    for v in lote:
                        url = v.get("url", "")
                        if url and url not in urls_vistos:
                            urls_vistos.add(url)
                            vagas.append(v)

            logger.info("DuckDuckGoSource: %d vagas únicas coletadas", len(vagas))
            return vagas

        except Exception as e:
            logger.warning("DuckDuckGoSource: erro geral: %s", e)
            return []

    async def _buscar_safe(self, query: str) -> list[dict]:
        try:
            raw = await self._tool.arun(query)
            resultados = _parse_resultados(raw)
            return [_normalizar(r) for r in resultados if r.get("link")]
        except Exception as e:
            logger.debug("DuckDuckGoSource query=%r: %s", query[:60], e)
            return []


def _parse_resultados(raw: str) -> list[dict]:
    """Parseia o output do DDG — suporta lista Python e string flat."""
    if not raw or not isinstance(raw, str):
        return []

    # Formato antigo: lista Python serializada
    try:
        resultado = ast.literal_eval(raw)
        if isinstance(resultado, list):
            return resultado
    except Exception:
        pass

    # Formato novo: "snippet: ..., title: ..., link: https://..., snippet: ..."
    # Usa regex para extrair cada resultado
    try:
        items = []
        # Particiona a string em blocos por URL (campo link é sempre uma URL)
        # Regex captura snippet, title e link de cada bloco
        pattern = re.compile(
            r"snippet:\s*(.*?),\s*title:\s*(.*?),\s*link:\s*(https?://[^\s,]+)",
            re.DOTALL,
        )
        for m in pattern.finditer(raw):
            items.append({
                "snippet": m.group(1).strip(),
                "title": m.group(2).strip(),
                "link": m.group(3).strip(),
            })
        return items
    except Exception:
        return []


def _normalizar(item: dict) -> dict:
    titulo = item.get("title", "") or ""
    # Tenta separar "Titulo - Empresa" do título
    partes = titulo.split(" - ", 1)
    nome_vaga = partes[0].strip()
    empresa = partes[1].strip() if len(partes) > 1 else ""

    snippet = item.get("snippet", "") or ""
    url = item.get("link", "") or ""
    # Detecta candidatura simplificada por URL (gupy.io tem apply nativo) ou snippet
    _SIMPLIFICADA_KEYWORDS = ("candidatura simplificada", "easy apply", "gupy.io", "apply now")
    candidatura_simplificada = any(k in (snippet + url).lower() for k in _SIMPLIFICADA_KEYWORDS)

    return {
        "titulo": nome_vaga,
        "empresa": empresa,
        "localizacao": "",
        "descricao": snippet,
        "requisitos": "",
        "url": url,
        "fonte": FonteVaga.DUCKDUCKGO.value,
        "raw_data": item,
        "candidatura_simplificada": candidatura_simplificada,
    }
