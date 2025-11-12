# Integrate Scorecard for Groq Privilege Classification Evaluation

## Overview

Integrate Scorecard (https://www.scorecard.io) into the RexLit privilege determination pipeline to systematically evaluate the accuracy and reliability of Groq API-based privilege classification. This will provide quantified metrics (precision, recall, F1 score) for privilege model performance, enabling data-driven improvements and legal defensibility for the privilege review process.

**Current State:** RexLit uses a hybrid privilege pipeline combining pattern-based pre-filtering (≥85% confidence, skips LLM) with Groq API escalation for uncertain cases (50-84% confidence). Performance is tested manually with 9 scripted tests and 25 fixture testcases, but lacks systematic measurement against ground truth data.

**Proposed Value:** Scorecard provides EDRM TAR (Technology Assisted Review) compliant evaluation metrics, enabling:
- **Quantified Accuracy**: Precision, recall, F1 score against labeled ground truth
- **Confidence Calibration**: Validate that confidence thresholds align with actual accuracy
- **Model Comparison**: A/B test Groq vs. OpenAI vs. pattern-only approaches scientifically
- **Regression Prevention**: CI/CD integration to catch accuracy drops before production
- **Legal Defensibility**: Document evaluation methodology for potential court challenges

## Problem Statement / Motivation

**Legal e-discovery context:** Privilege determinations have severe consequences:
- Missing privileged documents = waiver + ethical violations (Rule 502)
- Incorrectly marked privileged = over-redaction + discovery delays
- Current manual testing doesn't measure false positive/negative rates
- No systematic way to validate that the 85%/50% confidence thresholds are optimal

**Current gaps in RexLit's privilege pipeline:**
1. **No ground truth validation**: Test scripts use synthetic/curated examples, not real production data
2. **No quantified metrics**: Anecdotal test pass/fail, but no precision/recall/F1 measurements
3. **No A/B testing capability**: Can't scientifically compare different model/policy combinations
4. **No regression detection**: New policy/model changes not validated against baseline
5. **No confidence calibration**: Unknown if 85% pattern confidence actually predicts 85% accuracy

**Why Scorecard specifically:**
- **TAR-aligned**: Industry-standard evaluation metrics used in technology-assisted review
- **MCP Integration**: Can optionally use Claude's native MCP to invoke evaluations conversationally
- **REST API**: Direct Python SDK for CI/CD integration
- **Free tier**: 100,000 scores lifetime (covers ~333 evaluation runs at 3 metrics per run)
- **Audit trail**: Evaluation results tracked in Scorecard dashboard with historical comparison

## Proposed Solution

Implement a three-phase integration with clear PR boundaries:

### Phase 1a: Evaluation Adapter (First PR - MVP Foundation)
Create the evaluation adapter and port interface following ports-and-adapters pattern:
- `rexlit/app/ports/scorecard_port.py` - Port interface
- `rexlit/app/adapters/scorecard_evaluation_adapter.py` - REST API adapter implementation
- `rexlit/bootstrap.py` - Wire adapter (behind `offline_gate`)
- Unit tests with mocked Scorecard responses

### Phase 1b: CLI Integration & Documentation (Second PR - User-Facing Features)
Add CLI command and document evaluation workflow:
- `rexlit evaluate-privilege-model` command
- `docs/SCORECARD_EVALUATION.md` - Setup and usage guide
- `docs/PRIVILEGE_EVALUATION_METHODOLOGY.md` - Legal defensibility documentation
- Integration test with mocked Scorecard (lightweight smoke test)

### Phase 1c: Baseline Evaluation Report (Third PR - Data-Driven)
Run evaluation against ground truth testset and establish baseline:
- Import 50-100 labeled documents into Scorecard
- Run evaluation against current Groq + Harmony+ configuration
- Document results in `SCORECARD_BASELINE_RESULTS.md`
- Create CI/CD readiness checklist

### Phase 2: CI/CD Integration (Optional, Follow-up)
- Pytest fixtures and regression test suite
- GitHub Actions workflow with pass/fail gates
- Automated alerts on accuracy drops

### Phase 3: MCP Integration (Optional, Long-term)
- MCP server wrapper around Scorecard API
- Conversational evaluation triggers via Claude

## Technical Approach

### Architecture

```
RexLit Privilege Pipeline (offline)
    ↓
Scorecard Evaluation Module (online-only)
    ├─ REST API Adapter
    │  ├─ scorecard_port.py (port interface)
    │  └─ scorecard_evaluation_adapter.py (implementation)
    │
    ├─ Bootstrap Wiring
    │  └─ offline_gate.require("Scorecard evaluation")
    │
    ├─ CLI Integration
    │  └─ rexlit evaluate-privilege-model --online
    │
    └─ Mocked Adapter (for tests/offline)
       └─ scorecard_evaluation_adapter_mock.py (for CI without API key)
```

### Offline-First Design (Critical)

**Problem:** RexLit defaults to offline mode; Scorecard requires network access.

**Solution:** Enforce `--online` flag requirement with graceful degradation.

**Implementation:**

File: `rexlit/app/adapters/scorecard_evaluation_adapter.py`
```python
from rexlit.utils.offline import OfflineModeGate

class ScorecardPrivilegeAdapter(ScorecardEvaluationPort):
    def __init__(
        self,
        privilege_service: PrivilegeService,
        ledger: Ledger,
        project_id: str,
        api_key: Optional[str] = None,
        offline_gate: OfflineModeGate = None,
    ):
        # Require online mode
        if offline_gate:
            offline_gate.require("Scorecard evaluation")

        self.client = Scorecard(api_key=api_key or os.environ.get("SCORECARD_API_KEY"))
        # ... rest of init
```

File: `rexlit/bootstrap.py` (add to container creation)
```python
def _create_scorecard_evaluation_adapter(settings: Settings, offline_gate: OfflineModeGate) -> ScorecardEvaluationPort:
    """Create Scorecard adapter only if online mode enabled."""
    if not settings.online and not os.getenv("REXLIT_ONLINE"):
        # Return no-op stub or None for offline usage
        return ScorecardEvaluationAdapterStub()  # Logs warning, no-ops gracefully

    api_key = settings.get_scorecard_api_key()
    if not api_key:
        raise ConfigError("SCORECARD_API_KEY not configured; cannot create evaluation adapter")

    return ScorecardPrivilegeAdapter(
        privilege_service=container.privilege_service(),
        ledger=container.ledger(),
        project_id=settings.scorecard_project_id,
        api_key=api_key,
        offline_gate=offline_gate
    )
```

File: `rexlit/cli.py` (CLI command)
```python
@app.command()
def evaluate_privilege_model(
    testset_file: Path = typer.Option(...),
    testset_name: str = typer.Option(...),
    output: Optional[Path] = typer.Option(None),
    online: bool = typer.Option(False, "--online", help="Enable online mode (required for Scorecard)"),
):
    """Evaluate privilege model using Scorecard (requires --online flag)."""

    # This automatically requires --online
    if not online:
        raise typer.Exit(
            "Scorecard evaluation requires --online flag. "
            "Run: rexlit evaluate-privilege-model --testset ground_truth.jsonl --online"
        )

    # ... rest of implementation
```

**Testing offline:**

File: `tests/conftest.py` (pytest fixture)
```python
@pytest.fixture
def mock_scorecard_adapter():
    """Mock Scorecard adapter for testing without API key or network."""
    class MockScorecardAdapter(ScorecardEvaluationPort):
        def create_testset(self, name, description, testcases):
            return "mock_testset_123"

        def run_evaluation(self, testset_id, metric_ids, system_version=None):
            # Return pre-canned results for deterministic testing
            return EvaluationRun(
                run_id="mock_run_456",
                url="https://mock.scorecard.io/run/456",
                testset_id=testset_id,
                metric_ids=metric_ids,
                system_version=system_version
            )

        def get_results(self, run_id):
            return EvaluationResult(
                run_id=run_id,
                metric_averages={"accuracy": 0.92, "f1_score": 0.88},
                total_testcases=50,
                records=[]
            )

    return MockScorecardAdapter()
```

### Data Privacy & Security (Critical)

**Problem:** Sample JSONL shows full `document_text`, but issue says never send privileged data to Scorecard.

**Solution:** Use hashed references and redacted snippets only.

**Implementation:**

File: `examples/privilege_testcases.jsonl` (REVISED)
```json
{"document_hash": "sha256:abc123...", "document_metadata": {"type": "email", "custodian": "Jane Doe", "date": "2025-01-15"}, "snippet": "[REDACTED: Attorney-client email discussing legal strategy]", "is_privileged": true, "privilege_category": "attorney-client", "confidence_reasoning": "Redacted attorney-client communication", "document_id": "DOC-001", "source_file": "[REDACTED]"}
{"document_hash": "sha256:def456...", "document_metadata": {"type": "report", "custodian": "Finance", "date": "2025-01-10"}, "snippet": "Q4 2024 Financial Summary: Revenue $10M, Expenses $8M, Net Income $2M", "is_privileged": false, "privilege_category": "none", "confidence_reasoning": "Standard business financial report", "document_id": "DOC-002", "source_file": "FINANCE/reports/Q4_2024.pdf"}
```

**Never include in testcases:**
- Full document text or email bodies
- Client names or email addresses (use generic placeholders)
- Specific transaction amounts or confidential business details
- Actual file paths (use generic descriptions)

**Scorecard receives:**
- `document_hash` (SHA-256, no way to reverse to original)
- `snippet` (redacted/synthetic, <100 chars)
- `document_metadata` (custodian, doctype, date only; no internal IDs)
- Ground truth labels (`is_privileged`, `privilege_category`)

**Justification:** Aligns with RexLit's security posture (ADR 0006) and GDPR/privacy requirements.

### Metric Management (Clear Ownership)

**Problem:** Unclear who maintains Scorecard metrics or how IDs propagate into code/defaults.

**Solution:** Store metric IDs in config with update procedure.

**Implementation:**

File: `rexlit/config.py` (add to Settings model)
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
    reasoning_quality: str = Field(
        default="metric_reasoning_quality",
        description="Metric ID for explanation quality assessment"
    )
    confidence_calibration: str = Field(
        default="metric_confidence_calibration",
        description="Metric ID for confidence threshold validation"
    )

class Settings(BaseSettings):
    # ... existing fields ...

    scorecard_project_id: str = Field(
        default="",
        description="Scorecard project ID (required for evaluations)"
    )
    scorecard_metrics: ScorecardMetrics = Field(
        default_factory=ScorecardMetrics,
        description="Scorecard metric IDs for privilege evaluation"
    )
```

File: `.env.example` (update docs)
```
# Scorecard Integration (optional, requires --online flag)
SCORECARD_API_KEY=
SCORECARD_PROJECT_ID=
SCORECARD_METRIC_PRIVILEGE_ACCURACY=metric_privilege_accuracy
SCORECARD_METRIC_CATEGORY_ACCURACY=metric_category_accuracy
SCORECARD_METRIC_REASONING_QUALITY=metric_reasoning_quality
```

**Update Procedure (documented in CLAUDE.md):**
```markdown
### Updating Scorecard Metrics

When metrics are modified in the Scorecard UI:

1. Get new metric IDs from Scorecard dashboard:
   - Login to https://www.scorecard.io
   - Navigate to your project
   - Click "Metrics" tab
   - Copy each metric's ID

2. Update local config:
   ```bash
   export SCORECARD_METRIC_PRIVILEGE_ACCURACY="new_id_here"
   # ... other metrics
   ```

3. Or update `.env` file directly:
   ```
   SCORECARD_METRIC_PRIVILEGE_ACCURACY=new_id_here
   ```

4. Verify with CLI:
   ```bash
   rexlit evaluate-privilege-model --testset ground_truth.jsonl --online --validate-metrics
   ```
```

### Test Strategy (Brittle-Proof)

**Problem:** Single integration test checking real F1 threshold is brittle if testset/model changes.

**Solution:** Use mocked tests for CI; reserve real-score checks for manual/canary evaluations.

**Implementation:**

File: `tests/test_scorecard_evaluation.py` (UNIT TESTS - Always Pass)
```python
"""Unit tests for Scorecard adapter using mocked responses."""

import pytest
from unittest.mock import MagicMock, patch
from rexlit.app.adapters.scorecard_evaluation_adapter import ScorecardPrivilegeAdapter
from rexlit.app.ports.scorecard_port import EvaluationRun, EvaluationResult


@pytest.fixture
def mock_scorecard_client():
    """Mock Scorecard API client."""
    return MagicMock()


@pytest.fixture
def scorecard_adapter(mock_scorecard_client):
    """Scorecard adapter with mocked client."""
    adapter = ScorecardPrivilegeAdapter(
        privilege_service=MagicMock(),
        ledger=MagicMock(),
        project_id="test_project",
        api_key="test_key"
    )
    adapter.client = mock_scorecard_client
    return adapter


def test_create_testset(scorecard_adapter, mock_scorecard_client):
    """Test testset creation with mocked Scorecard."""
    mock_scorecard_client.testsets.create.return_value = MagicMock(id="testset_123")
    mock_scorecard_client.testcases.create.return_value = None

    testset_id = scorecard_adapter.create_testset(
        name="Test Privilege",
        description="Test evaluation",
        testcases=[{"json_data": {"document_hash": "abc", "is_privileged": True}}]
    )

    assert testset_id == "testset_123"
    mock_scorecard_client.testsets.create.assert_called_once()


def test_run_evaluation(scorecard_adapter, mock_scorecard_client):
    """Test evaluation run creation with mocked Scorecard."""
    mock_scorecard_client.runs.create.return_value = MagicMock(
        id="run_456",
        url="https://scorecard.io/run/456"
    )

    run = scorecard_adapter.run_evaluation(
        testset_id="testset_123",
        metric_ids=["metric_1", "metric_2"],
        system_version="v0.2.0"
    )

    assert isinstance(run, EvaluationRun)
    assert run.run_id == "run_456"


def test_offline_mode_blocks_evaluation(offline_gate):
    """Test that offline mode prevents Scorecard adapter creation."""
    offline_gate.online_enabled = False

    with pytest.raises(RuntimeError, match="requires online mode"):
        offline_gate.require("Scorecard evaluation")
```

File: `scripts/validate_scorecard_baseline.py` (MANUAL/CANARY - For Humans)
```python
"""
Manual script to validate Scorecard baseline evaluation.

Run this AFTER deploying Phase 1c to validate against real ground truth.
Requires: SCORECARD_API_KEY and real testset in Scorecard project.

Usage:
    SCORECARD_PROJECT_ID=314 python scripts/validate_scorecard_baseline.py
"""

from scorecard_ai import Scorecard
from rexlit.app.privilege_service import PrivilegeService
from rexlit.bootstrap import create_container

MINIMUM_F1 = 0.65
MINIMUM_RECALL = 0.75  # Avoid privilege waiver


def validate_baseline():
    """Run evaluation and report results."""
    client = Scorecard()
    container = create_container()
    privilege_service = container.privilege_service()

    # Load existing testset (created in Phase 1c)
    testset_id = "testset_baseline_privilege"  # Set during Phase 1c

    # Run evaluation
    run = client.runs.create(
        project_id=os.environ["SCORECARD_PROJECT_ID"],
        metric_ids=container.settings.scorecard_metrics.to_list(),
        testset_id=testset_id
    )

    print(f"Evaluation run: {run.url}")
    print("⏳ Waiting for scoring... (check Scorecard UI for real-time progress)")

    # Retrieve results (may need polling)
    # ... implementation

    # Check against minimums
    if results["f1_score"] < MINIMUM_F1:
        print(f"❌ F1 {results['f1_score']:.3f} below minimum {MINIMUM_F1}")
        return False

    if results["recall"] < MINIMUM_RECALL:
        print(f"❌ Recall {results['recall']:.3f} below minimum {MINIMUM_RECALL}")
        return False

    print(f"✅ Baseline validated: F1={results['f1_score']:.3f}, Recall={results['recall']:.3f}")
    return True
```

### Acceptance Criteria - Scoped by Phase

#### Phase 1a: Evaluation Adapter (First PR)
- [ ] Create `rexlit/app/ports/scorecard_port.py` with `ScorecardEvaluationPort` protocol
  - Methods: `create_testset()`, `run_evaluation()`, `get_results()`
  - Data classes: `EvaluationRun`, `EvaluationResult`
- [ ] Implement `rexlit/app/adapters/scorecard_evaluation_adapter.py`
  - Scorecard REST API client initialization
  - Testset schema definition (field mapping, JSON schema)
  - Integration with existing `PrivilegeService.classify_document()`
  - Audit logging of evaluation runs (using hash-preserving approach)
  - Graceful offline-mode handling with no-op stub adapter
- [ ] Wire adapter in `rexlit/bootstrap.py` with `offline_gate.require()` check
- [ ] Add `ScorecardEvaluationAdapterStub` for offline/test usage
- [ ] Unit tests with mocked Scorecard (100% pass rate, deterministic)
  - Test testset creation with field mapping
  - Test evaluation run creation
  - Test result retrieval and aggregation
  - Test offline mode blocks adapter creation
- [ ] Update `CLAUDE.md` with environment variable setup
- [ ] All existing tests still pass (146/146)

#### Phase 1b: CLI Integration & Documentation (Second PR)
- [ ] Add `rexlit evaluate-privilege-model` command to CLI
  - Required: `--testset-file`, `--testset-name`, `--online`
  - Optional: `--metric-ids`, `--system-version`, `--output`
  - Enforce `--online` flag (error message if missing)
- [ ] Create `docs/SCORECARD_EVALUATION.md`
  - Step-by-step setup (account creation, API key, project creation)
  - Data format spec (what's redacted, why)
  - CLI command usage examples
  - How to interpret results (F1, precision, recall definitions)
  - Troubleshooting (API key issues, offline mode, etc.)
- [ ] Create `docs/PRIVILEGE_EVALUATION_METHODOLOGY.md`
  - Legal defensibility justification (TAR compliance, EDRM standards)
  - Testset design rationale (coverage, stratification, attorney review)
  - Metric definitions (what each metric measures, how they align with legal standards)
  - How to validate ground truth labels
  - How to update metrics without breaking CI/CD
- [ ] Add config fields to `rexlit/config.py`
  - `scorecard_project_id`
  - `scorecard_metrics` (nested model with metric IDs)
  - Document in `.env.example`
- [ ] Integration test (mocked Scorecard)
  - Smoke test that CLI command parses arguments correctly
  - Mocked adapter returns expected data structures
  - Does NOT run against real Scorecard (no flakiness in CI)
- [ ] Update `CLAUDE.md` with CLI usage and metric update procedure
- [ ] All existing tests still pass (146/146)

#### Phase 1c: Baseline Evaluation (Third PR - Optional for First Release)
- [ ] Prepare ground truth testset (50-100 documents)
  - Attorney-reviewed labels (privileged/non-privileged with category)
  - Redacted/synthetic testcases (no actual privileged information)
  - Document composition: coverage of email, memo, report, contract types
  - Diverse custodians and date ranges
- [ ] Create Scorecard project and import testset
- [ ] Define 4-5 metrics in Scorecard UI
  - Privilege Accuracy (binary, is_privileged match?)
  - Category Accuracy (for privileged docs, does category match?)
  - Reasoning Quality (does explanation cite evidence and legal principles?)
  - Confidence Calibration (heuristic: documents with 80-85% confidence, actual accuracy?)
  - (Optional) False Positive Cost (risk assessment for incorrectly marked privileged)
- [ ] Run evaluation against current Groq + Harmony+ configuration
- [ ] Document results in `SCORECARD_BASELINE_RESULTS.md`
  - Testset composition (sizes, types, custodians)
  - Per-metric results (averages, ranges, confidence intervals)
  - Baseline F1, precision, recall, and confidence calibration
  - Analysis of any edge cases or failure modes
- [ ] Create manual validation script: `scripts/validate_scorecard_baseline.py`
- [ ] Create CI/CD readiness checklist for Phase 2

#### Phase 2: CI/CD Integration (Optional Follow-up PR)
- [ ] Add pytest fixture for loading testset from Scorecard
- [ ] Regression test suite with mocked Scorecard
  - Verifies minimum F1 threshold against pre-canned results
- [ ] GitHub Actions workflow for nightly evaluations
  - Runs against real Scorecard with real API key (secrets management)
  - Alerts if F1 drops >5% from baseline
- [ ] Metric validation command: `rexlit evaluate-privilege-model --validate-metrics`
  - Confirms metric IDs are accessible and current

## Dependencies & Prerequisites

**Required (Phase 1a-1b):**
- Python 3.8+
- `scorecard-ai` SDK: `pip install scorecard-ai`
- Network access for API calls (during evaluation only, not runtime)
- Existing RexLit dependencies (no new breaking changes)

**Recommended (Phase 1c):**
- Scorecard account (free tier sufficient for initial baseline)
- 50-100 labeled documents with attorney review
- 1-2 hours for metric definition in Scorecard UI

**Optional (Phase 2+):**
- GitHub Actions
- MCP framework (`mcp[cli]`)

**External Dependencies:**
- Scorecard API: `https://api.scorecard.io` (requires SCORECARD_API_KEY)
- Scorecard MCP: `https://mcp.scorecard.io/mcp` (Phase 3 only)

## Risk Analysis & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|-----------|
| Ground truth data quality | Results invalid if labels incorrect | Medium | Attorney review; document labeling guidelines in PR; validate sample against existing test results |
| Testset contains privileged information | Confidentiality breach, legal exposure | High | Use only redacted/synthetic testcases; hash references; policy review before Phase 1c |
| Scorecard API quota exceeded | Evaluation blocked or unexpected costs | Low | Monitor free tier usage; Growth tier ($299/mo) cost-justified by risk mitigation |
| Metric IDs drift from code | CI/CD breaks, confusing errors | Medium | Store metric IDs in config; document update procedure; add validation CLI command |
| Offline mode exceptions leak into tests | Non-deterministic CI failures | Medium | Mock Scorecard responses in all tests; manual validation is separate from automated tests |
| Confidence calibration shows poor alignment | Thresholds need recalibration | Medium | Treat baseline as diagnostic; use results to inform future threshold tuning; no breaking changes required |
| Phase creep: all 3 sub-PRs block each other | Delivery delayed, scope confusion | High | **Clear PR boundaries** (see Acceptance Criteria); Phase 1a and 1b are independent PRs; Phase 1c is optional for release |

**Data Privacy Mitigation (Critical):**
- All testcases redacted before Scorecard upload
- Security review of `examples/privilege_testcases.jsonl` before committing
- CLAUDE.md policy: "Never send actual privileged information to external services"

**Offline-First Mitigation:**
- `OfflineModeGate.require()` enforces `--online` flag
- Mocked stub adapter for offline/test runs
- No breaking changes to CLI (evaluation is optional)

## Resource Requirements

**Implementation Timeline:**
- Phase 1a (Adapter): 6-8 hours
  - Port + adapter implementation: 3h
  - Bootstrap wiring: 1h
  - Unit tests: 2-3h

- Phase 1b (CLI + Docs): 6-8 hours
  - CLI command: 2h
  - Documentation: 3-4h
  - Integration test (mocked): 1-2h

- Phase 1c (Baseline): 8-12 hours (can defer)
  - Testset preparation & attorney review: 4-6h
  - Scorecard setup & metric definition: 2-3h
  - Evaluation run & results analysis: 2-3h

**Team:**
- 1 engineer (primary: adapter, CLI, bootstrap)
- 1 attorney/legal expert (testcase review, metric definitions)
- 1 code reviewer (architecture, security, offline handling)

**Infrastructure:**
- Scorecard: Free tier (100K scores) or Growth tier ($299/mo)
- Storage: <1MB for testset + results
- No new cloud infrastructure required

## Future Considerations

### Extensibility

- **Multi-stage evaluation**: Extend to evaluate responsiveness (Stage 2) and redaction detection (Stage 3)
- **Model versioning**: Track performance across Groq model updates (v0 → v1, if released)
- **Policy versioning**: A/B test different privilege policies (Harmony v1.0 vs v1.1 vs custom)
- **Custodian segmentation**: Identify custodians with lower privilege accuracy (e.g., in-house counsel)
- **Document type segmentation**: Benchmark email vs. memo vs. contract separately

### Integration Opportunities

- **Human-in-the-loop**: Use Scorecard UI to manually review/correct misclassifications
- **Active learning**: Automatically suggest high-uncertainty cases for attorney labeling
- **Cost optimization**: Adjust 85%/50% thresholds to minimize LLM API costs while maintaining F1 > 0.65
- **Policy evolution**: Use failed cases to suggest improvements to Harmony+ policy

### Long-term Vision

If successful, expand Scorecard evaluation to:
- Bates numbering accuracy (page header/footer extraction)
- Redaction plan correctness (sensitive span detection)
- Document extraction quality (OCR, text extraction from PDFs)
- Search relevance ranking (Tantivy index quality)
- Deduplication accuracy (hash-based duplicate detection)

## Documentation Plan

**Files to create/update:**

1. **`docs/SCORECARD_EVALUATION.md`** (NEW, Phase 1b)
   - Setup: Account creation, API key, project creation
   - Data privacy: What's redacted, why
   - CLI usage: Examples of `evaluate-privilege-model` command
   - Result interpretation: F1, precision, recall, confidence definitions
   - Troubleshooting: Common errors and solutions

2. **`docs/PRIVILEGE_EVALUATION_METHODOLOGY.md`** (NEW, Phase 1b)
   - Legal defensibility: TAR compliance, EDRM standards, Rule 502 context
   - Testset design: Coverage strategy, stratification, attorney review process
   - Metric definitions: What each metric measures, alignment with legal standards
   - Validation: How to verify ground truth labels, calibration approach
   - Maintenance: How to update metrics without breaking CI/CD

3. **`SCORECARD_BASELINE_RESULTS.md`** (NEW, Phase 1c - optional for initial release)
   - Testset composition: Sizes, types, custodians, coverage
   - Baseline metrics: F1, precision, recall by metric
   - Confidence calibration: Actual accuracy in each confidence bucket
   - Edge case analysis: Which types of documents are hardest to classify
   - Recommendations: Threshold adjustments, policy improvements

4. **`CLAUDE.md`** (UPDATE)
   - Add "Privilege Model Evaluation" section to "Common Development Tasks"
   - Environment variables: `SCORECARD_API_KEY`, `SCORECARD_PROJECT_ID`, metric IDs
   - CLI command: `rexlit evaluate-privilege-model --online`
   - Metric maintenance: How to update metric IDs when they change in Scorecard
   - Data privacy: Policy on testcase redaction

5. **`.env.example`** (UPDATE)
   - Add Scorecard configuration variables
   - Add metric ID variables with defaults

6. **Code docstrings:**
   - Numpy-style docstrings in adapter and port interface
   - Explain offline-mode behavior and why `--online` is required
   - Document data privacy constraints

## References & Research

### Internal References

- Current Groq adapter: [rexlit/app/adapters/groq_privilege.py:1-346](rexlit/app/adapters/groq_privilege.py)
- Privilege service orchestration: [rexlit/app/privilege_service.py:1-333](rexlit/app/privilege_service.py)
- Privilege port interface: [rexlit/app/ports/privilege.py:20-77](rexlit/app/ports/privilege.py#L20-L77)
- Bootstrap wiring: [rexlit/bootstrap.py:415-520](rexlit/bootstrap.py#L415-L520)
- Offline-first gating: [rexlit/utils/offline.py:1-49](rexlit/utils/offline.py)
- Test infrastructure: [scripts/test_groq_privilege.py](scripts/test_groq_privilege.py)
- Integration tests: [tests/test_privilege_classification.py](tests/test_privilege_classification.py)
- Current policy: [rexlit/policies/juul_privilege_stage1_harmony_plus.txt](rexlit/policies/juul_privilege_stage1_harmony_plus.txt)
- ADR on privilege: [docs/adr/0008-privilege-safeguard-integration.md](docs/adr/0008-privilege-safeguard-integration.md)

### External References

**Scorecard Documentation:**
- Main site: https://www.scorecard.io
- API reference: https://docs.scorecard.io/api-reference/overview
- Python SDK: https://github.com/scorecard-ai/scorecard-python
- MCP server: https://github.com/scorecard-ai/scorecard-mcp

**E-Discovery Standards:**
- EDRM TAR Guidelines: https://edrm.net/resources/frameworks-and-standards/technology-assisted-review/
- TAR Best Practices PDF: https://edrm.net/wp-content/uploads/2019/02/TAR-Guidelines-Final.pdf

**LLM Evaluation:**
- MLflow Evaluations: https://mlflow.org/docs/latest/llm-evaluate/
- RAGAS Framework: https://docs.ragas.io/

**Related RexLit PRs:**
- #28: Groq adapter and OpenAI dependency
- #32: Harmony+ policy rollout
- #31: Phase 2 CLAUDE.md updates

## Labels

- `enhancement`
- `evaluation`
- `privilege-classification`
- `quality-assurance`
- `phase-3`
- `legal-defensibility`
- `optional`

---

**Issue Version:** 2.0 (Refined with adaptations for scope clarity, offline-first design, data privacy, and metric ownership)
