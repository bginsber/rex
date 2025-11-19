# Legal Highlighter: Technical Design & Implementation Roadmap

**Author:** Claude
**Date:** 2025-11-19
**Status:** Concept Design
**Related ADRs:** ADR 0006 (Redaction Plan/Apply), ADR 0008 (Privilege Safeguard Integration)

---

## Executive Summary

This document outlines a **2-day sprint** concept for adapting RexLit's redaction and privilege classification systems into a **color-coded legal highlighter** that can mark documents with confidence-based shading for legal team review. The system would use AI models (like `gpt-oss-safeguard-20b` or SAE-based approaches) to identify and categorize legal concepts, outputting visual annotations that legal teams can review in the CLI-API web UI.

**Key Innovation:** Instead of redacting (blacking out) sensitive information, the system highlights interesting segments with different colors:
- 🟦 **Blue** = Looks like an email/correspondence
- 🟩 **Green** = Legal advice or privilege indicators
- 🟨 **Yellow** = Contract terms or obligations
- 🟥 **Red** = Hot documents or regulatory concerns
- **Shade intensity** = Model confidence (darker = higher confidence)

**Architectural Fit:** This reuses ~80% of RexLit's existing privilege classification and redaction infrastructure, requiring minimal new code.

---

## 1. Technical Feasibility: Architecture Analysis

### 1.1 Existing Components We Can Reuse

RexLit already has the building blocks for this feature:

#### A. **Redaction Plan/Apply Pattern (ADR 0006)**
- **Current:** Two-phase workflow (plan → apply) for redactions
- **Adaptation:** Replace "apply redaction" with "apply highlight"
- **Reuse:**
  - Plan generation logic (scan PDFs, compute coordinates)
  - Hash verification (ensure PDF hasn't changed)
  - JSONL plan format (schema versioning)

**File:** `rexlit/app/ports/redaction_port.py` (currently missing, needs creation)

#### B. **Privilege Classification Pipeline (ADR 0008)**
- **Current:** 3-stage modular pipeline (Privilege → Responsiveness → Redaction)
- **Adaptation:** Add 4th stage for "Concept Highlighting"
- **Reuse:**
  - `PrivilegeReasoningPort` interface
  - `PolicyDecision` model with confidence scoring
  - Circuit breaker pattern for resilience
  - Privacy-preserving audit logging (hashed reasoning)

**Files:**
- `rexlit/app/privilege_service.py:306-609` - Orchestration service
- `rexlit/app/adapters/privilege_safeguard.py:38-428` - LLM adapter

#### C. **PDF Manipulation Infrastructure**
- **Current:** Placeholder module `rexlit/pdf/`
- **Required:** Add PyMuPDF for highlight annotations
- **Adaptation:** Create `HighlighterPort` similar to `RedactionPlannerPort`

#### D. **CLI-API Web UI Integration**
- **Current:** Bun/Elysia API wraps Python CLI via subprocess
- **Adaptation:** Add `/api/highlights/:hash` endpoint
- **UI:** React PDF viewer with overlay annotations

---

### 1.2 New Components Required

| Component | Purpose | LOC Est. | Complexity |
|-----------|---------|----------|------------|
| `HighlighterPort` | Port interface for highlight planning | 50 | Low |
| `HighlightPlannerAdapter` | Concrete adapter using LLM | 200 | Medium |
| `HighlightApplier` | PDF annotation renderer (PyMuPDF) | 150 | Medium |
| `rexlit highlight plan` CLI | Command to generate highlight plans | 100 | Low |
| `rexlit highlight apply` CLI | Command to render highlights on PDFs | 100 | Low |
| `/api/highlights/:hash` endpoint | API route for UI | 50 | Low |
| React Highlight Viewer component | UI overlay for annotations | 200 | Medium |
| **Total** | | **~850 LOC** | **2-day sprint feasible** |

---

## 2. AI Model Assessment: gpt-oss-safeguard-20b vs SAE-LLM

### 2.1 gpt-oss-safeguard-20b (Recommended for Phase 1)

**What it is:** OpenAI's open-source 20B parameter policy reasoning model, designed for Harmony-style policy enforcement with chain-of-thought reasoning.

**Why it fits:**
- ✅ **Already integrated** in RexLit for privilege classification (ADR 0008)
- ✅ **Policy-as-prompt** design allows custom highlighting rules
- ✅ **Self-hosted** (offline-first, Apache 2.0 license)
- ✅ **Multi-label classification** built-in (can output multiple categories)
- ✅ **Confidence scoring** native to model output
- ✅ **Tool use capabilities** (can output structured JSON with bounding boxes)

**Technical Integration:**

The model already produces `PolicyDecision` objects with labels and confidence:

```python
# Current privilege classification output
PolicyDecision(
    labels=["PRIVILEGED:ACP", "RESPONSIVE"],
    confidence=0.92,
    reasoning_hash="a3f2b1c8...",
    reasoning_summary="Communication from external counsel",
)
```

**Adaptation for highlighting:**

```python
# Extended for multi-category highlighting
HighlightDecision(
    highlight_spans=[
        HighlightSpan(
            category="EMAIL",
            start=0,
            end=245,
            confidence=0.95,
            color="#3B82F6",  # Blue
            justification="RFC 822 email header detected",
        ),
        HighlightSpan(
            category="LEGAL_ADVICE",
            start=450,
            end=892,
            confidence=0.87,
            color="#10B981",  # Green
            justification="Attorney opinion language per ACP indicators",
        ),
    ],
    document_hash="def456...",
    model_version="gpt-oss-safeguard-20b",
)
```

**Policy Template Example:**

```text
# HARMONY POLICY: Legal Concept Highlighter v1.0

You are a legal document analyzer that identifies and categorizes key concepts for attorney review.

## Categories

1. **EMAIL** (Blue, #3B82F6)
   - Email headers, correspondence, communications
   - Indicators: "From:", "To:", "Subject:", RFC 822 format

2. **LEGAL_ADVICE** (Green, #10B981)
   - Attorney opinions, legal analysis, privilege indicators
   - Indicators: "In my legal opinion", attorney email domains, privileged markers

3. **CONTRACT** (Yellow, #F59E0B)
   - Contract terms, obligations, warranties
   - Indicators: "shall", "agrees to", "warranty", defined terms

4. **REGULATORY** (Red, #EF4444)
   - Compliance issues, regulatory citations, hot documents
   - Indicators: FDA, FTC, regulatory citations, warning language

## Output Format

Return JSON with character-level spans:

```json
{
  "highlight_spans": [
    {
      "category": "EMAIL",
      "start": 0,
      "end": 245,
      "confidence": 0.95,
      "justification": "RFC 822 email header detected"
    }
  ]
}
```

## Confidence Scoring

- 0.90-1.00: High confidence (dark shade)
- 0.75-0.89: Medium confidence (medium shade)
- 0.50-0.74: Low confidence (light shade)
- <0.50: Do not highlight (needs human review)
```

**Performance Characteristics:**
- **Latency:** 2-5 seconds per document (20B model on GPU)
- **Accuracy:** Expected 85-95% on legal concept detection (based on privilege task performance)
- **Throughput:** 10-20 docs/minute single GPU, 100+ docs/minute with 8 GPUs
- **Memory:** 16GB+ VRAM required

---

### 2.2 SAE-LLM Concept (Future Research Direction)

**What it is:** Sparse Autoencoder (SAE) interpretability technique applied to LLMs to identify "concept neurons" that activate for specific semantic features.

**How it could work for highlighting:**

1. **Train SAE on RexLit corpus** to discover latent legal concepts
2. **Map SAE features to categories** (e.g., Feature 42 = "attorney-client communication")
3. **Real-time activation analysis** to highlight spans where features fire
4. **Confidence = activation strength** (higher activation = darker highlight)

**Advantages:**
- ✅ **Interpretable:** Each highlight tied to specific SAE feature
- ✅ **Fast:** No full LLM inference, just forward pass + SAE decode
- ✅ **Fine-grained:** Can highlight sub-sentence spans
- ✅ **Mechanistically grounded:** Understands *why* a span is highlighted

**Challenges:**
- ❌ **Research-stage:** SAE for legal documents not yet proven
- ❌ **Training overhead:** Requires large labeled corpus + GPU compute
- ❌ **Feature engineering:** Mapping SAE features to legal categories non-trivial
- ❌ **No open-source tooling** for legal domain (general SAE tools exist)

**Recommendation:** **Defer to Phase 2** research sprint after initial gpt-oss-safeguard-20b prototype proves value.

**Potential Research Path:**
1. Use gpt-oss-safeguard-20b to auto-label 10K+ documents for SAE training data
2. Train SAE on labeled corpus (e.g., using [Anthropic's SAE toolkit](https://github.com/anthropics/sae))
3. Validate SAE feature→category mapping against human annotations
4. If accuracy ≥90%, deploy as faster alternative to full LLM

---

## 3. Architecture Design: Highlight Plan/Apply Pattern

### 3.1 Port Interface: `HighlighterPort`

```python
# rexlit/app/ports/highlighter_port.py

from typing import Protocol, Literal
from pathlib import Path
from pydantic import BaseModel, Field

ColorHex = str  # e.g., "#3B82F6"

class HighlightSpan(BaseModel):
    """A span of text to highlight with a specific category and color."""

    category: Literal["EMAIL", "LEGAL_ADVICE", "CONTRACT", "REGULATORY", "CUSTOM"]
    start: int  # Character offset (0-indexed, inclusive)
    end: int    # Character offset (0-indexed, exclusive)
    confidence: float = Field(ge=0.0, le=1.0)
    color: ColorHex
    justification: str  # Non-privileged explanation for audit trail

    @property
    def opacity(self) -> float:
        """Calculate opacity based on confidence (0.3-0.8 range)."""
        return 0.3 + (self.confidence * 0.5)  # High confidence = 0.8, low = 0.3


class HighlightPlan(BaseModel):
    """Plan for highlighting documents (similar to RedactionPlan)."""

    schema_id: str = "highlight_plan"
    schema_version: int = 1
    plan_id: str  # SHA-256 hash of input document hashes
    documents: list[HighlightDocumentPlan]
    policy_version: str
    created_at: str  # ISO 8601 UTC


class HighlightDocumentPlan(BaseModel):
    """Highlight plan for a single document."""

    path: Path
    sha256: str
    highlight_spans: list[HighlightSpan]


class HighlighterPort(Protocol):
    """Port interface for highlight planning."""

    def plan_highlights(
        self,
        text: str,
        *,
        categories: list[str] | None = None,
        min_confidence: float = 0.5,
    ) -> list[HighlightSpan]:
        """Analyze text and return highlight spans.

        Args:
            text: Document text to analyze
            categories: Filter to specific categories (None = all)
            min_confidence: Minimum confidence threshold for highlights

        Returns:
            List of HighlightSpan objects sorted by start position
        """
        ...

    def requires_online(self) -> bool:
        """Check if adapter requires network access."""
        ...
```

---

### 3.2 Adapter: `HighlightSafeguardAdapter`

```python
# rexlit/app/adapters/highlight_safeguard_adapter.py

from rexlit.app.ports.highlighter_port import HighlighterPort, HighlightSpan
from rexlit.app.adapters.privilege_safeguard import PrivilegeSafeguardAdapter

class HighlightSafeguardAdapter(HighlighterPort):
    """Safeguard-based highlight planner using policy templates."""

    # Color mapping for categories
    CATEGORY_COLORS = {
        "EMAIL": "#3B82F6",         # Blue
        "LEGAL_ADVICE": "#10B981",  # Green
        "CONTRACT": "#F59E0B",      # Yellow
        "REGULATORY": "#EF4444",    # Red
        "CUSTOM": "#8B5CF6",        # Purple
    }

    def __init__(
        self,
        safeguard_adapter: PrivilegeSafeguardAdapter,
        policy_path: Path,
    ):
        self.safeguard = safeguard_adapter
        self.policy_path = policy_path
        self.policy_text = policy_path.read_text()

    def plan_highlights(
        self,
        text: str,
        *,
        categories: list[str] | None = None,
        min_confidence: float = 0.5,
    ) -> list[HighlightSpan]:
        """Use safeguard to identify highlight spans."""

        # Construct prompt with policy + document
        prompt = f"""{self.policy_text}

---

Analyze the following document and identify highlight spans:

{text}

Return JSON with highlight_spans array as specified in the policy."""

        # Call underlying safeguard model (reuse existing adapter!)
        decision = self.safeguard.classify_privilege(
            text,
            threshold=min_confidence,
            reasoning_effort="medium",
        )

        # Parse highlight spans from decision.redaction_spans
        # (We piggyback on the existing redaction span detection!)
        spans = []
        for redaction_span in decision.redaction_spans:
            category = redaction_span.category

            # Filter by requested categories
            if categories and category not in categories:
                continue

            # Map category to color
            color = self.CATEGORY_COLORS.get(category, "#8B5CF6")

            spans.append(HighlightSpan(
                category=category,
                start=redaction_span.start,
                end=redaction_span.end,
                confidence=decision.confidence,
                color=color,
                justification=redaction_span.justification,
            ))

        return sorted(spans, key=lambda s: s.start)

    def requires_online(self) -> bool:
        return False  # Self-hosted only
```

**Key insight:** We can **reuse the existing `PrivilegeSafeguardAdapter`** by treating highlight spans as a special case of redaction spans! The policy template just changes the instructions from "identify text to redact" to "identify concepts to highlight."

---

### 3.3 PDF Rendering: `HighlightApplier`

```python
# rexlit/app/adapters/highlight_applier.py

import fitz  # PyMuPDF
from pathlib import Path
from rexlit.app.ports.highlighter_port import HighlightPlan, HighlightSpan

class HighlightApplier:
    """Apply highlight annotations to PDFs."""

    def apply_highlights(
        self,
        plan: HighlightPlan,
        output_dir: Path,
    ) -> list[Path]:
        """Render highlights on PDFs per plan.

        Args:
            plan: HighlightPlan with spans to render
            output_dir: Directory for output PDFs

        Returns:
            List of output PDF paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_paths = []

        for doc_plan in plan.documents:
            # Verify hash matches (safety check from ADR 0006)
            current_hash = compute_hash(doc_plan.path)
            if current_hash != doc_plan.sha256:
                raise ValueError(
                    f"PDF hash mismatch for {doc_plan.path}. "
                    f"Expected {doc_plan.sha256}, got {current_hash}. "
                    "Regenerate plan or use --force."
                )

            # Open PDF
            pdf = fitz.open(doc_plan.path)

            # Apply highlights page by page
            for page_num in range(pdf.page_count):
                page = pdf[page_num]

                # Find spans on this page
                page_spans = self._spans_for_page(
                    doc_plan.highlight_spans,
                    page,
                    page_num,
                )

                for span in page_spans:
                    # Convert character offsets to PDF coordinates
                    quads = self._get_quads_for_span(page, span)

                    # Add highlight annotation
                    for quad in quads:
                        annot = page.add_highlight_annot(quad)

                        # Set color and opacity
                        rgb = self._hex_to_rgb(span.color)
                        annot.set_colors(stroke=rgb)
                        annot.set_opacity(span.opacity)

                        # Add comment with justification
                        annot.set_info(
                            content=f"{span.category} ({span.confidence:.0%}): {span.justification}"
                        )
                        annot.update()

            # Save highlighted PDF
            output_path = output_dir / doc_plan.path.name
            pdf.save(output_path)
            pdf.close()
            output_paths.append(output_path)

        return output_paths

    def _hex_to_rgb(self, hex_color: str) -> tuple[float, float, float]:
        """Convert hex color to RGB tuple (0.0-1.0 range)."""
        hex_color = hex_color.lstrip("#")
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (r / 255.0, g / 255.0, b / 255.0)

    def _get_quads_for_span(
        self,
        page: fitz.Page,
        span: HighlightSpan,
    ) -> list[fitz.Quad]:
        """Convert character offsets to PDF quad coordinates."""
        # Extract text with position info
        blocks = page.get_text("dict")["blocks"]

        quads = []
        char_offset = 0

        for block in blocks:
            for line in block.get("lines", []):
                for span_dict in line.get("spans", []):
                    text = span_dict["text"]
                    bbox = span_dict["bbox"]

                    # Check if this span overlaps with highlight span
                    span_start = char_offset
                    span_end = char_offset + len(text)

                    if span_start < span.end and span_end > span.start:
                        # This text span overlaps, add quad
                        quads.append(fitz.Quad(bbox))

                    char_offset += len(text)

        return quads
```

---

## 4. CLI Integration

### 4.1 Command: `rexlit highlight plan`

```python
# rexlit/cli.py (excerpt)

@app.command()
def highlight_plan(
    docs_dir: Path = typer.Argument(..., help="Directory of documents to analyze"),
    output: Path = typer.Option("highlight_plan.jsonl", help="Output plan file"),
    categories: str = typer.Option(
        "EMAIL,LEGAL_ADVICE,CONTRACT,REGULATORY",
        help="Comma-separated categories to detect",
    ),
    min_confidence: float = typer.Option(0.5, help="Minimum confidence threshold"),
    workers: int = typer.Option(4, help="Parallel workers"),
):
    """Generate highlight plan for documents."""

    container = bootstrap.create_container()
    highlighter = container.get_highlighter_adapter()

    # Discover documents
    docs = list(discover_documents(docs_dir))

    # Process in parallel
    category_list = categories.split(",")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                highlighter.plan_highlights,
                doc.text,
                categories=category_list,
                min_confidence=min_confidence,
            )
            for doc in docs
        ]

        results = [f.result() for f in futures]

    # Build plan
    plan = HighlightPlan(
        plan_id=compute_plan_hash(docs),
        documents=[
            HighlightDocumentPlan(
                path=doc.path,
                sha256=doc.sha256,
                highlight_spans=spans,
            )
            for doc, spans in zip(docs, results)
        ],
        policy_version=highlighter.policy_hash,
        created_at=datetime.utcnow().isoformat(),
    )

    # Write plan
    output.write_text(plan.model_dump_json(indent=2))

    typer.echo(f"✅ Highlight plan saved to {output}")
    typer.echo(f"📊 Found {sum(len(d.highlight_spans) for d in plan.documents)} highlights")
```

### 4.2 Command: `rexlit highlight apply`

```python
@app.command()
def highlight_apply(
    plan: Path = typer.Argument(..., help="Highlight plan JSONL file"),
    output_dir: Path = typer.Option("./highlighted", help="Output directory"),
    force: bool = typer.Option(False, help="Force apply despite hash mismatches"),
):
    """Apply highlights to PDFs from plan."""

    # Load plan
    plan_obj = HighlightPlan.model_validate_json(plan.read_text())

    # Apply highlights
    applier = HighlightApplier()

    try:
        output_paths = applier.apply_highlights(plan_obj, output_dir)
    except ValueError as e:
        if "hash mismatch" in str(e) and not force:
            typer.echo(f"❌ {e}", err=True)
            typer.echo("Regenerate plan or use --force", err=True)
            raise typer.Exit(1)
        raise

    typer.echo(f"✅ Highlighted {len(output_paths)} documents")
    typer.echo(f"📁 Output: {output_dir}")
```

---

## 5. UI Integration: Browser-Based Review

### 5.1 API Endpoint: `/api/highlights/:hash`

```typescript
// api/index.ts (excerpt)

app.get("/api/highlights/:hash", async ({ params }) => {
  const { hash } = params;

  // Call Python CLI to get highlight plan
  const result = execSync(
    `rexlit highlight show --hash ${hash} --json`,
    { encoding: "utf-8" }
  );

  const plan = JSON.parse(result);

  return Response.json(plan);
});
```

### 5.2 React Component: `HighlightViewer`

```tsx
// ui/src/components/HighlightViewer.tsx

import { useState, useEffect } from "react";

interface HighlightSpan {
  category: string;
  start: number;
  end: number;
  confidence: number;
  color: string;
  justification: string;
}

export function HighlightViewer({ documentHash }: { documentHash: string }) {
  const [highlights, setHighlights] = useState<HighlightSpan[]>([]);
  const [documentText, setDocumentText] = useState("");

  useEffect(() => {
    // Fetch highlight plan
    fetch(`/api/highlights/${documentHash}`)
      .then((res) => res.json())
      .then((plan) => {
        setHighlights(plan.highlight_spans);
        setDocumentText(plan.text);
      });
  }, [documentHash]);

  // Render text with highlights
  const renderHighlightedText = () => {
    if (highlights.length === 0) return <div>{documentText}</div>;

    const segments = [];
    let lastEnd = 0;

    // Sort highlights by start position
    const sorted = [...highlights].sort((a, b) => a.start - b.start);

    for (const span of sorted) {
      // Add unhighlighted text before this span
      if (span.start > lastEnd) {
        segments.push(
          <span key={`text-${lastEnd}`}>
            {documentText.slice(lastEnd, span.start)}
          </span>
        );
      }

      // Add highlighted span
      segments.push(
        <mark
          key={`highlight-${span.start}`}
          style={{
            backgroundColor: span.color,
            opacity: 0.3 + span.confidence * 0.5,
            cursor: "pointer",
          }}
          title={`${span.category} (${(span.confidence * 100).toFixed(0)}%): ${span.justification}`}
        >
          {documentText.slice(span.start, span.end)}
        </mark>
      );

      lastEnd = span.end;
    }

    // Add remaining text after last highlight
    if (lastEnd < documentText.length) {
      segments.push(
        <span key={`text-${lastEnd}`}>
          {documentText.slice(lastEnd)}
        </span>
      );
    }

    return <div className="highlighted-text">{segments}</div>;
  };

  return (
    <div className="highlight-viewer">
      <div className="legend">
        {Object.entries({
          EMAIL: "#3B82F6",
          LEGAL_ADVICE: "#10B981",
          CONTRACT: "#F59E0B",
          REGULATORY: "#EF4444",
        }).map(([category, color]) => (
          <div key={category} className="legend-item">
            <span
              className="color-box"
              style={{ backgroundColor: color }}
            />
            <span>{category}</span>
          </div>
        ))}
      </div>

      <div className="document-content">
        {renderHighlightedText()}
      </div>
    </div>
  );
}
```

---

## 6. Two-Day Sprint Breakdown

### Day 1: Core Infrastructure (Backend)

**Morning (4 hours):**
1. ✅ Create `HighlighterPort` interface (`rexlit/app/ports/highlighter_port.py`)
2. ✅ Create `HighlightSafeguardAdapter` (reuse existing `PrivilegeSafeguardAdapter`)
3. ✅ Write policy template (`policies/highlight_stage1.txt`) with 4 categories
4. ✅ Add configuration to `Settings` (model path, policy path)
5. ✅ Wire adapter in `bootstrap.py`

**Afternoon (4 hours):**
6. ✅ Implement `HighlightApplier` with PyMuPDF
7. ✅ Add CLI commands (`rexlit highlight plan`, `rexlit highlight apply`)
8. ✅ Write integration tests (plan generation, PDF rendering)
9. ✅ Test on sample corpus (10-20 documents)

**Evening:**
- Code review, fix bugs discovered during testing

### Day 2: UI Integration (Frontend + API)

**Morning (4 hours):**
1. ✅ Add `/api/highlights/:hash` endpoint in Bun API
2. ✅ Create React `HighlightViewer` component
3. ✅ Add highlight legend (category color mapping)
4. ✅ Implement click-to-explain (show justification on hover)

**Afternoon (4 hours):**
5. ✅ Add "Accept/Reject" buttons for each highlight (attorney review workflow)
6. ✅ Store review decisions in audit trail
7. ✅ Add export to privilege log (JSONL format)
8. ✅ End-to-end testing with legal team sample documents

**Evening:**
- Documentation, demo video, handoff to stakeholders

---

## 7. Expandability & Future Enhancements

### Phase 2: Human-in-the-Loop Refinement (1 week)

- **Feedback loop:** Attorneys accept/reject highlights → fine-tune policy template
- **Active learning:** Model learns from corrections to improve confidence calibration
- **Custom categories:** Users define domain-specific categories via UI
- **Batch review queue:** Process 1000+ docs, review only low-confidence highlights

### Phase 3: SAE-Based Highlighter (2-4 weeks research)

- **Train SAE** on RexLit corpus auto-labeled by gpt-oss-safeguard-20b
- **Feature engineering:** Map SAE latents to legal categories
- **Real-time highlighting:** <100ms latency (vs 2-5s for full LLM)
- **Interpretability dashboard:** Show which SAE features triggered each highlight

### Phase 4: Production Hardening (1 week)

- **Performance tuning:** GPU batch inference for 10x throughput
- **Error recovery:** Retry logic, circuit breakers, graceful degradation
- **Audit compliance:** EDRM-format privilege logs, tamper-evident chains
- **Security:** Hash-based document access, no path traversal vulnerabilities

---

## 8. Risk Assessment & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Model hallucination** (wrong highlights) | High | Medium | Set `min_confidence=0.7` default, require human review |
| **PDF coordinate mismatch** (highlights on wrong text) | Medium | Low | Use PyMuPDF's robust text extraction with bbox validation |
| **Performance bottleneck** (slow inference) | Medium | High | Parallel processing with ProcessPoolExecutor, GPU batching |
| **Privacy leak** (privileged text in audit logs) | Critical | Low | Reuse ADR 0008 hashed reasoning, redacted summaries |
| **UI/UX confusion** (too many highlights) | Low | Medium | Default to top-K highlights, hide low-confidence spans |
| **Model installation complexity** | Medium | High | Provide Docker image with gpt-oss-safeguard-20b pre-installed |

---

## 9. Success Metrics

**Quantitative:**
- **Accuracy:** ≥85% precision/recall on legal concept detection (validated against human annotations)
- **Throughput:** Process 100+ docs/hour on single GPU
- **Latency:** <5s per document for highlight plan generation
- **Adoption:** 80%+ of attorneys prefer highlighted docs over raw text review

**Qualitative:**
- **Ease of use:** Legal team can onboard in <30 minutes
- **Explainability:** Attorneys understand *why* a span is highlighted
- **Trust:** Confidence calibration matches human judgment (well-calibrated probabilities)

---

## 10. Conclusion & Recommendations

### ✅ Recommended Approach (Phase 1)

1. **Use gpt-oss-safeguard-20b** as the foundation (already integrated, proven for privilege classification)
2. **Reuse 80% of existing code** (ports/adapters pattern, redaction infrastructure, CLI-API UI)
3. **2-day sprint is feasible** for proof-of-concept with 4 highlight categories
4. **Defer SAE research** until Phase 1 proves value proposition

### 🔬 Research Questions for SAE Approach (Phase 3)

1. Can SAE latents reliably map to legal categories? (Need empirical validation)
2. What training corpus size is required? (10K docs? 100K docs?)
3. Does SAE-based highlighting match LLM accuracy? (Need A/B testing)
4. Can we achieve <100ms latency? (Benchmark required)

### 📊 Next Steps

**Immediate (Today):**
- ✅ Review this design doc with stakeholders
- ✅ Approve 2-day sprint scope
- ✅ Identify sample corpus for testing (20-50 legal documents)

**Week 1:**
- ✅ Execute 2-day sprint (backend + frontend)
- ✅ Demo to legal team with real documents
- ✅ Gather feedback on categories, colors, confidence thresholds

**Week 2:**
- ✅ Iterate based on feedback
- ✅ Expand to 10+ categories if needed
- ✅ Production deployment to legal team's RexLit instance

**Month 2-3 (Optional):**
- 🔬 Research SAE-based approach if Phase 1 successful
- 🔬 Benchmark gpt-oss-safeguard-20b vs SAE latency/accuracy
- 🔬 Publish findings for legal AI research community

---

## Appendix A: Policy Template Example

```text
# HARMONY POLICY: RexLit Legal Highlighter v1.0

You are a legal document analyzer for e-discovery workflows. Your task is to identify and categorize key legal concepts in documents to assist attorneys during privilege review.

## Categories

### 1. EMAIL (Blue, #3B82F6)
**Definition:** Electronic correspondence, communications, email headers

**Indicators:**
- RFC 822 email headers ("From:", "To:", "Subject:", "Date:")
- Email signatures with contact information
- Reply/forward chains ("On [date], [person] wrote:")
- Email client artifacts (Outlook, Gmail, Exchange)

**Examples:**
- ✅ "From: john@acme.com\nTo: jane@acme.com\nSubject: Meeting notes"
- ✅ "Sent from my iPhone"
- ❌ Letter on company letterhead (not email)

### 2. LEGAL_ADVICE (Green, #10B981)
**Definition:** Attorney opinions, legal analysis, privilege indicators

**Indicators:**
- Attorney-client privilege markers ("privileged and confidential")
- Legal opinion language ("In my legal opinion...", "Based on the case law...")
- Attorney email domains (@lawfirm.com, @legal.acme.com)
- Work product doctrine indicators ("prepared in anticipation of litigation")

**Examples:**
- ✅ "This communication is privileged. My legal advice is..."
- ✅ "From: counsel@jonesday.com - Here is our analysis of the complaint."
- ❌ Routine business advice from in-house counsel

### 3. CONTRACT (Yellow, #F59E0B)
**Definition:** Contractual terms, obligations, warranties, defined terms

**Indicators:**
- Modal verbs of obligation ("shall", "must", "agrees to")
- Defined terms in ALL CAPS or "quotation marks"
- Warranties and representations ("warrants that", "represents and warrants")
- Contract sections (WHEREAS clauses, consideration, indemnification)

**Examples:**
- ✅ "Licensor hereby grants to Licensee a non-exclusive license..."
- ✅ "The 'Effective Date' shall mean January 1, 2024."
- ❌ Informal handshake agreement (no contract language)

### 4. REGULATORY (Red, #EF4444)
**Definition:** Compliance issues, regulatory citations, hot documents, government warnings

**Indicators:**
- Regulatory agency mentions (FDA, FTC, SEC, DOJ, EPA)
- Statutory citations (21 CFR §, 15 USC §)
- Warning language ("violation", "non-compliance", "enforcement action")
- Subpoenas, civil investigative demands (CIDs), warning letters

**Examples:**
- ✅ "FDA Warning Letter: Adulterated product under 21 CFR 111.70"
- ✅ "FTC issued a Civil Investigative Demand regarding youth marketing"
- ❌ Routine compliance training materials

## Output Format

Return JSON with character-level spans:

```json
{
  "highlight_spans": [
    {
      "category": "EMAIL",
      "start": 0,
      "end": 245,
      "confidence": 0.95,
      "justification": "RFC 822 email header with From/To/Subject fields"
    },
    {
      "category": "LEGAL_ADVICE",
      "start": 450,
      "end": 892,
      "confidence": 0.87,
      "justification": "Attorney opinion language with privilege marker"
    }
  ]
}
```

## Confidence Scoring Guidelines

- **0.90-1.00 (Dark shade):** Unambiguous indicators present (e.g., explicit email header, "privileged and confidential")
- **0.75-0.89 (Medium shade):** Strong indicators but some ambiguity (e.g., legal language without privilege marker)
- **0.50-0.74 (Light shade):** Weak indicators, plausible but uncertain (e.g., business email with legal topics)
- **<0.50 (Do not highlight):** Insufficient evidence, flag for human review

## Privacy Requirement

**CRITICAL:** Do NOT include document excerpts or quoted text in your `justification` field. Only reference indicators and policy sections.

❌ Bad: "Justification: 'This is privileged per our prior conversation' indicates legal advice"
✅ Good: "Justification: Attorney privilege marker detected per policy §2.1"

## Edge Cases

- **Overlapping categories:** If a span matches multiple categories, output multiple highlights (e.g., EMAIL + LEGAL_ADVICE for privileged email)
- **Nested spans:** Allowed (e.g., CONTRACT term within a LEGAL_ADVICE paragraph)
- **Ambiguous language:** If confidence <0.5, omit highlight (attorney will review manually)
```

---

**End of Technical Design Document**
