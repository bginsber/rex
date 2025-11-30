"""Batch highlight processing with parallel execution."""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from rexlit.app.ports.concept import ConceptFinding


@dataclass
class BatchHighlightResult:
    """Result of batch highlight processing."""

    total_documents: int
    successful: int
    failed: int
    total_highlights: int
    duration_seconds: float
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "successful": self.successful,
            "failed": self.failed,
            "total_highlights": self.total_highlights,
            "duration_seconds": self.duration_seconds,
            "results": self.results,
            "errors": self.errors,
        }


@dataclass
class DocumentHighlightJob:
    """A single document to be highlighted."""

    document_path: Path
    output_path: Path
    sha256: str


def _process_single_document(
    job: DocumentHighlightJob,
    concepts: list[str] | None,
    threshold: float,
    plan_key: bytes,
) -> dict[str, Any]:
    """Process a single document for highlighting (worker function).

    This function runs in a separate process, so it imports dependencies lazily.
    """
    from rexlit.app.adapters.pattern_concept_adapter import PatternConceptAdapter
    from rexlit.app.highlight_service import HighlightService, DEFAULT_CATEGORY_COLORS
    from rexlit.app.adapters.storage import FileSystemStorageAdapter
    from rexlit.utils.plans import (
        compute_highlight_plan_id,
        write_highlight_plan_entry,
    )

    try:
        adapter = PatternConceptAdapter()
        storage = FileSystemStorageAdapter()

        # Analyze document
        findings = adapter.analyze_document(
            str(job.document_path),
            concepts=concepts,
            threshold=threshold,
        )

        # Convert findings to highlights
        highlights = []
        for f in findings:
            color = DEFAULT_CATEGORY_COLORS.get(f.category, "yellow")
            shade = 0.3 if f.confidence < 0.5 else min(1.0, 0.3 + (f.confidence - 0.5) * 1.4)
            highlights.append({
                "concept": f.concept,
                "category": f.category,
                "confidence": f.confidence,
                "start": f.start,
                "end": f.end,
                "page": f.page,
                "color": color,
                "shade_intensity": shade,
                "reasoning_hash": f.reasoning_hash,
                "snippet_hash": f.snippet_hash,
            })

        # Build plan
        document_hash = storage.compute_hash(job.document_path)
        annotations = {
            "concept_types": sorted({f.concept for f in findings}),
            "detector": "PatternConceptAdapter",
            "highlight_count": len(highlights),
            "pages_with_highlights": sorted({h.get("page") for h in highlights if h.get("page")}),
            "confidence_range": (
                min((h["confidence"] for h in highlights), default=0.0),
                max((h["confidence"] for h in highlights), default=0.0),
            ),
            "color_palette": DEFAULT_CATEGORY_COLORS,
        }

        plan_id = compute_highlight_plan_id(
            document_hash=document_hash,
            highlights=highlights,
            annotations=annotations,
        )

        plan_entry = {
            "document_hash": document_hash,
            "plan_id": plan_id,
            "highlights": highlights,
            "annotations": annotations,
            "notes": f"Batch: {len(highlights)} highlights",
        }

        # Write plan
        job.output_path.parent.mkdir(parents=True, exist_ok=True)
        write_highlight_plan_entry(job.output_path, plan_entry, key=plan_key)

        return {
            "status": "success",
            "path": str(job.document_path),
            "output": str(job.output_path),
            "plan_id": plan_id,
            "highlight_count": len(highlights),
        }

    except Exception as e:
        return {
            "status": "error",
            "path": str(job.document_path),
            "error": str(e),
        }


def discover_documents(
    source_dir: Path,
    extensions: set[str] | None = None,
) -> Iterator[Path]:
    """Discover documents in a directory for batch processing."""
    if extensions is None:
        extensions = {".pdf", ".docx", ".txt", ".md"}

    for path in sorted(source_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in extensions:
            yield path


def run_batch_highlights(
    source_dir: Path,
    output_dir: Path,
    *,
    concepts: list[str] | None = None,
    threshold: float = 0.5,
    workers: int | None = None,
    extensions: set[str] | None = None,
    plan_key: bytes,
    progress_callback: Any = None,
) -> BatchHighlightResult:
    """Run batch highlight processing on a directory of documents.

    Args:
        source_dir: Directory containing documents to process
        output_dir: Directory to write highlight plans
        concepts: Optional list of concept types to detect
        threshold: Confidence threshold for concept detection
        workers: Number of parallel workers (default: CPU count)
        extensions: File extensions to process
        plan_key: Encryption key for highlight plans
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        BatchHighlightResult with processing statistics
    """
    import os

    if workers is None:
        workers = os.cpu_count() or 4

    # Discover documents
    documents = list(discover_documents(source_dir, extensions))
    total = len(documents)

    if total == 0:
        return BatchHighlightResult(
            total_documents=0,
            successful=0,
            failed=0,
            total_highlights=0,
            duration_seconds=0.0,
        )

    # Compute SHA256 hashes and create jobs
    from rexlit.app.adapters.storage import FileSystemStorageAdapter
    storage = FileSystemStorageAdapter()

    jobs: list[DocumentHighlightJob] = []
    for doc_path in documents:
        sha256 = storage.compute_hash(doc_path)
        output_path = output_dir / f"{sha256}.highlight-plan.enc"
        jobs.append(DocumentHighlightJob(
            document_path=doc_path,
            output_path=output_path,
            sha256=sha256,
        ))

    output_dir.mkdir(parents=True, exist_ok=True)

    # Process in parallel
    start_time = time.monotonic()
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    total_highlights = 0
    completed = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _process_single_document,
                job,
                concepts,
                threshold,
                plan_key,
            ): job
            for job in jobs
        }

        for future in as_completed(futures):
            completed += 1
            if progress_callback:
                progress_callback(completed, total)

            result = future.result()
            if result["status"] == "success":
                results.append(result)
                total_highlights += result.get("highlight_count", 0)
            else:
                errors.append({
                    "path": result["path"],
                    "error": result.get("error", "Unknown error"),
                })

    duration = time.monotonic() - start_time

    return BatchHighlightResult(
        total_documents=total,
        successful=len(results),
        failed=len(errors),
        total_highlights=total_highlights,
        duration_seconds=duration,
        results=results,
        errors=errors,
    )


def save_batch_checkpoint(
    checkpoint_path: Path,
    result: BatchHighlightResult,
) -> None:
    """Save batch processing checkpoint for resume capability."""
    checkpoint_data = {
        "timestamp": time.time(),
        "total_documents": result.total_documents,
        "successful": result.successful,
        "failed": result.failed,
        "total_highlights": result.total_highlights,
        "completed_paths": [r["path"] for r in result.results],
        "failed_paths": [e["path"] for e in result.errors],
    }
    checkpoint_path.write_text(
        json.dumps(checkpoint_data, indent=2),
        encoding="utf-8",
    )


def load_batch_checkpoint(checkpoint_path: Path) -> set[str]:
    """Load completed paths from a checkpoint file."""
    if not checkpoint_path.exists():
        return set()

    try:
        data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        return set(data.get("completed_paths", []))
    except Exception:
        return set()

