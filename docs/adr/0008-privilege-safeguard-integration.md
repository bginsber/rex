# ADR 0008: Privilege Classification with gpt-oss-safeguard Integration

**Status:** Accepted
**Date:** 2025-11-05
**Authors:** RexLit Core Team
**Supersedes:** N/A

## Context

RexLit requires attorney-client privilege classification for legal e-discovery workflows to:
1. Identify privileged documents (ACP, work product, common interest) before production
2. Prevent inadvertent disclosure of privileged material in discovery responses
3. Support privilege review workflows with explainable AI reasoning
4. Maintain audit trails for privilege determinations while protecting confidentiality

### Requirements

**Functional:**
- Classify documents for attorney-client privilege (ACP), work product (WP), and common interest (CI)
- Provide confidence scores and "needs review" flags for uncertain classifications
- Support multi-label classification (privilege + responsiveness + redactions)
- Enable batch processing for large document collections
- Export review reports in audit-ready JSONL format

**Non-Functional:**
- **Offline-first:** All processing must be self-hosted (no external API calls)
- **Privacy-preserving:** Chain-of-thought reasoning must not leak privileged content
- **Resilient:** Gracefully handle model failures, timeouts, and malformed outputs
- **Deterministic:** Consistent classifications across multiple runs (for legal defensibility)
- **Auditable:** Tamper-evident logs without compromising privilege protection

### Privacy Risks

**Problem:** Large language models (LLMs) generate detailed chain-of-thought (CoT) reasoning that may quote or paraphrase privileged document text. If this reasoning is logged verbatim in audit trails, it could constitute inadvertent disclosure of privileged material.

**Example Risk:**
```json
{
  "operation": "privilege.classify",
  "doc_id": "EMAIL-001",
  "reasoning": "The email states 'Here is my legal opinion on the merger...' which clearly indicates attorney-client privilege per ACP definition."
}
```
☠️ **Breach:** The audit log now contains the privileged excerpt "Here is my legal opinion on the merger", which could be discoverable.

## Decision

We will integrate OpenAI's **gpt-oss-safeguard-20b** model for policy-based privilege reasoning with the following privacy-preserving architecture:

### 1. Privacy Controls (Default: Hashed CoT Only)

**Approach:** Hash full chain-of-thought reasoning with salted SHA-256 before audit logging. Store only:
1. **Reasoning hash** (SHA-256): Verifiable proof of reasoning without content exposure
2. **Redacted summary** (≤200 chars): Policy citations and high-level rationale WITHOUT document excerpts

**Implementation:**
```python
class PolicyDecision(BaseModel):
    reasoning_hash: str          # SHA-256(full_cot + salt)
    reasoning_summary: str       # Redacted 1-2 sentences (no excerpts)
    full_reasoning_available: bool = False  # Vault flag
```

**Redaction Strategy for Summaries:**
```python
def _redact_summary(full_cot: str) -> str:
    """Remove document excerpts, keep policy citations only."""
    lines = full_cot.split("\n")
    safe_lines = [
        line for line in lines
        if not ('"' in line or "excerpt:" in line.lower())
    ]
    return " ".join(safe_lines)[:200]
```

**Optional Encrypted Vault (Opt-In):**
- **Default:** `log_full_cot=false` (privacy-preserving, hashed only)
- **Opt-In:** `log_full_cot=true` stores full CoT in encrypted vault at `cot_vault_path`
- Vault files named by hash (deduplication): `{reasoning_hash}.txt`
- Encrypted with Fernet key (reuse existing `rexlit/utils/crypto.py`)

**Configuration:**
```toml
[privilege]
log_full_cot = false  # Privacy-preserving default
cot_vault_path = "/secure/cot-vault/"  # Required if log_full_cot=true
```

### 2. Resilience: Circuit Breaker Pattern

**Problem:** Model inference can fail due to timeouts, OOM errors, malformed JSON, or repeated errors. Without resilience controls, these failures cascade and block privilege review workflows.

**Solution:** Implement circuit breaker pattern to fail fast after repeated errors:

```python
class CircuitBreaker:
    states: CLOSED | OPEN | HALF_OPEN
    failure_threshold: int = 5
    timeout_seconds: float = 60.0

    def call(fn: Callable) -> Result:
        if state == OPEN:
            raise CircuitBreakerOpen("Backend unavailable")
        try:
            result = fn()
            on_success()
            return result
        except Exception:
            on_failure()
            raise
```

**Behavior:**
- **CLOSED (normal):** All calls pass through, failures increment counter
- **OPEN (tripped):** Fail fast for `timeout_seconds`, skip model inference
- **HALF_OPEN (recovery):** Allow limited test calls to check if service recovered

**Fallback Strategy:**
When circuit breaker opens or model errors occur:
1. Return `PolicyDecision` with `needs_review=true`
2. Set `confidence=0.0` to flag for human review
3. Log error in `reasoning_summary` field
4. Continue processing remaining documents (fail gracefully, not fatally)

### 3. Modular Multi-Label Pipeline (3 Stages)

**Problem:** Single monolithic prompt for privilege + responsiveness + redactions degrades accuracy on each task.

**Solution:** Separate prompts for each classification stage:

```
┌──────────────────────────────────────┐
│ Stage 1: Privilege Detection         │
│ Policy: JUUL §2 (ACP/WP/CI only)     │
│ Output: PRIVILEGED:ACP + confidence  │
└────────────┬─────────────────────────┘
             │ If privileged...
             ▼
┌──────────────────────────────────────┐
│ Stage 2: Responsiveness (Optional)   │
│ Policy: JUUL §3 (litigation topics)  │
│ Output: RESPONSIVE + HOTDOC:n        │
└────────────┬─────────────────────────┘
             │ If responsive...
             ▼
┌──────────────────────────────────────┐
│ Stage 3: Redaction Spans (Optional)  │
│ Policy: JUUL §5 (CPI/trade secrets)  │
│ Output: redaction_spans[]            │
└──────────────────────────────────────┘
```

**Benefits:**
- Focused prompts → better per-task accuracy
- Modular: Disable stages 2/3 if not needed
- Audit trail per stage (separate log entries)

**Configuration:**
```python
service = PrivilegeReviewService(
    safeguard_adapter=adapter,
    enable_responsiveness=False,  # Stage 2 disabled
    enable_redactions=False,       # Stage 3 disabled
)
```

### 4. Dynamic Reasoning Effort

**Problem:** Fixed reasoning effort (low/medium/high) wastes compute on simple cases or underperforms on complex documents.

**Solution:** Adapter selects effort based on document complexity:

```python
def _select_reasoning_effort(text: str) -> str:
    # Complex legal terms → high effort
    complex_terms = ["attorney-client privilege", "work product", ...]
    if any(term in text.lower() for term in complex_terms):
        return "high"

    # Long documents → medium effort
    if len(text) > 5000:
        return "medium"

    # Simple cases → low effort
    return "low"
```

**Override:** Users can force effort via CLI: `--reasoning-effort high`

### 5. Self-Hosted Only (Offline-First)

**Decision:** gpt-oss-safeguard-20b will ONLY be supported as a self-hosted model. No external API deployment (Groq, OpenAI, etc.) to ensure:
- Data residency compliance (JUUL requirements)
- No third-party data processors
- Offline operation for air-gapped environments

**Model Loading:**
```python
from transformers import pipeline

model = pipeline(
    "text-generation",
    model="/models/gpt-oss-safeguard-20b",  # Local path
    torch_dtype="auto",
    device_map="auto",
)
```

**Configuration Validation:**
```python
# Enforce offline-first in adapter
def __init__(self, model_path: Path, ...):
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}. "
            "Install gpt-oss-safeguard-20b or configure privilege_model_path."
        )
```

### 6. Harmony Policy Templates

Privilege classification uses **Harmony-format policies** (OpenAI's policy-as-prompt framework):

**Stage 1: Privilege Detection (`juul_privilege_stage1.txt`)**
- Defines ACP, WP, CI per FRCP/case law
- Privileged indicators (attorney domains, legal advice keywords)
- Non-privileged criteria (business communications, public info)
- Confidence scoring rubric (0.0-1.0)
- Examples with expected outputs
- **Privacy instruction:** "Do NOT include email excerpts or quoted text in your rationale"

**Stage 2: Responsiveness (`juul_responsiveness_stage2.txt`)**
- Litigation topics (youth marketing, product safety, regulatory)
- HOTDOC severity levels (1-5 scale)
- Responsiveness indicators (custodians, time period, keywords)

**Stage 3: Redaction Spans (`juul_redaction_stage3.txt`)**
- Redaction categories (CPI/PERSONNEL, TRADE_SECRET, FINANCIAL, PRIVACY)
- Character offset detection (start/end inclusive/exclusive)
- Minimal redaction principle (preserve context)

**Policy Versioning:**
- Each policy file SHA-256 hashed → stored in `PolicyDecision.policy_version`
- Audit trail records which policy version produced each classification
- Supports A/B testing and iterative policy tuning

## Consequences

### Positive

1. **Privacy-Preserving by Default:**
   - Hashed CoT prevents inadvertent disclosure in audit logs
   - Redacted summaries safe for discovery/privilege logs
   - Encrypted vault opt-in for rare cases requiring full reasoning

2. **Resilient to Model Failures:**
   - Circuit breaker prevents cascading failures
   - Graceful degradation with `needs_review` flag
   - Continues processing batch despite individual errors

3. **Modular & Extensible:**
   - Easy to add new classification stages
   - Swap out adapters (future: pattern-based, other LLMs)
   - Policy templates versioned and tunable

4. **Audit-Ready:**
   - Tamper-evident logs with SHA-256 hash chain (existing ADR 0004)
   - Policy version tracking for reproducibility
   - Reasoning hashes allow verification without content exposure

5. **Offline-First Compliance:**
   - Self-hosted only → no data leaves environment
   - Deterministic processing (ADR 0003) for legal defensibility
   - Compatible with air-gapped deployments

### Negative

1. **Model Installation Complexity:**
   - Users must install 20B parameter model (~40GB disk, 16GB+ VRAM)
   - Requires GPU for acceptable performance (CPU inference too slow)
   - No cloud API fallback (by design for privacy)

2. **Hashed CoT Limits Explainability:**
   - Cannot inspect full reasoning without enabling encrypted vault
   - Redacted summaries may be too terse for complex cases
   - Trade-off: Privacy vs. explainability (chose privacy by default)

3. **Modular Pipeline Increases Latency:**
   - 3-stage pipeline = 3 model calls per document
   - Privilege-only review faster, but full pipeline slower
   - Mitigated by disabling stages 2/3 when not needed

4. **Dynamic Reasoning Effort Heuristics:**
   - Simple heuristics (text length, keywords) may not generalize
   - Future: ML-based effort prediction or adaptive feedback
   - Users can override with `--reasoning-effort` flag

5. **No Hybrid Pattern/LLM Yet:**
   - Currently LLM-only (pattern pre-filter planned for future)
   - All documents go through model inference (compute expensive)
   - Future optimization: Pattern adapter with confidence thresholds

## Implementation Status

**Completed (v2):**
- ✅ `PrivilegeReasoningPort` interface with `PolicyDecision` model
- ✅ `PrivilegeSafeguardAdapter` with circuit breaker and CoT privacy
- ✅ `PrivilegeReviewService` orchestration with 3-stage pipeline
- ✅ Configuration fields in `Settings` (model path, vault, thresholds)
- ✅ CLI commands: `rexlit privilege classify` and `rexlit privilege explain`
- ✅ Harmony policy templates for all 3 stages
- ✅ Integration tests (mock adapter, circuit breaker, service)

**Future Work:**
- ⚠️ Pattern-based pre-filter adapter (fast heuristics, skip LLM when high confidence)
- ⚠️ Expanded calibration (250-doc stratified sample for κ measurement)
- ⚠️ Stages 2/3 implementation (responsiveness, redactions) - currently placeholders
- ⚠️ Encrypted vault with Fernet key integration
- ⚠️ Batch processing optimization (parallel inference)
- ⚠️ Human-in-loop review queue integration

## Alternatives Considered

### 1. Log Full CoT by Default (Rejected)

**Proposal:** Store complete chain-of-thought reasoning in audit logs for maximum explainability.

**Rejection Reason:** Unacceptable privacy risk. Full CoT likely contains privileged excerpts, which would be discoverable if audit logs are produced. Violates core requirement of protecting privilege during classification process.

### 2. External API Deployment (Rejected)

**Proposal:** Deploy safeguard via Groq, OpenAI, or other cloud APIs for easier setup.

**Rejection Reason:** Violates offline-first architecture (ADR 0001) and data residency requirements. Third-party APIs = third-party data processors, unacceptable for JUUL litigation. Self-hosted only ensures no data leaves environment.

### 3. Single-Stage Monolithic Prompt (Rejected)

**Proposal:** Combine privilege + responsiveness + redactions in one prompt to reduce latency.

**Rejection Reason:** Multi-task prompts degrade per-task accuracy. Privilege detection is critical (false negatives = inadvertent disclosure), so we prioritize accuracy over speed. Modular pipeline allows disabling stages 2/3 when not needed.

### 4. No Circuit Breaker (Rejected)

**Proposal:** Let model errors propagate and fail the entire batch on first error.

**Rejection Reason:** Brittleness unacceptable for production workflows. Single timeout or OOM error would block entire privilege review. Circuit breaker + graceful degradation ensures review continues with `needs_review` flags for problematic documents.

### 5. Pattern-Only (No LLM) (Rejected for Now)

**Proposal:** Use fast heuristics (attorney email domains, keywords) without LLM inference.

**Rejection Reason:** Insufficient accuracy for privilege classification. Patterns generate too many false positives/negatives. However, **future hybrid approach** will use patterns as pre-filter to skip LLM on obvious cases.

## References

- [OpenAI gpt-oss-safeguard-20b](https://github.com/openai/gpt-oss-safeguard) (Apache 2.0)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html) (Martin Fowler)
- ADR 0001: Offline-First Gate
- ADR 0002: Ports/Adapters Import Contracts
- ADR 0003: Determinism Policy
- ADR 0004: JSONL Schema Versioning
- ADR 0006: Redaction Plan/Apply Model

## Appendix: Example Audit Log Entry

**Privacy-Preserving Audit Entry:**
```json
{
  "operation": "privilege.privilege",
  "doc_id": "EMAIL-001",
  "labels": ["PRIVILEGED:ACP"],
  "confidence": 0.92,
  "needs_review": false,
  "reasoning_hash": "a3f2b1c8d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
  "reasoning_summary": "Communication from external counsel per ACP definition §2.1",
  "model_version": "gpt-oss-safeguard-20b",
  "policy_version": "a1b2c3d4",
  "reasoning_effort": "medium",
  "decision_ts": "2025-11-05T14:30:00.123456Z",
  "timestamp": "2025-11-05T14:30:00.123456Z",
  "prev_hash": "...",
  "current_hash": "..."
}
```

**Notes:**
- ✅ No document text or excerpts logged
- ✅ Reasoning hash provides verifiable proof
- ✅ Summary contains policy citations only (no privileged content)
- ✅ Tamper-evident hash chain (ADR 0004)
- ✅ Policy version tracked for reproducibility
