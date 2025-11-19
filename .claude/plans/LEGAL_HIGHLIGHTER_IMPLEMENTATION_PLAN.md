# Legal Highlighter Implementation Plan

**Status:** Planning Phase
**Target Release:** v0.3.0-m2
**Architecture Pattern:** Reuse redaction pipeline with highlight-specific adapters
**Date:** 2025-11-19

---

## Executive Summary

This plan outlines the implementation of a "legal highlighter" feature that reuses RexLit's existing redaction pipeline architecture to provide confidence-based, color-coded visual annotations for legal review. The system will detect and highlight key concepts (emails, legal advice, party mentions, privilege markers) and present them as a visual heatmap in the web UI, enabling attorneys to triage high-value documents first.

**Core Innovation:** Transform the redaction plan/apply pattern into a highlight plan/render pattern, leveraging existing port interfaces and LLM classification infrastructure.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Highlight Plan Schema](#highlight-plan-schema)
3. [Port Interfaces](#port-interfaces)
4. [Domain Services](#domain-services)
5. [CLI Commands](#cli-commands)
6. [Web UI Integration](#web-ui-integration)
7. [Implementation Phases](#implementation-phases)
8. [Testing Strategy](#testing-strategy)
9. [Security Considerations](#security-considerations)
10. [Performance Targets](#performance-targets)

---

## Architecture Overview

### Reusing the Redaction Pipeline

The legal highlighter reuses the proven redaction architecture with concept-specific adaptations:

```
┌─────────────────────────────────────────────────────────────┐
│ REDACTION PIPELINE (Existing)                               │
├─────────────────────────────────────────────────────────────┤
│ 1. PIIPort → Detect entities (SSN, EMAIL, PHONE)           │
│ 2. RedactionService → Generate coordinates + confidence     │
│ 3. Plan Format → JSONL with actions, hash verification     │
│ 4. Apply → StampPort applies black boxes to PDF            │
└─────────────────────────────────────────────────────────────┘
                             ↓ ADAPT
┌─────────────────────────────────────────────────────────────┐
│ HIGHLIGHT PIPELINE (New)                                    │
├─────────────────────────────────────────────────────────────┤
│ 1. ConceptPort → Detect concepts (EMAIL, LEGAL_ADVICE, etc)│
│ 2. HighlightService → Generate spans + confidence + color   │
│ 3. Plan Format → JSONL with highlights, hash verification  │
│ 4. Render → Web UI overlays color-coded annotations        │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

1. **Plan/Render Pattern** (mirrors redaction plan/apply):
   - Phase 1: `rexlit highlight plan` generates read-only highlight coordinates
   - Phase 2: Web UI renders highlights without modifying source documents
   - Hash verification ensures highlights match current document state

2. **Concept Detection Strategy** (mirrors PII detection):
   - Pattern-based pre-filtering (fast, offline, ≥85% confidence)
   - LLM escalation for uncertain cases (50-84% confidence)
   - Confidence-based color shading (darker = higher confidence)

3. **Ports and Adapters**:
   - New `ConceptPort` interface (similar to `PIIPort`)
   - Adapters: `PatternConceptAdapter` (offline), `SafeguardConceptAdapter` (LLM)
   - `HighlightService` orchestrates detection and plan generation

4. **Web UI Rendering**:
   - Highlight plans embedded in manifest or served via API
   - PDF.js or custom viewer renders color overlays
   - Heatmap scroll bar shows document "temperature"

---

## Highlight Plan Schema

### JSONL Schema (v1)

Following ADR 0004 (JSONL Schema Versioning), each highlight plan entry:

```json
{
  "schema_id": "highlight_plan",
  "schema_version": 1,
  "producer": "rexlit-0.3.0",
  "produced_at": "2025-11-19T14:30:00Z",

  "document": "/data/discovery/email_chain_2024.pdf",
  "sha256": "a1b2c3d4e5f6...",
  "plan_id": "highlight_abc123...",

  "highlights": [
    {
      "concept": "EMAIL_COMMUNICATION",
      "category": "communication",
      "text": "From: attorney@lawfirm.com",
      "confidence": 0.95,
      "start": 120,
      "end": 148,
      "page": 1,
      "color": "cyan",
      "shade_intensity": 0.95,
      "reasoning_hash": "sha256_of_reasoning",
      "reasoning_summary": "Email header detected with high confidence"
    },
    {
      "concept": "LEGAL_ADVICE",
      "category": "privilege",
      "text": "Our legal analysis suggests...",
      "confidence": 0.88,
      "start": 450,
      "end": 620,
      "page": 2,
      "color": "magenta",
      "shade_intensity": 0.88,
      "reasoning_hash": "sha256_of_reasoning",
      "reasoning_summary": "Attorney opinion language with legal conclusions"
    },
    {
      "concept": "KEY_PARTY",
      "category": "entity",
      "text": "Patent #455",
      "confidence": 0.92,
      "start": 890,
      "end": 900,
      "page": 3,
      "color": "yellow",
      "shade_intensity": 0.92,
      "reasoning_hash": "sha256_of_reasoning",
      "reasoning_summary": "Specific patent number from case facts"
    }
  ],

  "annotations": {
    "concept_types": ["EMAIL_COMMUNICATION", "LEGAL_ADVICE", "KEY_PARTY"],
    "detector": "SafeguardConceptAdapter",
    "highlight_count": 3,
    "pages_with_highlights": [1, 2, 3],
    "confidence_range": [0.88, 0.95],
    "color_palette": {
      "cyan": "communication",
      "magenta": "privilege/legal_advice",
      "yellow": "key_entities",
      "red": "hot_doc_indicators",
      "green": "responsive_content"
    }
  },

  "notes": "Highlighted 3 key concepts across 3 pages"
}
```

### Concept Categories

| Category | Color | Use Case | Examples |
|----------|-------|----------|----------|
| `communication` | Cyan | Email headers, sender/recipient | "From: john@company.com" |
| `privilege` | Magenta | Legal advice, ACP markers | "Our counsel advises..." |
| `entity` | Yellow | Key parties, patents, contracts | "Patent #455", "Martinez" |
| `hotdoc` | Red | Smoking guns, admissions | "I know this violates..." |
| `responsive` | Green | Relevant to case topics | Claim terms, allegations |

### Shade Intensity Algorithm

```python
def compute_shade_intensity(confidence: float) -> float:
    """
    Map confidence [0.0, 1.0] to shade intensity [0.3, 1.0].

    Low confidence (0.5) → light shade (0.3 opacity)
    High confidence (1.0) → dark shade (1.0 opacity)
    """
    if confidence < 0.5:
        return 0.3  # Minimum visible threshold
    return 0.3 + (confidence - 0.5) * 1.4  # Linear scale
```

---

## Port Interfaces

### ConceptPort (New)

Similar to `PIIPort`, but for legal concept detection:

```python
# rexlit/app/ports/concept.py

from typing import Protocol
from pydantic import BaseModel


class ConceptFinding(BaseModel):
    """Legal concept detection finding."""

    concept: str  # "EMAIL_COMMUNICATION", "LEGAL_ADVICE", etc.
    category: str  # "communication", "privilege", "entity", etc.
    text: str
    confidence: float
    start: int
    end: int
    page: int | None = None
    reasoning_hash: str | None = None
    reasoning_summary: str | None = None


class ConceptPort(Protocol):
    """Port interface for legal concept detection.

    Adapters:
    - PatternConceptAdapter (offline, regex-based)
    - SafeguardConceptAdapter (LLM-based, online)

    Side effects: None (read-only analysis).
    """

    def analyze_text(
        self,
        text: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        """Analyze text for legal concepts.

        Args:
            text: Text to analyze
            concepts: Concept types to detect (None = all)
            threshold: Minimum confidence threshold

        Returns:
            List of concept findings with confidence scores
        """
        ...

    def analyze_document(
        self,
        path: str,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> list[ConceptFinding]:
        """Analyze document for legal concepts.

        Args:
            path: Document path
            concepts: Concept types to detect (None = all)
            threshold: Minimum confidence threshold

        Returns:
            List of concept findings with page numbers
        """
        ...

    def get_supported_concepts(self) -> list[str]:
        """Get list of supported concept types."""
        ...

    def requires_online(self) -> bool:
        """Return True when adapter needs network access."""
        ...
```

### HighlightRenderPort (New)

Interface for rendering highlights in different formats:

```python
# rexlit/app/ports/highlight_render.py

from typing import Protocol
from pathlib import Path


class HighlightRenderPort(Protocol):
    """Port interface for highlight rendering.

    Adapters:
    - PDFHighlightAdapter (PDF.js annotations)
    - HTMLHighlightAdapter (styled spans)
    - JSONHighlightAdapter (structured data for UI)

    Side effects: Writes rendered output files.
    """

    def render_highlights(
        self,
        document_path: Path,
        highlights: list[dict],
        output_path: Path,
        *,
        format: str = "json",
    ) -> Path:
        """Render highlights onto document.

        Args:
            document_path: Source document
            highlights: Highlight coordinates and colors
            output_path: Output file path
            format: Output format ("json", "html", "pdf_annotations")

        Returns:
            Path to rendered output
        """
        ...
```

---

## Domain Services

### HighlightService

Orchestrates concept detection and plan generation (mirrors `RedactionService`):

```python
# rexlit/app/highlight_service.py

from pathlib import Path
from typing import Any
from pydantic import BaseModel

from rexlit.app.ports import LedgerPort, StoragePort
from rexlit.app.ports.concept import ConceptPort
from rexlit.config import Settings, get_settings
from rexlit.utils.plans import (
    compute_highlight_plan_id,
    load_highlight_plan_entry,
    validate_highlight_plan_entry,
    write_highlight_plan_entry,
)


class HighlightPlan(BaseModel):
    """Highlight plan with deterministic ID."""

    plan_id: str
    input_hash: str
    highlights: list[dict[str, Any]]
    annotations: dict[str, Any]
    rationale: str


class HighlightService:
    """Orchestrates legal concept highlighting.

    Implements plan/render pattern:
    1. plan: Generate highlight coordinates without modifying documents
    2. render: Web UI displays color-coded highlights

    All I/O is delegated to ports.
    """

    def __init__(
        self,
        *,
        concept_port: ConceptPort,
        storage_port: StoragePort,
        ledger_port: LedgerPort | None,
        settings: Settings | None = None,
    ):
        """Initialize highlight service."""
        self.concept = concept_port
        self.storage = storage_port
        self.ledger = ledger_port
        self._settings = settings or get_settings()
        self._plan_key = self._settings.get_highlight_plan_key()

    def plan(
        self,
        input_path: Path,
        output_plan_path: Path,
        *,
        concepts: list[str] | None = None,
        threshold: float = 0.5,
    ) -> HighlightPlan:
        """Generate highlight plan without modifying documents.

        Args:
            input_path: Path to document or directory
            output_plan_path: Output path for plan JSONL
            concepts: Concept types to detect (default: all)
            threshold: Minimum confidence threshold

        Returns:
            HighlightPlan with deterministic plan_id
        """
        # Similar to RedactionService.plan()
        # 1. Run concept detection
        # 2. Convert findings to highlight actions
        # 3. Compute plan_id (hash of inputs + actions)
        # 4. Write JSONL plan
        # 5. Log to audit trail
        ...

    def validate_plan(self, plan_path: Path) -> bool:
        """Validate highlight plan against current documents."""
        # Hash verification (same as redaction)
        ...

    def export_for_ui(
        self,
        plan_path: Path,
        output_format: str = "json",
    ) -> dict[str, Any]:
        """Export highlight plan for web UI consumption.

        Returns:
            Dictionary with highlights grouped by page,
            heatmap data for scroll bar, color legend
        """
        ...
```

---

## CLI Commands

### `rexlit highlight plan`

Generate highlight plan from documents:

```bash
# Basic usage
rexlit highlight plan ./discovery --output highlights.jsonl

# Specific concepts only
rexlit highlight plan ./emails \
  --concepts EMAIL_COMMUNICATION,LEGAL_ADVICE \
  --output email_highlights.jsonl

# Custom confidence threshold
rexlit highlight plan ./hotdocs \
  --threshold 0.75 \
  --output hotdoc_highlights.jsonl

# LLM-powered (online mode)
REXLIT_ONLINE=1 rexlit highlight plan ./production \
  --force-llm \
  --output llm_highlights.jsonl
```

**CLI Implementation:**

```python
# rexlit/cli.py

@app.command()
def highlight_plan(
    input_path: Path = typer.Argument(..., help="Document or directory to analyze"),
    output: Path = typer.Option(..., help="Output JSONL plan path"),
    concepts: str | None = typer.Option(None, help="Comma-separated concept types"),
    threshold: float = typer.Option(0.5, help="Confidence threshold"),
    force_llm: bool = typer.Option(False, help="Skip pattern pre-filter, use LLM"),
):
    """Generate highlight plan for legal review."""
    container = bootstrap.create_container()
    service = container.get_highlight_service()

    concept_list = concepts.split(",") if concepts else None

    plan = service.plan(
        input_path=input_path,
        output_plan_path=output,
        concepts=concept_list,
        threshold=threshold,
    )

    typer.echo(f"Generated highlight plan: {plan.plan_id}")
    typer.echo(f"Highlights: {len(plan.highlights)}")
    typer.echo(f"Output: {output}")
```

### `rexlit highlight validate`

Validate highlight plan against current documents:

```bash
rexlit highlight validate highlights.jsonl
# ✓ Plan valid: hash matches current documents
# ✓ 150 highlights across 45 documents
```

### `rexlit highlight export`

Export highlight plan for UI consumption:

```bash
# JSON format for web UI
rexlit highlight export highlights.jsonl \
  --format json \
  --output highlights_ui.json

# Heatmap-only (for scroll bar)
rexlit highlight export highlights.jsonl \
  --format heatmap \
  --output heatmap.json
```

---

## Web UI Integration

### API Endpoints (Bun/Elysia)

Following the CLI-as-API pattern (ADR 0009), add endpoints in `api/index.ts`:

```typescript
// api/index.ts

interface HighlightData {
  document_hash: string
  highlights: Array<{
    concept: string
    category: string
    text: string
    confidence: number
    start: number
    end: number
    page: number
    color: string
    shade_intensity: number
  }>
  heatmap: Array<{
    page: number
    temperature: number  // 0.0 - 1.0
    highlight_count: number
  }>
  color_legend: Record<string, string>
}

// GET /api/highlights/:hash
app.get('/api/highlights/:hash', async ({ params }) => {
  const { hash } = params

  // Shell out to CLI: rexlit highlight export <plan> --format json --hash <hash>
  const result = execSync(
    `${REXLIT_BIN} highlight export ${HIGHLIGHTS_PLAN_PATH} --format json --hash ${hash}`,
    { encoding: 'utf-8' }
  )

  return Response.json(JSON.parse(result))
})

// GET /api/highlights/:hash/heatmap
app.get('/api/highlights/:hash/heatmap', async ({ params }) => {
  const { hash } = params

  // Shell out to CLI: rexlit highlight export <plan> --format heatmap --hash <hash>
  const result = execSync(
    `${REXLIT_BIN} highlight export ${HIGHLIGHTS_PLAN_PATH} --format heatmap --hash ${hash}`,
    { encoding: 'utf-8' }
  )

  return Response.json(JSON.parse(result))
})
```

### React UI Components

**1. Heatmap Scroll Bar** (`ui/src/components/documents/HeatmapScrollBar.tsx`):

```typescript
interface HeatmapScrollBarProps {
  pages: Array<{
    page: number
    temperature: number  // 0.0 - 1.0
    highlight_count: number
  }>
  currentPage: number
  onPageClick: (page: number) => void
}

export function HeatmapScrollBar({ pages, currentPage, onPageClick }: HeatmapScrollBarProps) {
  return (
    <div className="heatmap-scrollbar">
      {pages.map((p) => (
        <div
          key={p.page}
          className={cn("page-segment", { active: p.page === currentPage })}
          style={{
            backgroundColor: `rgba(255, 0, 0, ${p.temperature})`,
            height: `${100 / pages.length}%`
          }}
          onClick={() => onPageClick(p.page)}
          title={`Page ${p.page}: ${p.highlight_count} highlights`}
        />
      ))}
    </div>
  )
}
```

**2. Highlight Overlay** (`ui/src/components/documents/HighlightOverlay.tsx`):

```typescript
interface HighlightOverlayProps {
  highlights: Array<{
    concept: string
    text: string
    confidence: number
    start: number
    end: number
    page: number
    color: string
    shade_intensity: number
  }>
  currentPage: number
  onHighlightClick?: (highlight: any) => void
}

export function HighlightOverlay({ highlights, currentPage, onHighlightClick }: HighlightOverlayProps) {
  const pageHighlights = highlights.filter(h => h.page === currentPage)

  return (
    <div className="highlight-overlay">
      {pageHighlights.map((h, idx) => (
        <span
          key={idx}
          className={cn("highlight", `highlight-${h.color}`)}
          style={{
            opacity: h.shade_intensity,
            backgroundColor: getColorHex(h.color)
          }}
          data-concept={h.concept}
          data-confidence={h.confidence}
          onClick={() => onHighlightClick?.(h)}
          title={`${h.concept} (${(h.confidence * 100).toFixed(0)}% confidence)`}
        >
          {h.text}
        </span>
      ))}
    </div>
  )
}

function getColorHex(color: string): string {
  const palette = {
    cyan: '#00FFFF',
    magenta: '#FF00FF',
    yellow: '#FFFF00',
    red: '#FF0000',
    green: '#00FF00'
  }
  return palette[color] || '#CCCCCC'
}
```

**3. Enhanced DocumentViewer** (`ui/src/components/documents/DocumentViewer.tsx`):

```typescript
export function DocumentViewer({ document, getDocumentUrl }: DocumentViewerProps) {
  const [highlights, setHighlights] = useState<HighlightData | null>(null)
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)

  useEffect(() => {
    if (document?.sha256) {
      // Fetch highlights for this document
      rexlitApi.getHighlights(document.sha256)
        .then(setHighlights)
        .catch(err => console.error('Failed to load highlights:', err))
    }
  }, [document?.sha256])

  return (
    <div className="document-viewer">
      {/* Heatmap Scroll Bar */}
      {showHeatmap && highlights && (
        <HeatmapScrollBar
          pages={highlights.heatmap}
          currentPage={currentPage}
          onPageClick={setCurrentPage}
        />
      )}

      {/* PDF Viewer with Highlight Overlay */}
      <div className="pdf-container">
        <PDFView
          url={getDocumentUrl(document.sha256)}
          page={currentPage}
        />

        {highlights && (
          <HighlightOverlay
            highlights={highlights.highlights}
            currentPage={currentPage}
            onHighlightClick={(h) => {
              console.log('Clicked highlight:', h)
              // Could show detail panel, jump to related docs, etc.
            }}
          />
        )}
      </div>

      {/* Color Legend */}
      {highlights && (
        <ColorLegend legend={highlights.color_legend} />
      )}
    </div>
  )
}
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)

**Goal:** Establish port interfaces and schema

- [ ] Define `ConceptPort` protocol (`rexlit/app/ports/concept.py`)
- [ ] Define `ConceptFinding` model
- [ ] Create highlight plan schema v1 (JSON Schema + JSONL format)
- [ ] Add `compute_highlight_plan_id()` to `rexlit/utils/plans.py`
- [ ] Add `write_highlight_plan_entry()` / `load_highlight_plan_entry()`
- [ ] Write unit tests for schema validation

**Deliverable:** Port interfaces and schema ready for adapter implementation

### Phase 2: Pattern-Based Concept Detection (Week 3)

**Goal:** Offline concept detection without LLM

- [ ] Implement `PatternConceptAdapter` (`rexlit/app/adapters/pattern_concept_adapter.py`)
  - Email detection (regex for headers, addresses)
  - Legal advice markers ("counsel advises", "attorney-client")
  - Key entity extraction (patent numbers, party names)
- [ ] Add concept confidence scoring
- [ ] Write integration tests with sample legal documents
- [ ] Benchmark performance (target: <100ms per document)

**Deliverable:** Offline concept detection working end-to-end

### Phase 3: Highlight Service & CLI (Week 4)

**Goal:** CLI commands for plan generation

- [ ] Implement `HighlightService` (`rexlit/app/highlight_service.py`)
  - `plan()` method (mirrors `RedactionService.plan()`)
  - `validate_plan()` method
  - `export_for_ui()` method
- [ ] Wire up in `rexlit/bootstrap.py`
- [ ] Implement CLI commands:
  - `rexlit highlight plan`
  - `rexlit highlight validate`
  - `rexlit highlight export`
- [ ] Add audit logging for highlight operations
- [ ] Write CLI integration tests

**Deliverable:** CLI can generate highlight plans from documents

### Phase 4: LLM-Powered Detection (Week 5)

**Goal:** Safeguard integration for complex concepts

- [ ] Implement `SafeguardConceptAdapter` (reuse `PrivilegeReasoningPort`)
- [ ] Create concept detection policy templates:
  - `concept_detection_stage1.txt` (email/communication)
  - `concept_detection_stage2.txt` (legal advice)
  - `concept_detection_stage3.txt` (hotdoc indicators)
- [ ] Add escalation logic (pattern → LLM for uncertain cases)
- [ ] Privacy-preserving audit logs (hash reasoning chains)
- [ ] Write LLM integration tests (mocked responses)

**Deliverable:** LLM-powered concept detection with confidence scoring

### Phase 5: Web UI - Heatmap & Highlights (Week 6-7)

**Goal:** Visual highlight rendering in React

- [ ] Add API endpoints (`/api/highlights/:hash`, `/api/highlights/:hash/heatmap`)
- [ ] Implement `HeatmapScrollBar` component
- [ ] Implement `HighlightOverlay` component
- [ ] Implement `ColorLegend` component
- [ ] Enhance `DocumentViewer` with highlight toggle
- [ ] Add CSS for highlight colors and opacity
- [ ] Write Playwright E2E tests for UI interactions

**Deliverable:** Working heatmap and highlight overlay in web UI

### Phase 6: Triage Workflow (Week 8)

**Goal:** Complete the "Neon Triage" story

- [ ] Add highlight statistics to search results (show "temperature")
- [ ] Implement document sorting by highlight density
- [ ] Add "Jump to Next Highlight" navigation
- [ ] Implement highlight detail panel (show reasoning summary)
- [ ] Add export feature (highlighted docs to privilege log)
- [ ] Write end-to-end workflow tests

**Deliverable:** Attorney can triage 4,500 docs in hours instead of days

### Phase 7: Performance & Polish (Week 9)

**Goal:** Production-ready performance

- [ ] Batch processing for large document sets
- [ ] Highlight plan caching (avoid re-detection)
- [ ] Progressive loading for UI (render as highlights load)
- [ ] Add telemetry (time saved, docs triaged)
- [ ] Documentation (CLI guide, UI walkthrough)
- [ ] Release notes and migration guide

**Deliverable:** v0.3.0-m2 ready for production use

---

## Testing Strategy

### Unit Tests

**Concept Detection** (`tests/test_concept_detection.py`):
```python
def test_pattern_adapter_detects_email_headers():
    """Pattern adapter extracts email headers with high confidence."""
    adapter = PatternConceptAdapter()
    text = "From: attorney@lawfirm.com\nTo: client@company.com"

    findings = adapter.analyze_text(text, concepts=["EMAIL_COMMUNICATION"])

    assert len(findings) >= 1
    assert findings[0].concept == "EMAIL_COMMUNICATION"
    assert findings[0].confidence >= 0.85

def test_safeguard_adapter_detects_legal_advice():
    """Safeguard adapter identifies legal advice language."""
    adapter = SafeguardConceptAdapter(api_key="test")
    text = "Our counsel advises that the patent infringement claim lacks merit."

    findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])

    assert len(findings) >= 1
    assert findings[0].concept == "LEGAL_ADVICE"
    assert findings[0].category == "privilege"
```

**Highlight Service** (`tests/test_highlight_service.py`):
```python
def test_highlight_plan_hash_verification():
    """Highlight plan validates against document hash."""
    service = create_highlight_service()
    pdf_path = create_test_pdf("contract.pdf")
    plan_path = tmp_path / "highlights.jsonl"

    # Generate plan
    plan = service.plan(pdf_path, plan_path)

    # Modify PDF
    pdf_path.write_bytes(b"MODIFIED")

    # Validation should fail
    assert service.validate_plan(plan_path) is False
```

### Integration Tests

**CLI Workflow** (`tests/test_highlight_cli.py`):
```python
def test_highlight_plan_cli_end_to_end(tmp_path):
    """CLI generates valid highlight plan from documents."""
    docs_dir = create_test_documents(tmp_path / "docs", count=10)
    plan_path = tmp_path / "highlights.jsonl"

    result = CliRunner().invoke(
        app,
        ["highlight", "plan", str(docs_dir), "--output", str(plan_path)]
    )

    assert result.exit_code == 0
    assert plan_path.exists()

    # Validate schema
    plan = load_highlight_plan_entry(plan_path)
    assert plan["schema_id"] == "highlight_plan"
    assert len(plan["highlights"]) > 0
```

### UI Tests (Playwright)

**Heatmap Navigation** (`ui/tests/e2e/highlights.spec.ts`):
```typescript
test('heatmap scroll bar navigates to pages', async ({ page }) => {
  await page.goto('/search')
  await page.fill('[data-testid="search-input"]', 'privileged')
  await page.click('[data-testid="search-button"]')

  // Select first result
  await page.click('[data-testid="result-0"]')

  // Heatmap should appear
  await expect(page.locator('.heatmap-scrollbar')).toBeVisible()

  // Click on high-temperature page
  const hotPage = page.locator('.page-segment').filter({ hasText: /temperature: 0\.9/ })
  await hotPage.click()

  // PDF viewer should jump to that page
  await expect(page.locator('.pdf-page-number')).toHaveText(/Page 12/)
})
```

---

## Security Considerations

### Audit Logging

All highlight operations are logged to the audit trail:

```json
{
  "operation": "highlight_plan_create",
  "inputs": ["/data/discovery/email_chain.pdf"],
  "outputs": ["/data/highlights/plan_abc123.jsonl"],
  "args": {
    "plan_id": "highlight_abc123...",
    "document_sha256": "a1b2c3d4e5f6...",
    "concept_types": ["EMAIL_COMMUNICATION", "LEGAL_ADVICE"],
    "highlight_count": 15,
    "detector": "SafeguardConceptAdapter",
    "reasoning_hashes": ["sha256_1...", "sha256_2..."]
  },
  "timestamp": "2025-11-19T14:30:00Z"
}
```

### Privacy Guarantees

1. **No Document Text in Logs:** Only reasoning hashes and summaries logged
2. **Encrypted Plans:** Highlight plans encrypted at rest (same as redaction plans)
3. **Hash Verification:** Prevents tampering with highlight coordinates
4. **Offline-First:** Pattern detection works without network access

### Path Traversal Defense

- All document paths resolved with `.resolve()` and validated against allowed roots
- Highlight plans reference documents by SHA-256 hash (not raw paths)
- API endpoints use hash-based lookups (not user-provided paths)

---

## Performance Targets

### Throughput

| Operation | Target | Notes |
|-----------|--------|-------|
| Pattern concept detection | 50 docs/sec | Offline, CPU-bound |
| LLM concept detection | 2-5 docs/sec | Online, API rate limited |
| Highlight plan generation | 100 docs/sec | I/O bound (reading PDFs) |
| UI highlight rendering | <100ms | Client-side, per page |
| Heatmap generation | <50ms | Server-side, per document |

### Scalability

- **100K document corpus:** Generate highlights in ~30 minutes (pattern mode)
- **10K document corpus:** Generate highlights in ~45 minutes (LLM mode)
- **Web UI:** Load highlights for 500-page document in <2 seconds

### Memory Constraints

- Pattern adapter: <100MB peak
- LLM adapter: <500MB peak (model caching)
- Highlight service: <10MB per document (streaming mode)

---

## Success Metrics

### Quantitative

- [ ] Attorneys triage 4,500 docs in <3 hours (vs. 40+ hours manual review)
- [ ] 95%+ precision for EMAIL_COMMUNICATION detection
- [ ] 85%+ precision for LEGAL_ADVICE detection
- [ ] <5% false negative rate for hotdoc indicators
- [ ] Zero path traversal vulnerabilities (security scan)

### Qualitative

- [ ] Attorneys prefer heatmap navigation over linear review
- [ ] Highlight colors intuitively match legal concepts
- [ ] Confidence shading helps prioritize manual review
- [ ] Reasoning summaries provide actionable context
- [ ] Export to privilege log saves manual data entry

---

## Migration Path

### From v0.2.0-m1 to v0.3.0-m2

1. **Backward Compatible:** Highlight plans stored separately from existing manifests
2. **Opt-In:** Highlight feature disabled by default, enabled via `--enable-highlights`
3. **Schema Versioning:** Highlight plans use `highlight_plan@1.json` schema
4. **UI Toggle:** Web UI shows toggle to enable/disable highlight overlay

### Future Extensions

- **Phase 4 (M3):** Machine learning-based concept detection (train on attorney feedback)
- **Phase 5 (M4):** Cross-document highlight clustering (find similar concepts across corpus)
- **Phase 6 (M5):** Automated privilege log generation from highlights

---

## References

- **ADR 0006:** Redaction Plan/Apply Model (architecture pattern)
- **ADR 0004:** JSONL Schema Versioning (schema design)
- **ADR 0008:** EDRM Privilege Log Protocol (privilege workflows)
- **ADR 0009:** CLI-as-API Pattern (web integration)
- **Story:** "The Neon Triage" (use case inspiration)

---

## Appendix A: Color Palette Design Rationale

| Color | Hex Code | Psychology | Legal Use Case |
|-------|----------|------------|----------------|
| Cyan | `#00FFFF` | Cool, informative | Email/communication (factual) |
| Magenta | `#FF00FF` | Alert, privilege | Legal advice (protected) |
| Yellow | `#FFFF00` | Highlight, attention | Key entities (important) |
| Red | `#FF0000` | Danger, critical | Hot docs (smoking guns) |
| Green | `#00FF00` | Positive, relevant | Responsive content (on-topic) |

**Accessibility:** All colors meet WCAG 2.1 AA contrast requirements when overlaid on white background.

---

## Appendix B: Sample CLI Session

```bash
# Setup: Ingest and index discovery corpus
rexlit ingest ./discovery --manifest out/manifest.jsonl
rexlit index build ./discovery --index-dir out/index

# Generate highlight plan (pattern-based, offline)
rexlit highlight plan ./discovery \
  --concepts EMAIL_COMMUNICATION,LEGAL_ADVICE,KEY_PARTY \
  --threshold 0.75 \
  --output out/highlights.jsonl

# Output:
# Analyzed 4,500 documents
# Generated 12,847 highlights
# Concepts detected:
#   EMAIL_COMMUNICATION: 6,234 (avg confidence: 0.92)
#   LEGAL_ADVICE: 4,102 (avg confidence: 0.78)
#   KEY_PARTY: 2,511 (avg confidence: 0.85)
# Plan saved: out/highlights.jsonl (plan_id: highlight_abc123...)

# Validate plan (ensure docs haven't changed)
rexlit highlight validate out/highlights.jsonl
# ✓ Plan valid: all document hashes match

# Export for web UI
rexlit highlight export out/highlights.jsonl \
  --format json \
  --output out/highlights_ui.json

# Start web UI
cd api && bun run index.ts &
cd ui && npm run dev

# Open browser to http://localhost:5173
# → Search for "privileged"
# → Click result
# → See heatmap scroll bar with color-coded pages
# → Click magenta (high-temperature) page
# → Read only the highlighted legal advice sections
# → Export to privilege log with one click
```

---

**End of Implementation Plan**

This plan provides a comprehensive roadmap for building the legal highlighter feature while staying true to RexLit's architectural principles: offline-first, deterministic, audit-ready, and legally defensible.
