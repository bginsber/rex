# ADR 0008: EDRM Privilege Log Protocol Integration

**Status:** Proposed

**Date:** 2025-11-07

**Decision Makers:** Engineering Team

---

## Context

Legal e-discovery requires producing **two distinct types of logs** with different purposes:

1. **Internal Audit Ledger** (existing in RexLit):
   - Purpose: Tamper-evident chain-of-custody for internal operations
   - Audience: Internal team, court (if process is challenged)
   - Scope: ALL operations on ALL documents
   - Current implementation: `rexlit/audit/ledger.py`

2. **External Privilege Log** (this ADR):
   - Purpose: Formal disclosure to opposing counsel of withheld documents
   - Audience: Opposing counsel, court (for privilege disputes)
   - Scope: ONLY documents withheld due to attorney-client privilege or work product protection
   - Required by: FRCP Rule 26(b)(5), EDRM Privilege Log Protocol v2.0
   - Current implementation: **Missing**

### Problem Statement

When parties withhold documents claiming privilege, Federal Rules of Civil Procedure require:

> "When a party withholds information otherwise discoverable... the party must:
> (i) expressly make the claim; and
> (ii) describe the nature of the documents... not produced or disclosed—and do so in a manner that, without revealing information itself privileged or protected, will enable other parties to assess the claim."
>
> — FRCP 26(b)(5)(A)

Traditional privilege logs are burdensome:
- Manual data entry for thousands of documents
- Inconsistent formats between parties
- Disputes over insufficient descriptions
- Costly meet-and-confer cycles

**EDRM Privilege Log Protocol v2.0** proposes a modern solution:
- **Metadata-plus logs**: Export existing metadata fields instead of manual descriptions
- **Structured workflows**: Standardized meet-and-confer process
- **Redacted document exclusion**: Documents produced with redactions need not be logged
- **Rolling production support**: Logs can be produced incrementally
- **Attorney lists**: Share known attorney/firm lists to avoid ambiguity

### Current RexLit State

RexLit already has components that **enable** privilege logging but lacks **export** functionality:

✅ **Existing Capabilities:**
- Document metadata capture (author, recipients, dates, custodian, file extension)
- Privilege detection (in development: `PII_PRIVILEGE_INTEGRATION_SUMMARY.md`)
- Bates numbering (ADR 0005)
- Redaction tracking (ADR 0006)
- Audit logging infrastructure (tamper-evident ledger)

❌ **Missing Capabilities:**
- Export of withheld documents to EDRM-compliant privilege log format
- Family grouping (email threads with attachments)
- Privilege basis field (attorney-client, work product, both)
- Attorney/firm lists management
- Rolling vs cumulative log generation
- Excel/CSV export with EDRM metadata schema

---

## Decision

**We will implement EDRM Privilege Log Protocol support as a new service with dedicated port/adapter:**

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                   CLI Layer                         │
│  rexlit privilege-log create --index ./index        │
│    --output privilege_log.xlsx --format edrm        │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│            Bootstrap (DI Container)                 │
│  - EDRMPrivilegeLogAdapter (PrivilegeLogPort)       │
│  - TantivyIndexAdapter (IndexPort)                  │
│  - AuditLedgerAdapter (LedgerPort)                  │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│          PrivilegeLogService (new)                  │
│  - query_withheld_documents()                       │
│  - build_family_groups()                            │
│  - generate_log()                                   │
│  - export_attorney_lists()                          │
└────────────────────┬────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ Tantivy Index   │    │ EDRM Exporter   │
│ (withheld docs) │    │ (Excel/CSV)     │
└─────────────────┘    └─────────────────┘
```

### EDRM Metadata-Plus Schema

Based on EDRM protocol Section 6 and provided example table:

| Field | RexLit Source | EDRM Required | Notes |
|-------|--------------|---------------|-------|
| **PrivLog ID #** | Generated sequential | Yes | `PRIVID-0001`, `PRIVID-0002`, ... |
| **Family ID** | Email thread hash | Yes | Groups related documents |
| **ProdBeg Doc #** | Bates number | Yes | What number would have been assigned |
| **Doc Date** | `date_sent` or `date_created` | Yes | ISO 8601 date |
| **Doc Time** | `date_sent` time component | Optional* | May be redacted if privileged |
| **From / Author** | `author` field | Yes | Person who created/sent |
| **To** | `recipients` field | Yes | Primary recipients |
| **CC** | `cc` field | Yes | Carbon copy recipients |
| **BCC** | `bcc` field | Optional | Blind carbon copy |
| **Basis for Claim** | `privilege_basis` (new field) | Yes | "Attorney-Client Privilege; Work Product" |
| **Subject / Filename** | `subject` or `filename` | Optional* | May be redacted if privileged |
| **File Ext.** | `file_extension` | Yes | MSG, PDF, DOCX, etc. |
| **Parent or Attachment** | Email family position | Yes | "Parent", "Attachment", "N/A" |

**Note:** Fields marked with * may be redacted or omitted if revealing them would expose privileged content.

### Example Output (Excel)

```
PrivLog ID # | Family ID    | ProdBeg Doc # | Doc Date   | Doc Time | From / Author     | To              | CC              | Basis for Claim                       | Subject / Filename                          | File Ext. | Parent or Attachment
-------------|--------------|---------------|------------|----------|-------------------|-----------------|-----------------|---------------------------------------|---------------------------------------------|-----------|---------------------
PRIVID-0001  | PRIVID-0001  | REX000001     | 2024-05-17 | 1:42PM   | Alligator, Abe    | Felix, Fox      |                 | Attorney-Client Privilege; Work Product | FW: Customer Fish Past Due.msg              | MSG       | Parent
PRIVID-0002  | PRIVID-0001  | REX000004     | 2024-05-17 | 1:00PM   | Alligator, Abe    |                 |                 | Work Product                          | Draft Fish Timeline for Counsel.docx        | DOCX      | Attachment
PRIVID-0003  | PRIVID-0001  | REX000001     | 2024-05-17 | 8:57AM   | Hen, Harriet      | Lion, Leonard   | Owl, Olivia     | Attorney-Client Privilege; Work Product | Re Customer Fish Past Due.msg               | MSG       | N/A
```

### Workflow

```
┌──────────────────────────────────────────────────────────┐
│  Phase 1: Index Documents with Privilege Markers         │
├──────────────────────────────────────────────────────────┤
│  1. Ingest documents (existing)                          │
│  2. Detect privilege (PII/Privilege integration)         │
│  3. Mark as WITHHELD in index metadata                   │
│     - privilege_basis: ["attorney_client", "work_product"]│
│     - withheld: true                                      │
│  4. Assign Bates numbers (ADR 0005)                      │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Phase 2: Generate Privilege Log                        │
├──────────────────────────────────────────────────────────┤
│  1. Query index for withheld documents                   │
│  2. Build family groups (email threads + attachments)    │
│  3. Assign PrivLog IDs (sequential, deterministic)       │
│  4. Export to Excel/CSV with EDRM schema                 │
│  5. Generate attorney lists (Section 9 compliance)       │
│  6. Log to audit trail                                   │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Phase 3: Produce to Opposing Counsel                   │
├──────────────────────────────────────────────────────────┤
│  1. Export non-withheld documents (standard production)  │
│  2. Include privilege log Excel/CSV file                 │
│  3. Include attorney lists (if agreed in protocol)       │
│  4. Metadata-plus format reduces meet-and-confer burden  │
└──────────────────────────────────────────────────────────┘
```

### New Data Model

```python
# rexlit/app/ports/privilege_log.py
from typing import Protocol, Literal
from pydantic import BaseModel
from pathlib import Path

class PrivilegeLogEntry(BaseModel):
    """Single privilege log entry (one document/page)."""
    privlog_id: str              # PRIVID-0001
    family_id: str               # Groups email threads
    prodbeg_doc_num: str         # Bates number (REX000001)
    doc_date: str                # ISO 8601 date
    doc_time: str | None         # Time or None if redacted
    from_author: str             # Author/sender
    to: list[str]                # Primary recipients
    cc: list[str]                # CC recipients
    bcc: list[str]               # BCC recipients (optional)
    basis_for_claim: str         # "Attorney-Client Privilege; Work Product"
    subject_filename: str | None # Subject or filename (may be redacted)
    file_ext: str                # MSG, PDF, DOCX, etc.
    parent_or_attachment: str    # "Parent", "Attachment", "N/A"

class AttorneyList(BaseModel):
    """Known attorneys/firms for privilege determination."""
    attorneys: list[str]         # ["Smith, John (in-house)", ...]
    firms: list[str]             # ["Jones & Associates LLP", ...]
    roles: dict[str, str]        # {"smith.john@example.com": "in-house"}

class PrivilegeLogPort(Protocol):
    """Port for generating EDRM-compliant privilege logs."""

    def generate_log(
        self,
        withheld_docs: list[Document],
        output_path: Path,
        *,
        format: Literal["excel", "csv"] = "excel",
        cumulative: bool = True,
        previous_log: Path | None = None,
    ) -> Path:
        """Generate privilege log from withheld documents.

        Args:
            withheld_docs: Documents marked as withheld in index
            output_path: Path to write privilege log
            format: "excel" or "csv"
            cumulative: Include all prior entries (vs. incremental)
            previous_log: Path to previous log for cumulative mode

        Returns:
            Path to generated privilege log file
        """
        ...

    def generate_attorney_lists(
        self,
        output_path: Path,
    ) -> AttorneyList:
        """Export attorney/firm lists per EDRM Section 9."""
        ...
```

### Integration with Existing Systems

1. **Index Metadata** (new fields):
   ```json
   {
     "doc_id": "abc123...",
     "withheld": true,
     "privilege_basis": ["attorney_client", "work_product"],
     "privilege_confidence": 0.85,
     "family_id": "thread_xyz789",
     "is_parent": true,
     "attachment_count": 2
   }
   ```

2. **Audit Ledger** (new operation):
   ```json
   {
     "operation": "privilege_log_create",
     "inputs": ["out/index"],
     "outputs": ["privilege_log_2025-11-07.xlsx"],
     "args": {
       "format": "edrm_metadata_plus_v2",
       "withheld_count": 1247,
       "family_count": 342,
       "cumulative": true,
       "protocol_version": "EDRM 2.0",
       "prior_log": "privilege_log_2025-10-15.xlsx"
     }
   }
   ```

3. **Bates Registry** (link to privilege log):
   - Documents withheld still receive Bates numbers
   - Numbers appear in privilege log `ProdBeg Doc #` column
   - Shows what number "would have been" assigned if produced

---

## Consequences

### Positive

- **FRCP Compliance:** Satisfies Rule 26(b)(5) privilege disclosure requirements
- **EDRM Protocol Alignment:** Follows industry best practices
- **Reduced Manual Work:** Exports existing metadata instead of manual entry
- **Dispute Reduction:** Structured format reduces meet-and-confer burden
- **Audit Trail:** Privilege log generation logged for defensibility
- **Interoperability:** Standard Excel/CSV format accepted by all parties
- **Reuses Existing Infrastructure:** Builds on index, Bates, audit ledger

### Negative

- **New Metadata Fields:** Requires adding `privilege_basis`, `withheld`, `family_id` to index
- **Family Grouping Logic:** Complex algorithm to group email threads with attachments
- **Storage Overhead:** Privilege logs add to production output size
- **Testing Complexity:** Must verify EDRM compliance across edge cases

### Mitigation

- **Incremental Implementation:** Phase 1 (basic export), Phase 2 (family grouping), Phase 3 (rolling logs)
- **Validation:** Reference implementation tests against EDRM sample data
- **Documentation:** Clear CLI examples and EDRM protocol references
- **Backward Compatibility:** New fields optional; existing workflows unaffected

---

## Usage Examples

### Basic Workflow

```bash
# 1. Mark documents as privileged during review
rexlit index build ./docs --privilege-detection

# 2. Query withheld documents
rexlit index search ./index --query "withheld:true" --count
# Found 1,247 withheld documents

# 3. Generate privilege log
rexlit privilege-log create \
  --index ./index \
  --output privilege_log_2025-11-07.xlsx \
  --format excel \
  --cumulative

# Output:
# Generated privilege log: privilege_log_2025-11-07.xlsx
# - Withheld documents: 1,247
# - Families: 342
# - Format: EDRM Metadata-Plus v2.0
# - Logged to: audit/log.jsonl

# 4. Generate attorney lists (EDRM Section 9)
rexlit privilege-log attorney-lists \
  --index ./index \
  --output attorney_lists.csv

# Output:
# Exported attorney lists: attorney_lists.csv
# - Attorneys: 23 (15 in-house, 8 outside counsel)
# - Firms: 4
```

### Rolling Production (EDRM Section 2)

```bash
# Initial production (Month 1)
rexlit privilege-log create \
  --index ./index \
  --output privilege_log_2025-10-01.xlsx

# Supplemental production (Month 2)
rexlit privilege-log create \
  --index ./index \
  --output privilege_log_2025-11-01.xlsx \
  --cumulative \
  --previous-log privilege_log_2025-10-01.xlsx

# Marks new entries added since last log
```

### Meet-and-Confer Workflow (EDRM Sections 10-12)

```bash
# Opposing counsel requests clarification on 50 entries
# Export subset for review
rexlit privilege-log export \
  --index ./index \
  --filter "PRIVID-0100 to PRIVID-0150" \
  --output clarification_subset.xlsx \
  --include-subject  # Unredact subject lines for these

# After meet-and-confer, regenerate with clarifications
rexlit privilege-log create \
  --index ./index \
  --output privilege_log_amended.xlsx \
  --cumulative
```

### CSV Format (Alternative to Excel)

```bash
# Generate CSV for importing into review platform
rexlit privilege-log create \
  --index ./index \
  --output privilege_log.csv \
  --format csv \
  --delimiter "|"  # Pipe-delimited for recipients with commas

# Output columns match EDRM schema:
# PrivLog ID #,Family ID,ProdBeg Doc #,Doc Date,Doc Time,From / Author,To,CC,BCC,Basis for Claim,Subject / Filename,File Ext.,Parent or Attachment
```

---

## Alternatives Considered

### 1. Manual Privilege Log Creation

**Rejected:** Too error-prone and labor-intensive. 1,000+ documents = weeks of paralegal time.

### 2. Traditional Descriptive Logs (No Metadata Export)

**Rejected:** EDRM metadata-plus approach is industry best practice. Reduces meet-and-confer burden.

### 3. Integrate with Third-Party Review Platform

**Rejected:** RexLit is offline-first. Should generate logs locally, then import to platform if needed.

### 4. Store Privilege Log in Database

**Rejected:** Excel/CSV is portable, universally accepted, and required by opposing counsel. Database adds complexity.

---

## Edge Cases

### Documents with Privileged Metadata

**Problem:** Subject line itself contains privileged information
**Solution:** Redact field, mark with `[REDACTED]`, log in audit trail

```python
if is_privileged(doc.subject):
    entry.subject_filename = "[REDACTED - Privileged]"
    audit.log("privilege_log_metadata_redaction", doc_id=doc.id, field="subject")
```

### Family Grouping for Fragmented Threads

**Problem:** Email thread split across multiple custodians
**Solution:** Hash based on `In-Reply-To` and `References` headers

```python
def compute_family_id(doc: EmailDoc) -> str:
    """Deterministic family ID for email threads."""
    thread_identifiers = sorted([
        doc.message_id,
        *doc.in_reply_to,
        *doc.references,
    ])
    return f"FAMILY-{hashlib.sha256('|'.join(thread_identifiers).encode()).hexdigest()[:8]}"
```

### Documents Withheld After Production

**Problem:** Clawback request under FRE 502(b)
**Solution:** Generate supplement log, mark as "Clawed Back"

```bash
rexlit privilege-log create \
  --index ./index \
  --filter "clawback:true" \
  --output privilege_log_clawback_2025-11-15.xlsx \
  --basis "Inadvertent Production - FRE 502(b) Clawback"
```

### Missing Bates Numbers (Withheld Before Numbering)

**Problem:** Document segregated before Bates assignment
**Solution:** Assign "would-have-been" numbers in privilege log only, not to actual document

```python
# Assign placeholder Bates for privilege log export
if doc.withheld and not doc.bates_number:
    doc.privilege_log_bates = assign_next_available_bates()
    # Does NOT stamp PDF, only appears in privilege log
```

---

## Testing Strategy

```python
def test_privilege_log_edrm_schema_compliance():
    """Verify output matches EDRM v2.0 metadata-plus schema."""
    withheld_docs = [create_withheld_email(), create_withheld_pdf()]
    log_path = privilege_log_service.generate_log(withheld_docs, "log.xlsx")

    df = pd.read_excel(log_path)
    assert "PrivLog ID #" in df.columns
    assert "Basis for Claim" in df.columns
    assert len(df) == 2

def test_family_grouping_email_threads():
    """Verify email threads grouped correctly."""
    parent = create_email(message_id="<abc@example.com>")
    reply = create_email(in_reply_to=["<abc@example.com>"])

    families = build_family_groups([parent, reply])
    assert len(families) == 1
    assert families[0].documents == [parent, reply]

def test_deterministic_privlog_ids():
    """Verify PrivLog IDs are stable across regeneration."""
    docs = create_withheld_docs(count=100)

    log1 = generate_log(docs, "log1.xlsx")
    log2 = generate_log(docs, "log2.xlsx")

    df1 = pd.read_excel(log1)
    df2 = pd.read_excel(log2)
    assert df1["PrivLog ID #"].tolist() == df2["PrivLog ID #"].tolist()

def test_cumulative_log_includes_prior_entries():
    """Verify cumulative mode includes previous log entries."""
    log1 = generate_log(docs[:50], "log1.xlsx")
    log2 = generate_log(docs[50:100], "log2.xlsx", previous_log=log1)

    df2 = pd.read_excel(log2)
    assert len(df2) == 100  # 50 old + 50 new

def test_attorney_lists_export():
    """Verify attorney lists match EDRM Section 9 requirements."""
    lists = privilege_log_service.generate_attorney_lists("lists.csv")

    assert len(lists.attorneys) > 0
    assert len(lists.firms) > 0
    assert "in-house" in lists.roles.get("smith.john@example.com", "")
```

---

## Implementation Phases

### Phase 1: Basic Export (MVP)
- [ ] Add `privilege_basis`, `withheld` fields to index schema
- [ ] Create `PrivilegeLogPort` interface
- [ ] Implement `EDRMPrivilegeLogAdapter` with Excel export
- [ ] CLI command: `rexlit privilege-log create`
- [ ] Tests: Schema compliance, deterministic IDs

### Phase 2: Family Grouping
- [ ] Implement email thread family grouping algorithm
- [ ] Add `family_id`, `is_parent`, `attachment_count` to index
- [ ] Handle attachments and threading
- [ ] Tests: Thread reconstruction, attachment linking

### Phase 3: EDRM Protocol Compliance
- [ ] Cumulative vs rolling logs (Section 2, 8)
- [ ] Attorney lists export (Section 9)
- [ ] Metadata redaction support (privileged subject lines)
- [ ] Tests: EDRM reference data validation

### Phase 4: Advanced Features
- [ ] Meet-and-confer workflow tracking
- [ ] Clawback request handling (FRE 502)
- [ ] Dispute annotation support
- [ ] Integration with pack service for production

---

## References

- **EDRM Privilege Log Protocol v2.0**: https://edrm.net (CC BY 4.0 license)
- **FRCP Rule 26(b)(5)**: Claiming privilege or protection
- **Federal Rule of Evidence 502**: Attorney-client privilege and work product waiver
- **Related ADRs:**
  - ADR 0003: Determinism Policy (stable family IDs)
  - ADR 0004: JSONL Schema Versioning (backward compatibility)
  - ADR 0005: Bates Numbering Authority (ProdBeg Doc # assignment)
  - ADR 0006: Redaction Plan/Apply Model (privileged metadata redaction)

---

**Last Updated:** 2025-11-07
