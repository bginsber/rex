"""Build search index using Tantivy for document retrieval."""

from __future__ import annotations

import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
from pathlib import Path
from typing import TypedDict

import numpy as np
import tantivy

from rexlit.index.hnsw_store import HNSWStore
from rexlit.index.kanon2_embedder import DOCUMENT_TASK, EmbeddingResult, embed_texts
from rexlit.index.metadata import IndexMetadata
from rexlit.ingest.discover import DocumentMetadata, discover_documents
from rexlit.ingest.extract import extract_document


class DenseDocument(TypedDict):
    """Data captured for dense embedding construction."""

    identifier: str
    path: str
    sha256: str
    custodian: str | None
    doctype: str | None
    text: str


def create_schema() -> tantivy.Schema:
    """Create Tantivy schema for document indexing.

    Returns:
        Tantivy schema with required fields
    """
    schema_builder = tantivy.SchemaBuilder()

    # Document fields
    schema_builder.add_text_field("path", stored=True)
    schema_builder.add_text_field("sha256", stored=True)
    schema_builder.add_text_field("custodian", stored=True)
    schema_builder.add_text_field("doctype", stored=True)
    schema_builder.add_text_field("body", stored=False)  # Full text, not stored

    # Metadata fields
    schema_builder.add_text_field("metadata", stored=True)

    return schema_builder.build()


def _process_document_worker(doc_meta: DocumentMetadata) -> dict | None:
    """Worker function to process a single document in parallel.

    This function is designed to be pickled and executed in a worker process.
    It extracts document content and returns serializable data for indexing.

    Args:
        doc_meta: Document metadata from discovery phase

    Returns:
        Dictionary with processed document data, or None if extraction failed
    """
    try:
        # Extract document content
        extracted = extract_document(Path(doc_meta.path))

        # Return serializable data (not Tantivy Document objects)
        return {
            "path": doc_meta.path,
            "sha256": doc_meta.sha256,
            "custodian": doc_meta.custodian or "",
            "doctype": doc_meta.doctype or "unknown",
            "text": extracted.text or "",
            "metadata": str(extracted.metadata),
            # Preserve for cache updates
            "custodian_raw": doc_meta.custodian,
            "doctype_raw": doc_meta.doctype,
        }
    except Exception as e:
        # Return error information instead of raising
        return {
            "error": str(e),
            "path": doc_meta.path,
        }


def build_index(
    root: Path,
    index_dir: Path,
    rebuild: bool = False,
    show_progress: bool = True,
    max_workers: int | None = None,
    batch_size: int = 100,
    dense_collector: list[DenseDocument] | None = None,
) -> int:
    """Build search index from documents using parallel processing.

    Uses ProcessPoolExecutor to process documents in parallel, achieving 15-20x
    speedup on multi-core systems. Documents are processed in batches with
    periodic commits for memory management.

    Args:
        root: Root directory containing documents
        index_dir: Directory to store index
        rebuild: Rebuild index from scratch (default: False)
        show_progress: Show progress indicators (default: True)
        max_workers: Maximum number of worker processes (default: cpu_count() - 1)
        batch_size: Number of documents to process per batch (default: 100)
        dense_collector: Optional list that will be populated with dense-ready
            document payloads (identifier, metadata, text)

    Returns:
        Number of documents indexed

    Raises:
        FileNotFoundError: If root path does not exist
        ValueError: If root is not a directory
    """
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    if not root.is_dir():
        raise ValueError(f"Path is not a directory: {root}")

    # Remove existing index if rebuilding
    if rebuild and index_dir.exists():
        shutil.rmtree(index_dir)

    # Create index directory
    index_dir.mkdir(parents=True, exist_ok=True)

    # Initialize metadata cache
    metadata_cache = IndexMetadata(index_dir)
    if rebuild:
        metadata_cache.reset()

    # Create schema and index
    schema = create_schema()
    index = tantivy.Index(schema, str(index_dir))

    # Discover and index documents using streaming pattern
    if show_progress:
        print(f"Discovering and indexing documents in {root}...")

    # Determine worker count
    if max_workers is None:
        max_workers = max(1, cpu_count() - 1)

    if show_progress:
        print(f"Discovering and indexing documents in {root} (streaming)...")
        print(f"Processing with {max_workers} workers...")

    # Initialize index writer
    writer = index.writer(heap_size=200_000_000)  # 200MB heap for better performance

    # Track progress and performance
    indexed_count = 0
    skipped_count = 0
    discovered_count = 0
    start_time = time.time()
    commit_interval = max(1000, batch_size * 4)

    def document_stream():
        nonlocal discovered_count
        for doc_meta in discover_documents(root, recursive=True):
            discovered_count += 1
            yield doc_meta

    documents_iter = document_stream()

    # Process documents in parallel
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for result in executor.map(_process_document_worker, documents_iter, chunksize=batch_size):
            try:
                if not result:
                    skipped_count += 1
                    continue

                # Check if processing had an error
                if "error" in result:
                    skipped_count += 1
                    if show_progress:
                        print(f"Warning: Skipping {result['path']}: {result['error']}")
                    continue

                # Create Tantivy document from processed data
                doc = tantivy.Document()
                doc.add_text("path", result["path"])
                doc.add_text("sha256", result["sha256"])
                doc.add_text("custodian", result["custodian"])
                doc.add_text("doctype", result["doctype"])
                doc.add_text("body", result["text"])
                doc.add_text("metadata", result["metadata"])

                # Add document to index
                writer.add_document(doc)
                indexed_count += 1

                # Update metadata cache
                metadata_cache.update(
                    custodian=result["custodian_raw"],
                    doctype=result["doctype_raw"],
                )

                if dense_collector is not None and result["text"]:
                    dense_collector.append(
                        {
                            "identifier": result["sha256"],
                            "path": result["path"],
                            "sha256": result["sha256"],
                            "custodian": result["custodian"] or None,
                            "doctype": result["doctype"] or None,
                            "text": result["text"],
                        }
                    )

                # Periodic commits for memory management
                if indexed_count and indexed_count % commit_interval == 0:
                    writer.commit()

                    if show_progress:
                        elapsed = time.time() - start_time
                        docs_per_sec = indexed_count / elapsed if elapsed > 0 else 0
                        print(
                            f"Indexed {indexed_count} documents "
                            f"({docs_per_sec:.1f} docs/sec) — committed batch"
                        )

                # Regular progress updates
                elif show_progress and indexed_count % 100 == 0:
                    elapsed = time.time() - start_time
                    docs_per_sec = indexed_count / elapsed if elapsed > 0 else 0
                    print(
                        f"Indexed {indexed_count} documents "
                        f"({docs_per_sec:.1f} docs/sec)"
                    )

            except Exception as e:  # pragma: no cover - defensive guard
                skipped_count += 1
                if show_progress:
                    print(f"Warning: Error processing document: {e}")
                continue

    # Final commit
    writer.commit()

    # Save metadata cache
    metadata_cache.save()

    # Final performance report
    elapsed = time.time() - start_time
    docs_per_sec = indexed_count / elapsed if elapsed > 0 else 0

    if show_progress:
        print(f"\nIndex complete:")
        print(f"  - Discovered: {discovered_count} documents")
        print(f"  - Indexed: {indexed_count} documents")
        print(f"  - Skipped: {skipped_count} documents")
        print(f"  - Time: {elapsed:.1f} seconds")
        print(f"  - Throughput: {docs_per_sec:.1f} docs/sec")

    return indexed_count


def update_index(
    index_dir: Path,
    document_path: Path,
) -> bool:
    """Update index with a single document.

    Args:
        index_dir: Directory containing index
        document_path: Path to document to index

    Returns:
        True if document was indexed successfully

    Raises:
        FileNotFoundError: If index or document not found
    """
    if not index_dir.exists():
        raise FileNotFoundError(f"Index not found: {index_dir}")

    if not document_path.exists():
        raise FileNotFoundError(f"Document not found: {document_path}")

    # Load existing index
    schema = create_schema()
    index = tantivy.Index(schema, str(index_dir))

    # Load metadata cache
    metadata_cache = IndexMetadata(index_dir)

    # Discover and extract document
    try:
        # Get first (and only) document from iterator
        doc_meta = next(discover_documents(document_path))
        extracted = extract_document(document_path)

        # Create Tantivy document
        doc = tantivy.Document()
        doc.add_text("path", doc_meta.path)
        doc.add_text("sha256", doc_meta.sha256)
        doc.add_text("custodian", doc_meta.custodian or "")
        doc.add_text("doctype", doc_meta.doctype or "unknown")

        if extracted.text:
            doc.add_text("body", extracted.text)

        metadata_str = str(extracted.metadata)
        doc.add_text("metadata", metadata_str)

        # Add to index
        writer = index.writer()
        writer.add_document(doc)
        writer.commit()

        # Update metadata cache
        metadata_cache.update(
            custodian=doc_meta.custodian,
            doctype=doc_meta.doctype,
        )
        metadata_cache.save()

        return True

    except Exception as e:
        print(f"Error indexing document: {e}")
        return False


def get_index_stats(index_dir: Path) -> dict[str, int] | None:
    """Get statistics about the index.

    Args:
        index_dir: Directory containing index

    Returns:
        Dictionary with index statistics or None if index not found
    """
    if not index_dir.exists():
        return None

    try:
        schema = create_schema()
        index = tantivy.Index(schema, str(index_dir))
        searcher = index.searcher()

        return {
            "num_docs": searcher.num_docs,
            "num_segments": len(searcher.segment_readers),
        }
    except Exception:
        return None


def _aggregate_usage(records: list[EmbeddingResult]) -> dict[str, float]:
    """Aggregate usage and latency telemetry across embedding batches."""
    total_latency = sum(record.latency_ms for record in records)
    token_totals: dict[str, float] = {}

    for record in records:
        usage = record.usage or {}
        for key, value in usage.items():
            if not isinstance(value, (int, float)):
                continue
            token_totals[key] = token_totals.get(key, 0.0) + float(value)

    token_totals["latency_ms"] = total_latency
    token_totals["batches"] = float(len(records))
    return token_totals


def build_dense_index(
    dense_documents: list[DenseDocument],
    *,
    index_dir: Path,
    dim: int = 768,
    batch_size: int = 32,
    api_key: str | None = None,
    api_base: str | None = None,
) -> dict[str, object] | None:
    """Construct a Kanon 2 HNSW index for dense retrieval.

    Returns a dictionary with paths and telemetry metadata, or None when no
    documents were suitable for embedding.
    """
    filtered_docs = [doc for doc in dense_documents if doc["text"].strip()]
    if not filtered_docs:
        return None

    telemetry_records: list[EmbeddingResult] = []
    embeddings: list[list[float]] = []
    identifiers: list[str] = []
    doc_metadata: dict[str, dict] = {}

    for start in range(0, len(filtered_docs), batch_size):
        batch = filtered_docs[start : start + batch_size]

        result = embed_texts(
            (doc["text"] for doc in batch),
            task=DOCUMENT_TASK,
            dimensions=dim,
            api_key=api_key,
            api_base=api_base,
        )
        telemetry_records.append(result)

        if len(result.embeddings) != len(batch):
            raise RuntimeError(
                "Embedding provider returned a mismatched number of vectors."
            )

        embeddings.extend(result.embeddings)
        identifiers.extend(doc["identifier"] for doc in batch)

        for doc in batch:
            doc_metadata[doc["identifier"]] = {
                "path": doc["path"],
                "sha256": doc["sha256"],
                "custodian": doc["custodian"],
                "doctype": doc["doctype"],
            }

    if not embeddings:
        return None

    array = np.asarray(embeddings, dtype=np.float32)
    dense_dir = index_dir / "dense"
    store = HNSWStore(dim=dim, index_path=dense_dir / f"kanon2_{dim}.hnsw")
    store.build(
        array,
        identifiers,
        doc_metadata=doc_metadata,
    )

    usage_summary = _aggregate_usage(telemetry_records)
    usage_summary["vectors"] = float(len(identifiers))
    usage_summary["dim"] = float(dim)

    return {
        "index_path": str(store.index_path),
        "metadata_path": str(store.metadata_path),
        "usage": usage_summary,
    }
