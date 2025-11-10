#!/usr/bin/env python3
"""Validate privilege policy effectiveness against test set.

This script runs the Groq privilege adapter against a curated test set
of 25 examples and computes accuracy, precision, recall, and F1 score.

Usage:
    python scripts/validate_privilege_policy.py

Requirements:
    - GROQ_API_KEY must be set (or stored via setup_groq_key.py)
    - REXLIT_ONLINE=1 must be set
    - Test set: tests/fixtures/privilege_test_set.jsonl
"""

import json
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rexlit.app.adapters.groq_privilege import GroqPrivilegeAdapter


def load_test_set(path: Path) -> list[dict]:
    """Load test set from JSONL file."""
    test_cases = []
    with open(path) as f:
        for line in f:
            test_cases.append(json.loads(line))
    return test_cases


def validate_policy(adapter: GroqPrivilegeAdapter, test_set: list[dict], threshold: float = 0.75) -> dict:
    """Run test set through adapter and compute metrics."""
    results = {
        "true_positives": 0,  # Correctly detected privilege
        "true_negatives": 0,  # Correctly detected non-privilege
        "false_positives": 0,  # Incorrectly detected privilege
        "false_negatives": 0,  # Missed privilege
        "total": len(test_set),
        "errors": [],
        "details": [],
    }

    print(f"\nRunning validation on {len(test_set)} test cases (threshold={threshold})...")
    print("=" * 70)

    for i, case in enumerate(test_set, 1):
        case_id = case["id"]
        print(f"[{i}/{len(test_set)}] {case_id}: ", end="", flush=True)

        try:
            findings = adapter.analyze_text(case["text"], threshold=threshold)
            detected_privileged = len(findings) > 0
            expected_privileged = case["expected_privileged"]

            confidence = findings[0].confidence if findings else 0.0

            if detected_privileged and expected_privileged:
                results["true_positives"] += 1
                print(f"✓ TP (conf={confidence:.2%})")
            elif not detected_privileged and not expected_privileged:
                results["true_negatives"] += 1
                print(f"✓ TN")
            elif detected_privileged and not expected_privileged:
                results["false_positives"] += 1
                print(f"❌ FP (conf={confidence:.2%}) - {case['notes']}")
                results["errors"].append({
                    "type": "false_positive",
                    "id": case_id,
                    "confidence": confidence,
                    "notes": case["notes"],
                })
            else:  # missed privilege
                results["false_negatives"] += 1
                print(f"❌ FN - {case['notes']}")
                results["errors"].append({
                    "type": "false_negative",
                    "id": case_id,
                    "notes": case["notes"],
                })

            results["details"].append({
                "id": case_id,
                "expected": expected_privileged,
                "detected": detected_privileged,
                "confidence": confidence,
                "correct": (detected_privileged == expected_privileged),
            })

        except Exception as e:
            print(f"❌ ERROR: {str(e)[:50]}")
            results["errors"].append({
                "type": "exception",
                "id": case_id,
                "error": str(e),
            })

    # Compute metrics
    tp = results["true_positives"]
    tn = results["true_negatives"]
    fp = results["false_positives"]
    fn = results["false_negatives"]

    results["accuracy"] = (tp + tn) / results["total"] if results["total"] > 0 else 0
    results["precision"] = tp / (tp + fp) if (tp + fp) > 0 else 0
    results["recall"] = tp / (tp + fn) if (tp + fn) > 0 else 0
    results["f1"] = (
        2 * results["precision"] * results["recall"] / (results["precision"] + results["recall"])
        if (results["precision"] + results["recall"]) > 0
        else 0
    )

    return results


def print_results(results: dict):
    """Print formatted results."""
    print("\n" + "=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)
    print(f"Accuracy:  {results['accuracy']:.1%} ({results['true_positives'] + results['true_negatives']}/{results['total']} correct)")
    print(f"Precision: {results['precision']:.1%} (of detected privilege, how many were correct)")
    print(f"Recall:    {results['recall']:.1%} (of actual privilege, how many were detected)")
    print(f"F1 Score:  {results['f1']:.1%} (harmonic mean of precision and recall)")
    print()
    print(f"True Positives:  {results['true_positives']} (correctly detected privilege)")
    print(f"True Negatives:  {results['true_negatives']} (correctly detected non-privilege)")
    print(f"False Positives: {results['false_positives']} (incorrectly detected privilege)")
    print(f"False Negatives: {results['false_negatives']} (missed privilege)")
    print()

    # Print error details
    if results["errors"]:
        print("=" * 70)
        print("ERRORS & MISCLASSIFICATIONS")
        print("=" * 70)
        for error in results["errors"]:
            if error["type"] == "false_positive":
                print(f"FALSE POSITIVE: {error['id']} (conf={error.get('confidence', 0):.2%})")
                print(f"  {error['notes']}")
            elif error["type"] == "false_negative":
                print(f"FALSE NEGATIVE: {error['id']}")
                print(f"  {error['notes']}")
            elif error["type"] == "exception":
                print(f"EXCEPTION: {error['id']}")
                print(f"  {error['error']}")
            print()

    # Assessment
    print("=" * 70)
    print("ASSESSMENT")
    print("=" * 70)

    if results["accuracy"] >= 0.90:
        print("✓ EXCELLENT: Accuracy ≥90% - Ready for production")
    elif results["accuracy"] >= 0.80:
        print("⚠ GOOD: Accuracy ≥80% - Consider policy refinements")
    else:
        print("❌ NEEDS IMPROVEMENT: Accuracy <80% - Policy iteration required")

    if results["false_positives"] > 0.10 * results["total"]:
        print("⚠ HIGH FALSE POSITIVE RATE (>10%) - Risk of inadvertent production")
    else:
        print("✓ Low false positive rate - Safe for production")

    if results["false_negatives"] > 0.10 * results["total"]:
        print("⚠ HIGH FALSE NEGATIVE RATE (>10%) - Risk of privilege disclosure")
    else:
        print("✓ Low false negative rate - Privilege protection adequate")

    print()


def main():
    # Check for API key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        # Try loading from settings
        try:
            from rexlit.config import Settings
            settings = Settings()
            api_key = settings.get_groq_api_key()
        except:
            pass

    if not api_key:
        print("❌ GROQ_API_KEY not set")
        print("   Run: python scripts/setup_groq_key.py")
        print("   Or set: export GROQ_API_KEY='gsk_...'")
        return 1

    # Check for online mode
    if not os.getenv("REXLIT_ONLINE"):
        print("❌ REXLIT_ONLINE not set")
        print("   Run: export REXLIT_ONLINE=1")
        return 1

    policy_path = Path("rexlit/policies/privilege_groq_v1.txt")
    if not policy_path.exists():
        print(f"❌ Policy not found: {policy_path}")
        return 1

    test_set_path = Path("tests/fixtures/privilege_test_set.jsonl")
    if not test_set_path.exists():
        print(f"❌ Test set not found: {test_set_path}")
        return 1

    # Initialize adapter
    print(f"Initializing Groq adapter...")
    print(f"  Policy: {policy_path}")
    print(f"  Model: openai/gpt-oss-safeguard-20b")

    try:
        adapter = GroqPrivilegeAdapter(api_key=api_key, policy_path=policy_path)
    except Exception as e:
        print(f"❌ Failed to initialize adapter: {e}")
        return 1

    # Load test set
    test_set = load_test_set(test_set_path)
    print(f"  Test set: {len(test_set)} cases")

    # Run validation
    results = validate_policy(adapter, test_set, threshold=0.75)

    # Print results
    print_results(results)

    # Save detailed results
    output_path = Path("validation_results.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Detailed results saved to: {output_path}")

    # Exit code based on accuracy
    return 0 if results["accuracy"] >= 0.90 else 1


if __name__ == "__main__":
    sys.exit(main())
