# RexLit Highlighting System - Pseudocode Sketch

## 1. Data Models (`rexlit/app/ports/highlighting.py`)

```python
class HighlightingFinding(BaseModel):
    """Single text region marked for highlighting."""

    # Core identification
    category: str  # "ACP", "ADMISSION", "DAMAGES", "CONTRADICTION", "CREDIBILITY"
    text: str      # Actual highlighted text
    score: float   # Confidence (0.0-1.0): regex=1.0, LLM-enhanced=0.6-0.9

    # Location in document
    start: int           # Character offset (from concatenated PDF text)
    end: int            # Character offset
    page: int | None    # PDF page number (0-indexed)

    # Context & reasoning
    reason: str         # Why highlighted: "matches_admission_pattern" or "llm_credibility"
    context_before: str # Preceding 50 chars for human review
    context_after: str  # Following 50 chars for human review

    # Visual properties
    color: str          # "yellow", "green", "red", "blue" (mapped from category)
    opacity: float      # 0.3-0.7 for semi-transparency

    # Metadata
    metadata: dict      # Extra info: {"pattern": "we admit", "pattern_confidence": 0.95}


class HighlightingPlan(BaseModel):
    """Complete highlighting plan for a document."""

    plan_id: str                          # Deterministic hash (document + findings)
    input_hash: str                       # SHA-256 of source document
    document_path: str                    # Source file
    findings: list[HighlightingFinding]  # All highlights

    # Annotations
    timestamp: datetime
    detector: str                         # "HighlightingPatternAdapter" or provider name
    stage: int                            # 1=credibility, 2=relevance, 3=expert_review
    notes: str                            # Human-readable summary

    # Statistics
    summary: dict  # {
                   #   "total_findings": 42,
                   #   "by_category": {"ACP": 10, "ADMISSION": 8, ...},
                   #   "by_confidence": {"high": 35, "medium": 7},
                   #   "pages_affected": [1, 3, 5, 7],
                   # }


class HighlightingCategory(Enum):
    """Predefined highlight categories for legal discovery."""

    # Privilege-adjacent (but not privileged)
    ACP_DESIGNATION = ("ACP/WP designation language", "yellow")
    PRIVILEGE_CLAIM = ("Privilege invocation attempt", "yellow")

    # Admissions & Adverse Statements
    ADMISSION = ("Party admission/concession", "red")
    CONTRADICTION = ("Internal contradiction", "red")
    DENIAL = ("Denial of key fact", "orange")

    # Credibility Indicators
    EVASIVENESS = ("Evasive/non-responsive language", "red")
    DEMEANOR = ("Demeanor language (angry, biased)", "orange")

    # Damages & Remedies
    DAMAGES_ESTIMATE = ("Damages/harm quantification", "green")
    SETTLEMENT_DEMAND = ("Settlement demand/amount", "green")

    # Causation & Knowledge
    CAUSATION = ("Causation statement", "blue")
    KNOWLEDGE = ("Knowledge statement", "blue")

    # Inconsistencies
    PRIOR_STATEMENT = ("Contradicts prior statement", "red")
    DATE_INCONSISTENCY = ("Date/timeline inconsistency", "orange")

```

---

## 2. Port Interface (`rexlit/app/ports/highlighting.py` - continued)

```python
from typing import Protocol

class HighlightFinderPort(Protocol):
    """Port for finding text regions to highlight."""

    def analyze_document(
        self,
        path: str,
        *,
        categories: list[str] | None = None,  # Specific categories to find
        min_confidence: float = 0.5,
        context_size: int = 50,
    ) -> list[HighlightingFinding]:
        """
        Analyze document and return highlighting findings.

        Args:
            path: Path to PDF or document
            categories: Which highlight categories to search for (None = all)
            min_confidence: Minimum confidence score to include (0.0-1.0)
            context_size: Characters before/after to include as context

        Returns:
            List of HighlightingFinding objects, sorted by page/position
        """
        ...

    def get_supported_categories(self) -> list[str]:
        """Return list of supported highlight categories."""
        ...

    def requires_online(self) -> bool:
        """Return True if adapter needs network (e.g., LLM)."""
        ...


class HighlightApplierPort(Protocol):
    """Port for applying highlights to documents."""

    def apply(
        self,
        source_path: str,
        plan: HighlightingPlan,
        output_path: str,
        *,
        include_metadata: bool = True,
    ) -> int:
        """
        Apply highlights from plan to source document.

        Creates new PDF with:
        - Transparent highlight annotations (non-destructive)
        - Hover tooltips showing category/reason
        - Optional: metadata sidebar listing all highlights

        Args:
            source_path: Original PDF
            plan: HighlightingPlan with findings
            output_path: Path for highlighted PDF
            include_metadata: Add info panel to document

        Returns:
            Count of highlights successfully applied

        Raises:
            ValueError: If source_path doesn't match plan input_hash
        """
        ...

```

---

## 3. Adapter Implementation (`rexlit/app/adapters/highlighting_patterns.py`)

```python
class HighlightingPatternAdapter(HighlightFinderPort):
    """
    Multi-stage pattern-based highlighting finder.

    Stage 1: Fast regex patterns (100% offline)
    Stage 2: Optional LLM scoring (confidence enhancement)
    Stage 3: Context-aware filtering (reduce false positives)

    Design mirrors privilege classification pipeline for consistency.
    """

    def __init__(
        self,
        llm_port: LLMScoringPort | None = None,  # Optional escalation to LLM
        settings: Settings | None = None,
    ):
        self.llm = llm_port
        self._settings = settings or get_settings()
        self._compile_patterns()

    # ========== STAGE 1: PATTERN DEFINITIONS ==========

    PATTERNS: dict[str, dict] = {
        "ADMISSION": {
            "regex": [
                r"\b(we\s+admit|we\s+concede|it\s+is\s+true|agreed|we\s+agree)\b",
                r"\b(acknowledged|conceded|we\s+acknowledge)\b",
                r"\b(we\s+did\s+not|we\s+never|we\s+failed\s+to)\b",
            ],
            "confidence": 0.95,
            "description": "Party admission or concession",
        },

        "CONTRADICTION": {
            "regex": [
                r"\b(inconsistent\s+with|contradicts|contradicted\s+by|contrary\s+to)\b",
                r"\b(on\s+the\s+other\s+hand|however|but\s+earlier|previously\s+stated)\b",
            ],
            "confidence": 0.85,
            "description": "Internal contradiction or inconsistency",
        },

        "ACP_DESIGNATION": {
            "regex": [
                r"\b(attorney\s+client|work\s+product|attorney.?client|client\s+privilege)\b",
                r"\b(prepared\s+at\s+request\s+of|in\s+anticipation\s+of\s+litigation)\b",
                r"\b(confidential|privileged|attorney|counsel)\b(?=\s+(notes|advice|opinion))",
            ],
            "confidence": 0.90,
            "description": "ACP/Work Product designation (context clue)",
        },

        "DAMAGES_ESTIMATE": {
            "regex": [
                r"\$([\d,]+(?:\.\d{2})?)",  # Dollar amounts
                r"\b(damages?|compensation|harm|injury|loss)\s*[\$\d]",
                r"\b(calculate|estimate|assess|value)\s+(damages|harm|loss|injury)",
            ],
            "confidence": 0.80,
            "description": "Damages or monetary estimation",
        },

        "EVASIVENESS": {
            "regex": [
                r"\b(I\s+don't\s+recall|I\s+don't\s+remember|unclear|I\s+don't\s+know)\b",
                r"\b(as\s+far\s+as\s+I\s+know|to\s+the\s+best\s+of\s+my|I\s+can't\s+say)\b",
                r"\b(I\s+wouldn't\s+characterize|I\s+don't\s+think|no\s+response)\b",
            ],
            "confidence": 0.70,
            "description": "Evasive or non-responsive language",
        },

        "CAUSATION": {
            "regex": [
                r"\b(caused\s+by|because\s+of|resulted\s+from|led\s+to|caused)\b",
                r"\b(as\s+a\s+result\s+of|due\s+to|which\s+caused|which\s+led)\b",
            ],
            "confidence": 0.85,
            "description": "Causation or chain of events",
        },

        "KNOWLEDGE": {
            "regex": [
                r"\b(knew\s+or\s+should\s+have\s+known|aware|knew|should\s+have\s+known)\b",
                r"\b(had\s+knowledge|informed|notified|notice)\b",
            ],
            "confidence": 0.80,
            "description": "Knowledge statement",
        },
    }


    # ========== STAGE 1: PATTERN MATCHING ==========

    def analyze_document(
        self,
        path: str,
        *,
        categories: list[str] | None = None,
        min_confidence: float = 0.5,
        context_size: int = 50,
    ) -> list[HighlightingFinding]:
        """
        Multi-stage highlighting analysis.
        """

        # Extract text with page offsets
        path_obj = Path(path)
        text, page_spans = self._extract_text_with_offsets(path_obj)

        if not text:
            return []

        # Stage 1: Pattern matching
        findings = self._stage1_pattern_matching(
            text,
            page_spans,
            categories,
            min_confidence,
            context_size,
        )

        # Stage 2: Optional LLM confidence scoring (if available)
        if self.llm and not self._settings.is_offline:
            findings = self._stage2_llm_scoring(
                findings,
                text,
                page_spans,
            )

        # Stage 3: Context-aware filtering
        findings = self._stage3_filter_duplicates(findings)

        return sorted(findings, key=lambda f: (f.page or 0, f.start))


    def _stage1_pattern_matching(
        self,
        text: str,
        page_spans: list[tuple[int, int, int]],
        categories: list[str] | None,
        min_confidence: float,
        context_size: int,
    ) -> list[HighlightingFinding]:
        """
        Stage 1: Fast regex pattern matching (100% offline).

        Returns all pattern matches above min_confidence.
        """
        findings = []
        target_categories = (
            set(categories) & set(self.PATTERNS.keys())
            if categories
            else set(self.PATTERNS.keys())
        )

        for category in target_categories:
            pattern_config = self.PATTERNS[category]
            base_confidence = pattern_config["confidence"]

            if base_confidence < min_confidence:
                continue

            for regex_str in pattern_config["regex"]:
                pattern = re.compile(regex_str, re.IGNORECASE | re.MULTILINE)

                for match in pattern.finditer(text):
                    # Extract context
                    start = max(0, match.start() - context_size)
                    end = min(len(text), match.end() + context_size)

                    context_before = text[start:match.start()]
                    context_after = text[match.end():end]

                    # Determine page
                    page = self._lookup_page(match.start(), page_spans)

                    # Adjust confidence based on context length
                    # (longer match = higher confidence)
                    match_length = match.end() - match.start()
                    confidence = min(1.0, base_confidence * (1 + match_length / 100))

                    finding = HighlightingFinding(
                        category=category,
                        text=match.group(0),
                        score=confidence,
                        start=match.start(),
                        end=match.end(),
                        page=page,
                        reason=f"matches_{category.lower()}_pattern",
                        context_before=context_before[-30:],  # Last 30 chars
                        context_after=context_after[:30],     # First 30 chars
                        color=self._category_to_color(category),
                        opacity=0.3 + (confidence * 0.4),  # 0.3-0.7 based on confidence
                        metadata={
                            "pattern": pattern_config["description"],
                            "regex": regex_str,
                            "base_confidence": base_confidence,
                            "match_length": match_length,
                        },
                    )
                    findings.append(finding)

        return findings


    def _stage2_llm_scoring(
        self,
        findings: list[HighlightingFinding],
        text: str,
        page_spans: list[tuple[int, int, int]],
    ) -> list[HighlightingFinding]:
        """
        Stage 2: Optional LLM credibility scoring (requires online mode).

        For uncertain findings (0.5-0.8 confidence), escalate to LLM:
        - "Is this actually an admission, or just a neutral statement?"
        - "How credible is this statement in context?"
        - Returns adjusted confidence and credibility score

        Only call if online + finding.score in [0.5, 0.8]
        """
        low_confidence_findings = [
            f for f in findings if 0.5 <= f.score <= 0.8
        ]

        if not low_confidence_findings:
            return findings

        # Batch LLM calls to reduce API cost
        prompt_batch = []
        for finding in low_confidence_findings:
            # Build context window
            context_start = max(0, finding.start - 200)
            context_end = min(len(text), finding.end + 200)
            context = text[context_start:context_end]

            prompt = f"""
            Document excerpt:
            [{context}]

            Highlighted text: "{finding.text}"
            Category: {finding.category}

            Questions:
            1. Does this text actually support the "{finding.category}" category?
            2. On scale 0-10, how credible/significant is this?
            3. Should this be included in highlighted findings?

            Respond with JSON: {{"keep": true/false, "credibility": 0-10, "reason": "..."}}
            """
            prompt_batch.append((finding, prompt))

        # Call LLM (example using groq_port or similar)
        llm_results = self.llm.score_batch(prompt_batch)

        # Update findings with LLM confidence
        for finding, result in zip(low_confidence_findings, llm_results):
            if result["keep"]:
                # Boost confidence based on LLM credibility score (0-10 -> 0.0-1.0)
                llm_confidence = result["credibility"] / 10.0
                finding.score = (finding.score + llm_confidence) / 2.0  # Blend
                finding.metadata["llm_credibility"] = llm_confidence
                finding.metadata["llm_reason"] = result["reason"]
            else:
                # Mark for removal
                finding.score = -1.0  # Flag for filtering

        return [f for f in findings if f.score >= 0.0]


    def _stage3_filter_duplicates(
        self,
        findings: list[HighlightingFinding],
    ) -> list[HighlightingFinding]:
        """
        Stage 3: Remove overlapping findings (keep highest confidence).

        Example: If "we admit" (high conf) and "we" (medium conf) overlap,
        keep only the longer, higher-confidence one.
        """
        if not findings:
            return findings

        # Sort by page, then by start position, then by confidence (descending)
        sorted_findings = sorted(
            findings,
            key=lambda f: (f.page or 0, f.start, -f.score),
        )

        filtered = []
        last_end = -1
        last_page = -1

        for finding in sorted_findings:
            # Skip if overlaps with previous finding
            if (finding.page or 0) == last_page and finding.start < last_end:
                continue  # Overlapping; previous one had higher score

            filtered.append(finding)
            last_end = finding.end
            last_page = finding.page or 0

        return filtered


    # ========== HELPERS ==========

    def _extract_text_with_offsets(
        self,
        path: Path,
    ) -> tuple[str, list[tuple[int, int, int]]]:
        """
        Extract text from document with per-page character offsets.

        Mirrors PIIRegexAdapter._extract_pdf_text_with_offsets for consistency.

        Returns:
            (concatenated_text, [(page_index, start_offset, end_offset), ...])
        """
        if path.suffix.lower() == ".pdf":
            import fitz  # type: ignore

            doc = fitz.open(str(path))
            segments = []
            spans = []
            cursor = 0

            try:
                for page_index in range(doc.page_count):
                    page_text = doc[page_index].get_text()
                    segments.append(page_text)
                    start = cursor
                    cursor += len(page_text)
                    spans.append((page_index, start, cursor))
                    if page_index != doc.page_count - 1:
                        segments.append("\n\n")
                        cursor += 2

                return "".join(segments), spans
            finally:
                doc.close()
        else:
            # For non-PDFs, treat whole document as page 0
            text = extract_document(path).text
            return text, [(0, 0, len(text))]


    @staticmethod
    def _lookup_page(
        offset: int,
        spans: list[tuple[int, int, int]],
    ) -> int | None:
        """Find which page a character offset belongs to."""
        for page_index, start, end in spans:
            if start <= offset < end:
                return page_index
        return None


    @staticmethod
    def _category_to_color(category: str) -> str:
        """Map category to highlight color."""
        color_map = {
            "ADMISSION": "red",
            "CONTRADICTION": "red",
            "DENIAL": "orange",
            "EVASIVENESS": "red",
            "ACP_DESIGNATION": "yellow",
            "PRIVILEGE_CLAIM": "yellow",
            "DAMAGES_ESTIMATE": "green",
            "SETTLEMENT_DEMAND": "green",
            "CAUSATION": "blue",
            "KNOWLEDGE": "blue",
            "PRIOR_STATEMENT": "red",
            "DATE_INCONSISTENCY": "orange",
        }
        return color_map.get(category, "gray")


    def get_supported_categories(self) -> list[str]:
        """Return list of supported highlighting categories."""
        return list(self.PATTERNS.keys())


    def requires_online(self) -> bool:
        """Return True if LLM scoring is enabled."""
        return bool(self.llm)

```

---

## 4. Orchestration Service (`rexlit/app/highlighting_service.py`)

```python
class HighlightingService:
    """
    Orchestrates highlighting with plan/apply pattern.

    Mirrors RedactionService for architectural consistency:
    1. plan: Generate highlighting coordinates without modifying PDFs
    2. apply: Create annotated PDF with highlights
    3. audit: Log all operations in ledger
    """

    def __init__(
        self,
        *,
        finder_port: HighlightFinderPort,
        applier_port: HighlightApplierPort,
        ledger_port: LedgerPort | None = None,
        settings: Settings | None = None,
    ):
        self.finder = finder_port
        self.applier = applier_port
        self.ledger = ledger_port
        self._settings = settings or get_settings()


    def plan(
        self,
        input_path: Path,
        output_plan_path: Path,
        *,
        categories: list[str] | None = None,
        min_confidence: float = 0.5,
    ) -> HighlightingPlan:
        """
        Generate highlighting plan without modifying PDFs.

        Args:
            input_path: Path to PDF or directory
            output_plan_path: Output path for plan JSONL
            categories: Which categories to highlight (None = all)
            min_confidence: Minimum confidence threshold (0.0-1.0)

        Returns:
            HighlightingPlan with deterministic plan_id

        Side effects:
            - Writes plan to output_plan_path
            - Logs operation to ledger (if configured)
        """
        resolved_input = Path(input_path).resolve()
        resolved_output = Path(output_plan_path).resolve()

        if not resolved_input.exists():
            raise FileNotFoundError(f"Input not found: {resolved_input}")

        resolved_output.parent.mkdir(parents=True, exist_ok=True)

        # Find highlights
        findings = self.finder.analyze_document(
            str(resolved_input),
            categories=categories,
            min_confidence=min_confidence,
        )

        # Compute deterministic plan ID
        document_hash = self._compute_hash(resolved_input)
        plan_id = self._compute_plan_id(
            document_path=resolved_input,
            content_hash=document_hash,
            findings=findings,
        )

        # Build plan
        summary = self._summarize_findings(findings)
        plan = HighlightingPlan(
            plan_id=plan_id,
            input_hash=document_hash,
            document_path=str(resolved_input),
            findings=findings,
            timestamp=datetime.now(timezone.utc),
            detector=self.finder.__class__.__name__,
            stage=1,  # Configurable
            notes=f"Found {len(findings)} highlights across {len(summary['by_category'])} categories",
            summary=summary,
        )

        # Persist plan (encrypted JSONL, like redaction plans)
        self._write_plan(plan, resolved_output)

        # Audit
        if self.ledger:
            self.ledger.log(
                operation="highlighting_plan_create",
                inputs=[str(resolved_input)],
                outputs=[str(resolved_output)],
                args={
                    "plan_id": plan_id,
                    "document_sha256": document_hash,
                    "finding_count": len(findings),
                    "categories": list(summary["by_category"].keys()),
                    "min_confidence": min_confidence,
                },
            )

        return plan


    def apply(
        self,
        plan_path: Path,
        output_path: Path,
        *,
        include_metadata: bool = True,
        force: bool = False,
    ) -> int:
        """
        Apply highlights from plan to PDF.

        Safety checks:
        1. Verify source PDF hash matches plan (abort if mismatch)
        2. Validate plan integrity (deterministic ID)
        3. Create new PDF with annotation layer (non-destructive)

        Args:
            plan_path: Path to highlighting plan JSONL
            output_path: Output directory for highlighted PDFs
            include_metadata: Add info panel to document
            force: Skip hash verification (dangerous)

        Returns:
            Count of highlights successfully applied

        Raises:
            ValueError: If plan hash doesn't match current PDF
            FileNotFoundError: If plan or source PDF not found
        """
        resolved_plan = Path(plan_path).resolve()
        resolved_output = Path(output_path).resolve()

        if not resolved_plan.exists():
            raise FileNotFoundError(f"Plan not found: {resolved_plan}")

        # Load and validate plan
        plan = self._read_plan(resolved_plan)
        source_pdf = Path(plan.document_path).resolve()

        if not source_pdf.exists():
            raise FileNotFoundError(f"Source PDF not found: {source_pdf}")

        # Verify hash match
        if not force:
            current_hash = self._compute_hash(source_pdf)
            if current_hash != plan.input_hash:
                raise ValueError(
                    f"Hash mismatch: plan expects {plan.input_hash}, "
                    f"but PDF is {current_hash}. Use --force to override."
                )

        # Apply highlights
        resolved_output.mkdir(parents=True, exist_ok=True)
        destination_pdf = resolved_output / source_pdf.name

        applied_count = self.applier.apply(
            source_path=str(source_pdf),
            plan=plan,
            output_path=str(destination_pdf),
            include_metadata=include_metadata,
        )

        # Audit
        if self.ledger:
            self.ledger.log(
                operation="highlighting_apply",
                inputs=[str(source_pdf), str(resolved_plan)],
                outputs=[str(destination_pdf)],
                args={
                    "plan_id": plan.plan_id,
                    "highlight_count": applied_count,
                    "include_metadata": include_metadata,
                    "force": force,
                },
            )

        return applied_count


    def _summarize_findings(self, findings: list[HighlightingFinding]) -> dict:
        """Generate summary statistics."""
        by_category = {}
        by_confidence = {"high": 0, "medium": 0, "low": 0}
        pages = set()

        for finding in findings:
            # Category count
            by_category[finding.category] = by_category.get(finding.category, 0) + 1

            # Confidence tiers
            if finding.score >= 0.8:
                by_confidence["high"] += 1
            elif finding.score >= 0.6:
                by_confidence["medium"] += 1
            else:
                by_confidence["low"] += 1

            # Pages affected
            if finding.page is not None:
                pages.add(finding.page)

        return {
            "by_category": by_category,
            "by_confidence": by_confidence,
            "pages_affected": sorted(pages),
            "total": len(findings),
        }


    @staticmethod
    def _compute_hash(path: Path) -> str:
        """Compute SHA-256 hash of file (mirrors storage port)."""
        import hashlib
        hash_obj = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()


    @staticmethod
    def _compute_plan_id(
        document_path: Path,
        content_hash: str,
        findings: list[HighlightingFinding],
    ) -> str:
        """
        Compute deterministic plan ID from content.

        If findings change but document stays same, plan_id changes.
        Used for integrity verification.
        """
        import hashlib
        data = f"{document_path}|{content_hash}|" + "|".join(
            f"{f.start}:{f.end}:{f.category}" for f in findings
        )
        return hashlib.sha256(data.encode()).hexdigest()[:16]

```

---

## 5. Bootstrap Wiring (`rexlit/bootstrap.py` - additions)

```python
def create_container() -> Container:
    """Dependency injection container (existing + new highlighting)."""

    container = Container()
    settings = get_settings()

    # ... existing ports ...

    # Highlighting ports (new)
    if settings.highlighting_mode == "patterns":
        highlighting_finder = HighlightingPatternAdapter(
            llm_port=None if settings.is_offline else groq_llm_port,
            settings=settings,
        )
    elif settings.highlighting_mode == "llm":
        highlighting_finder = HighlightingLLMAdapter(settings=settings)
    else:
        highlighting_finder = NoOpHighlightingAdapter()

    highlighting_applier = PDFHighlightingApplier(settings=settings)

    container.highlighting_finder = highlighting_finder
    container.highlighting_applier = highlighting_applier
    container.highlighting_service = HighlightingService(
        finder_port=highlighting_finder,
        applier_port=highlighting_applier,
        ledger_port=ledger,
        settings=settings,
    )

    return container

```

---

## 6. CLI Integration (`rexlit/cli.py` - additions)

```python
@app.command()
def highlight_plan(
    input_path: Path = typer.Argument(...),
    output_plan: Path = typer.Option("highlights.plan.jsonl"),
    categories: str = typer.Option(
        None,
        help="Comma-separated categories (e.g., ADMISSION,CONTRADICTION)"
    ),
    min_confidence: float = typer.Option(0.5, min=0.0, max=1.0),
    json_output: bool = typer.Option(False),
) -> None:
    """
    Generate highlighting plan for document.

    Plan file can be inspected, edited, or applied later.
    """
    container = bootstrap.create_container()
    service = container.highlighting_service

    parsed_categories = categories.split(",") if categories else None

    plan = service.plan(
        input_path,
        output_plan,
        categories=parsed_categories,
        min_confidence=min_confidence,
    )

    if json_output:
        typer.echo(plan.model_dump_json())
    else:
        typer.echo(f"✓ Plan created: {output_plan}")
        typer.echo(f"  Findings: {plan.summary['total']}")
        for cat, count in plan.summary["by_category"].items():
            typer.echo(f"    {cat}: {count}")


@app.command()
def highlight_apply(
    plan_path: Path = typer.Argument(...),
    output_dir: Path = typer.Option("highlighted/"),
    include_metadata: bool = typer.Option(True),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """
    Apply highlighting plan to PDF.

    Creates new PDF with annotation layer (original unmodified).
    """
    container = bootstrap.create_container()
    service = container.highlighting_service

    count = service.apply(
        plan_path,
        output_dir,
        include_metadata=include_metadata,
        force=force,
    )

    typer.echo(f"✓ Applied {count} highlights")
    typer.echo(f"  Output: {output_dir}")

```

---

## 7. PDF Applier Adapter (`rexlit/app/adapters/highlighting_applier.py`)

```python
class PDFHighlightingApplier(HighlightApplierPort):
    """
    Apply highlighting annotations to PDFs using PyMuPDF.

    Creates transparent colored rectangles + metadata comments.
    Non-destructive: original PDF unmodified.
    """

    def apply(
        self,
        source_path: str,
        plan: HighlightingPlan,
        output_path: str,
        *,
        include_metadata: bool = True,
    ) -> int:
        """
        Create highlighted copy of PDF.

        For each finding:
        1. Draw semi-transparent highlight rectangle
        2. Add comment/annotation with category + reason
        3. Optional: Create metadata page listing all findings
        """
        import fitz  # type: ignore

        source = Path(source_path)
        output = Path(output_path)

        if not source.exists():
            raise FileNotFoundError(f"Source PDF not found: {source}")

        # Verify hash
        current_hash = self._compute_hash(source)
        if current_hash != plan.input_hash:
            raise ValueError("PDF hash mismatch with plan")

        # Open and copy PDF
        doc = fitz.open(str(source))
        try:
            applied = 0

            # Apply each finding
            for finding in plan.findings:
                if finding.page is None:
                    continue  # Skip findings without page info

                page = doc[finding.page]

                # Convert character offset to PDF coordinates
                # (This is approximate; exact mapping requires text extraction)
                rect = self._find_text_rect(
                    page,
                    finding.text,
                    finding.start,
                    finding.end,
                )

                if not rect:
                    continue  # Text not found on page

                # Add transparent highlight
                color_rgb = self._color_to_rgb(finding.color)
                page.draw_rect(
                    rect,
                    color=None,
                    fill=color_rgb,
                    transparency=1.0 - finding.opacity,  # Invert: opacity -> transparency
                )

                # Add annotation/comment
                comment_text = (
                    f"{finding.category}\n"
                    f"Confidence: {finding.score:.1%}\n"
                    f"Reason: {finding.reason}\n"
                    f"Context: {finding.context_before} [{finding.text}] {finding.context_after}"
                )
                page.add_highlight_annot(rect, type=5)  # Comment annotation

                applied += 1

            # Optional: Add metadata page
            if include_metadata:
                self._add_metadata_page(doc, plan)

            # Save
            output.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output), garbage=4, deflate=True)

            return applied
        finally:
            doc.close()


    def _find_text_rect(
        self,
        page,  # fitz.Page
        text: str,
        start: int,
        end: int,
    ):
        """Find bounding rectangle for text span on page."""
        # Approximate: search for exact text match, return first rect
        rects = page.search_for(text, quads=False)
        return rects[0] if rects else None


    @staticmethod
    def _color_to_rgb(color: str) -> tuple[float, float, float]:
        """Convert color name to RGB tuple (0.0-1.0)."""
        colors = {
            "red": (1.0, 0.0, 0.0),
            "yellow": (1.0, 1.0, 0.0),
            "green": (0.0, 1.0, 0.0),
            "blue": (0.0, 0.0, 1.0),
            "orange": (1.0, 0.647, 0.0),
            "gray": (0.5, 0.5, 0.5),
        }
        return colors.get(color, (1.0, 1.0, 0.0))


    def _add_metadata_page(self, doc, plan: HighlightingPlan) -> None:
        """Create first page listing all highlights."""
        import fitz  # type: ignore

        # New blank page at start
        page = doc.new_page(0, width=612, height=792)  # Letter size

        # Title
        page.insert_textbox(
            (50, 50, 550, 100),
            "Highlighting Summary",
            fontsize=16,
            fontname="helv-Bold",
        )

        # Summary stats
        summary_text = f"""
        Document: {Path(plan.document_path).name}
        Plan ID: {plan.plan_id[:8]}...
        Total Findings: {plan.summary['total']}

        By Category:
        {self._format_category_counts(plan.summary['by_category'])}

        By Confidence:
        {self._format_confidence_counts(plan.summary['by_confidence'])}

        Pages Affected: {', '.join(str(p) for p in plan.summary['pages_affected'])}
        """

        page.insert_textbox(
            (50, 120, 550, 400),
            summary_text,
            fontsize=10,
            fontname="helv",
        )

        # List of all findings
        findings_text = "Detailed Findings:\n\n"
        for i, finding in enumerate(plan.findings, 1):
            findings_text += (
                f"{i}. [{finding.category}] P.{finding.page}: "
                f"'{finding.text}' (confidence: {finding.score:.0%})\n"
            )

        page.insert_textbox(
            (50, 430, 550, 750),
            findings_text,
            fontsize=8,
            fontname="helv",
        )

```

---

## 8. Usage Flow (End-to-End)

```python
# Step 1: Generate highlighting plan
rexlit highlight plan input.pdf \
    --output-plan highlights.jsonl \
    --categories ADMISSION,CONTRADICTION,DAMAGES_ESTIMATE \
    --min-confidence 0.6 \
    --json-output

# Output:
# {
#   "plan_id": "a1b2c3d4e5f6g7h8",
#   "input_hash": "abc123...",
#   "findings": [
#     {
#       "category": "ADMISSION",
#       "text": "we admit",
#       "score": 0.95,
#       "page": 3,
#       "color": "red",
#       "reason": "matches_admission_pattern",
#       "context_before": "...and we have also determined that ",
#       "context_after": " this is the root cause."
#     },
#     ...
#   ],
#   "summary": {
#     "by_category": {"ADMISSION": 8, "CONTRADICTION": 3, "DAMAGES_ESTIMATE": 5},
#     "by_confidence": {"high": 12, "medium": 4, "low": 0},
#     "pages_affected": [1, 2, 3, 5, 7]
#   }
# }


# Step 2: Review plan (optional, can edit to remove false positives)
cat highlights.jsonl | jq '.findings[] | select(.score < 0.8)'


# Step 3: Apply highlights to create annotated PDF
rexlit highlight apply highlights.jsonl \
    --output-dir highlighted/ \
    --include-metadata

# Output:
# ✓ Applied 16 highlights
#   Output: highlighted/


# Result: highlighted/input.pdf with transparent colored overlays + comments
```

---

## 9. Architecture Comparison: Redaction vs. Highlighting

| Aspect | Redaction System | Highlighting System |
|--------|------------------|---------------------|
| **Purpose** | Remove sensitive data | Annotate credible/key sections |
| **Safety Model** | Plan/Apply (verify hash) | Plan/Apply (verify hash) |
| **Detection** | PII regex + LLM | Legal pattern regex + LLM |
| **Output Modification** | Destructive (black box text) | Non-destructive (annotations) |
| **Port Pattern** | PII detection → Stamp → Apply | Highlight finding → Annotate → Apply |
| **Audit Trail** | SHA-256 chain logs redactions | SHA-256 chain logs highlights |
| **Parallelization** | ProcessPoolExecutor on batches | Same (batch findings by page) |
| **Offline-First** | Yes (patterns only) | Yes (patterns only) |
| **Human-in-Loop** | Review plan, approve apply | Review plan, refine thresholds |

---

## 10. Future Enhancements

```python
# Stage 4: Expert-level pattern refinement
# - Train on corpus of actual admissions/statements
# - Build domain-specific models (healthcare, IP, real estate)
# - Cross-reference with privilege log to prevent false positives

# Visualization layer
# - API endpoint: GET /api/documents/:hash/highlights
#   Returns: {"findings": [...], "visualization": "highlighted.pdf"}
# - React UI: Scroll through document with sidebar showing categories
# - Color legend: click category to filter/highlight only that type

# Workflow integration
# - "Mark as reviewed" → removes highlight on confirmed false positive
# - "Escalate to privilege" → if pattern looks like unintentional disclosure
# - "Export proof brief" → compile all highlights into summary document

# Multi-stage scoring
# - Stage 1: Pattern matching (this sketch)
# - Stage 2: LLM credibility (sketched in _stage2_llm_scoring)
# - Stage 3: Jurisprudence matching (compare to case law)
# - Stage 4: Expert validation (human paralegal confirms)
```

---

## Summary

This pseudocode sketch shows:

1. **Parallel architecture to redaction**: Same plan/apply safety model, same audit trail, same offline-first approach
2. **Extensible pattern system**: Easy to add new categories (JUUL-specific, local court rules, etc.)
3. **Multi-stage detection**: Pattern matching (fast) → LLM scoring (optional) → deduplication
4. **Non-destructive output**: Annotations layer, original preserved, fully reversible
5. **Human-in-loop**: Plan review before apply; edit thresholds without re-running detection
6. **Legal workflow fit**: Speeds up discovery by finding credible/damaging admissions in seconds

Key files to implement:
- `rexlit/app/ports/highlighting.py` (port interfaces)
- `rexlit/app/adapters/highlighting_patterns.py` (detection logic)
- `rexlit/app/adapters/highlighting_applier.py` (PDF annotation)
- `rexlit/app/highlighting_service.py` (orchestration)
- `rexlit/cli.py` (commands: `highlight plan`, `highlight apply`)
- `rexlit/bootstrap.py` (dependency wiring)
