"""
Fase 21a — Rate Limiting.

Verifica que os endpoints críticos bloqueiam após exceder o limite.
Os testes enviam N+1 requisições e checam que a última retorna 429.

NOTA: o ASGI transport do httpx sempre usa 127.0.0.1 como IP — todos os
contadores são por esse IP. O conftest reseta o storage antes de cada teste
para garantir isolamento.
"""
import pytest
from httpx import AsyncClient


# ── helpers ──────────────────────────────────────────────────────────────────

async def _post_form_n(client: AsyncClient, url: str, n: int, data: dict) -> list[int]:
    """Envia n requisições form-encoded e retorna lista de status codes."""
    return [
        (await client.post(url, data=data)).status_code
        for _ in range(n)
    ]


async def _post_json_n(client: AsyncClient, url: str, n: int, payload: dict) -> list[int]:
    """Envia n requisições JSON e retorna lista de status codes."""
    return [
        (await client.post(url, json=payload)).status_code
        for _ in range(n)
    ]


# ── /auth/login — 5 req/min/IP ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_bloqueado_apos_5_tentativas(client: AsyncClient):
    payload = {"username": "x", "password": "x"}

    # Primeiras 5 requisições: 401 (credenciais erradas), mas não 429
    statuses = await _post_form_n(client, "/auth/login", 5, payload)
    assert all(s != 429 for s in statuses), f"429 prematuro: {statuses}"

    # 6ª requisição deve ser bloqueada
    r = await client.post("/auth/login", data=payload)
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_login_nao_bloqueado_dentro_do_limite(client: AsyncClient):
    """Exatamente 5 requisições não devem disparar o limite."""
    payload = {"username": "x", "password": "x"}
    statuses = await _post_form_n(client, "/auth/login", 5, payload)
    assert 429 not in statuses


# ── /auth/forgot-password — 3 req/hora/IP ─────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_bloqueado_apos_3_tentativas(client: AsyncClient):
    payload = {"email": "a@b.com"}

    statuses = await _post_json_n(client, "/auth/forgot-password", 3, payload)
    assert all(s != 429 for s in statuses), f"429 prematuro: {statuses}"

    r = await client.post("/auth/forgot-password", json=payload)
    assert r.status_code == 429


# ── /auth/reset-password — 3 req/hora/IP ──────────────────────────────────────

@pytest.mark.asyncio
async def test_reset_password_bloqueado_apos_3_tentativas(client: AsyncClient):
    payload = {"token": "tok", "new_password": "abc123"}

    statuses = await _post_json_n(client, "/auth/reset-password", 3, payload)
    assert all(s != 429 for s in statuses), f"429 prematuro: {statuses}"

    r = await client.post("/auth/reset-password", json=payload)
    assert r.status_code == 429


# ── /api/admin/login — 5 req/min/IP ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_login_bloqueado_apos_5_tentativas(client: AsyncClient):
    payload = {"username": "x", "password": "x"}

    statuses = await _post_form_n(client, "/api/admin/login", 5, payload)
    assert all(s != 429 for s in statuses), f"429 prematuro: {statuses}"

    r = await client.post("/api/admin/login", data=payload)
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_admin_login_nao_bloqueado_dentro_do_limite(client: AsyncClient):
    payload = {"username": "x", "password": "x"}
    statuses = await _post_form_n(client, "/api/admin/login", 5, payload)
    assert 429 not in statuses
