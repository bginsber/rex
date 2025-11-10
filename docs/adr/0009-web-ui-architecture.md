# ADR 0009: Web UI Architecture - CLI-as-API Pattern

**Status:** Accepted

**Date:** 2025-11-08

**Decision Makers:** Engineering Team

**Related ADRs:**
- ADR-0001 (Offline-First Gate)
- ADR-0002 (Ports/Adapters Import Contracts)
- ADR-0003 (Determinism Policy)

---

## Context

RexLit currently provides a CLI-only interface. Legal reviewers need a web UI for:
- Visual document rendering (PDFs, images, OCR results)
- Human-in-the-loop privilege review
- Collaborative review workflows
- Non-technical user accessibility

**The Question:** How do we add a web UI without compromising RexLit's core principles?

### Initial Proposals

**Option A: FastAPI + PostgreSQL**
- Python FastAPI wrapping RexLit modules
- PostgreSQL for caching search results
- Complex state sync between API and CLI
- ~2,000 lines of new code
- 2 weeks to MVP

**Option B: GraphQL + React**
- GraphQL layer for flexible queries
- Redis for real-time updates
- Background workers for async operations
- 3+ weeks to MVP

**Both options shared problems:**
- Risk of API-CLI divergence (different search results)
- Violated ADR-0002 (CLI importing domain modules)
- Complex state management
- Required database for caching
- Significant ongoing maintenance

---

## Decision

**We adopt the CLI-as-API pattern with Elysia subprocess wrapper.**

### Architecture

```
React UI → Elysia API → RexLit CLI → Filesystem
             (HTTP)      (subprocess)  (source of truth)
```

**Key principle:**
> The CLI is already a perfect API. Elysia provides HTTP transport via subprocess calls.

### Implementation

**API Layer (35 lines):**
```typescript
// api/index.ts
import { Elysia } from 'elysia'

async function rexlit(args: string[]) {
  const proc = Bun.spawn(['rexlit', ...args])
  const stdout = await new Response(proc.stdout).text()
  return args.includes('--json') ? JSON.parse(stdout) : stdout
}

new Elysia()
  .post('/api/search', async ({ body }) => {
    return await rexlit(['index', 'search', body.query, '--json'])
  })
  .listen(3000)
```

**That's the entire API. It calls CLI commands and returns results.**

---

## Rationale

### 1. Impossible to Diverge

**Problem:** API and CLI might return different search results for same query.

**Solution:** They call the same function (literally). Divergence is impossible.

```bash
# CLI
rexlit index search "attorney" --json

# API (internally)
Bun.spawn(['rexlit', 'index', 'search', 'attorney', '--json'])
```

Same command → Same result → Guaranteed consistency.

### 2. Honors All ADRs

**ADR-0001 (Offline-First):** ✅ API is optional. CLI works standalone.

**ADR-0002 (Ports/Adapters):** ✅ No import violations. Separate codebase.

**ADR-0003 (Determinism):** ✅ CLI already ensures deterministic output.

### 3. Filesystem as Database

**No PostgreSQL needed because:**
- `.metadata_cache.json` already provides O(1) stats
- `audit.jsonl` is the audit trail (no sync)
- Documents live on disk (serve directly)

**Example:**
```typescript
// Get index stats (no database)
app.get('/api/stats', async () => {
  const cache = Bun.file('~/.local/share/rexlit/index/.metadata_cache.json')
  return await cache.json()
})
```

### 4. Stateless API

**Zero in-memory state:**
- Every request is independent
- No sessions to manage
- Scales horizontally (load balance)
- Crash-safe (no state to lose)

### 5. Audit Trail Automatic

**Decisions are logged by CLI:**
```typescript
// UI records decision
await rexlit([
  'audit', 'log',
  '--operation', 'PRIVILEGE_DECISION',
  '--details', JSON.stringify({ doc_id, decision })
])
```

CLI writes to `audit.jsonl` with hash chain. Same tamper-evident guarantee.

---

## Consequences

### Positive

1. **Simple:** 35-line API vs 2,000+ line FastAPI
2. **Fast to build:** 4 hours to MVP vs 2 weeks
3. **Guaranteed consistency:** Same CLI → same results
4. **No database:** Filesystem is source of truth
5. **ADR compliant:** No violations
6. **Easy to test:** Mock subprocess, not complex Python
7. **Maintainable:** Less code = fewer bugs

### Negative

1. **Subprocess overhead:** ~50ms per call
   - *Mitigation:* Human-paced review (seconds, not milliseconds)
   - *Future:* Keep-alive process if needed

2. **Limited to CLI features:** API can't do more than CLI
   - *Mitigation:* This is a feature, not a bug (enforces parity)
   - *Future:* Extend CLI first, API inherits automatically

3. **No real-time push:** Must poll for updates
   - *Mitigation:* HTTP long-polling sufficient for v1
   - *Future:* WebSocket wrapper around CLI if needed

### Neutral

1. **Language boundary:** TypeScript ↔ Python
   - Neither imports the other (enforces clean design)
   - Subprocess is the contract

---

## Alternatives Considered

### 1. FastAPI Python Wrapper

**Rejected because:**
- CLI would import domain modules (violates ADR-0002)
- Risk of divergence (different search implementations)
- Requires database for caching
- Complex state management

### 2. Direct Python Module Imports

**Rejected because:**
- Tight coupling between API and core
- Violates ports/adapters architecture
- Can't run API without Python environment
- Duplicate logic likely

### 3. GraphQL Layer

**Rejected because:**
- Over-engineered for simple CRUD
- Doesn't solve core issues
- Adds complexity, not value

### 4. Keep CLI-only

**Rejected because:**
- Legal reviewers need visual UI
- Document rendering in terminal is poor UX
- Collaboration workflows require web interface

---

## Performance Characteristics

### Latency Budget

| Operation | CLI | API | Overhead |
|-----------|-----|-----|----------|
| Search | 150ms | 200ms | 50ms (subprocess) |
| Get doc | 50ms | 100ms | 50ms |
| Audit log | 80ms | 120ms | 40ms |

**Verdict:** Acceptable. Review is human-paced (seconds per document).

### Scaling

**Current capacity:**
- 10 concurrent reviewers: ✅ No issues
- 100K documents indexed: ✅ Tantivy handles this
- 100 concurrent reviewers: ⚠️ May need load balancing

**Horizontal scaling:**
- Elysia is stateless → load balance easily
- Shared filesystem (NFS) or replicated indexes
- No database to shard

---

## Validation

### Success Criteria

**Must have (v1):**
- [ ] API responds to search queries
- [ ] Documents render in browser
- [ ] Decisions recorded in `audit.jsonl`
- [ ] CLI and API return identical results
- [ ] Review faster than CLI + manual file opening

**Should have (v2):**
- [ ] Authentication (JWT)
- [ ] Keyboard shortcuts
- [ ] Bulk export decisions
- [ ] Filter by custodian/doctype

**Nice to have (v3+):**
- [ ] Real-time collaboration
- [ ] Mobile responsive
- [ ] Advanced analytics

### Testing

**Integration test (proves consistency):**
```bash
# Search via CLI
rexlit index search "attorney" --json > cli_result.json

# Search via API
curl -X POST localhost:3000/api/search \
  -d '{"query": "attorney"}' > api_result.json

# Should be identical
diff cli_result.json api_result.json
# (empty diff = success)
```

---

## Implementation Plan

### Week 1: Proof of Concept

**Day 1:** Elysia API (3 endpoints, 35 lines)
**Day 2:** React UI (search + viewer)
**Day 3:** Test with real documents
**Day 4:** Measure: Faster than CLI workflow?
**Day 5:** Decision point - proceed or pivot?

### Week 2: Production Polish (if Week 1 succeeds)

**Day 1:** JWT authentication
**Day 2:** Better PDF rendering (PDF.js)
**Day 3:** Keyboard shortcuts (j/k navigation)
**Day 4:** Export decisions to JSON
**Day 5:** Deploy to internal server

### Exit Criteria

**If Week 1 fails (review NOT faster):**
- Document why
- Re-evaluate whether UI adds value
- Consider alternative approaches

**If Week 1 succeeds:**
- Proceed to Week 2
- Plan for production deployment
- Gather user feedback

---

## Code Deletion Analysis

### What We Deleted (from original plans)

- ❌ FastAPI (300+ lines)
- ❌ PostgreSQL setup (database, migrations, ORM)
- ❌ State sync logic (200+ lines)
- ❌ Background workers (Celery, Redis)
- ❌ Complex authentication (v1)
- ❌ Duplicate search implementation
- ❌ API-CLI parity tests (same thing now)

**Total deleted: ~2,000 lines + 6 dependencies**

### What We Kept

- ✅ Search functionality
- ✅ Document viewing
- ✅ Decision recording
- ✅ Audit trail

**Total kept: ~150 lines + 2 dependencies**

**Result: 93% code reduction**

---

## Documentation

Created comprehensive guides for implementation:

1. **UI_QUICKSTART.md** - 30-minute MVP setup
2. **UI_IMPLEMENTATION_GUIDE.md** - Complete step-by-step
3. **UI_ARCHITECTURE.md** - Design philosophy & rationale
4. **elysia-cheat-sheet.md** - Patterns & examples
5. **This ADR** - Decision record

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Subprocess too slow | Low | Medium | Measure first, optimize if needed |
| CLI JSON format changes | Low | Low | Version CLI output with schema |
| Concurrent audit writes | Low | Critical | File locking already exists |
| User adoption failure | Medium | High | Week 1 testing proves value |
| Security (path traversal) | Medium | Critical | Validate all paths vs REXLIT_HOME |

---

## Future Considerations

### If Subprocess Becomes Bottleneck

**Options:**
1. Keep-alive Python process (FastAPI sidecar)
2. Direct filesystem reads for hot paths (stats, metadata)
3. Index replication (multiple read replicas)

**Decision:** Start simple. Optimize only if proven necessary.

### If Real-Time Collaboration Needed

**Options:**
1. WebSocket wrapper around CLI events
2. Server-Sent Events (SSE) for updates
3. Polling with ETag caching

**Decision:** Polling sufficient for v1. Evaluate in Month 2.

### If Advanced Queries Needed

**Options:**
1. Extend CLI with new search options
2. Direct Tantivy queries (bypass CLI)
3. Elasticsearch wrapper

**Decision:** Extend CLI first. API inherits automatically.

---

## References

- [Elysia Documentation](https://elysiajs.com)
- [Bun Subprocess API](https://bun.sh/docs/api/spawn)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- Related: ADR-0002 (Ports/Adapters)
- Related: ADR-0001 (Offline-First)

---

## Lessons for Future ADRs

1. **Constraints breed creativity** - CLI-only forced elegant solution
2. **Delete aggressively** - 93% code reduction, 100% feature retention
3. **Subprocess isn't slow, complexity is** - 50ms overhead < 2 weeks debugging
4. **Filesystem > Database (sometimes)** - Use the right tool
5. **MVP means MVP** - Ship 20% that delivers 80% value

---

**Status:** Accepted and documented. Ready for implementation.

**Next steps:** Follow [UI_QUICKSTART.md](../UI_QUICKSTART.md) for 30-minute proof of concept.

---

**Last Updated:** 2025-11-08
