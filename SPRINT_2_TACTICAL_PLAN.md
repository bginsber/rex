# Sprint 2 Tactical Plan: Groq-Powered Privilege Detection

**Date:** November 9, 2025
**Duration:** 3-5 working days
**Owner:** Ready for implementation
**Branch:** `claude/rexlit-safeguard-integration-v2-011CUqa2pzmPDhWCZjbMqpEn`

## 🎯 Sprint Goal

Activate **Groq-hosted OpenAI gpt-oss-safeguard-20b** (~1000 tps) as a fast, production-ready option for attorney-client privilege detection alongside the existing self-hosted transformer backend. Enable rapid policy iteration with 400-600 word optimized templates.

## 🔍 Situation Analysis

### What We Have Now

**On `main` Branch (Already Merged):**
- ✅ `GroqPrivilegeAdapter` - API-based adapter using OpenAI client
- ✅ Groq API key configuration with encrypted storage
- ✅ Bootstrap auto-wiring when `GROQ_API_KEY` is set
- ✅ Offline gate integration (requires `--online` flag)

**On This Branch (Safeguard Integration):**
- ✅ `PrivilegeSafeguardAdapter` - Self-hosted transformers-based adapter
- ✅ `PrivilegeReasoningPort` interface
- ✅ `PrivilegeReviewService` - 3-stage orchestration
- ✅ Circuit breaker pattern for resilience
- ✅ Privacy-preserving CoT hashing
- ✅ Comprehensive 8,427-char policy template (`juul_privilege_stage1.txt`)

### The Integration Challenge

**Problem:** Two parallel privilege implementations exist:
1. **Self-hosted** (this branch): `PrivilegeReasoningPort` → `PrivilegeSafeguardAdapter` → transformers
2. **Groq** (main): `PrivilegePort` → `GroqPrivilegeAdapter` → OpenAI API

**Different Port Interfaces:**
- `PrivilegeReasoningPort` (this branch): Returns `PolicyDecision` with CoT reasoning
- `PrivilegePort` (main): Returns `List[PrivilegeFinding]` with text spans

**Solution:** Merge main into this branch, then choose the best integration strategy.

### What We Need (Sprint 2 Objectives)

1. **Merge main → safeguard branch** to bring in GroqPrivilegeAdapter
2. **Optimized 400-600 word Groq policy** (vs current 8,427 chars)
3. **Backend selection logic** - Use Groq when available, fall back to self-hosted
4. **Testing with real documents** - Validate accuracy with sample emails
5. **Policy effectiveness metrics** - Measure precision/recall on test set
6. **Performance comparison** - Groq API (fast) vs self-hosted (slow but private)

## 📋 Task Breakdown

### TASK 1: Merge Main Branch (30 minutes)

**Current State:**
- Safeguard branch diverged from main before GroqPrivilegeAdapter merge
- UI files deleted on this branch (not needed)

**Action Required:**

```bash
git checkout claude/rexlit-safeguard-integration-v2-011CUqa2pzmPDhWCZjbMqpEn
git merge origin/main

# Expected conflicts:
# - CLAUDE.md (keep both sections)
# - README.md (merge documentation)
# - pyproject.toml (merge dependencies)
```

**Merge Strategy:**
- Keep UI deletions on this branch (they're experimental)
- Merge GroqPrivilegeAdapter and related infrastructure
- Preserve safeguard-specific code (PrivilegeSafeguardAdapter, policies)
- Ensure both adapters coexist peacefully

**Acceptance:**
- ✅ Merge completes without breaking tests
- ✅ Both `GroqPrivilegeAdapter` and `PrivilegeSafeguardAdapter` exist
- ✅ Bootstrap can wire either adapter based on config
- ✅ All existing tests still pass

---

### TASK 2: Create 400-600 Word Groq-Optimized Policy (2-3 hours)

**Current State:**
- `juul_privilege_stage1.txt` is 8,427 characters ≈ 2,100 tokens
- Groq recommends 400-600 tokens for optimal performance
- Current policy includes Stage 1/2/3 content mixed together

**Action Required:**

**File:** `rexlit/policies/privilege_groq_v1.txt` (NEW)

**Strategy:**
1. Remove Stage 2 (responsiveness) and Stage 3 (redaction) content
2. Focus ONLY on privilege classification (ACP, WP, CI)
3. Condense examples from 10+ to 4 representative cases
4. Use Groq's recommended structure:
   - **Instructions** (clear task definition)
   - **Definitions** (ACP, WP, CI)
   - **Criteria** (privileged vs. not privileged)
   - **Examples** (4 cases with JSON outputs)

**Template Structure:**

```markdown
# ATTORNEY-CLIENT PRIVILEGE CLASSIFICATION

## INSTRUCTIONS
Classify whether the email/document qualifies for attorney-client privilege (ACP), work product (WP), or common interest (CI). Return JSON: {"violation": 0 or 1, "labels": [], "confidence": 0.0-1.0, "rationale": "..."}.

PRIVACY REQUIREMENT: Do NOT quote document text in rationale. Cite only policy sections.

## DEFINITIONS
- **ACP**: Confidential communications between attorney and client for legal advice.
  Requires: (1) attorney-client relationship, (2) confidential, (3) legal purpose.
- **WP**: Materials prepared by/for counsel in anticipation of litigation.
  Includes: attorney notes, legal research, litigation strategy.
- **CI**: ACP/WP shared among parties with common legal interest under formal agreement.

## CRITERIA

### PRIVILEGED (violation=1)
- Email from/to attorney domain (@lawfirm.com, in-house counsel @company.com)
- Explicit markers: "attorney-client privilege", "privileged and confidential", "work product"
- Legal advice language: "my legal opinion", "from legal perspective", "counsel advises"
- Litigation prep: draft pleadings, settlement strategy, deposition prep
- Attorney signature with "Esq." or bar number

### NOT PRIVILEGED (violation=0)
- Routine business communications without legal component
- Public information, marketing materials
- Attorney as business advisor (non-legal capacity)
- Broadly distributed emails (no confidentiality)
- Attorney merely CC'd without legal question

## EXAMPLES

Example 1 (Privileged ACP):
From: jsmith@cooley.com
To: client@company.com
Subject: Legal opinion on merger
Answer: {"violation": 1, "labels": ["PRIVILEGED:ACP"], "confidence": 0.95, "rationale": "Attorney domain + legal advice per ACP definition"}

Example 2 (Not Privileged):
From: sales@company.com
To: counsel@company.com (CC)
Subject: Product launch update
Answer: {"violation": 0, "labels": [], "confidence": 0.85, "rationale": "Business communication; counsel CC'd without legal question"}

Example 3 (Privileged WP):
From: attorney@law.com
To: client@company.com
Subject: Draft complaint for review
Answer: {"violation": 1, "labels": ["PRIVILEGED:WP"], "confidence": 0.92, "rationale": "Litigation preparation materials per WP definition"}

Example 4 (Uncertain - Needs Review):
From: legal@company.com
To: board@company.com
Subject: Q3 business strategy
Answer: {"violation": 0, "labels": [], "confidence": 0.55, "rationale": "Ambiguous; may be business advice not legal"}

## CONFIDENCE SCORING
- 0.90-1.00: Explicit markers + attorney domain + legal advice
- 0.75-0.89: Strong indicators (attorney + legal request)
- 0.50-0.74: Moderate indicators (legal terminology present)
- 0.25-0.49: Weak indicators (legal terms, no attorney)
- 0.00-0.24: No privilege indicators

Content to classify: {{USER_INPUT}}
Answer (JSON only):
```

**Word Count:** ~490 words (~410 tokens)

**Validation:**
```bash
# Count tokens using tiktoken
python -c "
import tiktoken
policy = open('rexlit/policies/privilege_groq_v1.txt').read()
enc = tiktoken.get_encoding('cl100k_base')
tokens = enc.encode(policy)
print(f'Tokens: {len(tokens)}')"
# Target: 400-600 tokens
```

**Acceptance:**
- ✅ Policy file is 400-600 words (≈ 350-550 tokens)
- ✅ Follows Groq's 4-section structure
- ✅ No document excerpts in rationale requirement
- ✅ JSON output format specified with examples
- ✅ 4 examples covering: privileged ACP, not privileged, privileged WP, uncertain

---

### TASK 3: Test Groq Adapter with Real API Calls (2-3 hours)

**Current State:**
- `GroqPrivilegeAdapter` exists but untested with actual API
- No sample documents for validation

**Action Required:**

**Setup:**
```bash
export GROQ_API_KEY="gsk_..."
export REXLIT_ONLINE=1
```

**Test Script:** `scripts/test_groq_privilege.py` (NEW)

```python
"""Test Groq privilege adapter with real API calls."""

import os
from pathlib import Path

from rexlit.app.adapters.groq_privilege import GroqPrivilegeAdapter


def test_groq_api():
    """Test Groq adapter with sample privileged email."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY not set")
        return

    policy_path = Path("rexlit/policies/privilege_groq_v1.txt")
    if not policy_path.exists():
        print(f"❌ Policy not found: {policy_path}")
        return

    adapter = GroqPrivilegeAdapter(
        api_key=api_key,
        policy_path=policy_path,
    )

    # Test 1: Privileged email (should detect ACP)
    privileged_email = """
From: jennifer.smith@cooley.com
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

    print("Test 1: Privileged email")
    findings = adapter.analyze_text(privileged_email, threshold=0.75)
    print(f"  Findings: {len(findings)}")
    if findings:
        f = findings[0]
        print(f"  Rule: {f.rule}")
        print(f"  Confidence: {f.confidence:.2%}")
        print(f"  Snippet: {f.snippet[:100]}...")
    print()

    # Test 2: Business email (should NOT detect privilege)
    business_email = """
From: sales@company.com
To: team@company.com
Subject: Q4 product launch plan

Team,

Here's the updated Q4 product launch plan. Please review and provide
feedback by Friday. Looking forward to a successful launch!

Thanks,
Sales Team
"""

    print("Test 2: Business email (not privileged)")
    findings = adapter.analyze_text(business_email, threshold=0.75)
    print(f"  Findings: {len(findings)}")
    if findings:
        print(f"  ❌ FALSE POSITIVE: Detected privilege when there is none")
    else:
        print(f"  ✓ Correctly identified as non-privileged")
    print()

    # Test 3: Edge case - Attorney CC'd without legal question
    cc_email = """
From: marketing@company.com
To: product@company.com
Cc: legal@company.com
Subject: New campaign ideas

Team,

Here are some new marketing campaign ideas for next quarter. Legal,
FYI in case you have any concerns.

Thanks,
Marketing
"""

    print("Test 3: Attorney CC'd (edge case)")
    findings = adapter.analyze_text(cc_email, threshold=0.75)
    print(f"  Findings: {len(findings)}")
    if findings:
        f = findings[0]
        print(f"  Confidence: {f.confidence:.2%}")
        if f.confidence < 0.75:
            print(f"  ✓ Correctly flagged for human review (low confidence)")
    print()


if __name__ == "__main__":
    test_groq_api()
```

**Run:**
```bash
python scripts/test_groq_privilege.py
```

**Expected Output:**
```
Test 1: Privileged email
  Findings: 1
  Rule: groq_policy
  Confidence: 92.00%
  Snippet: Here is my legal opinion on the proposed merger agreement...

Test 2: Business email (not privileged)
  Findings: 0
  ✓ Correctly identified as non-privileged

Test 3: Attorney CC'd (edge case)
  Findings: 0 (or low confidence <75%)
  ✓ Correctly flagged for human review
```

**Acceptance:**
- ✅ Groq API calls succeed (no errors)
- ✅ Test 1: Detects privilege with >90% confidence
- ✅ Test 2: No false positive on business email
- ✅ Test 3: Handles edge case appropriately (low confidence or no finding)
- ✅ Latency < 2 seconds per document
- ✅ Response includes valid JSON structure

---

### TASK 4: Integrate Groq Backend into Bootstrap (1 hour)

**Current State:**
- Bootstrap already has Groq adapter wiring (from main merge)
- Need to ensure it works with new optimized policy

**Action Required:**

**File:** `rexlit/bootstrap.py`

Verify/update the privilege adapter wiring logic (around line 479):

```python
def _init_privilege_port(
    settings: Settings,
    offline_gate: OfflineModeGate,
) -> PrivilegePort | None:
    """Initialize privilege detection adapter based on configuration.

    Priority:
    1. Groq API (if GROQ_API_KEY set and online mode enabled)
    2. Pattern-based fallback
    3. None (privilege detection unavailable)
    """
    # Try Groq first (fastest, requires online)
    groq_api_key = settings.get_groq_api_key()
    if groq_api_key and settings.online:
        try:
            policy_path = settings.get_privilege_policy_path(stage=1)
            # Try optimized Groq policy first
            groq_policy = Path("rexlit/policies/privilege_groq_v1.txt")
            if groq_policy.exists():
                return GroqPrivilegeAdapter(api_key=groq_api_key, policy_path=groq_policy)
            else:
                # Fall back to full policy (will be slower due to length)
                return GroqPrivilegeAdapter(api_key=groq_api_key, policy_path=policy_path)
        except Exception as e:
            logger.warning("Failed to initialize Groq adapter: %s", e)
            # Fall through to pattern-based

    # Fall back to pattern-based (offline-friendly)
    try:
        return PrivilegePatternsAdapter()
    except Exception as e:
        logger.debug("Pattern adapter unavailable: %s", e)
        return None
```

**Usage:**
```bash
# Enable Groq backend
export GROQ_API_KEY="gsk_..."
export REXLIT_ONLINE=1

# Run privilege detection
rexlit privilege classify email.eml
```

**Acceptance:**
- ✅ Bootstrap prefers optimized `privilege_groq_v1.txt` when it exists
- ✅ Falls back to full policy if optimized not found
- ✅ Gracefully degrades to pattern-based if Groq unavailable
- ✅ Clear warning logged if Groq init fails
- ✅ Works in offline mode (uses pattern adapter)

---

### TASK 5: Validate Policy Effectiveness with Test Set (3-4 hours)

**Current State:**
- No systematic testing of policy accuracy
- No precision/recall metrics

**Action Required:**

**Create Test Set:** `tests/fixtures/privilege_test_set.jsonl` (NEW)

```jsonl
{"id": "priv-001", "text": "From: attorney@law.com\nTo: client@company.com\nSubject: Legal opinion\n\nHere is my legal analysis...", "expected_privileged": true, "expected_labels": ["PRIVILEGED:ACP"], "notes": "Clear ACP case"}
{"id": "priv-002", "text": "From: sales@company.com\nTo: team@company.com\nSubject: Sales update\n\nHere are this week's numbers...", "expected_privileged": false, "expected_labels": [], "notes": "Business communication"}
{"id": "priv-003", "text": "From: counsel@law.com\nTo: client@company.com\nSubject: Draft complaint\n\nAttached is the draft complaint for your review...", "expected_privileged": true, "expected_labels": ["PRIVILEGED:WP"], "notes": "Work product"}
{"id": "priv-004", "text": "From: legal@company.com\nTo: ceo@company.com\nSubject: Board meeting agenda\n\nHere's the agenda for next week...", "expected_privileged": false, "expected_labels": [], "notes": "Business advice, not legal"}
{"id": "priv-005", "text": "From: marketing@company.com\nTo: team@company.com\nCc: legal@company.com\nSubject: Campaign launch\n\nNew campaign details. Legal, FYI.", "expected_privileged": false, "expected_labels": [], "notes": "Attorney CC'd without legal question"}
# ... Add 20-30 total examples covering edge cases
```

**Validation Script:** `scripts/validate_privilege_policy.py` (NEW)

```python
"""Validate privilege policy effectiveness against test set."""

import json
import os
from pathlib import Path

from rexlit.app.adapters.groq_privilege import GroqPrivilegeAdapter


def load_test_set(path: Path) -> list[dict]:
    """Load test set from JSONL file."""
    test_cases = []
    with open(path) as f:
        for line in f:
            test_cases.append(json.loads(line))
    return test_cases


def validate_policy(adapter: GroqPrivilegeAdapter, test_set: list[dict]) -> dict:
    """Run test set through adapter and compute metrics."""
    results = {
        "true_positives": 0,  # Correctly detected privilege
        "true_negatives": 0,  # Correctly detected non-privilege
        "false_positives": 0,  # Incorrectly detected privilege
        "false_negatives": 0,  # Missed privilege
        "total": len(test_set),
    }

    for case in test_set:
        findings = adapter.analyze_text(case["text"], threshold=0.75)
        detected_privileged = len(findings) > 0
        expected_privileged = case["expected_privileged"]

        if detected_privileged and expected_privileged:
            results["true_positives"] += 1
        elif not detected_privileged and not expected_privileged:
            results["true_negatives"] += 1
        elif detected_privileged and not expected_privileged:
            results["false_positives"] += 1
            print(f"❌ FALSE POSITIVE: {case['id']} - {case['notes']}")
        else:  # missed privilege
            results["false_negatives"] += 1
            print(f"❌ FALSE NEGATIVE: {case['id']} - {case['notes']}")

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


def main():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY not set")
        return

    policy_path = Path("rexlit/policies/privilege_groq_v1.txt")
    adapter = GroqPrivilegeAdapter(api_key=api_key, policy_path=policy_path)

    test_set_path = Path("tests/fixtures/privilege_test_set.jsonl")
    test_set = load_test_set(test_set_path)

    print(f"Running validation on {len(test_set)} test cases...")
    results = validate_policy(adapter, test_set)

    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    print(f"Accuracy:  {results['accuracy']:.1%}")
    print(f"Precision: {results['precision']:.1%}")
    print(f"Recall:    {results['recall']:.1%}")
    print(f"F1 Score:  {results['f1']:.1%}")
    print()
    print(f"True Positives:  {results['true_positives']}")
    print(f"True Negatives:  {results['true_negatives']}")
    print(f"False Positives: {results['false_positives']}")
    print(f"False Negatives: {results['false_negatives']}")


if __name__ == "__main__":
    main()
```

**Run:**
```bash
python scripts/validate_privilege_policy.py
```

**Target Metrics:**
- **Accuracy:** > 90%
- **Precision:** > 85% (minimize false positives = inadvertent production)
- **Recall:** > 90% (minimize false negatives = missed privilege)
- **F1 Score:** > 87%

**Acceptance:**
- ✅ Test set has 20-30 diverse examples
- ✅ Validation script runs without errors
- ✅ Accuracy > 90%
- ✅ False positives < 10% (critical for production)
- ✅ False negatives < 10% (critical for privilege protection)
- ✅ Results logged for policy iteration

---

### TASK 6: Performance Benchmarking (1-2 hours)

**Goal:** Compare Groq API vs. self-hosted performance.

**Benchmark Script:** `scripts/benchmark_privilege.py` (NEW)

```python
"""Benchmark privilege detection performance: Groq vs. self-hosted."""

import os
import time
from pathlib import Path

from rexlit.app.adapters.groq_privilege import GroqPrivilegeAdapter


def benchmark_groq(sample_text: str, iterations: int = 10) -> dict:
    """Benchmark Groq API adapter."""
    api_key = os.getenv("GROQ_API_KEY")
    policy_path = Path("rexlit/policies/privilege_groq_v1.txt")

    adapter = GroqPrivilegeAdapter(api_key=api_key, policy_path=policy_path)

    latencies = []
    for i in range(iterations):
        start = time.time()
        findings = adapter.analyze_text(sample_text, threshold=0.75)
        latency = time.time() - start
        latencies.append(latency)
        print(f"  Iteration {i+1}/{iterations}: {latency:.3f}s")

    return {
        "backend": "Groq API",
        "mean_latency": sum(latencies) / len(latencies),
        "min_latency": min(latencies),
        "max_latency": max(latencies),
        "throughput_docs_per_sec": 1.0 / (sum(latencies) / len(latencies)),
    }


def main():
    sample_text = """
From: attorney@law.com
To: client@company.com
Subject: Legal opinion on merger

Here is my legal opinion on the proposed merger agreement. From a legal
perspective, I advise proceeding with caution due to antitrust implications.
This communication is attorney-client privileged and confidential.
"""

    print("Benchmarking Groq API (10 iterations)...")
    groq_results = benchmark_groq(sample_text, iterations=10)

    print("\n" + "=" * 50)
    print("GROQ API PERFORMANCE")
    print("=" * 50)
    print(f"Mean latency:   {groq_results['mean_latency']:.3f}s")
    print(f"Min latency:    {groq_results['min_latency']:.3f}s")
    print(f"Max latency:    {groq_results['max_latency']:.3f}s")
    print(f"Throughput:     {groq_results['throughput_docs_per_sec']:.1f} docs/sec")
    print()

    # Note: Self-hosted benchmark would require model weights (~40GB)
    # and GPU. Skipping for now, but expected latency is 10-30s per doc.
    print("Self-hosted (estimated): 10-30s per doc, 0.03-0.1 docs/sec")
    print("Groq speedup: ~10-30x faster")


if __name__ == "__main__":
    main()
```

**Expected Results:**
- **Groq API:** 1-2 seconds per document (~0.5-1.0 docs/sec)
- **Self-hosted:** 10-30 seconds per document (< 0.1 docs/sec)
- **Speedup:** ~10-30x faster with Groq

**Acceptance:**
- ✅ Benchmark script runs successfully
- ✅ Groq latency < 2 seconds per document
- ✅ Throughput > 0.5 docs/sec
- ✅ Results documented for Sprint review

---

### TASK 7: Documentation & CLI Updates (1-2 hours)

**Files to Update:**

**1. README.md** - Add Groq quick start

```markdown
### Quick Start: Privilege Detection with Groq

```bash
# Install with privilege support
pip install -e '.[privilege]'

# Set Groq API key
export GROQ_API_KEY="gsk_..."
export REXLIT_ONLINE=1

# Classify a document
rexlit privilege classify email.eml

# Output:
# ✓ PRIVILEGED: PRIVILEGED:ACP
#   Confidence: 92.00%
#   Rationale: Attorney domain + legal advice per ACP definition
```

**2. CLAUDE.md** - Update privilege section

```markdown
## Privilege Detection

RexLit supports two backends for attorney-client privilege classification:

### Groq API (Recommended for Speed)
- **Model:** openai/gpt-oss-safeguard-20b hosted on Groq Cloud
- **Throughput:** ~1000 tokens/second (~0.5-1.0 docs/sec)
- **Latency:** 1-2 seconds per document
- **Requirements:** GROQ_API_KEY, online mode
- **Cost:** $0.075/1M input tokens, $0.30/1M output tokens

Setup:
```bash
export GROQ_API_KEY="gsk_..."
export REXLIT_ONLINE=1
```

### Self-Hosted (Privacy-First)
- **Model:** gpt-oss-safeguard-20b via transformers
- **Latency:** 10-30 seconds per document
- **Requirements:** ~40GB disk, 16GB+ VRAM
- **Cost:** $0 (self-hosted)

Setup:
```bash
export REXLIT_PRIVILEGE_MODEL_PATH="/models/gpt-oss-safeguard-20b"
```

**Backend Selection:** Bootstrap automatically uses Groq if API key is set and online mode enabled. Otherwise falls back to pattern-based detection or self-hosted if configured.
```

**3. CLI Commands** - Ensure privilege commands work

Test:
```bash
rexlit privilege classify tests/fixtures/privileged-email.eml
rexlit privilege classify tests/fixtures/business-email.eml
```

**Acceptance:**
- ✅ README has Groq quick start section
- ✅ CLAUDE.md documents both backends
- ✅ CLI commands work with Groq backend
- ✅ Error messages are user-friendly (e.g., "GROQ_API_KEY not set")

---

## ⚠️ Known Challenges & Mitigation

| Challenge | Risk | Mitigation |
|-----------|------|------------|
| Groq API rate limits | Medium | Retry logic + exponential backoff |
| Policy optimization (600 words) | Medium | Iterative testing with test set |
| Merge conflicts (main → safeguard) | Low | Careful conflict resolution |
| Test set creation | Medium | Use real examples from JUUL dataset |
| API costs ($0.075/1M tokens) | Low | ~$0.0003 per document (negligible) |

---

## 📊 Success Metrics

**After Sprint 2:**

- ✅ Main branch merged into safeguard branch
- ✅ `GroqPrivilegeAdapter` working with optimized policy
- ✅ Optimized policy is 400-600 words (≈350-550 tokens)
- ✅ Test set validation shows >90% accuracy
- ✅ Groq API latency < 2 seconds per document
- ✅ False positive rate < 10%
- ✅ False negative rate < 10%
- ✅ Documentation updated (README, CLAUDE.md)
- ✅ CLI commands functional
- ✅ Ready for production privilege review workflows

**Performance Targets:**
- ~0.5-1.0 docs/second with Groq API (vs <0.1 with self-hosted)
- 10-30x speedup vs. self-hosted transformers
- 90%+ accuracy on test set (precision + recall)

---

## 📅 Time Estimate

| Task | Estimate | Dependency |
|------|----------|------------|
| Merge main branch | 30 min | None |
| Create optimized 400-600 word policy | 2-3 hrs | Merge complete |
| Test Groq adapter with real API | 2-3 hrs | Policy created |
| Update bootstrap wiring | 1 hr | Tests passing |
| Validate with test set (20-30 examples) | 3-4 hrs | Policy + adapter working |
| Performance benchmarking | 1-2 hrs | All above |
| Documentation & CLI updates | 1-2 hrs | Tests passing |
| **TOTAL** | **11-16 hrs** | **3-5 days** |

---

## 🚀 Sprint Execution Plan

### Day 1: Foundation (3-4 hours)
- ✅ Merge main → safeguard branch
- ✅ Resolve conflicts (CLAUDE.md, README.md, pyproject.toml)
- ✅ Run full test suite to verify merge
- ✅ Create optimized 400-600 word Groq policy

### Day 2: Testing & Validation (5-6 hours)
- ✅ Test Groq adapter with real API calls
- ✅ Create 20-30 example test set
- ✅ Run validation script, compute metrics
- ✅ Iterate on policy if accuracy < 90%

### Day 3: Integration & Performance (3-4 hours)
- ✅ Verify bootstrap backend selection logic
- ✅ Run performance benchmarks
- ✅ Compare Groq vs. self-hosted (if available)
- ✅ Document results

### Day 4: Documentation & Polish (2-3 hours)
- ✅ Update README with Groq quick start
- ✅ Update CLAUDE.md with backend comparison
- ✅ Test CLI commands end-to-end
- ✅ Full regression test suite
- ✅ Commit + push for review

---

## ✅ Definition of Done

**Code:**
- ✅ Main branch merged successfully
- ✅ All tests passing (existing + new)
- ✅ Groq adapter working with optimized policy
- ✅ No regressions in self-hosted backend

**Policy:**
- ✅ Optimized policy is 400-600 words
- ✅ Follows Groq's recommended structure
- ✅ Test set validation shows >90% accuracy
- ✅ False positives < 10%, false negatives < 10%

**Performance:**
- ✅ Groq latency < 2 seconds per document
- ✅ Throughput > 0.5 docs/sec
- ✅ 10-30x faster than self-hosted

**Documentation:**
- ✅ README has Groq quick start
- ✅ CLAUDE.md documents both backends
- ✅ CLI commands work and are documented
- ✅ Benchmark results logged

**Ready for:**
- ✅ Code review
- ✅ Merge to main
- ✅ Production privilege review workflows
- ✅ Sprint 3 (responsiveness + redaction stages)

---

## 🔗 References

**ADRs:**
- ADR 0008: Privilege Safeguard Integration
- ADR 0001: Offline-First Gate
- ADR 0003: Determinism Policy

**Code Files:**
- `rexlit/app/adapters/groq_privilege.py` (from main - 347 lines)
- `rexlit/app/adapters/privilege_safeguard.py` (this branch - 385 lines)
- `rexlit/app/ports/privilege.py` (from main - 76 lines)
- `rexlit/app/ports/privilege_reasoning.py` (this branch - 172 lines)
- `rexlit/bootstrap.py` (merge required - wiring logic)
- `rexlit/policies/privilege_groq_v1.txt` (NEW - 400-600 words)

**External Docs:**
- [Groq gpt-oss-safeguard-20b](https://console.groq.com/docs/models)
- [OpenAI Harmony Policy Format](https://openai.com/research/safety-systems)
- [Groq Python SDK (via OpenAI)](https://github.com/openai/openai-python)

**Test Files:**
- `scripts/test_groq_privilege.py` (NEW - manual testing)
- `scripts/validate_privilege_policy.py` (NEW - metrics)
- `scripts/benchmark_privilege.py` (NEW - performance)
- `tests/fixtures/privilege_test_set.jsonl` (NEW - 20-30 examples)

---

## 📝 Notes

**Why Two Backends?**
- **Groq:** Fast iteration, policy testing, production workflows when speed matters
- **Self-hosted:** Air-gapped environments, data residency requirements, cost sensitivity

**Port Interface Unification (Future Work):**
- Current: `PrivilegePort` (main) vs. `PrivilegeReasoningPort` (safeguard)
- Future: Unify interfaces or create adapter shims
- Not blocking for Sprint 2 - both can coexist

**Policy Iteration Strategy:**
1. Start with 400-600 word baseline
2. Test on 20-30 examples
3. If accuracy < 90%, add more examples or refine criteria
4. Iterate until metrics meet targets
5. Version policies (v1, v2, etc.) for reproducibility

**Cost Analysis:**
- **Groq API:** ~$0.0003 per document (negligible for most use cases)
- **Self-hosted:** $0 API costs, but requires GPU hardware
- For 100K documents: ~$30 with Groq vs. free with self-hosted

**Security:**
- Groq API key encrypted at rest (same as Anthropic)
- No privileged content stored on Groq servers (policy + extracted text only)
- Full CoT reasoning not sent (only final classification)

---

**Status:** Ready to execute
**Blocker:** None
**Next Sprint:** Stage 2/3 Implementation (Responsiveness + Redaction Spans)
