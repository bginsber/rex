#!/usr/bin/env python3
"""Benchmark RexLit operations against IDL fixture corpora."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

from rexlit import __version__ as REXLIT_VERSION
from rexlit.index.build import build_index
from rexlit.index.search import search_index
from rexlit.ingest.discover import discover_documents


def _manifest_count(corpus_dir: Path) -> int:
    manifest = corpus_dir / "manifest.jsonl"
    if not manifest.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest}")
    return sum(1 for _ in manifest.open(encoding="utf-8"))


def benchmark_discovery(corpus_docs: Path) -> dict[str, Any]:
    start = time.perf_counter()
    documents = list(discover_documents(corpus_docs, recursive=True))
    elapsed = time.perf_counter() - start

    return {
        "operation": "discovery",
        "doc_count": len(documents),
        "elapsed_sec": elapsed,
        "throughput_docs_per_sec": len(documents) / elapsed if elapsed else None,
    }


def benchmark_indexing(corpus_docs: Path, workers: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="rexlit-idl-index-") as tmpdir:
        index_dir = Path(tmpdir) / "index"

        start = time.perf_counter()
        count = build_index(
            corpus_docs,
            index_dir,
            rebuild=True,
            show_progress=False,
            max_workers=workers,
        )
        elapsed = time.perf_counter() - start

        return {
            "operation": "indexing",
            "doc_count": count,
            "workers": workers,
            "elapsed_sec": elapsed,
            "throughput_docs_per_sec": count / elapsed if elapsed else None,
        }


def benchmark_search(index_dir: Path, queries: list[str]) -> dict[str, Any]:
    latencies: list[float] = []

    for query in queries:
        start = time.perf_counter()
        search_index(index_dir, query, limit=5)
        elapsed = time.perf_counter() - start
        latencies.append(elapsed * 1000.0)

    latencies.sort()
    p95_index = int(len(latencies) * 0.95) - 1
    p95_index = max(0, min(p95_index, len(latencies) - 1))

    return {
        "operation": "search",
        "query_count": len(queries),
        "mean_latency_ms": statistics.fmean(latencies),
        "median_latency_ms": statistics.median(latencies),
        "p95_latency_ms": latencies[p95_index],
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
    }


def run_benchmarks(corpus: str, workers: int, baseline_path: Path | None) -> dict[str, Any]:
    fixture_root = Path("rexlit/docs/idl-fixtures")
    corpus_root = fixture_root / corpus
    docs_dir = corpus_root / "docs"

    if not docs_dir.exists():
        raise FileNotFoundError(
            f"IDL corpus '{corpus}' not found at {docs_dir}. "
            "Run scripts/setup-idl-fixtures.sh first."
        )

    doc_count = _manifest_count(corpus_root)
    print(f"Running benchmarks for '{corpus}' corpus ({doc_count} documents)...\n")

    results: dict[str, Any] = {
        "corpus": corpus,
        "timestamp": time.time(),
        "doc_count": doc_count,
        "workers": workers,
        "metadata": {
            "rexlit_version": REXLIT_VERSION,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "benchmarks": [],
    }

    discovery_metrics = benchmark_discovery(docs_dir)
    results["benchmarks"].append(discovery_metrics)
    print(f"[1/3] Discovery: {discovery_metrics['elapsed_sec']:.2f}s")

    indexing_metrics = benchmark_indexing(docs_dir, workers)
    results["benchmarks"].append(indexing_metrics)
    print(f"[2/3] Indexing:  {indexing_metrics['elapsed_sec']:.2f}s")

    with tempfile.TemporaryDirectory(prefix="rexlit-idl-search-") as tmpdir:
        index_dir = Path(tmpdir) / "index"
        build_index(docs_dir, index_dir, rebuild=True, show_progress=False, max_workers=workers)
        search_metrics = benchmark_search(
            index_dir,
            queries=["privilege", "attorney", "contract", "email"],
        )
        results["benchmarks"].append(search_metrics)
    print(f"[3/3] Search:    mean={search_metrics['mean_latency_ms']:.2f}ms")

    if baseline_path and baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        results["baseline_comparison"] = _compare_to_baseline(results, baseline)

    return results


def _compare_to_baseline(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for current_metric in current.get("benchmarks", []):
        op = current_metric["operation"]
        base_metric = next(
            (item for item in baseline.get("benchmarks", []) if item.get("operation") == op),
            None,
        )
        if not base_metric:
            continue

        diffs: dict[str, Dict[str, Any]] = {}
        for key, value in current_metric.items():
            if key in ("operation",) or not isinstance(value, (int, float)):
                continue
            base_value = base_metric.get(key)
            if isinstance(base_value, (int, float)) and base_value:
                percent_change = ((value - base_value) / base_value) * 100
                diffs[key] = {
                    "baseline": base_value,
                    "current": value,
                    "percent_change": percent_change,
                    "description": _describe_change(key, percent_change),
                }
        if diffs:
            comparison[op] = diffs
    return comparison


def _describe_change(metric: str, percent_change: float) -> str:
    if abs(percent_change) < 0.01:
        return "no measurable change"

    lower_is_better = any(token in metric for token in ("elapsed", "latency"))
    higher_is_better = any(token in metric for token in ("throughput", "docs_per_sec"))

    if lower_is_better:
        if percent_change < 0:
            return f"{abs(percent_change):.1f}% faster"
        return f"{percent_change:.1f}% slower"

    if higher_is_better:
        if percent_change > 0:
            return f"{percent_change:.1f}% faster"
        return f"{abs(percent_change):.1f}% slower"

    direction = "higher" if percent_change > 0 else "lower"
    return f"{abs(percent_change):.1f}% {direction}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark RexLit using IDL fixture corpora.")
    parser.add_argument("--corpus", required=True, help="IDL corpus tier (small, medium, large, xl).")
    parser.add_argument("--workers", type=int, default=4, help="Number of indexing workers.")
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Optional JSON file containing baseline metrics for comparison.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write benchmark results (defaults to benchmark-results-<corpus>-<ts>.json).",
    )
    args = parser.parse_args()

    results = run_benchmarks(args.corpus, args.workers, args.baseline)

    output_path = args.output
    if not output_path:
        timestamp = int(results["timestamp"])
        output_path = Path(f"benchmark-results-{args.corpus}-{timestamp}.json")

    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":  # pragma: no cover
    main()

