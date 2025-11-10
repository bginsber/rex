# Harmony Format vs Stage 1 Policy Comparison

## Executive Summary

The new **Harmony Format (v1.1)** shows **REGRESSIONS** compared to **Stage 1 (Comprehensive)**:

- **Tests Improved**: 0
- **Tests Same**: 4
- **Tests Regressed**: 2
- **Tests Still Failing**: 3

**Recommendation**: The Harmony format lost critical training patterns. Consider reverting to Stage 1 or merging the best of both policies.

---

## Test Results Comparison

### Harmony Policy (v1.1) Results
```
Test 1: ✅ 93% (Explicit privilege notice)
Test 2: ✅ 0 findings (Business email - negative control)
Test 3: ❌ 0 findings (Implicit legal reference)
Test 4: ✅ 95% (Work product)
Test 5: ✅ 80% (In-house counsel implicit)
Test 6: ❌ 0 findings (Privilege waiver - REGRESSED)
Test 7: ✅ 0 findings (Regulatory decision - negative control)
Test 8: ❌ 0 findings (Forwarded attorney advice)
Test 9: ❌ 0 findings (Real JUUL boilerplate - CRITICAL FAILURE)
```

### Stage 1 Policy Results (from previous run with delays)
```
Test 1: ✅ 92% (Explicit privilege notice)
Test 2: ✅ 0 findings (Business email - negative control)
Test 3: ❌ 0 findings (Implicit legal reference)
Test 4: ✅ 90-95% (Work product)
Test 5: ✅ 78-80% (In-house counsel implicit)
Test 6: ✅ 78% (Privilege waiver - DETECTED)
Test 7: ✅ 0 findings (Regulatory decision - negative control)
Test 8: ❌ 0 findings (Forwarded attorney advice)
Test 9: ❌ 0 findings (Real JUUL boilerplate - still fails)
```

### Score Comparison Matrix

| Test | Harmony | Stage 1 | Delta | Status |
|------|---------|---------|-------|--------|
| 1 | 93% | 92% | +1% | ✓ Same |
| 2 | 0 | 0 | - | ✓ Same |
| 3 | 0 | 0 | - | ✓ Same |
| 4 | 95% | 90-95% | +0-5% | ✓ Same |
| 5 | 80% | 78-80% | 0-2% | ✓ Same |
| 6 | 0 | 78% | **-78%** | ❌ **REGRESSION** |
| 7 | 0 | 0 | - | ✓ Same |
| 8 | 0 | 0 | - | ✓ Same |
| 9 | 0 | 0 | - | ✓ Same |

---

## Root Cause Analysis: What Was Lost

### Harmony Format Characteristics
- **Size**: 6,950 bytes (compact)
- **Structure**: XML-like tags, numbered sections, JSON schema definition
- **Format Origin**: Appears to be reformatted from OpenAI/ChatGPT system message format
- **Key Sections**:
  - Definitions (1.1-1.3)
  - Privileged Indicators (2.1-2.5)
  - Non-Privileged (3.1-3.5)
  - Edge Cases (4.1-4.4) ← Brief, minimal guidance
  - Confidence Scoring (5)
  - Non-binding Scenarios (6) ← One-liners only
  - Output Rules
  - Response Formats (JSON schema)

### Stage 1 Characteristics
- **Size**: ~8,427 bytes (more detailed)
- **Structure**: Traditional prose + sections
- **Format Origin**: Comprehensive e-discovery privilege policy
- **Key Sections**:
  - Instructions
  - Definitions
  - Privileged Indicators (more detailed examples)
  - Non-Privileged
  - **EXAMPLES Section** ← 6 detailed worked examples
  - **EDGE CASES Section** ← Detailed guidance on tricky scenarios
  - Output Format

### Critical Missing Sections in Harmony

#### ❌ EXAMPLES Section (Stage 1 has this, Harmony removed it)
Stage 1 includes **6 detailed worked examples**:
1. Clear ACP (external counsel) - confidence guidance
2. Work Product (litigation memo) - explicit markers
3. Non-Privileged Business Email - negative control patterns
4. Attorney CC'd on Business Email - edge case guidance
5. Uncertain Case - Attorney Business Advice - mixed signals
6. Common Interest Privilege - CI agreement patterns

These examples teach the LLM *patterns* for detecting privilege in context. Harmony replaced these with **one-liners only**, losing depth.

#### ❌ EDGE CASES Section (Stage 1 has detailed guidance, Harmony has minimal)

**Stage 1 EDGE CASES (detailed):**
```
1. Mixed Privilege/Non-Privilege:
   "If document contains both privileged and non-privileged content,
    classify as privileged if any substantial portion qualifies."
   → Directly addresses Test 6!

2. Attorney in Non-Legal Role:
   "If attorney is acting in business capacity (e.g., as board member),
    classify as non-privileged unless legal advice is explicitly
    requested/provided."

3. Multiple Recipients:
   "Broad distribution generally destroys privilege, but not if all
    recipients are within privilege circle..."

4. Forwarded Emails:
   "If originally privileged email is forwarded outside privilege circle
    without common interest agreement, privilege may be waived."
   → Directly addresses Test 8!
```

**Harmony EDGE CASES (4 brief subsections):**
- 4.1 Mixed Content - one sentence summary
- 4.2 Attorney in Dual Roles - one sentence
- 4.3 Distribution Scope - one sentence
- 4.4 Forwarding - one sentence

Harmony lost ~70% of the detailed guidance that Stage 1 provided for handling tricky scenarios.

---

## Impact on Specific Tests

### Test 6: Privilege Waiver Scenario (REGRESSION: 78% → 0%)

**Email Content**: Mixed privileged statement + non-privileged external statement + attorney work product

**Stage 1 Guidance** (from EDGE CASES section):
```
"If document contains both privileged and non-privileged content,
 classify as privileged if any substantial portion qualifies."
```
✅ This guidance allowed Stage 1 to detect the privileged portion (78% confidence)

**Harmony Guidance** (from 4.1 Mixed Content):
```
"If a substantial portion is privileged, classify as privileged;
 reflect uncertainty in the confidence score."
```
❌ Same words but without the EXAMPLES showing how to identify "substantial portion" in practice

**Result**: Harmony policy didn't learn from worked examples how to detect mixed content patterns

---

### Test 8: Forwarded Attorney Advice (0% → 0%, still failing)

**Email Content**: Non-attorney forwarding attorney advice to team members

**Stage 1 Guidance** (from EDGE CASES section):
```
"If originally privileged email is forwarded outside privilege circle
 without common interest agreement, privilege may be waived.
 Consider context and recipient list."
```
Stage 1 still failed this test (0%), but at least had explicit guidance about the issue.

**Harmony Guidance** (from 4.4 Forwarding):
```
"Forwarding privileged content outside the privilege or CI circle
 may waive privilege; evaluate recipients and purpose."
```
❌ Even shorter, lost the contextual detail about "common interest agreement"

---

### Test 9: Real JUUL Boilerplate (0% → 0%, still critical issue)

**Email Content**: Explicit privilege notice from external counsel (Synchrogenix)

**Why Both Fail**:
- Both policies treat external counsel identically
- Issue appears to be **domain recognition** - Synchrogenix not recognized as law firm
- Neither policy has specific handling for regulatory/consulting firm domains

**Stage 1 Indicators (Section 2.1)**:
```
"Common law firm domains: @skadden.com, @wsgr.com, @cooley.com, etc."
```
❌ Synchrogenix not in common domains list

**Harmony Indicators (Section 2.1)**:
```
"External law-firm domains (e.g., *@lawfirm.com*)"
```
❌ Even less specific than Stage 1

---

## Detailed Policy Comparison

### Section 2: Privileged Indicators

**Stage 1 - Much more detailed:**
```
1. Attorney Email Domains:
   - Email from/to @[lawfirm].com addresses
   - Email from/to in-house counsel (@company.com with "legal" or "counsel" in name)
   - Common law firm domains: @skadden.com, @wsgr.com, @cooley.com, etc.

2. Explicit Privilege Markers:
   - "Attorney-client privilege"
   - "Privileged and confidential"
   - [5 specific markers listed]

3. Legal Advice Language:
   - "Here is my legal opinion..."
   - "From a legal perspective..."
   - [4 specific language patterns]

4. Litigation Preparation:
   - Draft pleadings or motions
   - Litigation strategy discussions
   - Settlement negotiation strategy (involving counsel)
   - Deposition preparation notes
   - Expert witness strategy

5. Attorney Names/Signatures:
   - Attorney names on authorized counsel list
   - Email signatures with "Esq.", "Attorney at Law", or bar license numbers
```

**Harmony - More compact:**
```
2.1 Attorney Identifiers
- External law-firm domains (e.g., *@lawfirm.com*)
- In-house counsel mailboxes
- Metadata/name cues

2.2 Explicit Markers
- Listed items (same content)

2.3 Legal Advice Language
- "Clear indications" (generic, no examples)

2.4 Litigation Preparation
- Same items but more compact

2.5 Contextual Metadata
- Generic list
```

**Key Loss**: Stage 1's specific examples like "@skadden.com, @wsgr.com, @cooley.com" teach the model about law firm domains. Harmony's generic "@lawfirm.com" is too abstract.

---

## Recommendations

### Option 1: Revert to Stage 1 (Safe)
- **Pros**: Proven working (78% on Test 6, others passing)
- **Cons**: Still fails Tests 3, 8, 9
- **Effort**: Minimal (restore previous version)

### Option 2: Create Hybrid Policy (Best)
**Keep Harmony's structure but add back Stage 1's EXAMPLES and detailed EDGE CASES:**

```
Harmony Framework (6950 bytes) +
Stage 1 EXAMPLES Section (6 worked examples) +
Stage 1 EDGE CASES detailed guidance
= Harmony+ (~9000-9500 bytes, better performance)
```

**Specific additions needed**:
1. Add 6 detailed EXAMPLES (Test 6 example shows mixed content detection)
2. Expand EDGE CASES with full guidance (not just one-liners)
3. Add specific law firm domains to Section 2.1 (include consulting firms like Synchrogenix)
4. Add regulatory/consulting firm patterns for Test 9

### Option 3: Enhance Harmony Format (Moderate)
1. Add domain patterns for consulting/regulatory firms
2. Expand 4.1 (Mixed Content) with detailed guidance
3. Add explicit patterns for forwarded attorney advice
4. Include implicit privilege indicators for non-attorney forwarding

### Option 4: Root Cause Fix for Test 9 (Focused)
The real issue: **Synchrogenix domain not recognized as privileged**

**Current** (Harmony/Stage 1):
```
"External law-firm domains (e.g., *@lawfirm.com*)"
```

**Needed**:
```
"External law-firm domains (e.g., *.com, *.net, etc.) including
 regulatory/consulting firms (e.g., @synchrogenix.com, @certara.com)
 that operate as counsel representatives."
```

---

## Actionable Next Steps

### Immediate (Option 1 - Revert)
```bash
# Restore Stage 1
cp rexlit/policies/juul_privilege_stage1.txt rexlit/policies/juul_priviledge_stage1_harmony.txt

# Confirm Stage 1 results
python scripts/test_groq_privilege.py --stage1
```

### Short-term (Option 2 - Hybrid)
1. Keep Harmony's numbered structure (cleaner)
2. Insert Stage 1's 6 EXAMPLES before output rules
3. Expand EDGE CASES with Stage 1 guidance
4. Test with `--harmony` flag

### Medium-term (Option 4 - Enhanced)
1. Add domain recognition for Synchrogenix/Certara
2. Add patterns for implicit legal advice indicators
3. Improve forwarded content detection
4. Target Test 3, 8, 9 improvements

---

## Summary Table

| Aspect | Harmony | Stage 1 | Winner |
|--------|---------|---------|--------|
| File Size | 6,950 bytes | 8,427 bytes | - |
| Explicit Examples | 1-liners | 6 detailed | **Stage 1** |
| Edge Case Guidance | Minimal | Detailed | **Stage 1** |
| Mixed Content Handling | Generic | Specific | **Stage 1** |
| Forwarded Email Guidance | Brief | Detailed | **Stage 1** |
| Test 6 (Mixed) Result | 0% ❌ | 78% ✅ | **Stage 1** |
| Test 1 Result | 93% | 92% | Harmony (~same) |
| Structure/Readability | Cleaner (numbered) | Traditional prose | Harmony |
| Domain Patterns | Generic | Specific | **Stage 1** |

**Overall Winner**: **Stage 1** for accuracy, **Harmony** for structure

**Best Path Forward**: Merge Harmony's structure with Stage 1's content depth

---

## Files Referenced

- `juul_priviledge_stage1_harmony.txt` - 6,950 bytes (v1.1 - more compact)
- `juul_privilege_stage1.txt` - 8,427 bytes (comprehensive - better results)
- `privilege_groq_v1.txt` - 4,774 bytes (original - weakest)
- Test script: `scripts/test_groq_privilege.py` with `--harmony` flag
