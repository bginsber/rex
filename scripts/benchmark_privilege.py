#!/usr/bin/env python3
"""Benchmark privilege detection performance: Groq API.

This script measures the latency and throughput of the Groq privilege
adapter to validate the ~1000 tps claim and measure real-world performance.

Usage:
    python scripts/benchmark_privilege.py [--iterations 10]

Requirements:
    - GROQ_API_KEY must be set
    - REXLIT_ONLINE=1 must be set
"""

import os
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rexlit.app.adapters.groq_privilege import GroqPrivilegeAdapter


def benchmark_groq(sample_text: str, iterations: int = 10) -> dict:
    """Benchmark Groq API adapter."""
    # Check for API key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        try:
            from rexlit.config import Settings
            settings = Settings()
            api_key = settings.get_groq_api_key()
        except:
            pass

    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")

    policy_path = Path("rexlit/policies/privilege_groq_v1.txt")
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy not found: {policy_path}")

    print(f"Initializing Groq adapter...")
    adapter = GroqPrivilegeAdapter(api_key=api_key, policy_path=policy_path)

    print(f"Running {iterations} iterations...")
    print("=" * 70)

    latencies = []
    for i in range(iterations):
        start = time.time()
        findings = adapter.analyze_text(sample_text, threshold=0.75)
        latency = time.time() - start
        latencies.append(latency)

        detected = "PRIVILEGE" if findings else "NON-PRIV"
        confidence = findings[0].confidence if findings else 0.0
        print(f"  Iteration {i+1:2d}/{iterations}: {latency:6.3f}s - {detected} (conf={confidence:.2%})")

    return {
        "backend": "Groq API",
        "mean_latency": sum(latencies) / len(latencies),
        "min_latency": min(latencies),
        "max_latency": max(latencies),
        "median_latency": sorted(latencies)[len(latencies) // 2],
        "throughput_docs_per_sec": 1.0 / (sum(latencies) / len(latencies)),
        "total_time": sum(latencies),
        "iterations": iterations,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark Groq privilege detection")
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations to run (default: 10)",
    )
    args = parser.parse_args()

    # Sample text (privileged email)
    sample_text = """From: attorney@cooley.com
To: client@company.com
Subject: Legal opinion on merger agreement

Here is my legal opinion on the proposed merger agreement. From a legal
perspective, I advise proceeding with caution due to potential antitrust
implications. This communication is attorney-client privileged and confidential.

Please review and provide feedback by end of week.

Best regards,
Jennifer Smith, Esq.
Cooley LLP
"""

    print("=" * 70)
    print("GROQ API PRIVILEGE DETECTION BENCHMARK")
    print("=" * 70)
    print()
    print(f"Sample text: {len(sample_text)} characters")
    print(f"Iterations: {args.iterations}")
    print()

    try:
        groq_results = benchmark_groq(sample_text, iterations=args.iterations)
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Backend:        {groq_results['backend']}")
    print(f"Iterations:     {groq_results['iterations']}")
    print(f"Total time:     {groq_results['total_time']:.2f}s")
    print()
    print(f"Mean latency:   {groq_results['mean_latency']:.3f}s")
    print(f"Median latency: {groq_results['median_latency']:.3f}s")
    print(f"Min latency:    {groq_results['min_latency']:.3f}s")
    print(f"Max latency:    {groq_results['max_latency']:.3f}s")
    print()
    print(f"Throughput:     {groq_results['throughput_docs_per_sec']:.2f} docs/sec")
    print()

    # Assessment
    print("=" * 70)
    print("ASSESSMENT")
    print("=" * 70)

    mean_latency = groq_results['mean_latency']
    throughput = groq_results['throughput_docs_per_sec']

    if mean_latency < 2.0:
        print(f"✓ EXCELLENT: Mean latency {mean_latency:.2f}s < 2.0s target")
    elif mean_latency < 3.0:
        print(f"⚠ GOOD: Mean latency {mean_latency:.2f}s < 3.0s (acceptable)")
    else:
        print(f"❌ SLOW: Mean latency {mean_latency:.2f}s > 3.0s (investigate)")

    if throughput > 0.5:
        print(f"✓ HIGH THROUGHPUT: {throughput:.2f} docs/sec > 0.5 target")
    elif throughput > 0.3:
        print(f"⚠ MODERATE THROUGHPUT: {throughput:.2f} docs/sec (acceptable)")
    else:
        print(f"❌ LOW THROUGHPUT: {throughput:.2f} docs/sec < 0.3 (investigate)")

    print()
    print("Comparison to self-hosted:")
    print(f"  Self-hosted (estimated): 10-30s per doc (~0.03-0.1 docs/sec)")
    print(f"  Groq speedup: ~{(15.0 / mean_latency):.0f}x faster")
    print()

    print("Note: Groq's ~1000 tps claim refers to token throughput,")
    print("      not document throughput. This benchmark measures end-to-end")
    print("      document classification latency.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
