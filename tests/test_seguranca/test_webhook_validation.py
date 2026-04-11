"""
Testes de validação de origem dos webhooks (Fase 21e).

- WhatsApp: header 'apikey' vs EVOLUTION_API_KEY
- Telegram: header 'X-Telegram-Bot-Api-Secret-Token' vs webhook_secret da instância
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from docagent.api import app
from docagent.whatsapp.router import _validar_webhook_evolution
from docagent.telegram.router import _validar_webhook_telegram
from fastapi import HTTPException, Request


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_request(headers: dict) -> MagicMock:
    """Cria um objeto Request fake com headers específicos."""
    req = MagicMock(spec=Request)
    req.headers = headers
    return req


# ── WhatsApp: _validar_webhook_evolution ─────────────────────────────────────

class TestValidarWebhookEvolution:
    def test_apikey_correta_passa(self):
        req = _mock_request({"apikey": "secret123"})
        with patch("docagent.whatsapp.router.Settings") as MockSettings:
            MockSettings.return_value.EVOLUTION_API_KEY = "secret123"
            # Não deve levantar exceção
            _validar_webhook_evolution(req)

    def test_apikey_errada_retorna_401(self):
        req = _mock_request({"apikey": "errada"})
        with patch("docagent.whatsapp.router.Settings") as MockSettings:
            MockSettings.return_value.EVOLUTION_API_KEY = "secret123"
            with pytest.raises(HTTPException) as exc_info:
                _validar_webhook_evolution(req)
            assert exc_info.value.status_code == 401

    def test_sem_apikey_header_retorna_401(self):
        req = _mock_request({})
        with patch("docagent.whatsapp.router.Settings") as MockSettings:
            MockSettings.return_value.EVOLUTION_API_KEY = "secret123"
            with pytest.raises(HTTPException) as exc_info:
                _validar_webhook_evolution(req)
            assert exc_info.value.status_code == 401

    def test_evolution_api_key_vazia_aceita_tudo(self):
        """Sem chave configurada (dev local), qualquer requisição passa."""
        req = _mock_request({})
        with patch("docagent.whatsapp.router.Settings") as MockSettings:
            MockSettings.return_value.EVOLUTION_API_KEY = ""
            # Não deve levantar exceção
            _validar_webhook_evolution(req)

    def test_evolution_api_key_none_aceita_tudo(self):
        req = _mock_request({"apikey": "qualquer"})
        with patch("docagent.whatsapp.router.Settings") as MockSettings:
            MockSettings.return_value.EVOLUTION_API_KEY = None
            # Não deve levantar exceção
            _validar_webhook_evolution(req)


# ── Telegram: _validar_webhook_telegram ──────────────────────────────────────

class TestValidarWebhookTelegram:
    def test_secret_correto_passa(self):
        req = _mock_request({"X-Telegram-Bot-Api-Secret-Token": "mysecret"})
        # Não deve levantar exceção
        _validar_webhook_telegram(req, "mysecret")

    def test_secret_errado_retorna_401(self):
        req = _mock_request({"X-Telegram-Bot-Api-Secret-Token": "errado"})
        with pytest.raises(HTTPException) as exc_info:
            _validar_webhook_telegram(req, "mysecret")
        assert exc_info.value.status_code == 401

    def test_sem_header_retorna_401(self):
        req = _mock_request({})
        with pytest.raises(HTTPException) as exc_info:
            _validar_webhook_telegram(req, "mysecret")
        assert exc_info.value.status_code == 401

    def test_sem_webhook_secret_configurado_aceita_tudo(self):
        """Instâncias configuradas antes desta feature não têm secret — devem funcionar."""
        req = _mock_request({})
        # Não deve levantar exceção quando webhook_secret é None
        _validar_webhook_telegram(req, None)

    def test_sem_webhook_secret_vazio_aceita_tudo(self):
        req = _mock_request({"X-Telegram-Bot-Api-Secret-Token": "qualquer"})
        _validar_webhook_telegram(req, "")


# ── Integração: POST /api/whatsapp/webhook ────────────────────────────────────

@pytest.mark.asyncio
async def test_whatsapp_webhook_sem_apikey_configurada_aceita(client: AsyncClient):
    """Sem EVOLUTION_API_KEY no settings, o webhook deve passar sem autenticação."""
    payload = {
        "event": "messages.upsert",
        "instance": "test",
        "data": {},
    }
    with patch("docagent.whatsapp.router.Settings") as MockSettings:
        MockSettings.return_value.EVOLUTION_API_KEY = ""
        MockSettings.return_value.EVOLUTION_API_URL = "http://evolution-api:8080"
        # _processar_mensagem vai falhar por falta de dados, mas o 401 não deve acontecer
        resp = await client.post("/api/whatsapp/webhook", json=payload)
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_whatsapp_webhook_apikey_errada_retorna_401(client: AsyncClient):
    payload = {
        "event": "messages.upsert",
        "instance": "test",
        "data": {},
    }
    with patch("docagent.whatsapp.router.Settings") as MockSettings:
        MockSettings.return_value.EVOLUTION_API_KEY = "chave-correta"
        resp = await client.post(
            "/api/whatsapp/webhook",
            json=payload,
            headers={"apikey": "chave-errada"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_whatsapp_webhook_apikey_correta_passa(client: AsyncClient):
    payload = {
        "event": "messages.upsert",
        "instance": "test",
        "data": {},
    }
    with patch("docagent.whatsapp.router.Settings") as MockSettings:
        MockSettings.return_value.EVOLUTION_API_KEY = "chave-correta"
        MockSettings.return_value.EVOLUTION_API_URL = "http://evolution-api:8080"
        resp = await client.post(
            "/api/whatsapp/webhook",
            json=payload,
            headers={"apikey": "chave-correta"},
        )
    # Passa a validação (pode retornar 200 ou outro erro de negócio, mas não 401)
    assert resp.status_code != 401
