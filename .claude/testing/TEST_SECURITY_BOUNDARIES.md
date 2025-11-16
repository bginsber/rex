# Security Boundary Test Cases

This document describes comprehensive test cases for security boundaries in the privilege API endpoints.

## Test File

The test file `index.test.ts` contains test suites for all critical security features.

## Prerequisites

### Installing Bun

Bun is required to run these tests. Install it using one of these methods:

**macOS/Linux:**
```bash
curl -fsSL https://bun.sh/install | bash
```

**Using Homebrew (macOS):**
```bash
brew install bun
```

**Using npm:**
```bash
npm install -g bun
```

**Verify installation:**
```bash
bun --version
```

## Running Tests

```bash
cd api
bun test index.test.ts
```

**First time setup:**
```bash
cd api
bun install  # Install dependencies
bun test index.test.ts
```

## Test Coverage

### 1. Path Traversal Protection (`ensureWithinRoot`)

**Purpose:** Prevent access to files outside `REXLIT_HOME` directory.

All candidate paths are resolved via `fs.realpathSync`, so symlink chains that point outside the root are rejected even if their original string path looks safe.

**Test Cases:**
- ✅ Allow paths within `REXLIT_HOME`
- ✅ Allow `REXLIT_HOME` itself
- ✅ Reject absolute paths outside root (`/etc/passwd`, `/root/.ssh/id_rsa`)
- ✅ Reject relative paths that escape root (`../../../etc/passwd`)
- ✅ Reject symlink traversal attempts
- ✅ Handle edge cases with trailing slashes
- ✅ Normalize paths before checking
- ✅ Handle empty/null-like paths
- ✅ Handle Windows-style paths on Unix systems
- ✅ Handle Unicode and special characters

**Attack Vectors Tested:**
- Directory traversal (`../`)
- Absolute path injection
- Symlink attacks
- Unicode-based attacks
- Path normalization bypass attempts

### 2. Timeout Protection (`runRexlit`)

**Purpose:** Prevent hanging requests from consuming resources indefinitely.

**Test Cases:**
- ✅ Complete successfully without timeout
- ✅ Timeout after specified duration
- ✅ Clear timeout on successful completion
- ✅ Handle timeout in error cases
- ✅ Don't set timeout if `timeoutMs` is 0
- ✅ Don't set timeout if `timeoutMs` is negative
- ✅ Include timeout duration in error message

**Scenarios Tested:**
- Normal completion (no timeout)
- Timeout triggers correctly
- Timeout cleanup on success
- Timeout cleanup on error
- Edge cases (0, negative values)

### 3. Input Validation

**Purpose:** Ensure only valid input values are accepted.

#### Threshold Validation

**Test Cases:**
- ✅ Accept valid thresholds (0.0, 0.5, 1.0)
- ✅ Reject thresholds below 0
- ✅ Reject thresholds above 1
- ✅ Reject non-numeric values (NaN, Infinity, strings, objects)
- ✅ Return null for undefined
- ✅ Handle string numbers

**Valid Range:** `0.0 <= threshold <= 1.0`

#### Reasoning Effort Validation

**Test Cases:**
- ✅ Accept valid effort values (`low`, `medium`, `high`, `dynamic`)
- ✅ Normalize case (accept `LOW`, `Medium`, etc.)
- ✅ Reject invalid values
- ✅ Return null for undefined/null
- ✅ Reject non-string values

**Valid Values:** `low`, `medium`, `high`, `dynamic` (case-insensitive)

### 4. Error Message Sanitization

**Purpose:** Prevent filesystem information leakage in error responses.

**Test Cases:**
- ✅ Sanitize file paths in error messages (`/etc/passwd` → `[path]`)
- ✅ Sanitize multiple paths in single message
- ✅ Sanitize Windows paths (`C:\Windows\...` → `[path]`)
- ✅ Preserve non-path error messages
- ✅ Handle empty error messages
- ✅ Use correct HTTP status codes (400, 404, 500, 504)

**Sanitization Rules:**
- Remove Unix paths (`/etc/...`, `/root/...`, `/home/...`)
- Remove Windows paths (`C:\...`)
- Remove any absolute paths
- Preserve error context without exposing filesystem details

### 5. Pattern Match Filtering

**Purpose:** Prevent filesystem details from leaking through pattern matches.

**Test Cases:**
- ✅ Include safe fields (`rule`, `confidence`, `snippet`, `stage`)
- ✅ Exclude filesystem paths (`path`, `file_path`, `filePath`, `directory`, `dir`)
- ✅ Exclude snippets containing paths
- ✅ Handle empty matches array
- ✅ Handle matches with only unsafe fields
- ✅ Preserve stage information

**Safe Fields:** `rule`, `confidence`, `snippet` (if no paths), `stage`  
**Unsafe Fields:** `path`, `file_path`, `filePath`, `directory`, `dir`

### 6. Secure Document Resolution (`resolveDocumentPath`)

**Purpose:** Safely resolve document paths from hash or user-provided path.

**Test Cases:**
- ✅ Resolve paths from hash lookup securely
- ✅ Reject paths that escape root when resolved
- ✅ Require either hash or path
- ✅ Normalize relative paths before validation

**Security Guarantees:**
- All resolved paths validated against `REXLIT_HOME`
- Relative paths normalized before validation
- Hash-based lookups use index as authoritative source

### 7. Stage Status Building (`buildStageStatus`)

**Purpose:** Build stage status information without leaking sensitive data.

**Test Cases:**
- ✅ Build stage status for privilege stage
- ✅ Use pattern mode for low reasoning effort
- ✅ Handle missing decision fields safely
- ✅ Handle null/undefined decision
- ✅ Detect responsive labels
- ✅ Count redaction spans correctly

**Output Structure:**
- Three stages: `privilege`, `responsiveness`, `redaction`
- Each stage has: `stage`, `status`, `mode`, `notes`
- No filesystem paths or sensitive data included

## Security Test Matrix

| Feature | Attack Vector | Protection | Test Coverage |
|---------|--------------|------------|---------------|
| Path Traversal | `../` sequences | `ensureWithinRoot()` | ✅ 10 tests |
| Path Traversal | Absolute paths | `ensureWithinRoot()` | ✅ 10 tests |
| Path Traversal | Symlinks | `resolve()` + validation | ✅ 10 tests |
| Timeout | Hanging processes | Timeout + `kill()` | ✅ 7 tests |
| Input Validation | Invalid threshold | Range validation | ✅ 7 tests |
| Input Validation | Invalid effort | Enum validation | ✅ 6 tests |
| Error Leakage | File paths in errors | Sanitization | ✅ 6 tests |
| Pattern Leakage | Filesystem in matches | Field filtering | ✅ 6 tests |

## Integration Test Scenarios

### Scenario 1: Malicious Path Injection

```typescript
// Attacker tries to access /etc/passwd
const response = await fetch('/api/privilege/classify', {
  method: 'POST',
  body: JSON.stringify({ path: '../../../etc/passwd' })
})

// Expected: 400 Bad Request with sanitized error
expect(response.status).toBe(400)
const data = await response.json()
expect(data.error).not.toContain('/etc/passwd')
expect(data.error).toContain('[path]')
```

### Scenario 2: Timeout Attack

```typescript
// Attacker sends request that hangs
const response = await fetch('/api/privilege/classify', {
  method: 'POST',
  body: JSON.stringify({ hash: 'valid-hash' })
})

// Expected: Request times out after 2 minutes
// Process is killed, timeout error returned
```

### Scenario 3: Invalid Input

```typescript
// Attacker sends invalid threshold
const response = await fetch('/api/privilege/classify', {
  method: 'POST',
  body: JSON.stringify({ 
    hash: 'valid-hash',
    threshold: 999  // Invalid: > 1.0
  })
})

// Expected: 400 Bad Request
expect(response.status).toBe(400)
const data = await response.json()
expect(data.error).toContain('threshold must be a number between 0.0 and 1.0')
```

## Test Execution

### Run All Tests

```bash
bun test index.test.ts
```

### Run Specific Test Suite

```bash
bun test index.test.ts -t "Path Traversal"
bun test index.test.ts -t "Timeout"
bun test index.test.ts -t "Input Validation"
```

### Run with Coverage

```bash
bun test --coverage index.test.ts
```

## Continuous Integration

These tests should run in CI/CD pipeline:

1. **Pre-commit:** Run security boundary tests
2. **Pull Request:** Full test suite
3. **Merge:** All tests must pass

## Maintenance

### Adding New Tests

When adding new security features:

1. Add test cases to appropriate suite
2. Document attack vectors tested
3. Update this README
4. Ensure tests run in CI

### Updating Tests

When security logic changes:

1. Update corresponding test cases
2. Verify all tests still pass
3. Add tests for new edge cases
4. Update documentation

## References

- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [Security Best Practices](./SECURITY.md)
- [API Documentation](./README.md)
