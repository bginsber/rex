---
status: resolved
priority: p1
issue_id: "003"
tags: [security, vulnerability, code-review, path-traversal]
dependencies: []
---

# Fix Path Traversal Vulnerability in Document Discovery

## Problem Statement

No validation that discovered files are within the intended root directory. While symlinks are checked, path traversal via `../` sequences or malicious symlinks is not prevented. This is a severe security risk for a legal e-discovery tool that may process adversarial documents.

## Findings

- **Location:** rexlit/ingest/discover.py:110-157, rexlit/utils/paths.py:78-91
- **Discovery:** Security audit during comprehensive code review
- **Vulnerability Type:** CWE-22 (Path Traversal), CWE-59 (Improper Link Resolution)
- **Risk Level:** HIGH - Tool processes potentially adversarial legal documents

**Problem Scenario:**
1. Attacker creates malicious document package for discovery
2. Package contains symlink: `evidence/secret.pdf -> /etc/passwd`
3. Or contains path traversal: `evidence/../../../../home/user/.ssh/id_rsa`
4. User runs `rexlit ingest ./malicious-documents`
5. Tool discovers and processes files outside intended directory
6. Sensitive system files are hashed, indexed, and potentially leaked
7. Audit trail reveals paths to sensitive files
8. Legal/compliance violation occurs

**Current Code Issues:**
```python
# discover.py:110-157
def discover_document(file_path: Path) -> DocumentMetadata:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    # NO PATH VALIDATION! Accepts any file_path
    stat = file_path.stat()
    # ... continues processing ...
```

**Incomplete symlink handling:**
```python
# utils/paths.py:78-91
if path.is_symlink() and not follow_symlinks:
    continue  # Only checks symlinks, not where they point
```

## Proposed Solutions

### Option 1: Path Resolution with Boundary Validation (Recommended)
- **Pros**:
  - Prevents path traversal attacks
  - Resolves symlinks to real paths
  - Validates all files are within allowed boundary
  - Industry standard approach
- **Cons**:
  - Requires passing root context through call stack
  - Slight performance overhead for resolve()
- **Effort**: Small (1 day including tests)
- **Risk**: Low - well-established security pattern

**Implementation:**
```python
def discover_document(
    file_path: Path,
    allowed_root: Path | None = None
) -> DocumentMetadata:
    """Discover document with path traversal protection."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # SECURITY: Resolve symlinks and validate path is within allowed root
    resolved_path = file_path.resolve()

    if allowed_root:
        allowed_root_resolved = allowed_root.resolve()
        try:
            resolved_path.relative_to(allowed_root_resolved)
        except ValueError:
            raise ValueError(
                f"Security: Path traversal detected. "
                f"File {file_path} resolves to {resolved_path} "
                f"which is outside allowed root {allowed_root}"
            ) from None

    if not resolved_path.is_file():
        raise ValueError(f"Not a file: {resolved_path}")

    # Continue with resolved_path...
    stat = resolved_path.stat()
    # ... rest of implementation using resolved_path
```

**Update discover_documents:**
```python
def discover_documents_streaming(
    root: Path,
    recursive: bool = True,
    ...
) -> Iterator[DocumentMetadata]:
    """Stream document discovery with security boundary."""
    allowed_root = root.resolve()  # Establish security boundary

    for file_path in find_files(root, recursive=recursive):
        try:
            yield discover_document(file_path, allowed_root=allowed_root)
        except ValueError as e:
            if "Path traversal" in str(e):
                print(f"SECURITY WARNING: {e}")
            continue
```

### Option 2: Strict No-Symlink Policy
- **Pros**:
  - Simpler implementation
  - No symlink risks
- **Cons**:
  - May break legitimate use cases with symlinks
  - Less flexible
- **Effort**: Very Small (< 4 hours)
- **Risk**: Medium - may block valid workflows

## Recommended Action

Implement **Option 1 (Path Resolution with Boundary Validation)** for comprehensive protection while maintaining flexibility. Add security logging for detected traversal attempts.

## Technical Details

- **Affected Files**:
  - `rexlit/ingest/discover.py` (add validation)
  - `rexlit/utils/paths.py` (enhance symlink handling)
  - `rexlit/cli.py` (ensure root path passed correctly)
- **Related Components**:
  - File system traversal
  - Document discovery
  - Security audit logging
- **Database Changes**: No
- **Dependencies**: None

## Resources

- OWASP Path Traversal (CWE-22)
- Python Path.resolve() and Path.relative_to() documentation
- Security best practices for file processing

## Acceptance Criteria

- [ ] All discovered files validated to be within allowed root directory
- [ ] Symlinks resolved and validated before processing
- [ ] Path traversal attempts logged to audit trail with WARNING level
- [ ] Security exception raised for files outside boundary
- [ ] Unit tests with malicious path examples (../../../etc/passwd)
- [ ] Unit tests with symlinks pointing outside root
- [ ] Documentation updated with security considerations
- [ ] Manual penetration testing with crafted malicious document sets
- [ ] All existing tests pass

## Work Log

### 2025-10-22 - Initial Discovery
**By:** Claude Security Audit (PR #2)
**Actions:**
- Vulnerability discovered during security review
- Categorized as P1 CRITICAL security issue
- Estimated effort: Small (1 day)
- Risk assessment: HIGH - legal discovery tool processes adversarial documents

**Learnings:**
- E-discovery tools are high-value attack targets (sensitive legal data)
- Path traversal is a common attack vector for file processing tools
- Symlink resolution must be combined with boundary validation
- Security logging is essential for forensic analysis

## Notes

**Source:** Security audit of PR #2 - RexLit Phase 1 (M0) Foundation

**Priority Justification:** This is a CRITICAL security vulnerability in a legal tool that processes potentially adversarial documents. Exploitation could lead to data breaches, compliance violations, and legal liability. Must be fixed before any production deployment.

**Compliance Impact:**
- May violate attorney-client privilege if sensitive files leaked
- Could compromise chain-of-custody if unauthorized files processed
- GDPR/privacy implications if personal data exposed
