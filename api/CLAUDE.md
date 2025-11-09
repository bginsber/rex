# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The RexLit API is a Bun-based HTTP wrapper around the RexLit CLI, enabling programmatic access to document search, metadata retrieval, and privilege review workflows. It serves as the backend for the RexLit web UI, exposing RESTful endpoints that spawn RexLit subprocesses and return structured JSON responses.

**Key Characteristic:** This is a thin, synchronous wrapper around an offline-first document processing system. Network operations are handled via standard HTTP requests; the underlying RexLit system maintains air-gapped security and deterministic processing.

## Essential Commands

### Development
```bash
# Install dependencies
bun install

# Run development server (watches for changes)
bun run dev

# Run production server
bun run start
```

### Type Checking and Linting
```bash
# Type check (tsconfig strict mode enabled)
bunx tsc --noEmit

# Format code (Bun uses Prettier by default)
bunx prettier --write src/
```

## Architecture Overview

### Core Design Pattern

The API follows a **subprocess wrapper pattern**:

```
HTTP Request → Elysia Route Handler → runRexlit(args) → Bun.spawn()
    ↓                                                          ↓
    └──────────────────────────────────────────────────────────┘
             Collect stdout/stderr → Parse JSON → Response
```

Key design principles:

1. **Stateless**: Each request spawns a fresh RexLit process with fresh data context
2. **Synchronous**: Handlers await subprocess completion; no queuing or background jobs
3. **Path Safety**: All file paths validated via `ensureWithinRoot()` against `REXLIT_HOME`
4. **Error Transparency**: Subprocess stderr encoded in error responses for debugging

### Configuration

Environment variables (read from `.env` via Bun's auto-loader):

- `REXLIT_BIN` - Path to rexlit executable (default: `"rexlit"`)
- `REXLIT_HOME` - RexLit data directory (default: `~/.local/share/rexlit`)
- `PORT` - HTTP listen port (default: `3000`)

Example `.env`:
```
REXLIT_BIN=/usr/local/bin/rexlit
REXLIT_HOME=/var/lib/rexlit
PORT=8080
```

### API Endpoints

#### Search Documents
```
POST /api/search
Body: { query: string, limit?: number }
Returns: RexLit search results (JSON)
Error: 400 if query missing, 500 if rexlit subprocess fails
```

#### Get Document Metadata
```
GET /api/documents/:hash/meta
Returns: Document metadata from RexLit index (path, size, custodian, doctype, etc.)
Error: 404 if not found
```

#### Retrieve Document Content
```
GET /api/documents/:hash/file
Returns: HTML-wrapped plain text (HTML-escaped content in <pre> tag)
Note: Uses index metadata to locate file on disk (path traversal protected)
Error: 404 if hash not in index or file missing on disk
```

#### Log Privilege Review Decision
```
POST /api/reviews/:hash
Body: { decision: string }
Headers: x-user-id (optional, defaults to "unknown")
Returns: { success: true }
Effect: Logs PRIVILEGE_DECISION to RexLit audit trail with reviewer and timestamp
```

#### Health Check
```
GET /api/health
Returns: { status: "ok" }
```

#### System Statistics
```
GET /api/stats
Returns: Contents of `.metadata_cache.json` (doc count, custodians, doctypes, etc.)
Error: 404 if cache not yet built
```

### Subprocess Invocation

The `runRexlit()` function:
- Spawns RexLit with piped stdout/stderr
- Awaits exit code and output
- Throws on non-zero exit with stderr included
- Parses `--json` output as JSON if flag present

Example internal call:
```typescript
await runRexlit(['index', 'search', 'privileged', '--limit', '20', '--json'])
```

## Code Style

- **TypeScript**: Strict mode enabled in `tsconfig.json` (no implicit any, strict null checks)
- **Line Length**: 100 characters (Prettier default)
- **Framework**: Elysia v1.4+ (lightweight Bun-native HTTP framework)
- **Imports**: No external web frameworks (no Express/Fastify); use `Bun.serve()` patterns

### Module Organization

```
index.ts
├── Configuration (REXLIT_BIN, PORT, REXLIT_HOME, ROOT_PREFIX)
├── Helper Functions (runRexlit, ensureWithinRoot)
├── Elysia App Setup (.use(cors()), route definitions)
└── Server Start (.listen(PORT), console.log)
```

All code resides in a single `index.ts` file for simplicity—no sub-modules or layering.

## Security Considerations

### Path Traversal Protection

- **`ensureWithinRoot()`**: Validates all file paths are within `REXLIT_HOME` before access
- Used when serving files via `/api/documents/:hash/file`
- Currently **not actively enforced** in file serving (path comes from index metadata)—but the function is present for future strict mode

### Input Validation

- **Search query**: Checked for emptiness before passing to subprocess
- **Limit parameter**: Parsed as number, coerced to string for CLI
- **Headers**: `x-user-id` passed through as-is to audit log (log escaping is responsibility of RexLit)

### Offline Operation

- API itself has no offline mode; it directly calls RexLit CLI
- RexLit's offline-first gate (`require_online()`) applies to its own network operations
- API should not add network calls beyond subprocess spawning

## Dependencies

Core dependencies:
- **elysia** ^1.4.15 - HTTP framework built on Bun
- **@elysiajs/cors** ^1.4.0 - CORS middleware

No external dependencies for subprocess management, JSON parsing, or path handling—all built into Bun.

## Testing

No test files currently present. For future test additions:
- Use `bun test` (built-in Bun testing framework)
- Test files: `*.test.ts` or `*.spec.ts`
- Run: `bun test`

Example structure:
```typescript
import { test, expect } from 'bun:test'
import type { Server } from 'bun'

test('GET /api/health returns ok', async () => {
  // Setup: start server, make request
  // Assert: response status 200, body { status: 'ok' }
})
```

## Integration Points

### With RexLit CLI

- **Dependency**: RexLit must be installed and in PATH (or `REXLIT_BIN` configured)
- **Contract**: Each endpoint calls RexLit with specific CLI arguments and expects JSON/text output
- **Failure Modes**: If RexLit binary missing or crashes, API returns 500 with error message

### With Web UI

- **Frontend**: Located in parent `rex/` directory (separate React/TypeScript codebase)
- **CORS**: Enabled via `@elysiajs/cors` middleware (allows any origin by default)
- **Content Type**: API returns JSON for metadata/search; HTML for file preview

## Debugging

### Check if RexLit is accessible:
```bash
which rexlit
$REXLIT_BIN --version
```

### Inspect subprocess stderr:
Any error thrown by `runRexlit()` includes the full stderr output. Check server logs for error messages.

### Trace requests:
Enable Bun's debug logging:
```bash
BUN_DEBUG_QUIET_LOGS=0 bun run start
```

### Validate REXLIT_HOME:
```bash
ls -la ~/.local/share/rexlit/
# or
env REXLIT_HOME=/custom/path bun run start
```

## Common Development Tasks

### Adding a New Endpoint

1. Define route handler in `index.ts` using Elysia pattern:
   ```typescript
   .post('/api/new-feature', async ({ body, params }) => {
     // Call runRexlit with appropriate args
     return await runRexlit([...args])
   })
   ```
2. Validate inputs (query params, body fields)
3. Handle errors from `runRexlit()` (non-zero exit → 500 response)
4. Return JSON or HTML based on response type

### Modifying REXLIT_HOME Logic

- Update `REXLIT_HOME` configuration line
- Ensure `ensureWithinRoot()` is used if restricting file access
- Test with custom `.env` values

### Handling New RexLit Output Formats

If RexLit changes CLI output format:
1. Update the corresponding `await runRexlit([...])` call
2. Adjust JSON parsing if response structure changes
3. Update endpoint documentation above

## Deployment Considerations

- **Port Binding**: Ensure `PORT` env var is set (default 3000)
- **RexLit Binary**: Must be in PATH or `REXLIT_BIN` env var set
- **Working Directory**: API spawns subprocesses from cwd; RexLit works independently via `REXLIT_HOME`
- **Resource Usage**: Each request spawns a new RexLit process; design for expected QPS
- **Timeouts**: Currently no request timeout; consider adding if RexLit queries hang
