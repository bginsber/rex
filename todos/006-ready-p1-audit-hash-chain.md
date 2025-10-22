---
status: resolved
priority: p1
issue_id: "006"
tags: [data-integrity, security, audit, cryptography, code-review]
dependencies: [005]
---

# Implement Hash Chain for Tamper-Evident Audit Trail

## Problem Statement

Each `AuditEntry` computes its own hash but doesn't include the previous entry's hash. This is not a true "chain" - entries are independent. An attacker can delete middle entries without detection, and temporal ordering cannot be proven. This violates the tamper-evident requirement for legal e-discovery audit trails.

## Findings

- **Location:** rexlit/audit/ledger.py:49-64, ledger.py:154-170
- **Discovery:** Data integrity review during code review
- **Compliance Impact:** CRITICAL - Affects tamper-evidence and chain-of-custody
- **Cryptographic Issue:** Independent hashes don't form a chain

**Problem Scenario:**
1. User processes 10,000 documents, creating 10,000 audit entries
2. Each entry has its own SHA-256 hash (computed from its content)
3. Attacker gains access to audit.jsonl file
4. Attacker deletes entries #4500-4600 (removes 100 entries)
5. Attacker rewrites file with remaining entries
6. User runs `rexlit audit verify`
7. Verification passes! Each remaining entry has valid hash
8. No way to detect the missing entries
9. Chain-of-custody compromised - cannot prove operation sequence
10. Legal defensibility destroyed

**Current Code:**
```python
class AuditEntry(BaseModel):
    """Single audit ledger entry."""
    timestamp: str
    operation: str
    inputs: list[str]
    outputs: list[str]
    args: dict[str, Any]
    versions: dict[str, str]
    entry_hash: str | None  # Hash of THIS entry only (not chained!)

    def compute_hash(self) -> str:
        """Compute hash of entry content."""
        data = self.model_dump(mode="json", exclude={"entry_hash"})
        content = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return compute_sha256(content.encode("utf-8"))
        # Does NOT include previous entry hash!
```

**Verification only checks individual hashes:**
```python
def verify(self) -> bool:
    """Verify integrity of all entries in the ledger."""
    entries = self.read_all()

    for entry in entries:
        expected_hash = entry.compute_hash()
        if entry.entry_hash != expected_hash:
            return False  # Only checks individual hash

    return True  # Cannot detect deleted entries!
```

## Proposed Solutions

### Option 1: Blockchain-Style Hash Chain (Recommended)
- **Pros**:
  - Tamper-evident (any modification breaks chain)
  - Detects missing/deleted entries
  - Detects reordering of entries
  - Industry standard (blockchain, git)
  - Cryptographically sound
- **Cons**:
  - Slightly more complex
  - Cannot verify single entry in isolation
- **Effort**: Small (1 day including tests)
- **Risk**: Low - well-established pattern

**Implementation:**
```python
class AuditEntry(BaseModel):
    """Single audit ledger entry with hash chain."""
    timestamp: str
    operation: str
    inputs: list[str]
    outputs: list[str]
    args: dict[str, Any]
    versions: dict[str, str]
    previous_hash: str = Field(
        default="0" * 64,  # Genesis entry has null previous hash
        description="SHA-256 hash of previous entry (chain link)"
    )
    entry_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of this entry including previous_hash"
    )

    def compute_hash(self) -> str:
        """Compute hash including previous entry's hash."""
        # Include previous_hash in computation to create chain
        data = self.model_dump(mode="json", exclude={"entry_hash"})
        content = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return compute_sha256(content.encode("utf-8"))

class AuditLedger:
    """Append-only audit ledger with hash chain."""

    def __init__(self, ledger_path: Path):
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = self._get_last_hash()

    def _get_last_hash(self) -> str:
        """Get hash of last entry for chaining."""
        try:
            entries = self.read_all()
            if entries:
                return entries[-1].entry_hash or ("0" * 64)
        except Exception:
            pass
        return "0" * 64  # Genesis hash

    def log(self, operation: str, ...) -> AuditEntry:
        """Log operation with hash chain."""
        entry = AuditEntry(
            timestamp=datetime.now(UTC).isoformat(),
            operation=operation,
            inputs=inputs or [],
            outputs=outputs or [],
            args=args or {},
            versions=versions,
            previous_hash=self._last_hash,  # Chain to previous
        )

        # Compute hash (includes previous_hash)
        entry.entry_hash = entry.compute_hash()

        # Write with fsync (from Issue #005)
        with open(self.ledger_path, "a") as f:
            f.write(entry.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())

        # Update last hash for next entry
        self._last_hash = entry.entry_hash

        return entry

    def verify(self) -> tuple[bool, str | None]:
        """Verify integrity of hash chain."""
        entries = self.read_all()

        if not entries:
            return True, None

        # Verify first entry has genesis previous_hash
        if entries[0].previous_hash != "0" * 64:
            return False, "First entry has invalid previous_hash"

        # Verify each entry's hash chain
        for i, entry in enumerate(entries):
            # Check individual hash
            expected_hash = entry.compute_hash()
            if entry.entry_hash != expected_hash:
                return False, f"Entry {i} has invalid hash"

            # Check chain link
            if i > 0:
                prev_entry = entries[i - 1]
                if entry.previous_hash != prev_entry.entry_hash:
                    return False, f"Entry {i} breaks hash chain (missing or reordered entries)"

        return True, None
```

### Option 2: Merkle Tree Structure
- **Pros**:
  - Even stronger guarantees
  - Can verify subset of entries
  - Used in Certificate Transparency
- **Cons**:
  - Much more complex
  - Overkill for append-only log
- **Effort**: Large (1 week)
- **Risk**: Medium - complexity

## Recommended Action

Implement **Option 1 (Hash Chain)** for tamper-evidence. This is the industry standard for append-only audit logs and provides strong guarantees with minimal complexity.

## Technical Details

- **Affected Files**:
  - `rexlit/audit/ledger.py` (add previous_hash field, update verify logic)
- **Related Components**:
  - Audit trail
  - Chain-of-custody verification
  - Cryptographic integrity
- **Database Changes**: No (backward compatible - old entries can have genesis hash)
- **Dependencies**: Issue #005 (fsync) should be implemented first

## Resources

- Blockchain hash chain design
- Git's hash chain implementation
- Certificate Transparency RFC 6962
- Cryptographic audit log best practices

## Acceptance Criteria

- [ ] `AuditEntry` includes `previous_hash` field
- [ ] Hash computation includes `previous_hash` (creates chain)
- [ ] `AuditLedger.log()` maintains `_last_hash` state
- [ ] First entry has genesis hash (0x00...00)
- [ ] `verify()` checks hash chain integrity
- [ ] `verify()` detects missing entries (broken chain)
- [ ] `verify()` detects reordered entries (broken chain)
- [ ] `verify()` returns detailed error message on failure
- [ ] Backward compatibility: existing logs can be migrated
- [ ] Performance impact measured (minimal overhead expected)
- [ ] All existing tests pass
- [ ] New tests for tampering detection:
  - [ ] Delete entry from middle
  - [ ] Modify entry content
  - [ ] Reorder entries
  - [ ] Duplicate entries

## Work Log

### 2025-10-22 - Initial Discovery
**By:** Claude Data Integrity Review (PR #2)
**Actions:**
- Issue discovered during cryptographic audit
- Categorized as P1 CRITICAL data integrity issue
- Estimated effort: Small (1 day)
- Risk assessment: HIGH - affects legal defensibility

**Learnings:**
- Independent hashes don't prevent deletion attacks
- Hash chains are the standard solution (blockchain, git)
- Tamper-evidence is critical for legal audit trails
- Chain verification is computationally cheap
- Hash chains also prove temporal ordering

## Notes

**Source:** Data integrity analysis of PR #2 - RexLit Phase 1 (M0) Foundation

**Priority Justification:** Without a hash chain, the audit trail is NOT tamper-evident. An attacker (or accidental corruption) can delete entries without detection. This violates the core requirement for a legally defensible audit trail in e-discovery.

**Cryptographic Guarantee:**
- Current: Each entry valid in isolation (weak)
- With chain: Any modification breaks entire chain (strong)
- Attack resistance: Requires full hash collision to forge (computationally infeasible)

**Legal Standards:**
- Audit trails must be tamper-evident (not just tamper-resistant)
- Must be able to detect any modification or deletion
- Hash chains are widely accepted in legal contexts
- Used in digital notarization and timestamping services

**Migration Path:**
- Old audit logs can be assigned genesis hash as previous_hash
- New entries start chaining from last old entry
- Or: mark old logs as "pre-chain" in metadata
