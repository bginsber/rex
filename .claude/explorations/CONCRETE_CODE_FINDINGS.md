# Concrete Code Findings: PDF Viewing Implementation

This document answers the "What would you want to know?" questions by examining actual code.

---

## Q1: Exact shape of metadata from `rexlit index get`

**Source**: `rexlit/ingest/discover.py:19-33` (Python)

**DocumentMetadata class**:
```python
class DocumentMetadata(BaseModel):
    """Metadata for a discovered document."""

    path: str                          # Absolute path to document
    sha256: str                        # SHA-256 hash of file content
    size: int                          # File size in bytes
    mime_type: str | None              # MIME type (can be None)
    extension: str                     # File extension (lowercase)
    mtime: str                         # Modification time (ISO 8601)
    custodian: str | None              # Document custodian (can be None)
    doctype: str | None                # Document type classification (can be None)
```

**Key points**:
- ✅ `mime_type` is present in metadata (not missing)
- ✅ `mime_type` can be `None` for unknown file types
- ✅ `size` is available (useful for preventing memory exhaustion)
- ⚠️ No charset suffix expected (e.g., not `'application/pdf; charset=binary'`)
- ✅ Pydantic v2 BaseModel is used (has `.model_dump()`)

**MIME type values observed**:
- `'application/pdf'` - for PDFs (checked with `.startswith("application/pdf")`)
- `'text/plain'` - for text files
- `None` - for unknown extensions

---

## Q2: MIME type variations for PDF

**Source**: `rexlit/ingest/discover.py:36-46, 49-65`

**Detection method**:
```python
def detect_mime_type(file_path: Path) -> str | None:
    """Detect MIME type of file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type
```

**Classification for PDFs**:
```python
def classify_doctype(mime_type: str | None, extension: str) -> str | None:
    if mime_type:
        if mime_type.startswith("application/pdf"):  # ← This is the check!
            return "pdf"
```

**Key findings**:
- ✅ Uses Python's standard `mimetypes.guess_type()` (very reliable)
- ✅ Only checks `mime_type.startswith("application/pdf")` - so any `application/pdf*` variant is treated as PDF
- ✅ No vendor-specific PDF MIME types in codebase (e.g., no `application/x-pdf` handling)
- **Implication**: Safe to use `mime_type?.startsWith('application/pdf')` in TypeScript

**Edge case**: Files with unknown extensions will have `mime_type: None`, so the doctype will also be `None`.

---

## Q3: How ensureWithinRoot and resolveDocumentPath are wired

**File location**: `api/index.ts:277-376`

### ensureWithinRoot (TypeScript)

```typescript
export function ensureWithinRoot(filePath: string) {
  if (!filePath) {
    throw new Error('Path traversal detected')
  }
  const absolute = resolve(filePath)
  const resolved = resolveRealPathAllowMissing(absolute)
  const relativePath = relative(REXLIT_HOME_REALPATH, resolved)
  if (
    relativePath === '' ||
    (!relativePath.startsWith('..') && !isAbsolute(relativePath))
  ) {
    return resolved
  }
  throw new Error('Path traversal detected')
}
```

**Key points**:
- ✅ Called in `/api/documents/:hash/file` at line 666: `const trustedPath = ensureWithinRoot(metadata.path)`
- ✅ Validates symlinks (resolves to real path first)
- ✅ Checks against `REXLIT_HOME_REALPATH` (environment variable)
- ✅ Returns the validated absolute path
- **Status**: Already in use in current code

### resolveDocumentPath (TypeScript)

```typescript
export async function resolveDocumentPath(
  body: PrivilegeRequestBody
): Promise<string> {
  // Priority: hash lookup > explicit path
  if (body?.hash) {
    const metadata = (await runRexlit([
      'index',
      'get',
      body.hash,
      '--json'
    ])) as { path?: unknown }

    if (!metadata?.path || typeof metadata.path !== 'string') {
      throw new Error(`No document found with hash ${body.hash}`)
    }

    return ensureWithinRoot(metadata.path)
  }

  if (body?.path) {
    return ensureWithinRoot(body.path)
  }

  throw new Error('Either hash or path must be provided')
}
```

**Key points**:
- ✅ Prefers hash-based lookup (queries index first)
- ✅ Falls back to direct path with validation
- ✅ Always calls `ensureWithinRoot()` before returning
- **Status**: Used in privilege classification, but NOT in `/api/documents/:hash/file`
- **Opportunity**: `/api/documents/:hash/file` could reuse this pattern

---

## Q4: How Elysia handles file responses

**Current pattern in `/api/documents/:hash/file`**:

```typescript
.get('/api/documents/:hash/file', async ({ params }) => {
  try {
    // ... validation ...
    const text = await file.text()  // Loads entire file into memory
    const htmlContent = `<!DOCTYPE html>...`
    return new Response(htmlContent, {
      headers: { 'Content-Type': 'text/html; charset=utf-8' }
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return jsonError(message, 500)
  }
})
```

**Key findings**:
- ✅ Uses `Bun.file(path)` to get file object (lazy - doesn't load yet)
- ✅ Calls `.text()` to load entire file into memory
- ✅ Returns plain `new Response(content, { headers })`
- ⚠️ No streaming (entire file loaded into memory)
- **For PDFs**: Should use `new Response(Bun.file(trustedPath), { headers })` for streaming

**Idiomatic patterns found**:
1. For text: `await Bun.file(path).text()` then wrap
2. For binary: Return `new Response(Bun.file(path), { headers })` directly
3. Error handling: Use `jsonError(message, statusCode)` helper

**Other binary endpoints**: None found in codebase yet (first binary endpoint)

---

## Q5: How mime_type flows through the UI

**Current flow**:

```
rexlit index search <query> --json
  ↓ returns SearchResult[] with path, sha256, custodian, doctype, ...
  ↓
ui/src/types/document.ts:5-15 (SearchResult interface)
  ⚠️ mime_type NOT in SearchResult type!
  ↓
ui/src/components/documents/DocumentViewer/DocumentViewer.tsx
  receives: document: SearchResult | null
  ✅ Has access to: path, sha256, custodian, doctype
  ❌ Does NOT have: mime_type
```

**Discovery**:
- ❌ `mime_type` is NOT included in search results
- ✅ But `/api/documents/:hash/meta` endpoint exists and returns full DocumentMetadata
- ⚠️ DocumentViewer never calls `/api/documents/:hash/meta`

**Two options to get mime_type**:
1. **Add to search results**: Include `mime_type` in `/api/search` response (requires API changes)
2. **Fetch on-demand**: Call `/api/documents/:hash/meta` when document is selected (current gap)
3. **Add to SearchResult type**: Extend `SearchResult` interface to include `mime_type` (best practice)

**Current assumption**: Search results return everything needed. This is violated for MIME types.

**Solution**:
- Update `SearchResult` interface to include `mime_type?: string | null`
- Update `/api/search` to include mime_type in response
- OR call `/api/documents/:hash/meta` in DocumentViewer before rendering

---

## Q6: Any hidden constraints or TODOs around document viewing

**Search results**:
```bash
grep -r "TODO\|FIXME\|HACK\|XXX" /home/user/rex/ui/src/components/documents/ | head -20
  # (no results - no TODOs found)

grep -r "TODO\|FIXME\|HACK\|viewer.*redact\|redact.*viewer" /home/user/rex/docs/
  # Found: docs/adr/0006-redaction-plan-apply-model.md
```

**Key findings**:

1. **DocumentViewer error handling** (lines 56-94):
   - Already detects JSON error responses inside iframes
   - Gracefully replaces iframe content with friendly error message
   - ✅ This will work fine with PDFs too (no JSON errors expected)

2. **No viewer 2.0 plans found**:
   - Only `/api/documents/:hash/file` endpoint mentioned
   - No TODO about "future PDF support" or "pdf.js integration"
   - No "viewer plugin" architecture

3. **Redaction constraints** (ADR 0006):
   - Two-phase model: plan → apply
   - Existing `pdf_stamper.py` uses PyMuPDF for Bates numbering
   - Document viewer is READ-ONLY (no redaction overlays in current UI)
   - ✅ Safe to add PDF viewing without breaking redaction pipeline

4. **iframe sandbox policy** (DocumentViewer line 55):
   - `sandbox="allow-same-origin allow-scripts"`
   - ✅ Allows PDF viewer to work (browser needs same-origin + scripts for PDF controls)
   - ⚠️ Could be tightened if PDF.js is added later (worker communication)

5. **No assumptions violated**:
   - `/api/documents/:hash/file` returns EITHER HTML-wrapped text OR raw bytes (no assumption broken)
   - iframe can display PDF or HTML (both work)
   - No code assumes text-only behavior

---

## Q7: Test harness capabilities for HTTP routes

**Current test file**: `api/index.test.ts` (330 lines)

**What's tested**:
- ✅ Helper functions: `ensureWithinRoot`, error messages, timeouts
- ✅ Unit tests with mocked `runRexlit` subprocess
- ❌ Full HTTP route tests (no full integration tests)
- ❌ No app.fetch() or app.handle() tests

**Test pattern for adding HTTP tests**:

```typescript
// Option 1: Direct app.fetch (if Elysia supports)
test('GET /api/documents/:hash/file returns PDF', async () => {
  const mockResponse = {
    path: '/docs/test.pdf',
    mime_type: 'application/pdf',
    size: 12345
  }
  __setRunRexlitImplementation(() => mockResponse)

  const response = await app.fetch(
    new Request('http://localhost/api/documents/abc123/file')
  )
  expect(response.status).toBe(200)
  expect(response.headers.get('Content-Type')).toBe('application/pdf')
})
```

**Current setup**:
- `__setRunRexlitImplementation` is exported for testing (good!)
- Test environment creates `POLICY_TEST_HOME` directory
- Helper `createMockProcess` available

**Cleanest way forward**:
1. Export `app` from api/index.ts (already done)
2. Use `app.fetch(request)` method (Elysia standard)
3. Mock `runRexlit` via `__setRunRexlitImplementation`

---

## Q8: Edge cases around huge/missing files

**Current implementation** (`api/index.ts:651-700`):

```typescript
const file = Bun.file(trustedPath)

if (!(await file.exists())) {
  return new Response(JSON.stringify({ error: 'File not found on disk' }), {
    status: 404
  })
}

const text = await file.text()  // ← Loads entire file!
```

**Findings**:
- ✅ Checks if file exists (good)
- ⚠️ No file size check before reading
- ⚠️ No streaming for large files
- ⚠️ `.text()` will fail on binary PDFs (but returns error properly)

**Size information available**:
- ✅ `metadata.size` is available from index metadata
- ✅ Could add: `if (metadata.size > 100_000_000) throw "File too large"`

**Existing constraints**:
- No `MAX_FILE_SIZE` environment variable found
- No timeout config for file reading (only subprocess timeout)
- No streaming pattern in API (all endpoints load into memory)

**Edge case handling**:
1. **Missing files**: Currently returns `{ error: 'File not found on disk' }` (good)
2. **Very large files**: Will load entire file into memory, could cause OOM
3. **Binary files**: `.text()` will fail, caught by error handler (returns 500)

**Recommendation**:
- Add size check: `if (size > 50_000_000) return jsonError('File too large', 400)`
- For PDFs: Return `new Response(Bun.file(trustedPath))` for streaming (zero-copy)

---

## Summary of Implementation Decisions

| Question | Finding | Decision |
|----------|---------|----------|
| Metadata shape | DocumentMetadata includes mime_type (nullable) | Use mime_type from metadata |
| MIME detection | Uses Python mimetypes, checks `.startswith("application/pdf")` | Same check in TypeScript: `.startsWith('application/pdf')` |
| File serving | Current: `.text()` + HTML wrap. Binary: return raw Bun.file() | For PDF: return `new Response(Bun.file(path), headers)` |
| mime_type in UI | NOT in SearchResult type currently | Add to SearchResult type OR fetch meta endpoint |
| Constraints | iframe sandbox allows same-origin + scripts | Works for PDFs (browser viewer) |
| Test harness | No HTTP tests yet, helper functions tested | Add HTTP tests using `app.fetch()` + mocked `runRexlit` |
| Size checks | None currently | Add optional size check before serving |

---

## Implementation Plan

1. **Modify `/api/documents/:hash/file`**:
   - Check metadata.mime_type
   - If PDF: return binary with headers
   - If text: keep current behavior
   - Add size validation

2. **Update React types**:
   - Add mime_type to SearchResult interface
   - Update search API client to include it
   - Update DocumentViewer to use it for rendering hints

3. **Add tests**:
   - HTTP tests for PDF vs text behavior
   - MIME type detection tests
   - Binary file handling tests

4. **No changes needed**:
   - Security: already protected via ensureWithinRoot
   - Offline-first: no network changes
   - iframe sandbox: already compatible
