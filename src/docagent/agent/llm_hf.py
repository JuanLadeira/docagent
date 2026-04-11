"""
Loader HuggingFace local com compressão TurboQuant de KV cache.

Expõe get_hf_llm() que retorna um BaseChatModel compatível com bind_tools().
O modelo é carregado uma única vez por processo (singleton via _HF_CACHE).

Requer dependências opcionais:
    uv sync --extra hf

ATENÇÃO: ao usar provider hf_local, rodar uvicorn com --workers 1.
O singleton vive em memória do processo — múltiplos workers carregariam
cópias duplicadas do modelo na VRAM.

Nota sobre TurboQuant:
    Usar sempre unbiased=False (MSE-only, Algoritmo 1 do paper).
    NÃO usar QJL (unbiased=True) — softmax amplifica a variância do estimador.
    Referência: arXiv:2504.19874 (Google Research, ICLR 2026).
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import opcional com graceful degradation
# ---------------------------------------------------------------------------

_TORCH_OK = False
_TQ_OK = False
_LCH_HF_OK = False

try:
    import torch  # noqa: F401
    _TORCH_OK = True
except ImportError:
    log.warning(
        "torch não instalado — provider hf_local indisponível. "
        "Instale com: uv sync --extra hf"
    )

try:
    import turboquant  # noqa: F401
    _TQ_OK = True
except ImportError:
    log.warning(
        "turboquant-torch não instalado — TurboQuant desabilitado. "
        "Modelo rodará em FP16 puro quando provider hf_local for usado."
    )

try:
    from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline  # noqa: F401
    _LCH_HF_OK = True
except ImportError:
    log.warning(
        "langchain-huggingface não instalado — provider hf_local indisponível. "
        "Instale com: uv sync --extra hf"
    )

# ---------------------------------------------------------------------------
# Singleton: chave = (model_name, device, effective_bits | None)
# effective_bits é None quando tq_enabled=False
# ---------------------------------------------------------------------------

_HF_CACHE: dict[tuple[str, str, int | None], "BaseChatModel"] = {}

# ---------------------------------------------------------------------------
# Leitura de configuração
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
_DEFAULT_DEVICE = "cuda"
_DEFAULT_BITS = 3
_DEFAULT_TQ_ENABLED = True


def _read_env() -> tuple[str, str, int, bool]:
    """Lê variáveis de ambiente do provider hf_local.

    Retorna:
        (model_name, device, bit_width, turboquant_enabled)
    """
    model = os.getenv("LLM_HF_MODEL", _DEFAULT_MODEL)
    device = os.getenv("TURBOQUANT_DEVICE", _DEFAULT_DEVICE)
    bits = int(os.getenv("TURBOQUANT_BITS", str(_DEFAULT_BITS)))
    enabled = os.getenv("TURBOQUANT_ENABLED", "true").lower() == "true"
    return model, device, bits, enabled


# ---------------------------------------------------------------------------
# Monitoramento de VRAM
# ---------------------------------------------------------------------------

def _log_vram(stage: str) -> None:
    """Loga uso atual de VRAM no device CUDA 0 (se disponível)."""
    if not _TORCH_OK:
        return
    try:
        import torch
        if torch.cuda.is_available():
            alocado = torch.cuda.memory_allocated(0) / 1024**3
            reservado = torch.cuda.memory_reserved(0) / 1024**3
            log.info("[%s] VRAM alocada=%.2fGB reservada=%.2fGB", stage, alocado, reservado)
    except Exception as exc:  # noqa: BLE001
        log.debug("Erro ao consultar VRAM: %s", exc)


# ---------------------------------------------------------------------------
# Carregamento com OOM retry
# ---------------------------------------------------------------------------

def _retry_sequence(bit_width: int) -> list[int]:
    """Sequência de bit_widths a tentar, da maior para a menor.

    Exemplo: bit_width=4 → [4, 3, 2]; bit_width=3 → [3, 2].
    """
    return [bw for bw in [4, 3, 2] if bw <= bit_width]


def _load_pipeline(
    model_name: str,
    device: str,
    bit_width: int,
    tq_enabled: bool,
) -> tuple[object, int]:
    """Carrega modelo HuggingFace e aplica TurboQuant.

    Tenta carregar com bit_width informado; em caso de CUDA OOM,
    reduz progressivamente até bit_width=2. Lança RuntimeError se
    esgotar todas as tentativas.

    Args:
        model_name: ID do modelo no HuggingFace Hub ou caminho local.
        device: 'cuda', 'cpu' ou 'mps'.
        bit_width: largura de bits desejada para o KV cache (2–4).
        tq_enabled: se False, carrega em FP16 puro sem TurboQuant.

    Returns:
        (HuggingFacePipeline, effective_bit_width)

    Raises:
        RuntimeError: se deps opcionais não estiverem instaladas.
        RuntimeError: se OOM mesmo com bit_width mínimo.
    """
    if not _TORCH_OK or not _LCH_HF_OK:
        raise RuntimeError(
            "Dependências 'hf' não instaladas. Execute: uv sync --extra hf"
        )

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    from langchain_huggingface import HuggingFacePipeline

    # Se CUDA solicitada mas indisponível, recai em CPU com aviso
    effective_device = device
    if device == "cuda" and not torch.cuda.is_available():
        log.warning("CUDA não disponível — usando CPU (inferência será lenta).")
        effective_device = "cpu"

    sequence = _retry_sequence(bit_width) if tq_enabled else [bit_width]
    last_exc: Exception | None = None

    for current_bits in sequence:
        model: object | None = None
        try:
            _log_vram("pre-load")
            log.info(
                "Carregando %s | device=%s | TurboQuant=%s | bits=%d",
                model_name, effective_device, tq_enabled, current_bits,
            )

            tokenizer = AutoTokenizer.from_pretrained(model_name)
            device_map = "auto" if effective_device != "cpu" else None
            model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16,
                device_map=device_map,
            )
            if effective_device == "cpu":
                model = model.to("cpu")

            if tq_enabled:
                if _TQ_OK:
                    import turboquant
                    log.info("Aplicando turboquant.wrap com %d bits (unbiased=False)", current_bits)
                    model = turboquant.wrap(
                        model,
                        bit_width=current_bits,
                        unbiased=False,  # MSE-only — nunca usar QJL
                        verbose=False,
                    )
                else:
                    log.warning(
                        "TURBOQUANT_ENABLED=true mas turboquant-torch não instalado. "
                        "Rodando em FP16 puro."
                    )

            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=2048,
                do_sample=False,
                return_full_text=False,
            )

            _log_vram("post-load")
            log.info("Modelo %s carregado com sucesso (bits=%d)", model_name, current_bits)
            return HuggingFacePipeline(pipeline=pipe), current_bits

        except RuntimeError as exc:
            is_oom = "out of memory" in str(exc).lower()
            if is_oom and tq_enabled:
                log.warning("OOM com bit_width=%d — tentando %d bits...", current_bits, current_bits - 1)
                if model is not None:
                    try:
                        del model
                    except Exception:  # noqa: BLE001
                        pass
                if _TORCH_OK and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                last_exc = exc
                continue
            raise

    raise RuntimeError(
        f"OOM mesmo com bit_width mínimo ao carregar '{model_name}'. "
        f"Último erro: {last_exc}"
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def get_hf_llm(
    model: str | None = None,
    device: str | None = None,
    bit_width: int | None = None,
    tq_enabled: bool | None = None,
) -> "BaseChatModel":
    """Retorna ChatHuggingFace singleton para o modelo configurado.

    Parâmetros explícitos têm precedência sobre variáveis de ambiente.
    O modelo é carregado uma única vez por processo — chamadas
    subsequentes com os mesmos parâmetros retornam a instância em cache.

    Args:
        model: ID do modelo HuggingFace (ex: 'Qwen/Qwen2.5-7B-Instruct').
        device: dispositivo de inferência ('cuda', 'cpu', 'mps').
        bit_width: largura de bits do KV cache TurboQuant (2, 3 ou 4).
        tq_enabled: ativa/desativa TurboQuant independentemente de env.

    Returns:
        BaseChatModel com suporte a .bind_tools() via chat template Qwen2.5.

    Raises:
        RuntimeError: se deps 'hf' não estiverem instaladas.
        RuntimeError: se OOM mesmo com bit_width mínimo.
    """
    env_model, env_device, env_bits, env_tq = _read_env()

    resolved_model = model or env_model
    resolved_device = device or env_device
    resolved_bits = bit_width if bit_width is not None else env_bits
    resolved_tq = tq_enabled if tq_enabled is not None else env_tq

    cache_key = (resolved_model, resolved_device, resolved_bits if resolved_tq else None)

    if not _TORCH_OK or not _LCH_HF_OK:
        raise RuntimeError(
            "Dependências 'hf' não instaladas. Execute: uv sync --extra hf"
        )

    if cache_key in _HF_CACHE:
        log.debug("Retornando modelo HF do cache: %s", resolved_model)
        return _HF_CACHE[cache_key]

    from langchain_huggingface import ChatHuggingFace

    hf_pipeline, effective_bits = _load_pipeline(
        resolved_model, resolved_device, resolved_bits, resolved_tq,
    )
    llm = ChatHuggingFace(llm=hf_pipeline)

    # Registra com bits efetivos (podem ter regredido por OOM)
    effective_key = (resolved_model, resolved_device, effective_bits if resolved_tq else None)
    _HF_CACHE[effective_key] = llm
    # Registra também a chave original como alias (evita retry desnecessário)
    if cache_key != effective_key:
        _HF_CACHE[cache_key] = llm

    return llm
