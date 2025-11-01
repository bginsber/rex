# PII & Privilege Detection Integration: Executive Summary

**Date:** 2025-10-28
**Purpose:** Quick reference for RexLit PII redaction and privilege recognition
**Full Documentation:** See `PII_PRIVILEGE_INTEGRATION_DOCS.md`

---

## TL;DR: Key Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **PII Detection** | Microsoft Presidio | Industry-standard, NLP+regex hybrid, extensible, actively maintained |
| **Privilege Detection** | Hybrid (Regex + Embeddings) | Combines keyword triggers with semantic context (Sentence Transformers) |
| **Embedding Model** | all-MiniLM-L6-v2 | Fast (CPU-friendly), 384 dims, good semantic understanding, 80MB |
| **Architecture** | Ports & Adapters | PIIDetectorPort, PrivilegeDetectorPort, existing RedactionService |
| **Redaction Pattern** | Plan/Apply (2-phase) | Generate plan → Review → Apply (ADR 0006 compliance) |

---

## Installation & Versions

Presidio dependencies are already included in `pyproject.toml`. Add the following for privilege detection:

```toml
# pyproject.toml
sentence-transformers = "^2.2.0"
torch = "^2.0.0"  # CPU version
```

One-time model downloads:

```bash
# spaCy model (~500MB)
python -m spacy download en_core_web_lg

# Sentence Transformer (~80MB): auto-downloads on first use
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

**Python Requirement:** 3.11+

---

## Quick Start Examples

### 1. Detect PII in Text

```bash
# Analyze document for PII
rexlit redact plan ./docs/sensitive.pdf --pii-types SSN EMAIL PHONE

# This creates:
# - ./docs/sensitive.redaction-plan.enc  (encrypted JSONL plan)
```

### 2. Apply Redactions

```bash
# Review plan, then apply
rexlit redact apply ./docs/sensitive.redaction-plan.enc --output ./redacted/

# Safety checks:
# - Verifies PDF hash matches plan
# - Aborts if document changed since planning
```

### 3. Privilege Detection

```bash
# Detect privileged communications
rexlit redact plan ./docs/emails/ --privilege --threshold 0.75

# Hybrid approach:
# - Regex: "attorney-client", "work product", "privileged"
# - Embeddings: Semantic similarity to exemplar privileged text
```

---

## Code Snippets

### Presidio (PII Detection)

```python
from presidio_analyzer import AnalyzerEngine

# Initialize engine (loads spaCy model)
analyzer = AnalyzerEngine()

# Detect PII entities
results = analyzer.analyze(
    text="John Doe's SSN is 078-05-1120, email john@example.com",
    entities=["SSN", "EMAIL", "PHONE_NUMBER", "CREDIT_CARD"],
    language="en"
)

# Results: [RecognizerResult(entity_type='SSN', start=17, end=28, score=0.85), ...]
```

### Presidio Anonymizer (Redaction)

```python
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

anonymizer = AnonymizerEngine()

# Redact (replace with type)
redacted = anonymizer.anonymize(
    text="SSN: 078-05-1120",
    analyzer_results=results,
    operators={"SSN": OperatorConfig("replace", {"new_value": "[REDACTED-SSN]"})}
)
# Output: "SSN: [REDACTED-SSN]"
```

### Custom Presidio Recognizer (Privilege Keywords)

```python
from presidio_analyzer import Pattern, PatternRecognizer

privilege_patterns = [
    Pattern(name="attorney_client", regex=r"\battorney[- ]client\b", score=0.7),
    Pattern(name="work_product", regex=r"\bwork product\b", score=0.7),
    Pattern(name="privileged", regex=r"\bprivileged\b", score=0.5),
]

privilege_recognizer = PatternRecognizer(
    supported_entity="PRIVILEGE",
    patterns=privilege_patterns,
    context=["confidential", "legal", "counsel", "attorney"]
)

analyzer.registry.add_recognizer(privilege_recognizer)
```

### Sentence Transformers (Privilege Embeddings)

```python
from sentence_transformers import SentenceTransformer, util
import numpy as np

# Load model (cached locally, ~80MB)
model = SentenceTransformer('all-MiniLM-L6-v2')

# Privileged exemplars (from training corpus)
exemplars = [
    "This email contains attorney-client privileged communications.",
    "Please provide legal advice on this matter under work product doctrine.",
    "Confidential legal opinion prepared by counsel."
]
exemplar_embeddings = model.encode(exemplars, convert_to_tensor=True)

# Check if candidate text is privileged
candidate = "Can you review this contract from a legal perspective?"
candidate_embedding = model.encode(candidate, convert_to_tensor=True)

# Compute cosine similarity
similarities = util.cos_sim(candidate_embedding, exemplar_embeddings)
max_similarity = similarities.max().item()

if max_similarity > 0.75:  # Threshold
    print(f"PRIVILEGED (score: {max_similarity:.2f})")
```

---

## Port Interfaces (Hexagonal Architecture)

### PIIDetectorPort

```python
from typing import Protocol
from pydantic import BaseModel

class PIIEntity(BaseModel):
    """Detected PII entity."""
    entity_type: str      # "SSN", "EMAIL", "PHONE_NUMBER", etc.
    start: int            # Character offset
    end: int              # Character offset
    score: float          # Confidence (0.0-1.0)
    text: str             # Matched text

class PIIDetectorPort(Protocol):
    """Port for PII detection."""

    def detect(
        self,
        text: str,
        *,
        entities: list[str] | None = None,
        language: str = "en",
    ) -> list[PIIEntity]:
        """Detect PII entities in text."""
        ...

    def supported_entities(self) -> list[str]:
        """Return list of supported entity types."""
        ...

    def is_online(self) -> bool:
        """False for Presidio (runs locally)."""
        ...
```

### PrivilegeDetectorPort

```python
class PrivilegeMatch(BaseModel):
    """Detected privileged content."""
    start: int            # Character offset
    end: int              # Character offset
    score: float          # Confidence (0.0-1.0)
    method: str           # "regex" or "semantic"
    trigger: str          # Keyword/phrase that triggered match

class PrivilegeDetectorPort(Protocol):
    """Port for privilege detection."""

    def detect(
        self,
        text: str,
        *,
        threshold: float = 0.75,
    ) -> list[PrivilegeMatch]:
        """Detect privileged content using hybrid approach."""
        ...

    def is_online(self) -> bool:
        """False (embedding model cached locally)."""
        ...
```

---

## Parameter Recommendations

### Presidio Parameters

| Parameter | Recommended | Notes |
|-----------|-------------|-------|
| **entities** | `["SSN", "EMAIL", "PHONE_NUMBER", "CREDIT_CARD"]` | Most common PII types |
| **language** | `"en"` | English (other languages supported) |
| **score_threshold** | 0.5 | Minimum confidence (lower = more sensitive) |
| **allow_list** | Contextual | Whitelist known non-PII (e.g., company emails) |

**Supported Entities:** SSN, EMAIL, PHONE_NUMBER, CREDIT_CARD, US_PASSPORT, US_DRIVER_LICENSE, MEDICAL_LICENSE, IP_ADDRESS, IBAN_CODE, etc. (50+ built-in)

### Privilege Detection Parameters

| Parameter | Recommended | Notes |
|-----------|-------------|-------|
| **threshold** | 0.75 | Semantic similarity cutoff (0.0-1.0) |
| **context_window** | 200 chars | Text surrounding keyword to embed |
| **model** | `all-MiniLM-L6-v2` | Fast, CPU-friendly, 384 dims |

**Trigger Keywords:** "attorney-client", "work product", "privileged", "counsel", "legal advice"

### Redaction Parameters

| Parameter | Recommended | Notes |
|-----------|-------------|-------|
| **operator** | `"replace"` | Replace with `[REDACTED-TYPE]` |
| **force** | `false` | Require hash match (safety) |
| **preview** | `true` | Dry-run before applying |

---

## Performance Estimates

### PII Detection (1000 documents, avg 5 pages)

| Stage | Time | Notes |
|-------|------|-------|
| spaCy model load | 2-3 sec | One-time per process |
| Analysis | 5-10 sec | ~100-200 docs/sec (CPU) |
| Plan generation | 1-2 sec | Encrypted JSONL write |
| **Total** | **8-15 sec** | Parallelizable across documents |

### Privilege Detection (1000 emails, avg 500 words)

| Stage | Time | Notes |
|-------|------|-------|
| Model load | 1-2 sec | One-time per process |
| Embedding generation | 10-20 sec | ~50-100 texts/sec (CPU) |
| Similarity computation | <1 sec | Fast cosine similarity |
| **Total** | **12-23 sec** | Can batch embed (GPU: ~10x faster) |

### Memory (Per Process)

| Component | Size | Notes |
|-----------|------|-------|
| spaCy model (`en_core_web_lg`) | ~500 MB | Loaded in RAM |
| Sentence Transformer | ~80 MB | Model weights |
| Presidio overhead | ~50 MB | Recognizers, registry |
| **Total** | **~630 MB** | Reasonable for local processing |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    CLI Layer                        │
│  rexlit redact plan PATH --pii-types SSN EMAIL      │
│  rexlit redact apply PLAN --output ./redacted/      │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│              Bootstrap (DI Container)               │
│  - PresidioAdapter (PIIDetectorPort)                │
│  - HybridPrivilegeAdapter (PrivilegeDetectorPort)   │
│  - PDFStampAdapter (existing)                       │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│           RedactionService (existing)               │
│  - plan() → Generate encrypted JSONL plan           │
│  - apply() → Verify hash, apply redactions          │
│  - validate_plan() → Check plan integrity           │
└──────────────────┬──────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
┌─────────────┐         ┌─────────────┐
│  Presidio   │         │  Sentence   │
│  Analyzer   │         │ Transformers│
└─────────────┘         └─────────────┘
       │                       │
       └───────────┬───────────┘
                   ▼
            ┌─────────────┐
            │ PDF Stamper │ (PyMuPDF/pikepdf)
            └─────────────┘
```

**Key Points:**
- RedactionService already exists (rexlit/app/redaction_service.py)
- Plan/apply pattern enforced (ADR 0006)
- Encrypted JSONL plans (already implemented)
- Offline-first: All models run locally

---

## Files to Create/Modify

### New Port Interfaces
- `rexlit/app/ports/pii_detector.py`
- `rexlit/app/ports/privilege_detector.py`

### New Adapters
- `rexlit/app/adapters/presidio_adapter.py`
- `rexlit/app/adapters/hybrid_privilege_adapter.py`

### Modify Existing
- `rexlit/app/redaction_service.py`
  - Wire PIIDetectorPort and PrivilegeDetectorPort
  - Implement PII/privilege detection in `plan()` method
- `rexlit/bootstrap.py`
  - Add `pii_detector` and `privilege_detector` to container
- `rexlit/cli.py`
  - Add `redact` Typer group with `plan` and `apply` commands
  - Add `--pii-types`, `--privilege`, `--threshold` flags

### Configuration
- Update `rexlit/config.py`:
  - `pii_score_threshold: float = 0.5`
  - `privilege_threshold: float = 0.75`
  - `privilege_model: str = "all-MiniLM-L6-v2"`
  - `spacy_model: str = "en_core_web_lg"`

### Tests
- `tests/test_pii_detector.py`
- `tests/test_privilege_detector.py`
- `tests/test_redaction_integration.py`

---

## Offline-First Compliance

**Online Operations:**
- None! All models run locally

**Offline Operations:**
- Presidio analysis (spaCy + regex, local)
- Sentence Transformer embeddings (local model cache)
- Plan generation (local file I/O)
- Plan application (local PDF manipulation)

**Model Downloads (One-Time Setup):**
```bash
# Download spaCy model (requires internet once)
python -m spacy download en_core_web_lg

# Download sentence transformer (auto-cached on first use)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

**After setup:** All operations are 100% offline.

---

## Audit Logging

**PII Detection Operation:**
```json
{
  "timestamp": "2025-10-28T10:00:00Z",
  "operation": "pii_detect",
  "inputs": ["document.pdf"],
  "outputs": ["document.redaction-plan.enc"],
  "args": {
    "entities": ["SSN", "EMAIL", "PHONE_NUMBER"],
    "matches": 12,
    "latency_ms": 500,
    "plan_id": "sha256:abc123..."
  }
}
```

**Privilege Detection Operation:**
```json
{
  "timestamp": "2025-10-28T10:05:00Z",
  "operation": "privilege_detect",
  "inputs": ["emails/"],
  "outputs": ["emails.redaction-plan.enc"],
  "args": {
    "threshold": 0.75,
    "matches": 3,
    "method": "hybrid",
    "latency_ms": 1200,
    "plan_id": "sha256:def456..."
  }
}
```

---

## Error Handling

### Presidio Errors

```python
from presidio_analyzer import AnalyzerEngine

try:
    results = analyzer.analyze(text, entities=["SSN"])
except ValueError as e:
    # Invalid entity type
    logger.error(f"Invalid entity: {e}")
except Exception as e:
    # Model not loaded, other errors
    logger.error(f"Presidio analysis failed: {e}")
```

### Sentence Transformer Errors

```python
from sentence_transformers import SentenceTransformer

try:
    model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    # Model not downloaded
    logger.error(f"Failed to load model: {e}")
    logger.info("Run: python -m sentence_transformers download all-MiniLM-L6-v2")
```

### Common Issues

1. **spaCy model not found:**
   ```bash
   python -m spacy download en_core_web_lg
   ```

2. **Sentence Transformer cache miss:**
   - First run will auto-download (~80MB)
   - Set `TRANSFORMERS_CACHE` env var to control location

3. **Plan hash mismatch:**
   - Document changed after plan generation
   - Use `--force` to override (not recommended)

---

## Security Considerations

**PII Data Handling:**
- Plans encrypted with Fernet key (existing RexLit pattern)
- Never log raw PII text (only offsets/types)
- Audit trail logs detection counts, not content

**Model Security:**
- All models run locally (no network calls)
- Models downloaded from trusted sources (HuggingFace, spaCy)
- Verify checksums on first download

**Privilege Detection:**
- Exemplar embeddings stored encrypted (if persisted)
- Threshold tunable to control false positives/negatives
- Human review recommended before applying

---

## Testing Strategy

### Unit Tests
- PresidioAdapter: Mock AnalyzerEngine responses
- HybridPrivilegeAdapter: Mock model inference
- RedactionService: Verify plan generation logic

### Integration Tests
- End-to-end: Detect PII → Generate plan → Apply redactions
- Privilege detection: Regex + embeddings hybrid
- Plan integrity: Hash verification, encryption

### Performance Tests
- Throughput: Documents/second for PII detection
- Memory: Track model loading overhead
- Latency: P50/P95/P99 for detection operations

### Regression Tests
- Deterministic plan IDs (hash-based)
- Audit ledger integrity
- Offline-only operations (no network calls)

---

## Success Criteria

- [ ] `rexlit redact plan PATH --pii-types SSN EMAIL` generates encrypted plan
- [ ] `rexlit redact apply PLAN --output ./redacted/` applies redactions to PDFs
- [ ] Presidio detects 15+ PII entity types with >90% precision
- [ ] Privilege detection achieves >80% recall on test corpus
- [ ] All operations run offline (no network after model download)
- [ ] Structured audit entries for all redaction operations
- [ ] Tests pass: `pytest -v --no-cov` (100% passing)
- [ ] Documentation updated: README.md, REDACTION-GUIDE.md

---

## Next Steps

1. **Read Full Documentation:** `/Users/bg/Documents/Coding/rex/PII_PRIVILEGE_INTEGRATION_DOCS.md` (to be created)
2. **Review Next_plan.md:** Work breakdown for implementation
3. **Create Port Interfaces:** PIIDetectorPort, PrivilegeDetectorPort
4. **Implement Adapters:** PresidioAdapter, HybridPrivilegeAdapter
5. **Wire into RedactionService:** Update `plan()` method
6. **Update CLI:** Add `redact plan/apply` commands
7. **Write Tests:** Achieve 100% passing
8. **Update Docs:** README, REDACTION-GUIDE.md

---

## Quick Links

- **Presidio GitHub:** https://github.com/microsoft/presidio
- **Presidio Docs:** https://microsoft.github.io/presidio/
- **Sentence Transformers:** https://www.sbert.net/
- **spaCy:** https://spacy.io/
- **ADR 0006 (Plan/Apply Pattern):** `docs/adr/0006-redaction-plan-apply-model.md`

---

**Document Version:** 1.0
**Last Updated:** 2025-10-28
**Compiled By:** Claude Code Planning Assistant
