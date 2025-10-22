"""Build search index using Tantivy for document retrieval."""

import shutil
from pathlib import Path

import tantivy

from rexlit.ingest.discover import discover_documents
from rexlit.ingest.extract import extract_document


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


def build_index(
    root: Path,
    index_dir: Path,
    rebuild: bool = False,
    show_progress: bool = True,
) -> int:
    """Build search index from documents.

    Args:
        root: Root directory containing documents
        index_dir: Directory to store index
        rebuild: Rebuild index from scratch (default: False)
        show_progress: Show progress indicators (default: True)

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

    # Create schema and index
    schema = create_schema()
    index = tantivy.Index(schema, str(index_dir))

    # Discover documents
    if show_progress:
        print(f"Discovering documents in {root}...")

    documents = discover_documents(root, recursive=True)

    if show_progress:
        print(f"Found {len(documents)} documents")
        print("Indexing documents...")

    # Index documents
    writer = index.writer(heap_size=50_000_000)  # 50MB heap

    indexed_count = 0
    for doc_meta in documents:
        try:
            # Extract document content
            extracted = extract_document(Path(doc_meta.path))

            # Create Tantivy document
            doc = tantivy.Document()
            doc.add_text("path", doc_meta.path)
            doc.add_text("sha256", doc_meta.sha256)

            if doc_meta.custodian:
                doc.add_text("custodian", doc_meta.custodian)
            else:
                doc.add_text("custodian", "")

            if doc_meta.doctype:
                doc.add_text("doctype", doc_meta.doctype)
            else:
                doc.add_text("doctype", "unknown")

            # Add body text (full content)
            if extracted.text:
                doc.add_text("body", extracted.text)

            # Add metadata as JSON string
            metadata_str = str(extracted.metadata)
            doc.add_text("metadata", metadata_str)

            # Add document to index
            writer.add_document(doc)
            indexed_count += 1

            if show_progress and indexed_count % 100 == 0:
                print(f"Indexed {indexed_count}/{len(documents)} documents...")

        except Exception as e:
            # Skip documents that can't be extracted
            if show_progress:
                print(f"Warning: Skipping {doc_meta.path}: {e}")
            continue

    # Commit changes
    writer.commit()

    if show_progress:
        print(f"Index complete: {indexed_count} documents indexed")

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

    # Discover and extract document
    try:
        doc_meta = discover_documents(document_path)[0]
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
