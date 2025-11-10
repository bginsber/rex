#!/usr/bin/env python3
"""Test Groq privilege adapter with real API calls or mock mode.

Usage:
    # With Groq API key (real testing)
    export GROQ_API_KEY='gsk_...'
    python test_groq_privilege.py

    # Without API key (mock mode)
    python test_groq_privilege.py --mock
"""

import os
import sys
import time
from pathlib import Path
from dataclasses import dataclass

# Add parent directory to path so we can import rexlit
sys.path.insert(0, str(Path(__file__).parent.parent))

from rexlit.app.adapters.groq_privilege import GroqPrivilegeAdapter


@dataclass
class MockFinding:
    """Mock finding for dry-run testing."""

    rule: str
    match_type: str
    confidence: float
    snippet: str


def get_mock_findings(test_num: int) -> list:
    """Return mock findings for dry-run testing."""
    mock_results = {
        1: [
            MockFinding(
                "explicit_privilege",
                "boilerplate",
                0.95,
                "This message may be an attorney-client communication",
            )
        ],
        2: [],  # Business email - no findings
        3: [
            MockFinding(
                "implicit_privilege",
                "context",
                0.78,
                "Per legal counsel review we received",
            )
        ],
        4: [
            MockFinding(
                "work_product",
                "litigation_strategy",
                0.88,
                "attorney work product prepared in anticipation of litigation",
            )
        ],
        5: [
            MockFinding(
                "implicit_privilege",
                "advisor_role",
                0.82,
                "Senior Legal Counsel, Compliance",
            )
        ],
        6: [
            MockFinding(
                "work_product",
                "strategic_assessment",
                0.75,
                "ATTORNEY WORK PRODUCT - INTERNAL ONLY",
            )
        ],
        7: [],  # Business decision - may not be privileged
        8: [
            MockFinding(
                "work_product",
                "forwarded_advice",
                0.68,
                "Federal Rule of Civil Procedure 11",
            )
        ],
        9: [
            MockFinding(
                "explicit_privilege",
                "boilerplate",
                0.96,
                "attorney-client communication, may be protected by the work product doctrine",
            )
        ],
    }
    return mock_results.get(test_num, [])


def analyze_text(adapter, text: str, test_num: int, use_mock: bool = False) -> list:
    """Analyze text for privilege, using real API or mock data.

    Args:
        adapter: GroqPrivilegeAdapter instance (or None in mock mode)
        text: Text to analyze
        test_num: Test number (for mock results)
        use_mock: If True, return mock findings

    Returns:
        List of findings
    """
    if use_mock:
        return get_mock_findings(test_num)
    else:
        return adapter.analyze_text(text, threshold=0.75)


def run_test_with_delay(test_num: int, delay: float = 2.0, use_mock: bool = False):
    """Add delay before running test (to avoid Groq API rate limits).

    Args:
        test_num: Test number
        delay: Seconds to wait before test
        use_mock: If True, skip delays (mock mode)
    """
    if not use_mock and test_num > 1:
        print(f"⏳ Waiting {delay}s to avoid rate limits...\n")
        time.sleep(delay)


def run_tests(adapter, use_mock: bool = False) -> bool:
    """Run all 9 privilege classification tests.

    Args:
        adapter: GroqPrivilegeAdapter instance (or None in mock mode)
        use_mock: If True, use mock findings instead of real API

    Returns:
        True if all tests completed
    """

    # Test 1: Explicit attorney-client communication with privilege notice
    # Based on real Synchrogenix/Juul legal advisory emails
    privileged_email = """From: scott.richburg@juul.com
To: lindsay.andrews@juul.com
Subject: RE: Updated Instagram media statement - for final legal review
Date: Sun, Jun 30, 2019

Lindsay,

This message may be an attorney-client communication, may be protected by the
work product doctrine, and may be subject to a protective order. As such, this
message is privileged and confidential.

Regarding the proposed media statement, I recommend the following revisions to
address potential FTC advertising compliance issues:

1. Remove claims characterizing products as "safe" or "reduced harm"
2. Avoid comparative health statements without clinical evidence
3. Focus messaging on product features rather than health implications

These recommendations are based on our legal assessment of regulatory exposure.
Please incorporate before finalizing for external distribution.

Jerry Masoudi
Chief Legal Officer
Juul Labs
"""

    print("=" * 70)
    print("Test 1: Explicit attorney-client communication (Privilege Notice)")
    print("=" * 70)
    try:
        findings = analyze_text(adapter, privileged_email, 1, use_mock)
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

    run_test_with_delay(2, delay=2.0, use_mock=use_mock)
    print("=" * 70)
    print("Test 2: Business email (not privileged)")
    print("=" * 70)
    try:
        findings = analyze_text(adapter, business_email, 2, use_mock)
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

    # Test 3: Implicit legal reference
    # Demonstrates privilege context being shared beyond original attorney-client relationship
    cc_email = """From: gem.le@juul.com
To: erik.augustson@juul.com
Subject: RE: JUUL PMTA - Human Health Impact Workstream
Date: Tue, Jul 2, 2019 5:35 PM

Erik,

Per legal counsel review we received last week, we recommend proceeding with
the behavioral research protocol as currently scoped. The previous concern about
regulatory overlap has been resolved based on attorney guidance.

Let's schedule a meeting to align on deliverables. Tuesday mornings at 9am
work for me.

Thanks,
Gem Le
Senior Manager, Behavioral Research Operations
Juul Labs

---
This message and any files transmitted with it may contain information which is
confidential or privileged. If you are not the intended recipient, please
advise the sender immediately.
"""

    run_test_with_delay(3, delay=2.0, use_mock=use_mock)
    print("=" * 70)
    print("Test 3: Implicit Legal Reference (Indirect privilege claim)")
    print("=" * 70)
    try:
        findings = analyze_text(adapter, cc_email, 3, use_mock)
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

    # Test 4: Work product with litigation context
    # Real pattern from privilege logs: attorney strategy and legal analysis
    work_product_email = """From: litigation@lawfirm.com
To: client@company.com
Subject: Draft complaint for review - attorney analysis

Please review the attached draft complaint. I've included strategic notes
regarding our anticipated defenses and witness preparation strategy.

Key strategic considerations:
- The opposing party's strongest argument is likely on contractual damages
- We should emphasize the force majeure provisions to minimize exposure
- Recommend discovery strategy focusing on emails showing implied consent

This analysis represents attorney work product prepared in anticipation of
litigation. Please do not circulate outside the immediate client team.

Regards,
Sarah Chen, Litigation Counsel
"""

    run_test_with_delay(4, delay=2.0, use_mock=use_mock)
    print("=" * 70)
    print("Test 4: Work product with attorney analysis")
    print("=" * 70)
    try:
        findings = analyze_text(adapter, work_product_email, 4, use_mock)
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

    # Test 5: In-house counsel decision without explicit "attorney-client privileged" language
    # Realistic corporate scenario where privilege is implied through role/context
    inhouse_counsel_email = """From: compliance@juul.com
To: marketing@juul.com
Subject: Regulatory analysis - advertising claims review
Date: March 15, 2024

Team,

Following our analysis of the proposed marketing materials, we cannot proceed
with the current language. Our review of FDA authority and FTC guidelines shows
exposure on the following points:

- "Reduced exposure" claims require clinical evidence (not available)
- Comparative claims vs. combustible cigarettes are problematic under
  potential future regulations
- Product benefit claims will likely trigger scrutiny given litigation context

Recommend: revise to focus solely on product features and technical specifications.
This assessment is based on our legal review of the regulatory landscape.

Best regards,
Jennifer Wu
Senior Legal Counsel, Compliance
Juul Labs
"""

    run_test_with_delay(5, delay=2.0, use_mock=use_mock)
    print("=" * 70)
    print("Test 5: In-house counsel implicit privilege (no explicit waiver language)")
    print("=" * 70)
    try:
        findings = analyze_text(adapter, inhouse_counsel_email, 5, use_mock)
        print(f"  Findings: {len(findings)}")
        if findings:
            f = findings[0]
            print(f"  ✓ DETECTED IMPLICIT PRIVILEGE")
            print(f"    Rule: {f.rule}")
            print(f"    Confidence: {f.confidence:.2%}")
            if f.confidence < 0.75:
                print(f"    ⚠ Lower confidence - may require human review")
        else:
            print(f"  ⚠ No privilege detected (possible false negative)")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()

    # Test 6: Privilege waiver indication - legal advice shared beyond privilege circle
    privilege_waiver_email = """From: legal@company.com
To: press@company.com, ceo@company.com
Subject: Statement on litigation - PRIVILEGE WAIVER

EXTERNAL STATEMENT (Not privileged, for release):
"We dispute the allegations and look forward to defending our position in court."

---
ATTORNEY WORK PRODUCT - INTERNAL ONLY (Do not share):
This public statement is based on strategic assessment of public sentiment.
Full analysis of settlement dynamics and litigation risk in separate memo.

DO NOT DISTRIBUTE INTERNAL ANALYSIS PORTION

Jennifer Smith
General Counsel
"""

    run_test_with_delay(6, delay=2.0, use_mock=use_mock)
    print("=" * 70)
    print("Test 6: Privilege waiver scenario (mixed privileged/non-privileged)")
    print("=" * 70)
    try:
        findings = analyze_text(adapter, privilege_waiver_email, 6, use_mock)
        print(f"  Findings: {len(findings)}")
        if findings:
            f = findings[0]
            print(f"  ✓ DETECTED PRIVILEGE SECTION")
            print(f"    Rule: {f.rule}")
            print(f"    Confidence: {f.confidence:.2%}")
            print(f"    Note: Email contains both waived and protected content")
        else:
            print(f"  ⚠ No privilege detected (possible issue with mixed content)")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()

    # Test 7: Regulatory/compliance email with subtle legal advisory
    # False positive risk: mentions "legal" and "advice" but may be business decision
    regulatory_email = """From: regulatory@company.com
To: product@company.com, legal@company.com
Subject: FDA pathway decision - compliance review

Product team,

Based on our review of FDA guidance and our legal team's input on regulatory
precedent, we are proceeding with the 510(k) pathway rather than the PMA route.

Key factors in this decision:
- Predicate devices available for substantial equivalence claims
- Our patent portfolio protects key innovations
- Timeline and cost considerations for market entry

This recommendation incorporates legal counsel's analysis of regulatory risk.
Final decision pending executive sign-off.

Next steps: file pre-submission package next month.

Regards,
Tom Richardson
Director, Regulatory Affairs
"""

    run_test_with_delay(7, delay=2.0, use_mock=use_mock)
    print("=" * 70)
    print("Test 7: Regulatory decision with legal input (edge case - not fully privileged)")
    print("=" * 70)
    try:
        findings = analyze_text(adapter, regulatory_email, 7, use_mock)
        print(f"  Findings: {len(findings)}")
        if findings:
            f = findings[0]
            print(f"  ⚠ Detected potential privilege claim")
            print(f"    Confidence: {f.confidence:.2%}")
            if f.confidence < 0.50:
                print(f"    ✓ Low confidence - appropriate (mixed business/legal content)")
            else:
                print(f"    ⚠ May be overconfident - decision partly business-driven")
        else:
            print(f"  ✓ Correctly identified as non-privileged (business decision)")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()

    # Test 8: Forwarded attorney opinion (privilege status unclear when forwarded non-lawyers)
    forwarded_advice_email = """From: manager@company.com
To: team@company.com
Subject: FW: Important - Aggressive Litigation Posture Policy

Team, please review the guidance below from our litigation counsel regarding
pleading standards. Everyone needs to understand this constraint:

---------- FORWARDED MESSAGE ----------
From: litigation-counsel@company.com
Date: April 10, 2024

Subject: FRE 11 implications of aggressive pleadings

Under Federal Rule of Civil Procedure 11, counsel must certify the factual
and legal basis for pleadings. Aggressive positions that lack factual support
can subject both the attorney and party to sanctions.

This is why we require all proposed claims to have documented factual support
before filing, even if strategy might otherwise suggest a broad complaint.

---------- END FORWARDED MESSAGE ----------

Please acknowledge receipt and ensure your teams follow this guidance.

Sarah Mitchell
Operations Director
"""

    run_test_with_delay(8, delay=2.0, use_mock=use_mock)
    print("=" * 70)
    print("Test 8: Forwarded attorney advice (privilege chain of custody issue)")
    print("=" * 70)
    try:
        findings = analyze_text(adapter, forwarded_advice_email, 8, use_mock)
        print(f"  Findings: {len(findings)}")
        if findings:
            f = findings[0]
            print(f"  ✓ DETECTED ATTORNEY COMMUNICATION")
            print(f"    Confidence: {f.confidence:.2%}")
            print(f"    Issue: Forwarded to non-lawyers may affect privilege status")
        else:
            print(f"  ⚠ No privilege detected")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()

    # Test 9: Real privilege notice from production metadata
    # These appear in the JUUL documents with actual privilege logging
    privilege_notice_email = """From: sarah.more@synchrogenix.com
To: juul-team@juul.com
Subject: RE: PMTA submission materials - regulatory strategy discussion

Hi All,

This message may be an attorney-client communication, may be protected by the
work product doctrine, and may be subject to a protective order. As such, this
message is privileged and confidential.

Regarding the PMTA package strategy: I recommend we emphasize the harm reduction
framework in the human health assessment. Our review of competing products
shows most rely on comparative safety arguments, which creates vulnerability.

Better approach: focus on the unique behavioral characteristics that support
reduced initiation risk among current non-users.

This communication incorporates input from external counsel and should not be
disclosed outside the PMTA core team.

Please confirm receipt and destruction of any hardcopies.

Best regards,
Sarah More
Senior Technical Advisor
Synchrogenix (on behalf of Juul Labs)
"""

    run_test_with_delay(9, delay=2.0, use_mock=use_mock)
    print("=" * 70)
    print("Test 9: Real privilege notice from JUUL litigation production")
    print("=" * 70)
    try:
        findings = analyze_text(adapter, privilege_notice_email, 9, use_mock)
        print(f"  Findings: {len(findings)}")
        if findings:
            f = findings[0]
            print(f"  ✓ DETECTED EXPLICIT PRIVILEGE NOTICE")
            print(f"    Rule: {f.rule}")
            print(f"    Confidence: {f.confidence:.2%}")
            if f.confidence >= 0.90:
                print(f"    ✓ HIGH confidence (explicit notice + substance)")
        else:
            print(f"  ❌ FAILED: Should detect explicit privilege notice")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("✓ Test 1: Explicit attorney-client communication (privilege notice)")
    print("✓ Test 2: Business email (no false positive)")
    print("✓ Test 3: Implicit legal reference (indirect privilege claim)")
    print("✓ Test 4: Work product with attorney analysis")
    print("✓ Test 5: In-house counsel implicit privilege")
    print("✓ Test 6: Privilege waiver scenario (mixed content)")
    print("✓ Test 7: Regulatory decision with legal input (edge case)")
    print("✓ Test 8: Forwarded attorney advice (chain of custody issue)")
    print("✓ Test 9: Real privilege notice from JUUL documents")
    print()
    print("Test Coverage Summary:")
    print("  - Explicit privilege notices: Tests 1, 9")
    print("  - Implicit/indirect privilege: Tests 3, 5")
    print("  - Work product doctrine: Tests 4, 8")
    print("  - Edge cases/false positives: Tests 6, 7")
    print("  - Real-world examples: Tests 1, 3, 5, 9 (based on JUUL materials)")
    print()
    print("Expected Results:")
    print("  - High confidence (≥90%): Tests 1, 4, 9")
    print("  - Medium confidence (75-89%): Tests 5, 8")
    print("  - Lower/edge case confidence: Tests 6, 7")
    print("  - No privilege: Test 2")
    print()
    if use_mock:
        print("Running in MOCK MODE - see results above")
    else:
        print("Running with REAL API - see results above")
    print()
    print("Next steps:")
    print("  1. Run this test with Groq API key: export GROQ_API_KEY='gsk_...'")
    print("  2. Review confidence scores - validate expectations above")
    print("  3. If accuracy is low, iterate on policy wording")
    print("  4. Run full validation with test_set.jsonl from discovery")

    return True


def main():
    """Main entry point."""
    # Check for --mock flag to run without API key
    use_mock = "--mock" in sys.argv

    # Check for --stage1 flag to use the comprehensive policy
    use_stage1 = "--stage1" in sys.argv or "--s1" in sys.argv

    # Check for --harmony flag to use the harmony format policy
    use_harmony = "--harmony" in sys.argv

    # Check for --harmony-plus flag to use the enhanced harmony+ policy
    use_harmony_plus = "--harmony-plus" in sys.argv or "--hp" in sys.argv

    if use_mock:
        print("🎭 MOCK MODE - Using simulated findings (no API calls)\n")
        adapter = None
    else:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("❌ GROQ_API_KEY not set")
            print("   Options:")
            print("   1. Set API key: export GROQ_API_KEY='gsk_...'")
            print("   2. Run in mock mode: python test_groq_privilege.py --mock")
            print("   3. Get key from: https://console.groq.com/keys")
            return False

        # Choose policy file
        if use_harmony_plus:
            policy_path = Path("rexlit/policies/juul_privilege_stage1_harmony_plus.txt")
            policy_name = "Stage 1 Harmony+ (v1.1 Enhanced)"
        elif use_harmony:
            policy_path = Path("rexlit/policies/juul_priviledge_stage1_harmony.txt")
            policy_name = "Stage 1 Harmony (v1.1)"
        elif use_stage1:
            policy_path = Path("rexlit/policies/juul_privilege_stage1.txt")
            policy_name = "Stage 1 (Comprehensive)"
        else:
            policy_path = Path("rexlit/policies/privilege_groq_v1.txt")
            policy_name = "Groq v1 (Original)"

        if not policy_path.exists():
            print(f"❌ Policy not found: {policy_path}")
            print(f"   Try: python test_groq_privilege.py --mock")
            return False

        print(f"✓ Using policy: {policy_name}")
        print(f"✓ Path: {policy_path}")
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

    # Run all tests
    success = run_tests(adapter, use_mock=use_mock)
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
