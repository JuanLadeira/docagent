"""
Source de vagas via Gupy API pública.
GET https://portal.api.gupy.io/api/v1/jobs?jobName=<termo>&limit=10&offset=N
Sem autenticação necessária.

IMPORTANTE: A API da Gupy NÃO suporta queries multi-palavra.
"Desenvolvedor Python" retorna 0 resultados; "Desenvolvedor" retorna 105.

Estratégia:
- Extrai tokens individuais do cargo_desejado e das skills (ex: ["Desenvolvedor", "Python", "Backend"])
- Para cada token: offset 0, 10, 20 → 3 requests
- Total: N_tokens × 3 requests em paralelo
- Deduplicação por URL após aggregate
"""
import asyncio
import logging
import re
from urllib.parse import quote

import httpx

from docagent.vagas.models import FonteVaga

logger = logging.getLogger(__name__)

GUPY_API_URL = "https://portal.api.gupy.io/api/v1/jobs"
LIMIT = 10
_OFFSETS = [0, 10, 20]

# Palavras a ignorar ao tokenizar o cargo
_STOPWORDS = {
    "de", "do", "da", "dos", "das", "e", "em", "com", "para",
    "o", "a", "os", "as", "um", "uma",
}


_MODALIDADE_TERMO: dict[str, str] = {
    "HOMEOFFICE": "remoto",
    "PRESENCIAL": "presencial",
    "HIBRIDO": "híbrido",
}


def _extrair_termos(perfil: dict) -> list[str]:
    """Extrai termos únicos e relevantes para busca na Gupy."""
    cargo = perfil.get("cargo_desejado", "")
    skills = perfil.get("skills", []) or []

    termos: list[str] = []
    vistos: set[str] = set()

    # Tokeniza o cargo por espaço/hífen
    for tok in re.split(r"[\s\-/]+", cargo):
        tok = tok.strip()
        if len(tok) >= 3 and tok.lower() not in _STOPWORDS:
            key = tok.lower()
            if key not in vistos:
                vistos.add(key)
                termos.append(tok)

    # Adiciona skills (até 5 extras)
    for skill in skills[:5]:
        if isinstance(skill, str) and len(skill) >= 2:
            key = skill.lower()
            if key not in vistos:
                vistos.add(key)
                termos.append(skill)

    # Injeta termo de modalidade no início (se configurado) para biesar a busca
    modalidade = perfil.get("_modalidade")
    if modalidade and modalidade in _MODALIDADE_TERMO:
        termo_mod = _MODALIDADE_TERMO[modalidade]
        if termo_mod.lower() not in vistos:
            termos.insert(0, termo_mod)

    # Limita a 6 termos para não sobrecarregar a API
    return termos[:6]


class GupySource:
    async def buscar(self, perfil: dict) -> list[dict]:
        termos = _extrair_termos(perfil)
        if not termos:
            return []

        try:
            async with httpx.AsyncClient(timeout=12) as client:
                tasks = [
                    self._fetch_page(client, termo, offset)
                    for termo in termos
                    for offset in _OFFSETS
                ]
                resultados = await asyncio.gather(*tasks, return_exceptions=True)

            vagas: list[dict] = []
            urls_vistos: set[str] = set()
            for r in resultados:
                if isinstance(r, list):
                    for v in r:
                        url = v.get("url", "")
                        if url and url not in urls_vistos:
                            urls_vistos.add(url)
                            vagas.append(v)

            logger.info("GupySource: %d vagas únicas (termos=%s)", len(vagas), termos)
            return vagas

        except Exception as e:
            logger.warning("GupySource: erro geral: %s", e)
            return []

    async def _fetch_page(self, client: httpx.AsyncClient, termo: str, offset: int) -> list[dict]:
        try:
            url = f"{GUPY_API_URL}?jobName={quote(termo)}&limit={LIMIT}&offset={offset}"
            resp = await client.get(url)
            resp.raise_for_status()
            return [_normalizar(item) for item in resp.json().get("data", [])]
        except Exception as e:
            logger.debug("GupySource page offset=%d termo=%r: %s", offset, termo, e)
            return []


def _normalizar(item: dict) -> dict:
    career_page = item.get("careerPage") or {}
    empresa = career_page.get("name", "") or item.get("company", "") or ""

    cidade = item.get("city", "") or ""
    estado = item.get("state", "") or ""
    localizacao = f"{cidade}, {estado}".strip(", ") if cidade or estado else ""

    return {
        "titulo": item.get("name", ""),
        "empresa": empresa,
        "localizacao": localizacao,
        "descricao": item.get("description", "") or "",
        "requisitos": item.get("prerequisites", "") or "",
        "url": item.get("jobUrl", "") or "",
        "fonte": FonteVaga.GUPY.value,
        "raw_data": item,
        # Gupy sempre usa candidatura direta pela plataforma (Easy Apply nativo)
        "candidatura_simplificada": True,
    }
