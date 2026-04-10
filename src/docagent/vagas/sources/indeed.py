"""
Source de vagas via Indeed Brasil.

Estratégia de paralelismo para contornar o limite por request do RSS:
- Múltiplas páginas em paralelo (start=0, 10, 20, 30)
- Múltiplas variações de query em paralelo (cargo, cargo+remoto, cargo+pleno)
- Fallback HTML com paginação se RSS falhar por completo
- Deduplicação por URL após aggregate
- Falha silenciosa sempre — nunca derruba o pipeline
"""
import asyncio
import logging
from urllib.parse import quote
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from docagent.vagas.models import FonteVaga

logger = logging.getLogger(__name__)

INDEED_RSS_BASE  = "https://br.indeed.com/rss?q={cargo}&l=Brasil&sort=date&start={start}"
INDEED_HTML_BASE = "https://br.indeed.com/jobs?q={cargo}&l=Brasil&sort=date&start={start}"

# Páginas RSS buscadas em paralelo (cada uma retorna até ~15 itens)
RSS_PAGES = [0, 10, 20, 30]

# Variações de query para ampliar cobertura
_QUERY_SUFIXOS = ["", " remoto", " pleno sênior", " júnior"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}
_SIMPLIFICADA_KW = ("easily apply", "candidatura simplificada", "quick apply")


class IndeedSource:
    async def buscar(self, perfil: dict) -> list[dict]:
        cargo = perfil.get("cargo_desejado", "")
        if not cargo:
            return []

        try:
            vagas = await self._buscar_paralelo(cargo)
            if vagas:
                return vagas
            # RSS bloqueado por completo → tenta HTML
            return await self._buscar_html_paralelo(cargo)
        except Exception as e:
            logger.info("IndeedSource: falha geral: %s", e)
            return []

    # ── RSS paralelo ──────────────────────────────────────────────────────────

    async def _buscar_paralelo(self, cargo: str) -> list[dict]:
        """Dispara (N queries × M páginas) requests RSS em paralelo."""
        async with httpx.AsyncClient(timeout=12, headers=HEADERS, follow_redirects=True) as client:
            tasks = [
                self._fetch_rss_page(client, cargo + sufixo, start)
                for sufixo in _QUERY_SUFIXOS
                for start in RSS_PAGES
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
        return vagas

    async def _fetch_rss_page(self, client: httpx.AsyncClient, cargo: str, start: int) -> list[dict]:
        try:
            url = INDEED_RSS_BASE.format(cargo=quote(cargo), start=start)
            resp = await client.get(url)
            resp.raise_for_status()
            return _parsear_rss(resp.text)
        except Exception as e:
            logger.debug("IndeedSource RSS page start=%d cargo=%r: %s", start, cargo, e)
            return []

    # ── HTML paralelo (fallback) ───────────────────────────────────────────────

    async def _buscar_html_paralelo(self, cargo: str) -> list[dict]:
        """Scraping HTML com múltiplas páginas em paralelo."""
        async with httpx.AsyncClient(timeout=12, headers=HEADERS, follow_redirects=True) as client:
            tasks = [
                self._fetch_html_page(client, cargo, start)
                for start in [0, 10, 20]
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
        return vagas

    async def _fetch_html_page(self, client: httpx.AsyncClient, cargo: str, start: int) -> list[dict]:
        try:
            url = INDEED_HTML_BASE.format(cargo=quote(cargo), start=start)
            resp = await client.get(url)
            resp.raise_for_status()
            return _parsear_html(resp.text)
        except Exception as e:
            logger.debug("IndeedSource HTML page start=%d: %s", start, e)
            return []


# ── Parsers ──────────────────────────────────────────────────────────────────

def _parsear_rss(xml_text: str) -> list[dict]:
    try:
        root = ElementTree.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []

        vagas = []
        for item in channel.findall("item"):
            titulo = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            descricao = item.findtext("description", "").strip()

            try:
                soup = BeautifulSoup(descricao, "lxml")
                descricao = soup.get_text(separator=" ", strip=True)
            except Exception:
                pass

            if titulo and link:
                simplificada = any(k in descricao.lower() for k in _SIMPLIFICADA_KW)
                vagas.append({
                    "titulo": titulo,
                    "empresa": "",
                    "localizacao": "",
                    "descricao": descricao,
                    "requisitos": "",
                    "url": link,
                    "fonte": FonteVaga.INDEED.value,
                    "raw_data": {"titulo": titulo, "link": link},
                    "candidatura_simplificada": simplificada,
                })
        return vagas
    except Exception as e:
        logger.debug("IndeedSource: erro ao parsear RSS: %s", e)
        return []


def _parsear_html(html: str) -> list[dict]:
    try:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("div.job_seen_beacon") or soup.select("div[data-jk]")

        vagas = []
        for card in cards:
            titulo_tag = card.select_one("h2.jobTitle a") or card.select_one("a[data-jk]")
            empresa_tag = card.select_one("span.companyName") or card.select_one("[data-testid='company-name']")
            local_tag = card.select_one("div.companyLocation") or card.select_one("[data-testid='text-location']")

            titulo = titulo_tag.get_text(strip=True) if titulo_tag else ""
            href = titulo_tag.get("href", "") if titulo_tag else ""
            url = f"https://br.indeed.com{href}" if href.startswith("/") else href
            empresa = empresa_tag.get_text(strip=True) if empresa_tag else ""
            localizacao = local_tag.get_text(strip=True) if local_tag else ""

            if titulo and url:
                easy_tag = card.select_one(".iaLabel") or card.select_one("[aria-label*='easily']")
                vagas.append({
                    "titulo": titulo,
                    "empresa": empresa,
                    "localizacao": localizacao,
                    "descricao": "",
                    "requisitos": "",
                    "url": url,
                    "fonte": FonteVaga.INDEED.value,
                    "raw_data": {},
                    "candidatura_simplificada": bool(easy_tag),
                })
        return vagas
    except Exception as e:
        logger.debug("IndeedSource: erro ao parsear HTML: %s", e)
        return []
