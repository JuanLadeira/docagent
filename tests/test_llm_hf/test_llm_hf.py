"""
TDD — docagent.agent.llm_hf

Testa o loader HuggingFace com TurboQuant sem GPU real.
Todos os módulos externos (torch, turboquant, transformers,
langchain_huggingface) são mockados via sys.modules + importlib.reload
para que os testes rodem no CI sem dependências opcionais instaladas.
"""
from __future__ import annotations

import importlib
import os
import sys
import types
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers para montar mocks
# ---------------------------------------------------------------------------

def _make_torch_mock(cuda_available: bool = True) -> MagicMock:
    torch_mock = MagicMock()
    torch_mock.cuda.is_available.return_value = cuda_available
    torch_mock.cuda.memory_allocated.return_value = int(2 * 1024**3)
    torch_mock.cuda.memory_reserved.return_value = int(3 * 1024**3)
    torch_mock.float16 = "float16_sentinel"
    return torch_mock


def _make_transformers_mock() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Retorna (transformers_mock, fake_model, fake_tokenizer, fake_pipeline_fn)."""
    tf = MagicMock()
    fake_model = MagicMock()
    fake_tokenizer = MagicMock()
    fake_pipeline_result = MagicMock()

    tf.AutoModelForCausalLM.from_pretrained.return_value = fake_model
    tf.AutoTokenizer.from_pretrained.return_value = fake_tokenizer
    tf.pipeline.return_value = fake_pipeline_result

    return tf, fake_model, fake_tokenizer, fake_pipeline_result


def _make_turboquant_mock() -> MagicMock:
    tq = MagicMock()
    tq.wrap.side_effect = lambda model, **kwargs: model  # pass-through
    return tq


def _make_lch_hf_mock() -> tuple[MagicMock, MagicMock]:
    """Retorna (langchain_huggingface_mock, fake_chat_instance)."""
    lch = MagicMock()
    fake_chat = MagicMock()
    fake_chat.bind_tools.return_value = fake_chat
    lch.HuggingFacePipeline.return_value = MagicMock()
    lch.ChatHuggingFace.return_value = fake_chat
    return lch, fake_chat


def _load_module_with_mocks(
    torch_mock=None,
    turboquant_mock=None,
    transformers_mock=None,
    lch_hf_mock=None,
) -> types.ModuleType:
    """Registra mocks no sys.modules e faz reload de llm_hf."""
    _patch_sys(torch_mock, turboquant_mock, transformers_mock, lch_hf_mock)
    sys.modules.pop("docagent.agent.llm_hf", None)
    import docagent.agent.llm_hf as mod
    return importlib.reload(mod)


def _patch_sys(torch_mock, turboquant_mock, transformers_mock, lch_hf_mock):
    if torch_mock is not None:
        sys.modules["torch"] = torch_mock
    else:
        sys.modules.pop("torch", None)

    if turboquant_mock is not None:
        sys.modules["turboquant"] = turboquant_mock
    else:
        sys.modules.pop("turboquant", None)

    if transformers_mock is not None:
        sys.modules["transformers"] = transformers_mock
    else:
        sys.modules.pop("transformers", None)

    if lch_hf_mock is not None:
        sys.modules["langchain_huggingface"] = lch_hf_mock
    else:
        sys.modules.pop("langchain_huggingface", None)


# ---------------------------------------------------------------------------
# Fixture: limpa estado entre testes
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    """Garante isolamento entre testes: limpa cache e sys.modules."""
    yield
    sys.modules.pop("docagent.agent.llm_hf", None)
    for key in ["torch", "turboquant", "transformers", "langchain_huggingface"]:
        sys.modules.pop(key, None)


# ---------------------------------------------------------------------------
# 1. Graceful degradation — sem deps instaladas
# ---------------------------------------------------------------------------

class TestGracefulDegradation:

    def test_import_sem_torch_nao_lanca_excecao(self):
        """Importar llm_hf sem torch disponível não deve quebrar."""
        mod = _load_module_with_mocks(
            torch_mock=None, turboquant_mock=None,
            transformers_mock=None, lch_hf_mock=None,
        )
        assert mod is not None

    def test_get_hf_llm_sem_torch_lanca_runtime_error(self):
        """get_hf_llm() sem torch deve lançar RuntimeError com instrução de instalação."""
        mod = _load_module_with_mocks(
            torch_mock=None, turboquant_mock=None,
            transformers_mock=None, lch_hf_mock=None,
        )
        with pytest.raises(RuntimeError, match="uv sync --extra hf"):
            mod.get_hf_llm()

    def test_sem_turboquant_nao_lanca_excecao(self):
        """Sem turboquant instalado, get_hf_llm(tq_enabled=False) não deve quebrar."""
        torch_m = _make_torch_mock()
        tf_m, *_ = _make_transformers_mock()
        lch_m, _ = _make_lch_hf_mock()

        mod = _load_module_with_mocks(
            torch_mock=torch_m,
            turboquant_mock=None,   # turboquant ausente
            transformers_mock=tf_m,
            lch_hf_mock=lch_m,
        )
        result = mod.get_hf_llm(tq_enabled=False)
        assert result is not None

    def test_cuda_indisponivel_usa_cpu(self):
        """Com CUDA indisponível, carregamento deve prosseguir sem lançar erro."""
        torch_m = _make_torch_mock(cuda_available=False)
        tf_m, *_ = _make_transformers_mock()
        lch_m, _ = _make_lch_hf_mock()
        tq_m = _make_turboquant_mock()

        mod = _load_module_with_mocks(
            torch_mock=torch_m, turboquant_mock=tq_m,
            transformers_mock=tf_m, lch_hf_mock=lch_m,
        )
        result = mod.get_hf_llm(device="cuda")
        assert result is not None


# ---------------------------------------------------------------------------
# 2. Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def _full_mod(self):
        torch_m = _make_torch_mock()
        tf_m, *_ = _make_transformers_mock()
        lch_m, fake_chat = _make_lch_hf_mock()
        tq_m = _make_turboquant_mock()
        mod = _load_module_with_mocks(torch_m, tq_m, tf_m, lch_m)
        mod._HF_CACHE.clear()
        return mod, torch_m, tf_m, lch_m, fake_chat

    def test_segunda_chamada_retorna_mesmo_objeto(self):
        """Duas chamadas com mesmos parâmetros devem retornar a mesma instância."""
        mod, *_ = self._full_mod()
        first = mod.get_hf_llm(model="Qwen/Qwen2.5-7B-Instruct")
        second = mod.get_hf_llm(model="Qwen/Qwen2.5-7B-Instruct")
        assert first is second

    def test_from_pretrained_chamado_apenas_uma_vez(self):
        """AutoModelForCausalLM.from_pretrained deve ser chamado só na primeira vez."""
        mod, _, tf_m, *_ = self._full_mod()
        mod.get_hf_llm()
        mod.get_hf_llm()
        mod.get_hf_llm()
        tf_m.AutoModelForCausalLM.from_pretrained.assert_called_once()

    def test_modelos_diferentes_nao_compartilham_cache(self):
        """Modelos distintos devem ter instâncias separadas."""
        torch_m = _make_torch_mock()
        lch_m, _ = _make_lch_hf_mock()
        tq_m = _make_turboquant_mock()
        tf_m, *_ = _make_transformers_mock()

        mod = _load_module_with_mocks(torch_m, tq_m, tf_m, lch_m)
        mod._HF_CACHE.clear()

        # Cada modelo gera uma instância de ChatHuggingFace diferente
        lch_m.ChatHuggingFace.side_effect = [MagicMock(), MagicMock()]

        llm_a = mod.get_hf_llm(model="ModelA")
        llm_b = mod.get_hf_llm(model="ModelB")
        assert llm_a is not llm_b


# ---------------------------------------------------------------------------
# 3. OOM Retry
# ---------------------------------------------------------------------------

class TestOomRetry:

    def _mod_with_oom(self, oom_count: int):
        """Retorna módulo onde from_pretrained falha `oom_count` vezes com OOM."""
        torch_m = _make_torch_mock()
        tf_m, fake_model, *_ = _make_transformers_mock()
        lch_m, _ = _make_lch_hf_mock()
        tq_m = _make_turboquant_mock()

        oom = RuntimeError("CUDA out of memory. Tried to allocate 2GB")
        side_effects = [oom] * oom_count + [fake_model]
        tf_m.AutoModelForCausalLM.from_pretrained.side_effect = side_effects

        mod = _load_module_with_mocks(torch_m, tq_m, tf_m, lch_m)
        mod._HF_CACHE.clear()
        return mod, torch_m, tf_m

    def test_oom_com_bits4_tenta_bits3(self):
        """OOM no primeiro carregamento (bits=4) deve retentativa com bits=3."""
        mod, _, tf_m = self._mod_with_oom(oom_count=1)
        result = mod.get_hf_llm(bit_width=4)
        assert result is not None
        assert tf_m.AutoModelForCausalLM.from_pretrained.call_count == 2

    def test_oom_em_todos_os_niveis_lanca_runtime_error(self):
        """OOM em todos os níveis de bit_width deve lançar RuntimeError claro."""
        torch_m = _make_torch_mock()
        tf_m, *_ = _make_transformers_mock()
        lch_m, _ = _make_lch_hf_mock()
        tq_m = _make_turboquant_mock()

        oom = RuntimeError("CUDA out of memory")
        tf_m.AutoModelForCausalLM.from_pretrained.side_effect = oom

        mod = _load_module_with_mocks(torch_m, tq_m, tf_m, lch_m)
        mod._HF_CACHE.clear()

        with pytest.raises(RuntimeError, match="OOM mesmo com bit_width mínimo"):
            mod.get_hf_llm(bit_width=4)

    def test_cuda_empty_cache_chamado_apos_oom(self):
        """torch.cuda.empty_cache() deve ser chamado após cada falha OOM."""
        mod, torch_m, _ = self._mod_with_oom(oom_count=1)
        mod.get_hf_llm(bit_width=4)
        torch_m.cuda.empty_cache.assert_called()

    def test_sequencia_retry_respeita_bit_width_inicial(self):
        """bits=3 → sequência de retry [3, 2], NÃO tenta 4."""
        torch_m = _make_torch_mock()
        tf_m, fake_model, *_ = _make_transformers_mock()
        lch_m, _ = _make_lch_hf_mock()
        tq_m = _make_turboquant_mock()

        oom = RuntimeError("CUDA out of memory")
        tf_m.AutoModelForCausalLM.from_pretrained.side_effect = [oom, fake_model]

        mod = _load_module_with_mocks(torch_m, tq_m, tf_m, lch_m)
        mod._HF_CACHE.clear()

        result = mod.get_hf_llm(bit_width=3)
        assert result is not None
        # Deve ter tentado exatamente 2 vezes (bits=3 e bits=2), nunca bits=4
        assert tf_m.AutoModelForCausalLM.from_pretrained.call_count == 2


# ---------------------------------------------------------------------------
# 4. TurboQuant wrap
# ---------------------------------------------------------------------------

class TestTurboQuantWrap:

    def _full_mod_tq(self):
        torch_m = _make_torch_mock()
        tf_m, *_ = _make_transformers_mock()
        lch_m, _ = _make_lch_hf_mock()
        tq_m = _make_turboquant_mock()
        mod = _load_module_with_mocks(torch_m, tq_m, tf_m, lch_m)
        mod._HF_CACHE.clear()
        return mod, tq_m

    def test_wrap_chamado_com_bit_width_correto(self):
        """turboquant.wrap() deve receber o bit_width configurado."""
        mod, tq_m = self._full_mod_tq()
        mod.get_hf_llm(bit_width=3, tq_enabled=True)
        tq_m.wrap.assert_called_once()
        _, kwargs = tq_m.wrap.call_args
        assert kwargs.get("bit_width") == 3

    def test_wrap_nao_chamado_quando_desabilitado(self):
        """Com tq_enabled=False, turboquant.wrap() NÃO deve ser chamado."""
        mod, tq_m = self._full_mod_tq()
        mod.get_hf_llm(tq_enabled=False)
        tq_m.wrap.assert_not_called()

    def test_unbiased_false_passado_para_wrap(self):
        """wrap() deve sempre receber unbiased=False (MSE-only, sem QJL)."""
        mod, tq_m = self._full_mod_tq()
        mod.get_hf_llm(bit_width=3, tq_enabled=True)
        _, kwargs = tq_m.wrap.call_args
        assert kwargs.get("unbiased") is False


# ---------------------------------------------------------------------------
# 5. Integração com llm_factory
# ---------------------------------------------------------------------------

class TestLLMFactoryIntegration:

    def test_hf_local_em_providers_tuple(self):
        """'hf_local' deve constar no tuple PROVIDERS da llm_factory."""
        from docagent.agent.llm_factory import PROVIDERS
        assert "hf_local" in PROVIDERS

    def test_get_llm_provider_hf_local_delega_para_get_hf_llm(self):
        """get_llm(provider='hf_local') deve chamar get_hf_llm() e retornar o resultado."""
        fake_llm = MagicMock()
        with patch("docagent.agent.llm_hf.get_hf_llm", return_value=fake_llm) as mock_fn:
            from docagent.agent import llm_factory
            result = llm_factory.get_llm(provider="hf_local")
        mock_fn.assert_called_once()
        assert result is fake_llm


# ---------------------------------------------------------------------------
# 6. Leitura de variáveis de ambiente
# ---------------------------------------------------------------------------

class TestEnvVars:

    def test_env_model_sobrescreve_default(self):
        """LLM_HF_MODEL do ambiente deve ser usado quando não há argumento explícito."""
        torch_m = _make_torch_mock()
        tf_m, *_ = _make_transformers_mock()
        lch_m, _ = _make_lch_hf_mock()
        tq_m = _make_turboquant_mock()

        mod = _load_module_with_mocks(torch_m, tq_m, tf_m, lch_m)
        mod._HF_CACHE.clear()

        with patch.dict(os.environ, {"LLM_HF_MODEL": "Qwen/Qwen2.5-3B-Instruct"}):
            mod.get_hf_llm()

        call_kwargs = tf_m.AutoModelForCausalLM.from_pretrained.call_args
        assert "Qwen/Qwen2.5-3B-Instruct" in call_kwargs.args or \
               call_kwargs.kwargs.get("pretrained_model_name_or_path") == "Qwen/Qwen2.5-3B-Instruct" or \
               call_kwargs.args[0] == "Qwen/Qwen2.5-3B-Instruct"

    def test_turboquant_bits_3_por_padrao(self):
        """TURBOQUANT_BITS padrão deve ser 3."""
        torch_m = _make_torch_mock()
        tf_m, *_ = _make_transformers_mock()
        lch_m, _ = _make_lch_hf_mock()
        tq_m = _make_turboquant_mock()

        mod = _load_module_with_mocks(torch_m, tq_m, tf_m, lch_m)
        mod._HF_CACHE.clear()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TURBOQUANT_BITS", None)
            mod.get_hf_llm(tq_enabled=True)

        _, kwargs = tq_m.wrap.call_args
        assert kwargs.get("bit_width") == 3
