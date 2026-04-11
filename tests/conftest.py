"""
Fixtures globais — carregadas em todos os testes.
"""
import pytest


@pytest.fixture(autouse=True)
def reset_rate_limit_storage():
    """
    Reseta os contadores do rate limiter antes/depois de cada teste.
    Necessário porque o Limiter usa um singleton em memória — sem reset,
    testes que esgotam o limite afetam os testes seguintes.
    """
    from docagent.api import app
    app.state.limiter._limiter.storage.reset()
    yield
    app.state.limiter._limiter.storage.reset()
