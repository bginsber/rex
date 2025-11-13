# RexLit Benchmarking Guide

This guide explains how to run RexLit's performance benchmarks against the optional UCSF IDL fixture corpora that are generated via `scripts/setup-idl-fixtures.sh`.

## Prerequisites

- Install the dev-only extras (requires PyTorch + Chug):  
  `pip install -e '.[dev-idl]'`
- Generate the desired corpora (small/medium/large/xl) with the setup script:  
  `scripts/setup-idl-fixtures.sh`  
  (set `IDL_SETUP_TIERS=medium` to target a specific tier)
- Ensure the fixture root is available locally (`rexlit/docs/idl-fixtures` by default, override with `IDL_FIXTURE_PATH`).

## Running Benchmarks

```bash
# Benchmark discovery, indexing, and search on the medium corpus
python scripts/benchmark_idl.py \
  --corpus medium \
  --workers 6 \
  --output benchmarks/medium-latest.json
```

The output JSON includes:

- A timestamped record of all benchmark metrics.
- Environment metadata (RexLit version, Python version, platform, CPU count).
- Detailed throughput/latency statistics for discovery, indexing, and search.

## Comparing to a Baseline

Capture a known-good baseline (for example, from main) and store it alongside your benchmark runs:

```bash
# Compare current results to a saved baseline
python scripts/benchmark_idl.py \
  --corpus medium \
  --workers 6 \
  --baseline benchmarks/medium-baseline.json \
  --output benchmarks/medium-comparison.json
```

The `baseline_comparison` section of the results annotates each metric with human-readable deltas (e.g., `"+12.4% slower"` or `"5.6% faster"`).

## Tips

- Use the same number of workers for comparable runs (the default is 4).
- CI workflows can store baselines (e.g., in `benchmarks/baselines/`) to detect regressions automatically.
- Large corpora (10k / 100k docs) require significant disk and compute resources; consider running them on dedicated hardware.

