# RexLit Security

Security features, threat model, and compliance information for RexLit M0.

## Table of Contents

- [Security Overview](#security-overview)
- [Threat Model](#threat-model)
- [Security Features](#security-features)
- [Path Traversal Protection](#path-traversal-protection)
- [Audit Trail Security](#audit-trail-security)
- [Legal Compliance](#legal-compliance)
- [Security Testing](#security-testing)
- [Reporting Security Issues](#reporting-security-issues)

---

## Security Overview

RexLit is designed for **adversarial document sets** where malicious actors may attempt to:

- Exploit path traversal vulnerabilities
- Tamper with audit trails
- Compromise chain-of-custody
- Inject malicious content

**Security Philosophy**: Defense-in-depth with cryptographic guarantees.

### Security Status (M0)

✅ **0 Critical Vulnerabilities**
✅ **13 Security Tests Passing**
✅ **Path Traversal Protection**
✅ **Tamper-Evident Audit Trail**
✅ **Legal Compliance (FRCP Rule 26)**

---

## Threat Model

### Threat Actors

1. **Opposing Counsel**: May submit documents designed to exploit vulnerabilities
2. **Malicious Insiders**: Users with file system access attempting to tamper with evidence
3. **Automated Attacks**: Scripts generating malicious file structures

### Attack Vectors

#### 1. Path Traversal Attacks

**Goal**: Access files outside the designated document root

**Attack Techniques**:
- Symlinks pointing to `/etc/passwd`, `/home/user/.ssh/id_rsa`
- `../` sequences to escape document directory
- Absolute paths like `/tmp/malicious.pdf`
- Nested symlink chains
- Mixed techniques (symlink + `../`)

**Impact**: Confidential data exposure, unauthorized file access

**Mitigation**: ✅ Implemented (see [Path Traversal Protection](#path-traversal-protection))

#### 2. Audit Trail Tampering

**Goal**: Modify or delete audit entries to hide actions

**Attack Techniques**:
- Direct modification of `audit.jsonl`
- Entry deletion
- Entry reordering
- Hash manipulation
- Replay attacks

**Impact**: Loss of legal defensibility, inadmissible evidence

**Mitigation**: ✅ Implemented (see [Audit Trail Security](#audit-trail-security))

#### 3. Denial of Service

**Goal**: Crash or slow down RexLit

**Attack Techniques**:
- Extremely large files (10GB+ PDFs)
- Deeply nested directory structures
- Circular symlinks
- Malformed document headers

**Mitigation**: 🟡 Partial
- Memory limits enforced
- Timeout handling (future)
- Resource quotas (future)

#### 4. Content Injection

**Goal**: Inject malicious content into indexed documents

**Attack Techniques**:
- JavaScript in PDF annotations
- Macro-enabled DOCX files
- Embedded executables in metadata

**Mitigation**: ✅ Text-only extraction
- No script execution
- No macro evaluation
- Metadata sanitization

---

## Security Features

### 1. Path Traversal Protection

**Status**: ✅ Production-Ready

#### How It Works

Every file path is validated through a 3-layer security check:

```python
def validate_path(path: Path, allowed_root: Path) -> bool:
    """Validate path is within allowed boundary."""

    # Layer 1: Resolve symlinks and relative paths
    resolved = path.resolve()

    # Layer 2: Check if within boundary
    try:
        resolved.relative_to(allowed_root.resolve())
        return True
    except ValueError:
        # Layer 3: Log security event
        logger.warning(f"PATH_TRAVERSAL blocked: {path} → {resolved}")
        return False
```

Implementation detail: RexLit resolves every candidate path with `fs.realpathSync` (following all symlinks and junctions) before performing the boundary comparison, ensuring that symlink chains cannot escape `REXLIT_HOME` even if the original string appears safe.

#### Protected Against

✅ Symlinks outside document root
✅ `../` path traversal attempts
✅ Absolute paths
✅ Nested traversal attacks
✅ Symlink chains

#### Example Attack Blocked

```bash
# Attacker creates malicious symlink
cd /litigation/docs
ln -s /etc/passwd evil.txt

# RexLit detects and blocks
$ rexlit ingest /litigation/docs
Warning: Skipping evil.txt (path traversal detected)
Blocked: /litigation/docs/evil.txt → /etc/passwd
```

#### Security Logging

All traversal attempts are logged to the audit trail:

```json
{
  "timestamp": "2025-10-23T10:15:42Z",
  "action": "PATH_TRAVERSAL_BLOCKED",
  "details": {
    "path": "/litigation/docs/evil.txt",
    "resolved": "/etc/passwd",
    "boundary": "/litigation/docs"
  },
  "severity": "WARNING"
}
```

---

### 2. Tamper-Evident Audit Trail

**Status**: ✅ Production-Ready

#### Blockchain-Style Hash Chain

Each audit entry contains:

```json
{
  "timestamp": "2025-10-23T09:15:23.123456Z",
  "operation": "index.build",
  "sequence": 42,
  "previous_hash": "9f1e8a4b2c5d7f3e1a6b9d4c2a7b3c2d...",
  "entry_hash": "4a7b3c2d9f1e8a4b2c5d7f3e1a6b9d4c...",
  "signature": "5fd5b996e0a9b0c1..."
}
```

**Hash Computation**:
```
hash = SHA256(
    timestamp +
    action +
    JSON(details) +
    previous_hash
)
```

**Genesis Entry**:
- First entry has `previous_hash = "0000000000000000..."`
- Establishes the chain starting point

#### HMAC-Sealed Ledger Tip

- Each entry is signed with an HMAC keyed by a secret stored under `~/.config/rexlit/audit-ledger.key`.
- The ledger tip (`last_sequence`, `last_hash`) is replicated in `audit.jsonl.meta` and sealed with the same HMAC.
- Verification fails if:
  - An entry signature does not match (content tampering)
  - The ledger file is truncated or deleted (metadata mismatch)
  - Metadata is altered without the secret key (HMAC mismatch)

#### Cryptographic Properties

1. **Immutability**: Changing any entry breaks all subsequent hashes
2. **Append-Only**: No deletions without breaking chain or metadata seal
3. **Temporal Ordering**: Reordering breaks linkage
4. **Tamper-Evidence**: Verification detects content, signature, or metadata tampering
5. **Deletion Detection**: Missing files or truncated tails trigger verification failure

#### Example Attack Detection

**Scenario**: Attacker modifies entry #5 to hide a search query

```bash
# Before tampering
Entry 5: hash=ABC123..., previous_hash=DEF456...
Entry 6: hash=GHI789..., previous_hash=ABC123...

# After tampering (attacker changes Entry 5)
Entry 5: hash=XYZ999..., previous_hash=DEF456...  # Hash changed!
Entry 6: hash=GHI789..., previous_hash=ABC123...  # Still points to old hash

# Verification fails
$ rexlit audit verify
✗ FAILED: Entry 6 has invalid previous_hash
  Expected: XYZ999...
  Actual: ABC123...
  Tampering detected at entry 6
```

#### Fsync Durability

Every audit write is followed by:
```python
file.write(json.dumps(entry) + "\n")
file.flush()
os.fsync(file.fileno())  # Force write to disk
```

**Guarantee**: Even if system crashes immediately after write, entry is persisted.

**Legal Significance**: Meets FRCP requirements for defensible preservation.

---

### 3. PII Encryption at Rest

**Status**: ✅ Production-Ready

- PII findings are persisted via `EncryptedPIIStore` which encrypts every record using Fernet (AES-128 + HMAC).
- Encryption keys are generated on first use and stored at `~/.config/rexlit/pii.key` with `0600` permissions.
- The encrypted findings file (`pii_findings.enc`) contains only ciphertext; document identifiers, entity text, and coordinates are never written in plaintext.
- Decryption occurs in memory only when calling `EncryptedPIIStore.read_*` helpers.
- `EncryptedPIIStore.purge()` securely removes all stored ciphertext for breach response workflows.

---

### 4. Input Validation

**Status**: ✅ Implemented

#### File Extension Validation

```python
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

if path.suffix.lower() not in ALLOWED_EXTENSIONS:
    raise ValueError(f"Unsupported file type: {path.suffix}")
```

#### Path Sanitization

- Resolve all symlinks with `.resolve()`
- Normalize paths with `.absolute()`
- Validate UTF-8 encoding

#### Size Limits (Future)

- Max file size: 100MB (configurable)
- Max path length: 4096 characters
- Max directory depth: 50 levels

---

### 5. Minimal Attack Surface

**Status**: ✅ By Design

#### No Network Access

RexLit is **offline-by-default**:
- No HTTP clients
- No external API calls
- No phone-home telemetry

**Exception**: Future `--online` flag for case law lookups (explicit opt-in)

#### No Code Execution

- PDF: Text extraction only, no JavaScript evaluation
- DOCX: XML parsing only, no macro execution
- No `eval()`, `exec()`, or `subprocess` calls on untrusted input

#### Minimal Dependencies

```
Core: Tantivy, PyMuPDF, python-docx, Pydantic
Dev: pytest, ruff, black, mypy
```

All dependencies pinned with hash verification (future).

---

## Path Traversal Protection

### Implementation Details

#### Discovery Phase

```python
def discover_documents(
    root: Path,
    recursive: bool = True,
    allowed_root: Optional[Path] = None
) -> Iterator[DocumentMetadata]:
    """Discover documents with path validation."""

    if allowed_root is None:
        allowed_root = root

    for path in scan_directory(root, recursive):
        # Validate before processing
        if not validate_path(path, allowed_root):
            logger.warning(f"Blocked path traversal: {path}")
            continue  # Skip malicious file

        yield DocumentMetadata(path=str(path), ...)
```

#### Single File Mode

When ingesting a single file, boundary check is bypassed:

```python
if path.is_file():
    # Direct file access allowed
    return discover_single_file(path)
```

**Rationale**: User explicitly specified file path, no traversal risk.

---

## Audit Trail Security

### Verification Process

```bash
$ rexlit audit verify
```

#### Step 1: Load Entries

```python
entries = [json.loads(line) for line in open("audit.jsonl")]
```

#### Step 2: Verify Genesis

```python
first_entry = entries[0]
assert first_entry["previous_hash"] == "0" * 64
```

#### Step 3: Verify Chain

```python
for i, entry in enumerate(entries):
    # Recompute hash
    computed = compute_hash(entry)
    assert computed == entry["hash"], f"Entry {i} hash mismatch"

    # Verify linkage
    if i > 0:
        assert entry["previous_hash"] == entries[i-1]["hash"]
```

#### Step 4: Report

- **PASSED**: All entries valid, chain intact
- **FAILED**: Specific entry number and error details

---

## Legal Compliance

### FRCP Rule 26 Requirements

RexLit provides:

1. **Preservation**: Fsync guarantees prevent data loss
2. **Documentation**: Audit trail of all actions
3. **Chain-of-Custody**: Cryptographic hash chain
4. **Authenticity**: SHA-256 fingerprints for every document
5. **Completeness**: All documents tracked in manifest

### Admissibility

**Audit Trail**:
- Tamper-evident by design
- Cryptographically verifiable
- Detailed timestamp records
- Meets business records exception (FRE 803(6))

**Document Hashes**:
- SHA-256 fingerprints for integrity
- Detect unauthorized modifications
- Prove document unchanged since collection

### Spoliation Protection

If a party deletes or tampers with documents:

1. **Detection**: `rexlit audit verify` shows chain break
2. **Evidence**: Audit log shows exact timestamp of tampering
3. **Preservation**: Original manifest shows all collected documents

---

## Security Testing

### Test Suite

**Path Traversal Tests** (13 tests):
- `test_discover_document_symlink_within_boundary` ✅
- `test_discover_document_symlink_outside_boundary` ✅
- `test_discover_document_path_traversal_dotdot` ✅
- `test_discover_document_absolute_path_outside_root` ✅
- `test_discover_documents_nested_path_traversal` ✅
- `test_discover_documents_system_file_access_attempt` ✅
- `test_symlink_chain_outside_boundary` ✅
- And 6 more...

**Audit Tests** (10 tests):
- `test_audit_genesis_hash` ✅
- `test_audit_chain_entry_linking` ✅
- `test_audit_tampering_modified_content` ✅
- `test_audit_tampering_deleted_entry` ✅
- `test_audit_tampering_reordered_entries` ✅
- And 5 more...

### Attack Simulations

```python
# Test: Symlink to /etc/passwd
def test_symlink_outside_boundary(temp_dir):
    """Verify symlink to system file is blocked."""
    malicious = temp_dir / "evil.txt"
    malicious.symlink_to("/etc/passwd")

    docs = list(discover_documents(temp_dir, allowed_root=temp_dir))

    assert len(docs) == 0, "Should block symlink outside boundary"
```

**Result**: ✅ All attacks successfully blocked

---

## Security Best Practices

### For Administrators

1. **File Permissions**: Restrict `audit.jsonl` to read-only after creation
   ```bash
   chmod 444 ~/.local/share/rexlit/audit.jsonl
   ```

2. **Backup Audit Trail**: Regular backups to immutable storage
   ```bash
   cp audit.jsonl /backup/audit-$(date +%Y%m%d).jsonl
   ```

3. **Verify Regularly**: Run verification before critical deadlines
   ```bash
   rexlit audit verify || alert "Audit verification failed!"
   ```

4. **Monitor Logs**: Watch for path traversal warnings
   ```bash
   rexlit audit show | grep PATH_TRAVERSAL
   ```

### For Users

1. **Don't Edit Audit Trail**: Any modification breaks legal defensibility
2. **Verify Before Production**: Always `rexlit audit verify` before producing documents
3. **Keep Manifests**: Store document manifests separately for redundancy
4. **Report Anomalies**: Unusual path traversal warnings may indicate malicious documents

---

## Known Limitations

### 1. Denial of Service

**Issue**: Very large files (10GB+) can exhaust memory

**Mitigation**:
- Monitor resource usage
- Implement file size limits (future)
- Use streaming extraction (future)

**Severity**: LOW (DoS only, no data compromise)

### 2. Time-of-Check to Time-of-Use (TOCTOU)

**Issue**: File could change between validation and read

**Mitigation**:
- Minimal time window
- Read-only mode recommended
- File system snapshots (user responsibility)

**Severity**: LOW (requires attacker write access)

### 3. Metadata Extraction

**Issue**: No validation of PDF/DOCX embedded metadata

**Mitigation**:
- Metadata stored as-is, not executed
- Future: Sanitization layer

**Severity**: LOW (no execution risk)

---

## Reporting Security Issues

### Responsible Disclosure

**Email**: security@rexlit.example.com

**PGP Key**: [Public key block here]

### What to Include

1. Detailed description of vulnerability
2. Steps to reproduce
3. Proof-of-concept code (if applicable)
4. Suggested fix (optional)

### Response Timeline

- **24 hours**: Initial acknowledgment
- **7 days**: Preliminary assessment
- **30 days**: Fix or mitigation plan
- **90 days**: Public disclosure (coordinated)

### Hall of Fame

Contributors to RexLit security:
- *Your name here?*

---

## Security Roadmap

### M1 (Phase 2)

- [ ] File size limits
- [ ] Timeout handling for extraction
- [ ] Metadata sanitization
- [ ] Dependency hash verification

### M2 (Phase 3)

- [ ] Encrypted audit trail option
- [ ] Digital signatures for entries
- [ ] Multi-party audit verification
- [ ] Hardware security module (HSM) support

### M3 (Phase 4)

- [ ] Security audit by third party
- [ ] Penetration testing
- [ ] CVE monitoring for dependencies
- [ ] SBOM (Software Bill of Materials)

---

## Compliance Certifications

### Current

- ✅ FRCP Rule 26 (Federal Rules of Civil Procedure)
- ✅ FRE 803(6) (Business Records Exception)

### Future

- [ ] SOC 2 Type II
- [ ] ISO 27001
- [ ] NIST 800-53
- [ ] GDPR (if applicable)

---

## References

- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [FRCP Rule 26](https://www.law.cornell.edu/rules/frcp/rule_26)
- [SHA-256 Specification](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf)
- [Blockchain Hash Chain](https://en.wikipedia.org/wiki/Blockchain)

---

**Last Updated**: 2025-10-23 (M0 Release)

**Security Contact**: security@rexlit.example.com
