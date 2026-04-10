"""
Source de vagas via LinkedIn (scraping httpx + BeautifulSoup).
ATENÇÃO: vai falhar com frequência (Cloudflare, CAPTCHA).
Trate como fonte bônus — falha silenciosa sempre.
"""
import logging
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from docagent.vagas.models import FonteVaga

logger = logging.getLogger(__name__)

LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords={cargo}&location=Brasil&f_TPR=r604800"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class LinkedInSource:
    async def buscar(self, perfil: dict) -> list[dict]:
        cargo = perfil.get("cargo_desejado", "")
        if not cargo:
            return []

        try:
            url = LINKEDIN_SEARCH_URL.format(cargo=quote(cargo))
            async with httpx.AsyncClient(timeout=10, headers=HEADERS, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return _parsear_html(resp.text)
        except Exception as e:
            logger.info("LinkedInSource: falha esperada ao buscar vagas: %s", e)
            return []


def _parsear_html(html: str) -> list[dict]:
    try:
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("li.jobs-search__results-list > li") or soup.select("ul.jobs-search__results-list li")

        vagas = []
        for item in items[:10]:
            titulo_tag = item.select_one("a.base-card__full-link") or item.select_one("h3")
            empresa_tag = item.select_one("span.base-search-card__subtitle") or item.select_one("h4")
            local_tag = item.select_one("span.job-search-card__location")

            titulo = titulo_tag.get_text(strip=True) if titulo_tag else ""
            url = titulo_tag.get("href", "") if titulo_tag else ""
            empresa = empresa_tag.get_text(strip=True) if empresa_tag else ""
            localizacao = local_tag.get_text(strip=True) if local_tag else ""

            if titulo and url:
                # LinkedIn Easy Apply: URL contém "/easy-apply" ou card tem o botão easy-apply
                easy_apply = (
                    "easy-apply" in url.lower()
                    or bool(item.select_one(".job-card-container__apply-method--easy-apply"))
                    or bool(item.select_one("[data-job-id]"))  # LinkedIn Easy Apply cards têm data-job-id
                )
                vagas.append({
                    "titulo": titulo,
                    "empresa": empresa,
                    "localizacao": localizacao,
                    "descricao": "",
                    "requisitos": "",
                    "url": url,
                    "fonte": FonteVaga.LINKEDIN.value,
                    "raw_data": {},
                    "candidatura_simplificada": easy_apply,
                })
        return vagas
    except Exception as e:
        logger.info("LinkedInSource: erro ao parsear HTML: %s", e)
        return []
