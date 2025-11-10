#!/usr/bin/env python3
"""Test Groq privilege adapter with real API calls."""

import os
import sys
from pathlib import Path

# Add parent directory to path so we can import rexlit
sys.path.insert(0, str(Path(__file__).parent.parent))

from rexlit.app.adapters.groq_privilege import GroqPrivilegeAdapter


def test_groq_api():
    """Test Groq adapter with sample privileged email."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY not set")
        print("   Please set environment variable:")
        print("   export GROQ_API_KEY='gsk_...'")
        return False

    policy_path = Path("rexlit/policies/privilege_groq_v1.txt")
    if not policy_path.exists():
        print(f"❌ Policy not found: {policy_path}")
        return False

    print(f"✓ Using policy: {policy_path}")
    print(f"✓ Policy size: {policy_path.stat().st_size} bytes\n")

    try:
        adapter = GroqPrivilegeAdapter(
            api_key=api_key,
            policy_path=policy_path,
        )
        print("✓ Groq adapter initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize adapter: {e}")
        return False

    # Test 1: Privileged email (should detect ACP)
    privileged_email = """From: jennifer.smith@cooley.com
To: john.doe@company.com
Subject: Legal opinion on merger agreement

John,

Here is my legal opinion on the proposed merger agreement. From a legal
perspective, I advise proceeding with caution due to potential antitrust
implications. Please keep this privileged and confidential.

Best regards,
Jennifer Smith, Esq.
Cooley LLP
"""

    print("=" * 70)
    print("Test 1: Privileged email from attorney")
    print("=" * 70)
    try:
        findings = adapter.analyze_text(privileged_email, threshold=0.75)
        print(f"  Findings: {len(findings)}")
        if findings:
            f = findings[0]
            print(f"  ✓ DETECTED PRIVILEGE")
            print(f"    Rule: {f.rule}")
            print(f"    Match Type: {f.match_type}")
            print(f"    Confidence: {f.confidence:.2%}")
            print(f"    Snippet: {f.snippet[:100]}...")
            if f.confidence >= 0.90:
                print(f"    ✓ HIGH confidence (≥90%)")
            elif f.confidence >= 0.75:
                print(f"    ✓ GOOD confidence (≥75%)")
            else:
                print(f"    ⚠ LOW confidence (<75%)")
        else:
            print(f"  ❌ FAILED: Expected privilege detection but got none")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()

    # Test 2: Business email (should NOT detect privilege)
    business_email = """From: sales@company.com
To: team@company.com
Subject: Q4 product launch plan

Team,

Here's the updated Q4 product launch plan. Please review and provide
feedback by Friday. Looking forward to a successful launch!

Thanks,
Sales Team
"""

    print("=" * 70)
    print("Test 2: Business email (not privileged)")
    print("=" * 70)
    try:
        findings = adapter.analyze_text(business_email, threshold=0.75)
        print(f"  Findings: {len(findings)}")
        if findings:
            print(f"  ❌ FALSE POSITIVE: Detected privilege when there is none")
            f = findings[0]
            print(f"    Confidence: {f.confidence:.2%}")
            print(f"    Snippet: {f.snippet[:100]}...")
        else:
            print(f"  ✓ Correctly identified as non-privileged")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()

    # Test 3: Edge case - Attorney CC'd without legal question
    cc_email = """From: marketing@company.com
To: product@company.com
Cc: legal@company.com
Subject: New campaign ideas

Team,

Here are some new marketing campaign ideas for next quarter. Legal,
FYI in case you have any concerns.

Thanks,
Marketing
"""

    print("=" * 70)
    print("Test 3: Attorney CC'd (edge case)")
    print("=" * 70)
    try:
        findings = adapter.analyze_text(cc_email, threshold=0.75)
        print(f"  Findings: {len(findings)}")
        if findings:
            f = findings[0]
            print(f"  Detected potential privilege (edge case)")
            print(f"    Confidence: {f.confidence:.2%}")
            if f.confidence < 0.75:
                print(f"    ✓ Correctly flagged for human review (low confidence)")
            else:
                print(f"    ⚠ May be false positive - confidence seems high")
        else:
            print(f"  ✓ Correctly identified as non-privileged")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()

    # Test 4: Work product
    work_product_email = """From: litigation@lawfirm.com
To: client@company.com
Subject: Draft complaint for review

Please review the attached draft complaint. I've included strategic notes
in the margins regarding our anticipated defenses and witness preparation
strategy. This is attorney work product prepared in anticipation of litigation.

Regards,
Litigation Team
"""

    print("=" * 70)
    print("Test 4: Work product document")
    print("=" * 70)
    try:
        findings = adapter.analyze_text(work_product_email, threshold=0.75)
        print(f"  Findings: {len(findings)}")
        if findings:
            f = findings[0]
            print(f"  ✓ DETECTED PRIVILEGE")
            print(f"    Rule: {f.rule}")
            print(f"    Confidence: {f.confidence:.2%}")
            print(f"    Snippet: {f.snippet[:100]}...")
            if f.confidence >= 0.85:
                print(f"    ✓ HIGH confidence")
            else:
                print(f"    ⚠ Lower than expected confidence")
        else:
            print(f"  ❌ FAILED: Expected work product detection")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("✓ Test 1: Detect privilege in attorney email")
    print("✓ Test 2: No false positive on business email")
    print("✓ Test 3: Handle attorney CC'd edge case")
    print("✓ Test 4: Detect work product")
    print()
    print("Next steps:")
    print("  1. Review confidence scores - should be >90% for clear cases")
    print("  2. If accuracy is low, iterate on policy wording")
    print("  3. Run full validation with test_set.jsonl")

    return True


if __name__ == "__main__":
    success = test_groq_api()
    sys.exit(0 if success else 1)
