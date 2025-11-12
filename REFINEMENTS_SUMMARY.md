# Scorecard Integration Issue - Refinements Summary

This document outlines how the GitHub issue was refined based on practical implementation feedback. The refined version is in `SCORECARD_ISSUE_REFINED.md`.

## Key Adaptations Implemented

### 1. ✅ Scope Creep Risk → Clear PR Boundaries

**Original Problem:**
- Phase 1 tried to do everything: adapter, CLI, docs, baseline evaluation, testing
- Would require massive PR with multiple concerns mixed

**Refined Solution:**
Split Phase 1 into three smaller PRs with clear dependencies:

| PR | Focus | Deliverables | Time |
|----|-------|--------------|------|
| **1a** | Adapter Foundation | Port interface, REST adapter, bootstrap wiring, unit tests | 6-8h |
| **1b** | User-Facing Features | CLI command, documentation, integration test (mocked) | 6-8h |
| **1c** | Data-Driven Baseline | Ground truth testset, baseline evaluation run, results doc | 8-12h (optional) |

**Why This Works:**
- PR 1a can land independently (testable, no external dependencies needed)
- PR 1b depends on 1a but can run CLI against mocked adapter
- PR 1c is optional (can defer to next release; uses completed 1a+1b)
- Each PR has clear acceptance criteria and is reviewable

**Impact:** Reviewers see focused changes; no blocker chains; easier to iterate.

---

### 2. ✅ Offline-Default Tension → Explicit Online-Only Gating

**Original Problem:**
- RexLit is offline-first by design
- Scorecard requires network access
- Tension not explicitly addressed (users confused about when evaluation works)

**Refined Solution:**
Enforce `--online` flag with three-layer approach:

```python
# Layer 1: CLI command requires --online
@app.command()
def evaluate_privilege_model(
    ...,
    online: bool = typer.Option(False, "--online"),
):
    if not online:
        raise typer.Exit("Scorecard evaluation requires --online flag")

# Layer 2: Adapter uses OfflineModeGate to block creation
class ScorecardPrivilegeAdapter(ScorecardEvaluationPort):
    def __init__(self, ..., offline_gate: OfflineModeGate):
        offline_gate.require("Scorecard evaluation")

# Layer 3: Bootstrap returns no-op stub adapter in offline mode
def _create_scorecard_evaluation_adapter(...):
    if not settings.online:
        return ScorecardEvaluationAdapterStub()  # No-op, logs warning
```

**For Testing:**
- All unit tests use `mock_scorecard_adapter` (no network)
- Mocked responses are deterministic (no flakiness)
- Real Scorecard integration only in optional Phase 1c

**Impact:** Clear error messages; offline mode never breaks; testable without API key.

---

### 3. ✅ Data Handling Detail → Redacted Testcases Policy

**Original Problem:**
- Sample JSONL showed full `document_text` with privileged information
- Contradicted the statement "never send raw privileged data"
- Security concern: could accidentally leak confidential data to Scorecard

**Refined Solution:**
Updated example testcase file to use redacted/synthetic data:

**Before (❌ WRONG):**
```json
{"document_text": "From: attorney@lawfirm.com\nTo: client@company.com\nSubject: RE: Litigation Strategy\n\nPer your request, here is my legal analysis of the contract dispute. I recommend...", ...}
```

**After (✅ CORRECT):**
```json
{"document_hash": "sha256:abc123...", "snippet": "[REDACTED: Attorney-client email discussing legal strategy]", "is_privileged": true, ...}
```

**Scorecard Never Receives:**
- Full document text or email bodies
- Client names or email addresses
- Specific transaction amounts or confidential details
- Actual file paths

**Scorecard Only Receives:**
- `document_hash` (SHA-256, irreversible)
- `snippet` (redacted/<100 chars, or synthetic)
- `document_metadata` (custodian, doctype, date only)
- Ground truth labels (`is_privileged`, `privilege_category`)

**Added Policy Section:**
```markdown
### Data Privacy & Security (Critical)

Never include in testcases:
- Full document text or email bodies
- Client names or email addresses (use generic placeholders)
- Specific transaction amounts or confidential business details
- Actual file paths (use generic descriptions)

Justification: Aligns with RexLit's security posture (ADR 0006) and GDPR/privacy requirements.
```

**Impact:** Compliant with data privacy; no confidentiality breach risk.

---

### 4. ✅ Validation Coverage → Mocked Tests + Manual Verification

**Original Problem:**
- Single integration test checking real F1 threshold (0.65)
- Brittle if testset size changes or model updates
- Couples CI/CD to Scorecard API availability
- Non-deterministic: test passes one day, fails next (no control over Scorecard evaluation order)

**Refined Solution:**
Separate concerns into two independent approaches:

**Unit Tests (Phase 1a-1b) - Mocked, Always Run in CI:**
```python
# tests/test_scorecard_evaluation.py (UNIT TESTS - Always Pass)

def test_create_testset(scorecard_adapter, mock_scorecard_client):
    """Test testset creation with mocked Scorecard."""
    mock_scorecard_client.testsets.create.return_value = MagicMock(id="testset_123")

    testset_id = scorecard_adapter.create_testset(...)

    assert testset_id == "testset_123"

def test_offline_mode_blocks_evaluation(offline_gate):
    """Test that offline mode prevents adapter creation."""
    with pytest.raises(RuntimeError):
        offline_gate.require("Scorecard evaluation")
```

**Why This Works:**
- 100% deterministic (no external API calls)
- Fast (<100ms per test)
- Tests error handling and data transformations
- Safe to run on every commit

**Manual Validation (Phase 1c) - Real Scorecard, Optional:**
```python
# scripts/validate_scorecard_baseline.py (MANUAL/CANARY)

"""
Run this AFTER deploying Phase 1b to validate against real ground truth.
Requires: SCORECARD_API_KEY and real testset in Scorecard project.

Usage:
    SCORECARD_PROJECT_ID=314 python scripts/validate_scorecard_baseline.py
"""

def validate_baseline():
    """Run evaluation and report results."""
    # Connects to real Scorecard
    # Checks: F1 > 0.65, Recall > 0.75
    # Reports: Baseline metrics for documentation
```

**Why This Approach:**
- Unit tests verify adapter logic (deterministic, always in CI)
- Manual validation confirms real-world performance (human-run, documented)
- No brittle thresholds in automated tests
- Phase 1c documentation includes baseline results for reference

**Added to Acceptance Criteria:**
```
#### Phase 1b (Integration Test)
- Integration test (mocked Scorecard)
  - Smoke test that CLI command parses arguments correctly
  - Mocked adapter returns expected data structures
  - Does NOT run against real Scorecard (no flakiness in CI)

#### Phase 1c (Manual Validation - Optional)
- Create manual validation script: scripts/validate_scorecard_baseline.py
```

**Impact:** CI/CD is reliable and fast; baseline validation is transparent and documented.

---

### 5. ✅ Metric Ownership → Config Management + Procedure

**Original Problem:**
- Issue references creating metrics in Scorecard UI
- Doesn't specify how metric IDs get into code
- No procedure for updating when metrics change
- Risk: metric IDs hardcoded, drift over time, CI/CD breaks

**Refined Solution:**
Store metric IDs in configuration with documented update procedure:

**Added to `rexlit/config.py`:**
```python
class ScorecardMetrics(BaseModel):
    """Scorecard metric IDs for privilege evaluation."""

    privilege_accuracy: str = Field(
        default="metric_privilege_accuracy",
        description="Metric ID for binary privilege classification accuracy"
    )
    category_accuracy: str = Field(
        default="metric_category_accuracy",
        description="Metric ID for privilege category accuracy (for privileged docs)"
    )
    # ... other metrics

class Settings(BaseSettings):
    scorecard_project_id: str = Field(default="")
    scorecard_metrics: ScorecardMetrics = Field(default_factory=ScorecardMetrics)
```

**Updated `.env.example`:**
```
# Scorecard Integration (optional, requires --online flag)
SCORECARD_API_KEY=
SCORECARD_PROJECT_ID=
SCORECARD_METRIC_PRIVILEGE_ACCURACY=metric_privilege_accuracy
SCORECARD_METRIC_CATEGORY_ACCURACY=metric_category_accuracy
# ... other metrics
```

**Added to `CLAUDE.md`:**
```markdown
### Updating Scorecard Metrics

When metrics are modified in the Scorecard UI:

1. Get new metric IDs from Scorecard dashboard
2. Update local config:
   ```bash
   export SCORECARD_METRIC_PRIVILEGE_ACCURACY="new_id_here"
   ```
3. Or update `.env` file directly
4. Verify with CLI:
   ```bash
   rexlit evaluate-privilege-model --testset ... --online --validate-metrics
   ```
```

**Impact:** Clear ownership; easy to update; documented procedure prevents drift.

---

## Summary of Refinements

| Area | Original | Refined | Benefit |
|------|----------|---------|---------|
| **Scope** | Single large PR | Three focused PRs (1a, 1b, 1c) | Reviewable, iterative, optional baseline |
| **Offline-First** | Mentioned, not enforced | `--online` flag required, 3-layer validation | Clear error messages, always safe |
| **Data Privacy** | Example showed full text | Redacted/synthetic testcases only | GDPR/privacy compliant |
| **Tests** | Real Scorecard threshold checks | Mocked unit tests + optional manual validation | Deterministic CI, transparent baseline |
| **Metrics** | Unclear how IDs propagate | Stored in config, update procedure documented | No drift, clear ownership |

---

## Ready to Create?

The refined issue is ready for GitHub. You can:

1. **Copy to GitHub UI** directly and adjust labels
2. **Use `gh` CLI:**
   ```bash
   gh issue create --title "feat: Integrate Scorecard for Groq privilege classification evaluation" \
     --body "$(cat SCORECARD_ISSUE_REFINED.md)" \
     --label enhancement,evaluation,privilege-classification,quality-assurance,phase-3,legal-defensibility
   ```
3. **Further iterate** if you want to adjust acceptance criteria or timeline

The issue now balances:
- ✅ Legal defensibility and audit trail (core goal)
- ✅ Practical implementation with clear boundaries (Phase 1a/b/c)
- ✅ Offline-first architecture (RexLit principle)
- ✅ Data privacy compliance (security-first)
- ✅ Reliable testing strategy (deterministic CI)
- ✅ Clear ownership and maintenance (config-driven)
