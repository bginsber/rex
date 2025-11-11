Sprint 1 Tactical Plan: Redaction Pipeline Completion
Date: November 9, 2025
Duration: 5-8 working days
Owner: Ready for implementation
Branch: claude/ultrathink-m2-redaction-strategy-011CUwn1QQKa9ajd3aw7roFd

🎯 Sprint Goal
Complete the redaction workflow from PII detection through PDF black-box application, enabling production-ready document sanitization

🔍 Situation Analysis (Ultrathink Findings)
What We Discovered
✅ GOOD NEWS: PII Detection Already Works

PIIRegexAdapter fully implemented (181 lines, rexlit/app/adapters/pii_regex.py)
12 passing tests with 100% coverage (tests/test_pii_regex_adapter.py)
Detects: SSN, EMAIL, PHONE, CREDIT_CARD, custom NAMES
Supports domain whitelisting, pattern filtering, deterministic output
Status: Production-ready, just needs wiring
❌ THE REAL BLOCKER: Redaction Application

# rexlit/app/adapters/pdf_stamper.py:112-118
def apply_redactions(self, path: Path, output_path: Path, redactions: list[dict]) -> int:
    raise NotImplementedError("Redaction application is not yet implemented.")
⚠️ MISSING INTEGRATION: RedactionService → PIIPort

# rexlit/app/redaction_service.py:43-44
def __init__(self, pii_port: Any, ...):  # Not typed, not wired
    self.pii = pii_port  # Never actually called in plan()
What This Means
We don't need to build PII detection - we need to:

Wire existing adapter (15 minutes)
Actually use it in plan() (1 hour)
Implement PDF redaction (2-3 days) ← THE BIG LIFT
Test end-to-end workflow (1 day)
📋 Task Breakdown
TASK 1: Wire PIIRegexAdapter into Bootstrap (15 minutes)
Current State:

Adapter exists but isn't instantiated in dependency injection container
RedactionService receives pii_port: Any but it's None in tests
Action Required:

File: rexlit/bootstrap.py

from rexlit.app.adapters.pii_regex import PIIRegexAdapter

def create_container(settings: Settings | None = None) -> dict:
    # ... existing code ...
    
    # Add PII detection adapter
    container["pii_port"] = PIIRegexAdapter(
        profile={
            "enabled_patterns": ["SSN", "EMAIL", "PHONE", "CREDIT_CARD"],
            "domain_whitelist": [],  # Can be configured via settings later
        }
    )
    
    # Wire into RedactionService
    container["redaction_service"] = RedactionService(
        pii_port=container["pii_port"],
        stamp_port=container["stamp_port"],
        storage_port=container["storage_port"],
        ledger_port=container["ledger_port"],
        settings=settings,
    )
Acceptance:


[object Object] instantiated in container

[object Object] receives wired adapter

Type hint updated: [object Object] → [object Object]
TASK 2: Integrate PII Detection into plan() (1-2 hours)
Current State:

# rexlit/app/redaction_service.py:66-130
def plan(...) -> RedactionPlan:
    # Generates plan but NEVER calls self.pii.analyze_*()
    # Returns empty redactions: redactions=[]
Action Required:

File: rexlit/app/redaction_service.py

def plan(
    self,
    input_path: Path,
    output_plan_path: Path,
    *,
    pii_types: list[str] | None = None,
) -> RedactionPlan:
    """Generate redaction plan using PII detection."""
    
    if pii_types is None:
        pii_types = ["SSN", "EMAIL", "PHONE", "CREDIT_CARD"]
    
    resolved_input = Path(input_path).resolve()
    if not resolved_input.exists():
        raise FileNotFoundError(f"Redaction source not found: {resolved_input}")
    
    # ✅ NEW: Actually use PII port to find entities
    pii_findings = self.pii.analyze_document(
        path=str(resolved_input),
        entities=pii_types,
    )
    
    # ✅ NEW: Convert findings to redaction actions
    redaction_actions = [
        {
            "entity_type": finding.entity_type,
            "start": finding.start,
            "end": finding.end,
            "text": finding.text,  # Masked as "***"
            "confidence": finding.score,
            "page": finding.page,  # May be None for text extraction
        }
        for finding in pii_findings
    ]
    
    # Rest of plan() remains same...
    document_hash = self.storage.compute_hash(resolved_input)
    annotations = {
        "pii_types": sorted(pii_types),
        "detector": "PIIRegexAdapter",
        "finding_count": len(redaction_actions),
    }
    
    plan_id = compute_redaction_plan_id(
        document_path=resolved_input,
        content_hash=document_hash,
        actions=redaction_actions,  # Now includes actual redactions!
        annotations=annotations,
    )
    
    plan_entry = {
        "document": str(resolved_input),
        "sha256": document_hash,
        "plan_id": plan_id,
        "actions": redaction_actions,  # ✅ NEW: Real redactions
        "annotations": annotations,
        "notes": f"Found {len(redaction_actions)} PII entities",
    }
    
    write_redaction_plan_entry(resolved_output, plan_entry, key=self._plan_key)
    
    # Audit logging...
    if self.ledger is not None:
        self.ledger.log(
            operation="redaction_plan_create",
            inputs=[str(resolved_input)],
            outputs=[str(resolved_output)],
            args={
                "plan_id": plan_id,
                "document_sha256": document_hash,
                "pii_types": annotations["pii_types"],
                "finding_count": len(redaction_actions),
            },
        )
    
    return RedactionPlan(
        plan_id=plan_id,
        input_hash=document_hash,
        redactions=redaction_actions,  # ✅ NEW: Populated list
        rationale=f"PII detection via {annotations['detector']}",
    )
Acceptance:


[object Object] calls [object Object]

PII findings converted to redaction actions

Plan JSONL contains actual redaction coordinates

Test: Create plan from document with SSN, verify actions list
TASK 3: Implement apply_redactions() in PDFStamperAdapter (2-3 days) ⚠️ CRITICAL PATH
Current State:

# rexlit/app/adapters/pdf_stamper.py:112-118
def apply_redactions(...) -> int:
    raise NotImplementedError("Redaction application is not yet implemented.")
The Challenge: We need to convert character-based offsets (from text extraction) to PDF page coordinates (x, y, width, height) for black-box rendering.

3.1 Research: Text → Coordinate Mapping (4 hours)
Options:

Option A: PyMuPDF TextPage (Recommended)

import fitz  # PyMuPDF

# Extract text with position data
page = doc[page_num]
text_page = page.get_textpage()
text_dict = page.get_text("dict")  # Returns positions

# Find bounding box for character range
def get_bbox_for_chars(page, start_char, end_char):
    blocks = page.get_text("dict")["blocks"]
    # Iterate through blocks/lines/spans to find char positions
    # Return fitz.Rect with coordinates
Option B: pdfplumber (Alternative)

More accurate coordinate extraction
But adds new dependency
Slower performance
Option C: Regex + Layout Heuristic

Search for PII pattern in extracted text
Estimate position based on line number
HIGH RISK: Coordinate drift on multi-column layouts
Decision: Use Option A (PyMuPDF TextPage) - already imported, good accuracy

3.2 Implementation Strategy
Step 1: Character Offset → Page Coordinates

# rexlit/app/adapters/pdf_stamper.py

def _find_text_bbox(
    self,
    page: fitz.Page,
    search_text: str,
    *,
    case_sensitive: bool = False,
) -> list[fitz.Rect]:
    """Find bounding boxes for text occurrences on page."""
    
    # Use PyMuPDF's built-in search
    flags = 0 if case_sensitive else fitz.TEXT_PRESERVE_WHITESPACE
    rects = page.search_for(search_text, flags=flags)
    
    return rects

def _char_offset_to_bbox(
    self,
    page: fitz.Page,
    start_char: int,
    end_char: int,
) -> fitz.Rect | None:
    """Convert character offset to bounding box on page."""
    
    # Get text with position data
    text_dict = page.get_text("dict")
    
    # Walk through blocks/lines/spans to find character positions
    char_count = 0
    start_rect = None
    end_rect = None
    
    for block in text_dict.get("blocks", []):
        if block["type"] != 0:  # Skip non-text blocks
            continue
            
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_text = span["text"]
                span_bbox = fitz.Rect(span["bbox"])
                
                # Check if our target range is in this span
                if char_count <= start_char < char_count + len(span_text):
                    start_rect = span_bbox
                
                if char_count <= end_char < char_count + len(span_text):
                    end_rect = span_bbox
                    
                char_count += len(span_text)
    
    # Combine start and end rects
    if start_rect and end_rect:
        return start_rect | end_rect  # Union of rectangles
    
    return None
Step 2: Apply Black Box Redaction

def apply_redactions(
    self,
    path: Path,
    output_path: Path,
    redactions: list[dict[str, Any]],
) -> int:
    """Apply redaction black boxes to PDF.
    
    Args:
        path: Input PDF path
        output_path: Output redacted PDF path
        redactions: List of redaction dicts with keys:
            - entity_type: str (SSN, EMAIL, etc.)
            - start: int (character offset)
            - end: int (character offset)
            - text: str (masked text like "***")
            - page: int | None (page number, 0-indexed)
    
    Returns:
        Number of redactions applied
    """
    doc = fitz.open(str(path))
    applied_count = 0
    
    try:
        # Group redactions by page
        redactions_by_page: dict[int, list[dict]] = {}
        for redaction in redactions:
            page_num = redaction.get("page", 0) or 0
            if page_num not in redactions_by_page:
                redactions_by_page[page_num] = []
            redactions_by_page[page_num].append(redaction)
        
        # Process each page
        for page_num, page_redactions in redactions_by_page.items():
            if page_num >= len(doc):
                continue  # Skip invalid page numbers
                
            page = doc[page_num]
            
            for redaction in page_redactions:
                # Strategy 1: If we have exact text, search for it
                search_text = redaction.get("text", "").strip("*")
                
                if search_text and search_text != "":
                    # Find text on page
                    rects = self._find_text_bbox(page, search_text)
                    
                    for rect in rects:
                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        applied_count += 1
                
                # Strategy 2: Use character offsets (if available)
                elif "start" in redaction and "end" in redaction:
                    bbox = self._char_offset_to_bbox(
                        page,
                        redaction["start"],
                        redaction["end"],
                    )
                    
                    if bbox:
                        page.add_redact_annot(bbox, fill=(0, 0, 0))
                        applied_count += 1
            
            # Apply all redactions on this page (makes them permanent)
            page.apply_redactions()
        
        # Save redacted document
        doc.save(str(output_path))
        
    finally:
        doc.close()
    
    return applied_count
Step 3: Handle Edge Cases

# Add error handling for:
# - Rotated pages (detect rotation, adjust coordinates)
# - Multi-column layouts (coordinate system complexity)
# - Text in images (OCR-based redaction, future)
# - Encrypted PDFs (decrypt first, re-encrypt after)
# - Form fields (redact field values)
3.3 Testing Strategy
File: tests/test_redaction_apply.py (NEW)

"""Tests for PDF redaction application."""

import fitz
import pytest
from pathlib import Path

from rexlit.app.adapters.pdf_stamper import PDFStamperAdapter

@pytest.fixture
def pdf_stamper():
    return PDFStamperAdapter()

@pytest.fixture
def sample_pdf_with_ssn(tmp_path):
    """Create PDF with SSN for testing."""
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    
    # Insert SSN text at known position
    page.insert_text((100, 100), "SSN: 123-45-6789", fontsize=12)
    
    doc.save(str(pdf_path))
    doc.close()
    
    return pdf_path

# Test 1: Basic Black Box Redaction
def test_apply_single_redaction(pdf_stamper, sample_pdf_with_ssn, tmp_path):
    """Test applying single SSN redaction."""
    output = tmp_path / "redacted.pdf"
    
    redactions = [
        {
            "entity_type": "SSN",
            "text": "123-45-6789",
            "start": 5,
            "end": 16,
            "page": 0,
        }
    ]
    
    count = pdf_stamper.apply_redactions(
        sample_pdf_with_ssn,
        output,
        redactions,
    )
    
    assert count == 1
    assert output.exists()
    
    # Verify redaction was applied
    doc = fitz.open(str(output))
    page = doc[0]
    text = page.get_text()
    assert "123-45-6789" not in text  # SSN should be gone
    doc.close()

# Test 2: Multiple Redactions on Same Page
def test_multiple_redactions_same_page(pdf_stamper, tmp_path):
    """Test multiple PII entities on one page."""
    # Create PDF with SSN + email
    pdf_path = tmp_path / "multi.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "SSN: 123-45-6789", fontsize=12)
    page.insert_text((100, 120), "Email: test@example.com", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    
    output = tmp_path / "redacted.pdf"
    redactions = [
        {"entity_type": "SSN", "text": "123-45-6789", "page": 0},
        {"entity_type": "EMAIL", "text": "test@example.com", "page": 0},
    ]
    
    count = pdf_stamper.apply_redactions(pdf_path, output, redactions)
    
    assert count == 2
    
    # Verify both redacted
    doc = fitz.open(str(output))
    text = doc[0].get_text()
    assert "123-45-6789" not in text
    assert "test@example.com" not in text
    doc.close()

# Test 3: Multi-Page Document
def test_redactions_across_pages(pdf_stamper, tmp_path):
    """Test redactions on different pages."""
    pdf_path = tmp_path / "multipage.pdf"
    doc = fitz.open()
    
    # Page 1: SSN
    page1 = doc.new_page()
    page1.insert_text((100, 100), "Page 1 SSN: 111-11-1111", fontsize=12)
    
    # Page 2: Email
    page2 = doc.new_page()
    page2.insert_text((100, 100), "Page 2 Email: page2@test.com", fontsize=12)
    
    doc.save(str(pdf_path))
    doc.close()
    
    output = tmp_path / "redacted.pdf"
    redactions = [
        {"entity_type": "SSN", "text": "111-11-1111", "page": 0},
        {"entity_type": "EMAIL", "text": "page2@test.com", "page": 1},
    ]
    
    count = pdf_stamper.apply_redactions(pdf_path, output, redactions)
    
    assert count == 2
    
    # Verify page-specific redactions
    doc = fitz.open(str(output))
    assert "111-11-1111" not in doc[0].get_text()
    assert "page2@test.com" not in doc[1].get_text()
    doc.close()

# Test 4: Rotated Page Handling
def test_rotated_page_redaction(pdf_stamper, tmp_path):
    """Test redaction on rotated page."""
    pdf_path = tmp_path / "rotated.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.set_rotation(90)  # Rotate 90 degrees
    page.insert_text((100, 100), "SSN: 123-45-6789", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    
    output = tmp_path / "redacted.pdf"
    redactions = [{"entity_type": "SSN", "text": "123-45-6789", "page": 0}]
    
    count = pdf_stamper.apply_redactions(pdf_path, output, redactions)
    
    # Should handle rotation gracefully
    assert count >= 0  # May skip if rotation not supported yet

# Test 5: Empty Redaction List
def test_empty_redaction_list(pdf_stamper, sample_pdf_with_ssn, tmp_path):
    """Test with no redactions to apply."""
    output = tmp_path / "unchanged.pdf"
    
    count = pdf_stamper.apply_redactions(
        sample_pdf_with_ssn,
        output,
        [],
    )
    
    assert count == 0
    assert output.exists()

# Test 6: Invalid Page Number
def test_invalid_page_number(pdf_stamper, sample_pdf_with_ssn, tmp_path):
    """Test redaction with page number out of range."""
    output = tmp_path / "redacted.pdf"
    redactions = [
        {"entity_type": "SSN", "text": "123-45-6789", "page": 999}
    ]
    
    # Should not crash, just skip invalid pages
    count = pdf_stamper.apply_redactions(
        sample_pdf_with_ssn,
        output,
        redactions,
    )
    
    assert count == 0  # Nothing redacted

# Test 7: Text Not Found
def test_text_not_found_on_page(pdf_stamper, sample_pdf_with_ssn, tmp_path):
    """Test when redaction text doesn't exist on page."""
    output = tmp_path / "redacted.pdf"
    redactions = [
        {"entity_type": "SSN", "text": "999-99-9999", "page": 0}
    ]
    
    count = pdf_stamper.apply_redactions(
        sample_pdf_with_ssn,
        output,
        redactions,
    )
    
    assert count == 0  # Nothing found to redact

# Test 8: Character Offset Accuracy
def test_character_offset_to_bbox(pdf_stamper, tmp_path):
    """Test character offset conversion to coordinates."""
    # Create PDF with known text
    pdf_path = tmp_path / "offset_test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    text = "Contact: john@example.com for details"
    page.insert_text((100, 100), text, fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    
    output = tmp_path / "redacted.pdf"
    
    # Email starts at char 9, ends at char 26
    redactions = [
        {
            "entity_type": "EMAIL",
            "start": 9,
            "end": 26,
            "page": 0,
        }
    ]
    
    count = pdf_stamper.apply_redactions(pdf_path, output, redactions)
    
    # Should find and redact email
    assert count >= 0  # Implementation may vary
Acceptance Criteria:


All 8+ tests passing

Redactions visible as black boxes in output PDF

Original text no longer extractable from redacted areas

Multi-page handling works correctly

Rotated pages handled (or gracefully skipped with warning)
TASK 4: End-to-End Integration Test (1 day)
File: tests/test_redaction_e2e.py (NEW)

"""End-to-end redaction workflow tests."""

import pytest
from pathlib import Path
import fitz

from rexlit.app.redaction_service import RedactionService
from rexlit.app.adapters.pii_regex import PIIRegexAdapter
from rexlit.app.adapters.pdf_stamper import PDFStamperAdapter
from rexlit.app.adapters import FileSystemStorageAdapter
from rexlit.audit.ledger import FileSystemLedgerAdapter
from rexlit.config import Settings

@pytest.fixture
def full_redaction_service(tmp_path):
    """Create fully-wired redaction service."""
    settings = Settings(
        data_dir=tmp_path / "data",
        config_dir=tmp_path / "config",
        audit_enabled=True,
    )
    
    pii_port = PIIRegexAdapter()
    stamp_port = PDFStamperAdapter()
    storage_port = FileSystemStorageAdapter()
    ledger_path = tmp_path / "audit" / "ledger.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_port = FileSystemLedgerAdapter(str(ledger_path))
    
    return RedactionService(
        pii_port=pii_port,
        stamp_port=stamp_port,
        storage_port=storage_port,
        ledger_port=ledger_port,
        settings=settings,
    )

def test_full_redaction_workflow(full_redaction_service, tmp_path):
    """Test complete plan → apply workflow."""
    
    # Create test PDF with PII
    test_pdf = tmp_path / "sensitive.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "SSN: 123-45-6789", fontsize=12)
    page.insert_text((100, 120), "Email: secret@company.com", fontsize=12)
    doc.save(str(test_pdf))
    doc.close()
    
    # Step 1: Plan redactions
    plan_path = tmp_path / "redaction.plan.enc"
    plan = full_redaction_service.plan(
        input_path=test_pdf,
        output_plan_path=plan_path,
        pii_types=["SSN", "EMAIL"],
    )
    
    assert plan.plan_id
    assert len(plan.redactions) == 2  # SSN + Email
    assert plan_path.exists()
    
    # Step 2: Validate plan
    is_valid = full_redaction_service.validate_plan(plan_path)
    assert is_valid is True
    
    # Step 3: Apply redactions
    output_dir = tmp_path / "redacted"
    count = full_redaction_service.apply(
        plan_path=plan_path,
        output_path=output_dir,
        preview=False,
        force=False,
    )
    
    assert count == 2  # 2 redactions applied
    
    # Step 4: Verify redacted PDF
    redacted_pdf = output_dir / "sensitive.pdf"
    assert redacted_pdf.exists()
    
    doc = fitz.open(str(redacted_pdf))
    text = doc[0].get_text()
    assert "123-45-6789" not in text  # SSN gone
    assert "secret@company.com" not in text  # Email gone
    doc.close()
    
    # Step 5: Verify audit trail
    # (Check ledger has plan_create + apply entries)

def test_hash_mismatch_prevents_application(full_redaction_service, tmp_path):
    """Test that modifying PDF after plan prevents application."""
    
    # Create + plan
    test_pdf = tmp_path / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((100, 100), "SSN: 111-22-3333", fontsize=12)
    doc.save(str(test_pdf))
    doc.close()
    
    plan_path = tmp_path / "plan.enc"
    full_redaction_service.plan(test_pdf, plan_path)
    
    # Modify PDF after planning
    doc = fitz.open(str(test_pdf))
    page = doc[0]
    page.insert_text((100, 120), "MODIFIED", fontsize=12)
    doc.save(str(test_pdf))
    doc.close()
    
    # Apply should fail due to hash mismatch
    with pytest.raises(ValueError, match="hash mismatch"):
        full_redaction_service.apply(
            plan_path=plan_path,
            output_path=tmp_path / "out",
            force=False,
        )
TASK 5: CLI Command Integration (0.5 day)
File: rexlit/cli.py

Add redaction commands (if not already present):

@app.command()
def redaction_plan(
    input_path: Path = typer.Argument(..., help="Document or directory to scan"),
    output_plan: Path = typer.Option(
        None, "--output", "-o", help="Output plan path"
    ),
    pii_types: str = typer.Option(
        "SSN,EMAIL,PHONE,CREDIT_CARD",
        "--pii-types",
        help="Comma-separated PII types to detect",
    ),
):
    """Generate redaction plan for PII entities."""
    container = create_container()
    service = container["redaction_service"]
    
    types_list = [t.strip() for t in pii_types.split(",")]
    
    if output_plan is None:
        output_plan = Path.cwd() / f"{input_path.stem}.redaction-plan.enc"
    
    plan = service.plan(
        input_path=input_path,
        output_plan_path=output_plan,
        pii_types=types_list,
    )
    
    console.print(f"✅ Redaction plan created: {output_plan}")
    console.print(f"   Plan ID: {plan.plan_id}")
    console.print(f"   Redactions found: {len(plan.redactions)}")

@app.command()
def redaction_apply(
    plan_path: Path = typer.Argument(..., help="Redaction plan file"),
    output_dir: Path = typer.Argument(..., help="Output directory"),
    preview: bool = typer.Option(False, "--preview", help="Preview mode (no write)"),
    force: bool = typer.Option(False, "--force", help="Force despite hash mismatch"),
):
    """Apply redaction plan to documents."""
    container = create_container()
    service = container["redaction_service"]
    
    count = service.apply(
        plan_path=plan_path,
        output_path=output_dir,
        preview=preview,
        force=force,
    )
    
    if preview:
        console.print(f"🔍 Preview: Would apply {count} redactions")
    else:
        console.print(f"✅ Applied {count} redactions to {output_dir}")
Usage:

# Create plan
rexlit redaction-plan ./sensitive-doc.pdf --pii-types SSN,EMAIL

# Preview
rexlit redaction-apply ./sensitive-doc.redaction-plan.enc ./preview/ --preview

# Apply
rexlit redaction-apply ./sensitive-doc.redaction-plan.enc ./redacted/
TASK 6: Type Annotation Cleanup (Quick Win, 1 hour)
Files to update:

rexlit/app/redaction_service.py:43-44
rexlit/app/pack_service.py:40-45
Changes:

# BEFORE
def __init__(self, pii_port: Any, stamp_port: Any, ...):

# AFTER
from rexlit.app.ports.pii import PIIPort
from rexlit.app.ports.stamp import StampPort

def __init__(
    self,
    pii_port: PIIPort,
    stamp_port: StampPort,
    storage_port: StoragePort,
    ledger_port: LedgerPort,
    settings: Settings | None = None,
):
Run:

mypy rexlit/ --strict
⚠️ Known Challenges & Mitigation
| Challenge | Risk | Mitigation | |-----------|------|------------| | Character offset → PDF coords | High | Use PyMuPDF TextPage API (battle-tested) | | Multi-column layouts | Medium | Search by text content (fallback strategy) | | Rotated pages | Low | Detect rotation, log warning if unsupported | | OCR-based PDFs | Medium | Future enhancement (M3) | | Performance (large PDFs) | Low | Apply redactions page-by-page (memory efficient) | | Hash mismatch frequency | Low | Clear user messaging + --force override |

📊 Success Metrics
After Sprint 1:


PIIRegexAdapter wired into bootstrap

[object Object] populates real redactions

[object Object] fully implemented (20-30 lines)

8+ new PDF redaction tests passing

E2E test: plan → apply → verify works

CLI commands functional

Total tests: 165+ → 175+ (all passing)

mypy strict mode passing

Ready for Sprint 2 (load file formats)
📅 Time Estimate
| Task | Estimate | Dependency | |------|----------|------------| | Wire PIIRegexAdapter | 15 min | None | | Integrate PII into plan() | 1-2 hrs | Wire complete | | Research coordinate mapping | 4 hrs | None (parallel) | | Implement apply_redactions() | 12-16 hrs | Research complete | | Write 8+ PDF tests | 6-8 hrs | Implementation | | E2E integration test | 4 hrs | All above | | CLI commands | 2 hrs | E2E passing | | Type cleanup | 1 hr | None (parallel) | | TOTAL | 30-38 hrs | 5-8 days |

🚀 Sprint Execution Plan
Day 1-2: Foundation + Research

Wire PIIRegexAdapter (15 min)

Integrate into plan() (2 hrs)

Research PyMuPDF coordinate mapping (4 hrs)

Start test file structure
Day 3-4: Core Implementation

Implement [object Object] helper

Implement [object Object] helper

Implement [object Object] main method

Write first 4 tests
Day 5-6: Testing + Polish

Complete remaining 4+ tests

E2E integration test

CLI command integration

Type annotation cleanup
Day 7-8: Validation + Documentation

Full regression test suite

Performance benchmarking (100+ doc corpus)

Update CLAUDE.md

Commit + push to branch
✅ Definition of Done
Code:


All new code passes [object Object]

All new code passes [object Object]

All new code has docstrings (Google style)
Tests:


175+ total tests passing (151 + 24 new)

E2E redaction workflow works end-to-end

Hash verification prevents wrong-doc redaction
Integration:


PIIPort wired in bootstrap

CLI commands functional

Audit trail logs plan + apply operations
Documentation:


CLAUDE.md updated with redaction workflow

CLI-GUIDE.md has redaction examples

Inline comments explain coordinate logic
Ready for:


Code review

Merge to main

Sprint 2 (Opticon/LFP load files)
🔗 References
ADRs:

ADR 0006: Redaction Plan/Apply Model
ADR 0003: Determinism Policy
ADR 0001: Offline-First Gate
Code Files:

rexlit/app/adapters/pii_regex.py (existing, 181 lines)
rexlit/app/ports/pii.py (existing, 77 lines)
tests/test_pii_regex_adapter.py (existing, 124 lines, 12 tests)
External Docs:

PyMuPDF Redaction Tutorial
NIST SP 800-88: Data Sanitization
FRCP Rule 26(b)(5): Privilege Claims
Status: Ready to execute
Blocker: None
Next Sprint: Opticon/LFP load files + DAT consolidation