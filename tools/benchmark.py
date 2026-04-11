#!/usr/bin/env python3
"""
Benchmark standalone: FP16 vs TurboQuant 4-bit vs TurboQuant 3-bit.

Mede latência e throughput em contextos de 512/1024/2048/4096 tokens.
Gera tabela no terminal e arquivo JSON com resultados.

Requer: uv sync --extra hf

Uso:
    uv run tools/benchmark.py
    uv run tools/benchmark.py --model Qwen/Qwen2.5-7B-Instruct --device cuda
    uv run tools/benchmark.py --context 512 1024 --bits 3 4 --no-fp16
    uv run tools/benchmark.py --output data/resultados.json
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    """Resultado de uma rodada de benchmark."""
    config: str
    context_tokens: int
    load_time_s: float
    total_time_s: float
    tokens_generated: int
    throughput_tok_s: float
    vram_allocated_gb: float
    vram_reserved_gb: float
    error: str | None = None


@dataclass
class BenchmarkSuite:
    """Conjunto de resultados com metadados da execução."""
    model: str
    device: str
    timestamp: str
    results: list[BenchmarkResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers de VRAM e inferência
# ---------------------------------------------------------------------------

def _vram_gb() -> tuple[float, float]:
    """Retorna (alocado_gb, reservado_gb) no device CUDA 0."""
    try:
        import torch
        if torch.cuda.is_available():
            return (
                torch.cuda.memory_allocated(0) / 1024**3,
                torch.cuda.memory_reserved(0) / 1024**3,
            )
    except Exception:  # noqa: BLE001
        pass
    return 0.0, 0.0


def _make_prompt(n_tokens: int, tokenizer) -> str:
    """Gera um prompt com aproximadamente n_tokens tokens."""
    # Texto de relleno em PT-BR para garantir comprimento consistente
    base = (
        "Explique detalhadamente o funcionamento de redes neurais transformers, "
        "incluindo mecanismo de atenção, embeddings posicionais, normalização de camadas "
        "e como o KV cache é utilizado para acelerar a inferência. "
    )
    # Repete até atingir o tamanho desejado
    text = base * ((n_tokens // len(tokenizer.encode(base))) + 2)
    ids = tokenizer.encode(text)[:n_tokens]
    return tokenizer.decode(ids)


def _run_inference(model, tokenizer, prompt: str, max_new_tokens: int = 50) -> tuple[float, int]:
    """Executa inferência e retorna (tempo_total_s, n_tokens_gerados)."""
    import torch

    inputs = tokenizer(prompt, return_tensors="pt")
    if hasattr(model, "device"):
        try:
            inputs = {k: v.to(model.device) for k, v in inputs.items()}
        except Exception:  # noqa: BLE001
            pass

    t0 = time.perf_counter()
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )
    t1 = time.perf_counter()

    n_new = output.shape[-1] - inputs["input_ids"].shape[-1]
    return t1 - t0, n_new


# ---------------------------------------------------------------------------
# Carregamento de modelo
# ---------------------------------------------------------------------------

def _load_model(
    model_name: str,
    device: str,
    use_turboquant: bool,
    bit_width: int,
) -> tuple[object, object, float]:
    """Carrega modelo e tokenizer, retorna (model, tokenizer, load_time_s)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    t0 = time.perf_counter()

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    device_map = "auto" if device != "cpu" and torch.cuda.is_available() else None
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map=device_map,
    )
    if device_map is None:
        model = model.to(device if torch.cuda.is_available() or device == "cpu" else "cpu")

    if use_turboquant:
        try:
            import turboquant
            print(f"  Aplicando TurboQuant {bit_width}-bit (unbiased=False)...")
            model = turboquant.wrap(model, bit_width=bit_width, unbiased=False, verbose=False)
        except ImportError:
            print("  AVISO: turboquant-torch não instalado — rodando em FP16 puro.")

    load_time = time.perf_counter() - t0
    return model, tokenizer, load_time


# ---------------------------------------------------------------------------
# Execução do benchmark
# ---------------------------------------------------------------------------

def run_benchmark(
    model_name: str,
    device: str,
    context_sizes: list[int],
    bits_list: list[int],
    include_fp16: bool,
    max_new_tokens: int,
) -> BenchmarkSuite:
    """Executa o benchmark completo e retorna o BenchmarkSuite."""
    suite = BenchmarkSuite(
        model=model_name,
        device=device,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Configurações a testar
    configs: list[tuple[str, bool, int]] = []
    if include_fp16:
        configs.append(("FP16", False, 0))
    for b in bits_list:
        configs.append((f"TQ-{b}bit", True, b))

    for config_name, use_tq, bits in configs:
        print(f"\n{'─'*60}")
        print(f"Configuração: {config_name}")
        print(f"{'─'*60}")

        try:
            print(f"  Carregando {model_name}...")
            model, tokenizer, load_time = _load_model(model_name, device, use_tq, bits)
            print(f"  Carregado em {load_time:.1f}s")

            for ctx_size in context_sizes:
                print(f"  Contexto: {ctx_size} tokens ", end="", flush=True)
                try:
                    prompt = _make_prompt(ctx_size, tokenizer)
                    vram_alloc, vram_res = _vram_gb()

                    total_time, n_tokens = _run_inference(
                        model, tokenizer, prompt, max_new_tokens=max_new_tokens
                    )
                    throughput = n_tokens / total_time if total_time > 0 else 0.0

                    result = BenchmarkResult(
                        config=config_name,
                        context_tokens=ctx_size,
                        load_time_s=round(load_time, 2),
                        total_time_s=round(total_time, 3),
                        tokens_generated=n_tokens,
                        throughput_tok_s=round(throughput, 1),
                        vram_allocated_gb=round(vram_alloc, 2),
                        vram_reserved_gb=round(vram_res, 2),
                    )
                    print(f"→ {throughput:.1f} tok/s | VRAM={vram_alloc:.1f}GB")

                except Exception as exc:  # noqa: BLE001
                    print(f"→ ERRO: {exc}")
                    result = BenchmarkResult(
                        config=config_name,
                        context_tokens=ctx_size,
                        load_time_s=round(load_time, 2),
                        total_time_s=0.0,
                        tokens_generated=0,
                        throughput_tok_s=0.0,
                        vram_allocated_gb=0.0,
                        vram_reserved_gb=0.0,
                        error=str(exc),
                    )

                suite.results.append(result)

            # Libera memória antes da próxima configuração
            try:
                import torch
                del model
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass

        except Exception as exc:  # noqa: BLE001
            print(f"  ERRO no carregamento: {exc}")
            for ctx_size in context_sizes:
                suite.results.append(BenchmarkResult(
                    config=config_name,
                    context_tokens=ctx_size,
                    load_time_s=0.0,
                    total_time_s=0.0,
                    tokens_generated=0,
                    throughput_tok_s=0.0,
                    vram_allocated_gb=0.0,
                    vram_reserved_gb=0.0,
                    error=str(exc),
                ))

    return suite


# ---------------------------------------------------------------------------
# Exibição de resultados
# ---------------------------------------------------------------------------

def _print_table(suite: BenchmarkSuite) -> None:
    """Exibe tabela de resultados no terminal."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(
            title=f"Benchmark: {suite.model} @ {suite.device}",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Config", style="bold")
        table.add_column("Context", justify="right")
        table.add_column("Load (s)", justify="right")
        table.add_column("Total (s)", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Throughput", justify="right")
        table.add_column("VRAM (GB)", justify="right")
        table.add_column("Erro", style="red")

        for r in suite.results:
            table.add_row(
                r.config,
                str(r.context_tokens),
                f"{r.load_time_s:.1f}",
                f"{r.total_time_s:.3f}" if not r.error else "—",
                str(r.tokens_generated) if not r.error else "—",
                f"{r.throughput_tok_s:.1f} tok/s" if not r.error else "—",
                f"{r.vram_allocated_gb:.2f}" if not r.error else "—",
                r.error or "",
            )

        console.print(table)

    except ImportError:
        # Fallback sem rich
        header = f"{'Config':<12} {'Context':>8} {'Load':>7} {'Total':>7} {'Tokens':>7} {'Thput':>10} {'VRAM':>7} {'Erro'}"
        print("\n" + "=" * 80)
        print(f"Benchmark: {suite.model} @ {suite.device}")
        print("=" * 80)
        print(header)
        print("-" * 80)
        for r in suite.results:
            thput = f"{r.throughput_tok_s:.1f}" if not r.error else "—"
            vram = f"{r.vram_allocated_gb:.2f}" if not r.error else "—"
            total = f"{r.total_time_s:.3f}" if not r.error else "—"
            erro = r.error or ""
            print(f"{r.config:<12} {r.context_tokens:>8} {r.load_time_s:>7.1f} {total:>7} {r.tokens_generated:>7} {thput:>10} {vram:>7} {erro}")
        print("=" * 80)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark TurboQuant KV cache compression",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
        help="ID do modelo HuggingFace (default: Qwen/Qwen2.5-7B-Instruct)",
    )
    parser.add_argument(
        "--device", default="cuda",
        help="Dispositivo de inferência: cuda | cpu | mps (default: cuda)",
    )
    parser.add_argument(
        "--context", nargs="+", type=int, default=[512, 1024, 2048, 4096],
        metavar="N",
        help="Tamanhos de contexto a testar (default: 512 1024 2048 4096)",
    )
    parser.add_argument(
        "--bits", nargs="+", type=int, default=[4, 3],
        metavar="B",
        help="Bit-widths TurboQuant a testar (default: 4 3)",
    )
    parser.add_argument(
        "--no-fp16", action="store_true",
        help="Pula baseline FP16 (só testa TurboQuant)",
    )
    parser.add_argument(
        "--max-new-tokens", type=int, default=50,
        help="Tokens a gerar por inferência (default: 50)",
    )
    parser.add_argument(
        "--output", default="data/benchmark_results.json",
        help="Caminho do arquivo JSON de saída (default: data/benchmark_results.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Valida disponibilidade de torch
    try:
        import torch  # noqa: F401
    except ImportError:
        print("ERRO: torch não instalado. Execute: uv sync --extra hf")
        raise SystemExit(1)

    print(f"Modelo:  {args.model}")
    print(f"Device:  {args.device}")
    print(f"Context: {args.context}")
    print(f"Bits:    {args.bits}")
    print(f"FP16:    {'não' if args.no_fp16 else 'sim'}")

    suite = run_benchmark(
        model_name=args.model,
        device=args.device,
        context_sizes=args.context,
        bits_list=args.bits,
        include_fp16=not args.no_fp16,
        max_new_tokens=args.max_new_tokens,
    )

    _print_table(suite)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(suite), indent=2, ensure_ascii=False))
    print(f"\nResultados salvos em: {output_path}")


if __name__ == "__main__":
    main()
