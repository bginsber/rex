# Kanana Safeguard-Prompt Assessment for RexLit

**Date:** 2025-01-27  
**Model:** Kakao Kanana Safeguard-Prompt (2.1B parameters)  
**License:** Apache 2.0 (Free, Open Source)  
**Purpose:** Prompt injection detection guardrail for privilege classification pipeline

---

## Executive Summary

**Verdict: ⚠️ Worth a 15-minute test, but Korean-language specialization is a concern**

The Kanana Safeguard-Prompt model could add a valuable security layer to RexLit's privilege classification pipeline, but its Korean-language specialization may limit effectiveness on English legal documents. **Recommended:** Run the test script to validate English prompt injection detection before integration.

---

## Current Security Gap

### Problem Identified

RexLit currently concatenates user document text directly into LLM prompts without prompt injection validation:

**Location:** `rexlit/app/adapters/groq_privilege.py:111-119`
```python
prompt = f"""{self.policy_text}

---

Classify the following document:

{text}  # ← Untrusted user input, no sanitization
```

**Risk:** Malicious documents containing prompt injection attempts (e.g., "Ignore all previous instructions...") could potentially manipulate the `gpt-oss-safeguard-20b` model's behavior.

**Attack Vector:** E-discovery documents come from untrusted sources (opposing parties, public records, etc.), making prompt injection a realistic threat.

---

## Kanana Safeguard-Prompt Overview

### Model Specifications

- **Size:** 2.1B parameters (lightweight, fast inference)
- **Output:** Single-token classification (`<SAFE>` or `<UNSAFE-A1>` / `<UNSAFE-A2>`)
- **Purpose:** Detects Prompt Injection (A1) and Prompt Leaking (A2)
- **Training:** Korean-language specialized dataset (~200K samples)
- **License:** Apache 2.0 (free, self-hostable)

### Key Advantages

1. ✅ **Fast Inference:** Single-token output means minimal latency overhead
2. ✅ **Free & Open Source:** Apache 2.0 license, no API costs
3. ✅ **Self-Hostable:** Aligns with RexLit's offline-first philosophy
4. ✅ **Specialized:** Trained specifically for prompt attack detection
5. ✅ **Lightweight:** 2.1B model can run alongside existing pipeline

### Potential Limitations

1. ⚠️ **Korean Language Focus:** Training data is Korean-specific; may miss English prompt injection patterns
2. ⚠️ **False Positives:** Could flag legitimate legal language as attacks
3. ⚠️ **Model Dependency:** Adds another model to maintain/deploy

---

## Integration Architecture

### Proposed Flow

```
Document Text
    ↓
[Kanana Safeguard-Prompt] ← Pre-filter guardrail
    ↓
<SAFE> → Continue to gpt-oss-safeguard-20b
<UNSAFE-A1/A2> → Block, log, flag for manual review
```

### Implementation Points

**Option 1: Pre-filter in PrivilegeService**
- Add guardrail check before `safeguard.classify_privilege()` call
- Fast rejection of obvious prompt injections
- Location: `rexlit/app/privilege_service.py:_classify_privilege()`

**Option 2: Adapter Pattern**
- Create `PromptGuardrailAdapter` implementing `PrivilegeReasoningPort`
- Wraps existing safeguard adapter
- Location: `rexlit/app/adapters/prompt_guardrail.py`

**Option 3: CLI-Level Filter**
- Check documents before privilege classification
- Early rejection, no LLM call needed
- Location: `rexlit/cli.py:privilege_classify()`

**Recommendation:** Option 2 (adapter pattern) for modularity and testability.

---

## Test Plan

### Quick Validation (15 minutes)

Run the test script to validate English prompt injection detection:

**Option 1: Via LM Studio (Recommended - Easier Setup)**
```bash
# 1. Download Kanana Safeguard-Prompt model in LM Studio
#    Search for "kakao/kanana-safeguard-prompt" in LM Studio's model browser

# 2. Load the model in LM Studio (make sure server is running)

# 3. Run test script
cd rex
python scripts/test_kanana_guardrail.py --lm-studio http://localhost:1234/v1
```

**Option 2: Direct Model Loading**
```bash
cd rex
python scripts/test_kanana_guardrail.py --model-path kakao/kanana-safeguard-prompt
```

**Test Cases:**
1. ✅ Classic prompt injections ("Ignore all previous instructions...")
2. ✅ Prompt leaking attempts ("What is your system prompt?")
3. ✅ Normal legal documents (should pass through)
4. ✅ Edge cases (ambiguous language)

**Success Criteria:**
- ≥80% accuracy → Strong candidate for integration
- 60-79% accuracy → Consider with English fine-tuning
- <60% accuracy → Not suitable without retraining

### Performance Benchmarks

Measure inference latency:
- Target: <50ms per document (single-token output should be fast)
- Compare: Current privilege classification latency (~1-2s per doc)

---

## Integration Considerations

### If Test Passes (≥60% accuracy)

1. **Add Kanana Guardrail Adapter**
   - Create `PromptGuardrailAdapter` class
   - Implement single-token inference
   - Add configuration option to enable/disable

2. **Update PrivilegeService**
   - Pre-filter documents through guardrail
   - Block `<UNSAFE-A1/A2>` documents
   - Log blocked attempts to audit trail

3. **Error Handling**
   - Graceful fallback if guardrail model unavailable
   - Circuit breaker pattern (reuse existing)
   - Clear error messages for blocked documents

4. **Testing**
   - Unit tests for guardrail adapter
   - Integration tests with real documents
   - Performance benchmarks

### If Test Fails (<60% accuracy)

**Alternatives:**
1. **English Fine-Tuning:** Fine-tune Kanana on English prompt injection dataset
2. **Rule-Based Pre-Filter:** Simple regex patterns for common injection attempts
3. **Other Guardrails:** Meta Llama Guard, OpenAI's guardrails, etc.
4. **Accept Risk:** Document limitation, rely on gpt-oss-safeguard-20b's built-in safety

---

## Cost-Benefit Analysis

### Benefits

- **Security:** Prevents prompt injection attacks before LLM processing
- **Cost:** Free (self-hosted), no API costs
- **Performance:** Minimal overhead (~50ms per document)
- **Defensibility:** Audit trail shows proactive security measures

### Costs

- **Development Time:** ~4-8 hours for integration
- **Maintenance:** Another model to update/deploy
- **False Positives:** May require manual review of blocked documents
- **Storage:** Model weights (~4-8GB)

### ROI

**If test passes:** High ROI - minimal cost, significant security improvement  
**If test fails:** Low ROI - would require fine-tuning investment

---

## Next Steps

1. ✅ **Run Test Script** (`scripts/test_kanana_guardrail.py`)
2. ⏳ **Evaluate Results** (accuracy, false positive rate)
3. ⏳ **Decision Point:**
   - If ≥60% accuracy → Proceed with integration
   - If <60% accuracy → Consider alternatives or fine-tuning
4. ⏳ **If Proceeding:** Create integration PR with adapter pattern

---

## References

- **Kanana Safeguard Series:** [Kakao Tech Blog](https://tech.kakao.com/2025/05/27/kanana-safeguard-series/)
- **HuggingFace Model:** `kakao/kanana-safeguard-prompt`
- **RexLit Security Docs:** `SECURITY.md`, `docs/adr/0008-privilege-safeguard-integration.md`
- **Current Implementation:** `rexlit/app/adapters/groq_privilege.py`

---

## Conclusion

Kanana Safeguard-Prompt is **worth testing** because:
1. It addresses a real security gap (prompt injection)
2. It's free and aligns with offline-first philosophy
3. Single-token output means minimal performance impact
4. 15-minute test is low-risk, high-potential-value

**However**, Korean-language specialization is a significant concern. The test script will quickly validate whether the model can detect English prompt injection patterns. If it fails, consider rule-based pre-filtering or English fine-tuning as alternatives.

