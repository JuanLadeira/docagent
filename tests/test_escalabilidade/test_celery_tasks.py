"""
Testes unitários para a task Celery ingerir_documento_task.

Roda em modo eager (CELERY_TASK_ALWAYS_EAGER=True) sem broker real.
A ingestão real (doc_service.create) é mockada para isolar a lógica da task.
Os testes são SÍNCRONOS para que asyncio.run() dentro da task funcione
(pytest-asyncio cria um event loop próprio que conflita com asyncio.run).
"""
import asyncio
import base64
import pytest
from unittest.mock import patch, AsyncMock


@pytest.fixture(autouse=True)
def celery_eager():
    """Executa tasks inline, sem broker."""
    from docagent.celery_app import celery
    celery.conf.update(task_always_eager=True, task_eager_propagates=True)
    yield
    celery.conf.update(task_always_eager=False, task_eager_propagates=False)


def _make_mock_ingerir():
    """Cria um coroutine mock que não precisa de asyncio ativo."""
    async def _mock(*args, **kwargs):
        return None
    return _mock


def test_ingerir_documento_task_sucesso():
    """Task retorna status=ok quando ingestão completa sem erros."""
    from docagent.tasks.ingestao import ingerir_documento_task

    conteudo = b"%PDF fake content"
    content_b64 = base64.b64encode(conteudo).decode()

    with patch("docagent.tasks.ingestao._ingerir", side_effect=_make_mock_ingerir()):
        result = ingerir_documento_task.apply(args=[1, "test.pdf", content_b64])
        assert result.result["status"] == "ok"


def test_ingerir_documento_task_retorna_agente_id():
    """Task inclui agente_id e filename na resposta."""
    from docagent.tasks.ingestao import ingerir_documento_task

    content_b64 = base64.b64encode(b"pdf").decode()
    with patch("docagent.tasks.ingestao._ingerir", side_effect=_make_mock_ingerir()):
        result = ingerir_documento_task.apply(args=[42, "doc.pdf", content_b64])
        assert result.result["agente_id"] == 42
        assert result.result["filename"] == "doc.pdf"


def test_ingerir_documento_task_falha_retry():
    """Task agenda retry quando ingestão falha — em eager mode levanta Retry."""
    from docagent.tasks.ingestao import ingerir_documento_task
    from celery.exceptions import Retry

    async def _falha(*args, **kwargs):
        raise RuntimeError("DB down")

    content_b64 = base64.b64encode(b"pdf").decode()
    with patch("docagent.tasks.ingestao._ingerir", side_effect=_falha):
        # Em eager+propagate, Celery re-executa até max_retries e então levanta Retry
        with pytest.raises(Retry):
            ingerir_documento_task.apply(args=[1, "fail.pdf", content_b64])
