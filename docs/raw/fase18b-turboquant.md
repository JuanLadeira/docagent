# Fase 18b — TurboQuant: KV Cache Compression para LLM Local

## Objetivo

Integrar o método **TurboQuant** (Google Research, ICLR 2026, arXiv:2504.19874) como um novo provider de LLM local no DocAgent, permitindo compressão do KV cache em ~3 bits e redução de ~5-6x no consumo de VRAM — viabilizando contextos mais longos e/ou modelos maiores em GPUs com 8GB (ex: RTX 5060).

---

## Contexto técnico

### Por que TurboQuant?

Com 8GB de VRAM, o KV cache cresce linearmente com o número de tokens e rapidamente consome toda a memória disponível quando o contexto é longo. TurboQuant comprime o cache em ~3 bits via:

1. **Walsh-Hadamard Transform** — rotaciona vetores K/V para espalhar outliers uniformemente
2. **Codebook Lloyd-Max** — quantiza cada coordenada com codebook ótimo para distribuição Beta
3. **Dequantização on-demand** — reverte o processo ao ler o cache

**Características críticas:**
- **Training-free** — funciona em qualquer modelo sem fine-tuning
- **3.5 bits** = qualidade idêntica a FP16; **2.5 bits** = degradação mínima
- **NÃO usar QJL** (estágio 2 do paper) — 6+ equipes confirmaram que softmax amplifica variância do QJL. Usar sempre `unbiased=False` (MSE-only, Algoritmo 1)
- Keys precisam de mais bits que Values (normas de K são 10-100x maiores)

### Pacote

```bash
pip install turboquant-torch   # ou: uv sync --extra hf
```

API principal:
```python
import turboquant

# One-liner (recomendado)
model = turboquant.wrap(model, bit_width=3, verbose=True)

# Cache explícito
from turboquant import TurboQuantDynamicCache
cache = TurboQuantDynamicCache.from_model(model)
output = model.generate(**inputs, past_key_values=cache)

# Baixo nível
from turboquant import TurboQuant
tq = TurboQuant(dim=128, bit_width=3, unbiased=False)  # unbiased=False = MSE-only
```

---

## Diferença da arquitetura atual

O projeto hoje usa **Ollama** como backend local (processo separado, exposto via HTTP). TurboQuant requer carregar modelos diretamente via **HuggingFace Transformers** (in-process, PyTorch). São execuções completamente diferentes — o novo provider `hf_local` coexiste com Ollama sem conflito.

| | Ollama | hf_local (novo) |
|---|---|---|
| Modelo carregado por | Processo Ollama separado | Python in-process (PyTorch) |
| Controle do KV cache | Ollama interno | Nós, via TurboQuant |
| Workers uvicorn | Qualquer | **Deve ser 1** (singleton VRAM) |
| VRAM dos pesos | Gerenciado pelo Ollama | `torch_dtype=float16` + `device_map="auto"` |

---

## O que será implementado

### Sprint 1 — Módulo `llm_hf.py` + TDD

**Criar `src/docagent/agent/llm_hf.py`:**
- Import opcional com graceful degradation para `torch`, `turboquant`, `transformers`, `langchain_huggingface`
- Singleton dict `_HF_CACHE: dict[tuple, BaseChatModel]` — chave `(model_name, device, effective_bits)`
- OOM retry em sequência descendente: `TURBOQUANT_BITS=4` → tenta `[4, 3, 2]`; `BITS=3` → tenta `[3, 2]`
  - No except OOM: `del model` + `torch.cuda.empty_cache()` antes de retentativa
- VRAM monitor: `torch.cuda.memory_allocated()` logado antes e após carregamento
- `unbiased=False` como padrão hardcoded (nunca usar QJL)
- Expor como `ChatHuggingFace(llm=HuggingFacePipeline(pipe))` → suporta `.bind_tools()` via chat template Qwen2.5

```python
def get_hf_llm(
    model: str | None = None,
    device: str | None = None,
    bit_width: int | None = None,
    tq_enabled: bool | None = None,
) -> BaseChatModel: ...
```

**Criar `tests/test_llm_hf/test_llm_hf.py`:**
- Todos os módulos externos mockados via `sys.modules` + `importlib.reload`
- Fixture `autouse` limpa `_HF_CACHE` e `sys.modules["docagent.agent.llm_hf"]` entre testes
- Casos: graceful degradation, singleton, OOM retry, TurboQuant wrap, integração com llm_factory

### Sprint 2 — Integração na factory + settings + deps

**Editar `src/docagent/agent/llm_factory.py`:**
```python
PROVIDERS = ("ollama", "openai", "groq", "anthropic", "gemini", "hf_local")

if provider == "hf_local":
    from docagent.agent.llm_hf import get_hf_llm
    return get_hf_llm()
```

**Editar `src/docagent/settings.py`:**
```python
LLM_HF_MODEL: str = os.getenv("LLM_HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
TURBOQUANT_ENABLED: bool = os.getenv("TURBOQUANT_ENABLED", "true").lower() == "true"
TURBOQUANT_BITS: int = int(os.getenv("TURBOQUANT_BITS", "3"))
TURBOQUANT_DEVICE: str = os.getenv("TURBOQUANT_DEVICE", "cuda")
```

**Editar `pyproject.toml`:**
```toml
[project.optional-dependencies]
hf = [
    "torch>=2.2.0",
    "transformers>=4.40.0",
    "accelerate>=0.30.0",
    "langchain-huggingface>=0.1.0",
    "turboquant-torch>=0.1.0",
]
```

**Editar `.env.example`:**
```bash
# HuggingFace Local com TurboQuant (provider hf_local)
# Instalar: uv sync --extra hf
# ATENÇÃO: usar --workers 1 no uvicorn (singleton não compartilhado entre processos)
LLM_HF_MODEL=Qwen/Qwen2.5-7B-Instruct
TURBOQUANT_ENABLED=true
TURBOQUANT_BITS=3
TURBOQUANT_DEVICE=cuda
```

### Sprint 3 — Benchmark script

**Criar `tools/benchmark.py`:**
- Standalone, executável com `uv run tools/benchmark.py`
- Compara: **FP16** vs **TQ-4bit** vs **TQ-3bit**
- Contextos: 512, 1024, 2048, 4096 tokens
- Métricas: load time (s), throughput (tok/s), VRAM alocada/reservada (GB)
- Output: tabela Rich no terminal + `data/benchmark_results.json`

```
┌─────────┬─────────┬──────────┬──────────────┬──────────┐
│ Config  │ Context │ Load (s) │ Throughput   │ VRAM(GB) │
├─────────┼─────────┼──────────┼──────────────┼──────────┤
│ FP16    │     512 │    12.3  │    42 tok/s  │   14.2   │
│ TQ-4bit │     512 │    12.5  │    52 tok/s  │    8.1   │
│ TQ-3bit │     512 │    12.5  │    55 tok/s  │    6.3   │
└─────────┴─────────┴──────────┴──────────────┴──────────┘
```

---

## Arquivos a criar/modificar

| Arquivo | Ação |
|---------|------|
| `src/docagent/agent/llm_hf.py` | **Criar** — módulo TurboQuant |
| `tests/test_llm_hf/__init__.py` | **Criar** |
| `tests/test_llm_hf/test_llm_hf.py` | **Criar** — TDD com mocks |
| `tools/benchmark.py` | **Criar** — benchmark standalone |
| `src/docagent/agent/llm_factory.py` | **Editar** — branch `hf_local` |
| `src/docagent/settings.py` | **Editar** — 4 novas vars |
| `pyproject.toml` | **Editar** — optional-deps `hf` |
| `.env.example` | **Editar** — documentar vars |

---

## Ordem dos commits

1. `docs(fase18b): spec TurboQuant KV cache compression`
2. `feat(fase18b/sprint1): settings + optional-deps hf`
3. `test(fase18b/sprint1): TDD tests llm_hf — fase red`
4. `feat(fase18b/sprint1): llm_hf.py — singleton + TurboQuant + OOM retry`
5. `feat(fase18b/sprint2): llm_factory hf_local provider`
6. `feat(fase18b/sprint3): benchmark.py`

---

## Verificação final

```bash
# Testes unitários (sem GPU, sem deps hf instaladas)
uv run pytest tests/test_llm_hf/ -v

# Todos os testes existentes continuam passando
uv run pytest tests/ -v -m "not integration"

# Benchmark real (requer GPU + deps hf)
uv sync --extra hf
uv run tools/benchmark.py --context 512 1024 --bits 3 4

# Ativar o provider via env
LLM_PROVIDER=hf_local uvicorn docagent.api:app --workers 1
```

---

## Gotchas antecipados

- **`temperature=0.0` com `do_sample=False`** → `UserWarning` no transformers. Omitir `temperature` quando `do_sample=False`.
- **`device_map="auto"` > `device_map=device`** → mais robusto para offload CPU↔GPU automático.
- **Thread safety do singleton** — dict é safe com GIL mas a sequência check→load→insert não é atômica. Aceitável para `--workers 1`; documentar limitação.
- **`turboquant-torch` pode não estar no PyPI ainda** — código sempre tem fallback para FP16 puro via `try/except ImportError`.
- **`ChatHuggingFace.bind_tools()`** só funciona com modelos que têm chat template com function calling (Qwen2.5 ✅). Documentar restrição.
