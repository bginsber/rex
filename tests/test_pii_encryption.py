"""Tests for encrypted PII findings storage."""

from __future__ import annotations

from rexlit.ediscovery import EncryptedPIIStore, PIIFindingRecord


def test_pii_store_encrypts_on_disk(override_settings) -> None:
    """PII findings must be encrypted at rest."""
    store = EncryptedPIIStore(override_settings)
    record = PIIFindingRecord(
        document_id="doc-1",
        entity_type="email",
        text="alice@example.com",
        score=0.99,
        start=0,
        end=17,
    )

    store.append(record)

    assert store.path.exists()
    raw = store.path.read_text(encoding="utf-8")
    assert "alice@example.com" not in raw
    assert "doc-1" not in raw  # Document identifier should be encrypted as well

    records = store.read_all()
    assert len(records) == 1
    stored = records[0]
    assert stored.document_id == "doc-1"
    assert stored.entity_type == "EMAIL"
    assert stored.text == "alice@example.com"
    assert stored.score == 0.99
    assert stored.start == 0
    assert stored.end == 17


def test_pii_store_filters_by_document(override_settings) -> None:
    """Filtering by document should return only relevant records."""
    store = EncryptedPIIStore(override_settings)

    records = [
        PIIFindingRecord(
            document_id="doc-1",
            entity_type="email",
            text="alice@example.com",
            score=0.95,
            start=0,
            end=17,
        ),
        PIIFindingRecord(
            document_id="doc-2",
            entity_type="ssn",
            text="123-45-6789",
            score=0.9,
            start=10,
            end=21,
        ),
    ]

    for record in records:
        store.append(record)

    doc1_records = store.read_by_document("doc-1")
    assert len(doc1_records) == 1
    assert doc1_records[0].document_id == "doc-1"
    assert doc1_records[0].text == "alice@example.com"


def test_pii_store_purge(override_settings) -> None:
    """Purging should remove encrypted findings."""
    store = EncryptedPIIStore(override_settings)
    store.append(
        PIIFindingRecord(
            document_id="doc-3",
            entity_type="phone",
            text="+1-555-0100",
            score=0.88,
            start=5,
            end=17,
        )
    )

    store.purge()
    assert not store.path.exists()
    assert store.read_all() == []
