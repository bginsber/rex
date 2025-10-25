# ADR 0004: JSONL Schema Versioning

**Status:** Accepted

**Date:** 2025-10-24

**Decision Makers:** Engineering Team

---

## Context

RexLit produces numerous artifacts in JSONL format:
- Audit ledgers (`audit.jsonl`)
- Document manifests (`manifest.jsonl`)
- Bates registries (`bates_map.jsonl`)
- PII findings (`pii_findings.jsonl`)
- Deduplication results (`near_dupes.jsonl`)
- Production packages (`rexpack.jsonl`)

As the system evolves, schemas will change:
- New fields added
- Fields renamed or removed
- Data types changed
- Validation rules updated

Without schema versioning:
- Old artifacts become unreadable
- No migration path for legacy data
- Breaking changes invisible to users
- Automated processing fragile

## Decision

**We adopt explicit schema versioning with registry and metadata stamping:**

### Schema Registry

JSON Schema files define each version:

```
rexlit/schemas/
├── audit@1.json          # Version 1 of audit schema
├── manifest@1.json
├── bates_map@1.json
├── pii_findings@1.json
├── near_dupes@1.json
└── rexpack@1.json
```

### Metadata Stamping

Every JSONL record includes schema metadata:

```json
{
  "schema_id": "manifest",
  "schema_version": 1,
  "producer": "rexlit-0.1.0",
  "produced_at": "2025-10-24T12:00:00Z",
  "content_hash": "abc123...",
  "path": "/docs/contract.pdf",
  "sha256": "def456...",
  ...
}
```

### Schema Evolution Rules

1. **Version Bump:** Increment `schema_version` for breaking changes
2. **Backward Compatibility:** Readers support multiple versions
3. **Forward Compatibility:** Unknown fields ignored (warnings logged)
4. **Fail-Fast:** Invalid records rejected in dev mode
5. **Graceful Degradation:** Warnings in prod mode

### Implementation

```python
from rexlit.utils.schema import stamp_metadata, validate_record

# Writing: stamp metadata
record = {"path": "/docs/contract.pdf", "sha256": "abc123...", ...}
stamped = stamp_metadata(record, schema_id="manifest", schema_version=1)
# Result: record with schema_id, schema_version, producer, produced_at, content_hash

# Reading: validate and handle versions
for line in open("manifest.jsonl"):
    record = json.loads(line)
    if record["schema_version"] == 1:
        # Process v1 format
        ...
    elif record["schema_version"] == 2:
        # Process v2 format (future)
        ...
    else:
        logger.warning(f"Unknown schema version: {record['schema_version']}")
```

## Consequences

### Positive

- **Evolvability:** Safe schema changes without breaking old data
- **Debuggability:** Know exactly which version produced artifact
- **Validation:** Automated schema validation catches errors
- **Migration:** Old data can be converted to new schemas
- **Documentation:** JSON Schema serves as formal spec

### Negative

- **Overhead:** Extra fields in every record (~50 bytes)
- **Complexity:** Must maintain multiple version readers
- **Boilerplate:** Stamp metadata on every write

### Mitigation

- **Utilities:** `stamp_metadata()` automates stamping
- **Testing:** Schema validation runs in CI
- **Documentation:** Schema registry clearly versioned

## Schema Evolution Example

### Version 1 → Version 2 Migration

```json
// Version 1 (original)
{
  "schema_id": "manifest",
  "schema_version": 1,
  "path": "/docs/contract.pdf",
  "sha256": "abc123...",
  "doctype": "pdf"
}

// Version 2 (added fields)
{
  "schema_id": "manifest",
  "schema_version": 2,
  "path": "/docs/contract.pdf",
  "sha256": "abc123...",
  "doctype": "pdf",
  "ocr_confidence": 0.95,  // NEW
  "language": "en"         // NEW
}
```

Readers handle both:

```python
def read_manifest(record: dict) -> Manifest:
    if record["schema_version"] == 1:
        return Manifest(
            path=record["path"],
            sha256=record["sha256"],
            doctype=record["doctype"],
            ocr_confidence=None,  # Not present in v1
            language=None,
        )
    elif record["schema_version"] == 2:
        return Manifest(
            path=record["path"],
            sha256=record["sha256"],
            doctype=record["doctype"],
            ocr_confidence=record["ocr_confidence"],
            language=record["language"],
        )
```

## Validation

```bash
# Validate manifest against schema
python -c "from rexlit.utils.schema import validate_file; \
    valid, invalid = validate_file('manifest.jsonl', 'manifest', 1); \
    print(f'Valid: {valid}, Invalid: {invalid}')"
```

## Alternatives Considered

### 1. No Versioning

**Rejected:** Breaks backward compatibility. No migration path.

### 2. Implicit Versioning (Field Presence)

**Rejected:** Ambiguous. Can't distinguish missing field vs. null value.

### 3. Separate Version Files

**Rejected:** Easy to lose version file. Metadata should travel with data.

## References

- JSON Schema specification
- Semantic Versioning (semver.org)
- Related: ADR 0003 (Determinism Policy)

---

**Last Updated:** 2025-10-24
