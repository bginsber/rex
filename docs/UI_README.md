# RexLit Web UI - START HERE

**Status:** 📝 Documentation Complete, Ready for Implementation
**Last Updated:** 2025-11-08

---

## Quick Links (Choose Your Path)

### 🚀 "I want to build this NOW"
→ **[UI_QUICKSTART.md](./UI_QUICKSTART.md)** (30 minutes to working MVP)

### 📖 "I want complete step-by-step instructions"
→ **[UI_IMPLEMENTATION_GUIDE.md](./UI_IMPLEMENTATION_GUIDE.md)** (4-6 hours to production-ready)

### 🧠 "I want to understand WHY we chose this approach"
→ **[UI_ARCHITECTURE.md](./UI_ARCHITECTURE.md)** (Design philosophy & rationale)

### 📚 "I want API patterns and examples"
→ **[elysia-cheat-sheet.md](./elysia-cheat-sheet.md)** (Elysia ↔ RexLit patterns)

### 📋 "I want the official decision record"
→ **[ADR-0009](./adr/0009-web-ui-architecture.md)** (Architecture Decision Record)

---

## TL;DR - What Is This?

A **radically simple** web UI for RexLit that:
- ✅ Wraps the CLI via subprocess calls (35 lines of code)
- ✅ Uses Elysia (Bun) for HTTP transport
- ✅ React UI for document review workflow
- ✅ Zero changes to Python codebase
- ✅ Honors all existing ADRs (offline-first, determinism, ports/adapters)

### The Core Principle

> **The CLI is already a perfect API. Elysia just adds HTTP.**

### Architecture Diagram

```
React UI (Browser)
    ↓ HTTP fetch
Elysia API (35 lines of TypeScript)
    ↓ Bun.spawn(['rexlit', ...])
RexLit CLI (Unchanged Python)
    ↓ reads/writes
Shared Filesystem (~/.local/share/rexlit/)
```

---

## What Makes This Elegant?

### 93% Code Reduction

**Original plans:**
- FastAPI + PostgreSQL + State Sync
- ~2,000 lines of new code
- 2 weeks to MVP
- 6+ new dependencies

**This solution:**
- Elysia subprocess wrapper
- ~150 lines total (API + UI boilerplate)
- 4 hours to MVP
- 2 new dependencies (elysia, react)

### Impossible to Diverge

**Problem:** API and CLI might return different search results.

**Solution:** They're the same thing.

```typescript
// API endpoint
app.post('/api/search', async ({ body }) => {
  return await Bun.spawn(['rexlit', 'index', 'search', body.query, '--json'])
})
```

Same CLI command → Same results → Guaranteed consistency.

### Honors All ADRs

- **ADR-0001 (Offline-First):** ✅ API is optional layer
- **ADR-0002 (Ports/Adapters):** ✅ No import violations
- **ADR-0003 (Determinism):** ✅ CLI guarantees this

---

## For Colleague Agents: Implementation Checklist

### Phase 1: Proof of Concept (30 minutes)

```bash
# 1. Setup API
cd /home/user/rex
mkdir api && cd api
bun init -y && bun add elysia @elysiajs/cors

# 2. Create index.ts (copy from UI_QUICKSTART.md)
# 3. Test: curl http://localhost:3000/api/health

# 4. Setup UI
cd /home/user/rex
bun create vite ui --template react-ts
cd ui && bun install

# 5. Create API client (copy from UI_QUICKSTART.md)
# 6. Test: Search, view, decide workflow
```

**Success criteria:** Can review 10 documents via UI.

### Phase 2: Production Ready (4-6 hours)

Follow **[UI_IMPLEMENTATION_GUIDE.md](./UI_IMPLEMENTATION_GUIDE.md)** for:
- Complete TypeScript types
- Error handling
- Testing strategy
- Deployment guide
- Security hardening

### Phase 3: Polish (Week 2, only if Phase 1 succeeds)

- JWT authentication
- Keyboard shortcuts
- Better PDF rendering (PDF.js)
- Export decisions to CSV

---

## Key Files Created

| File | Purpose | Lines | Target Audience |
|------|---------|-------|-----------------|
| [UI_QUICKSTART.md](./UI_QUICKSTART.md) | 30-min MVP guide | ~100 | Agents wanting immediate results |
| [UI_IMPLEMENTATION_GUIDE.md](./UI_IMPLEMENTATION_GUIDE.md) | Complete step-by-step | ~500 | Agents building production version |
| [UI_ARCHITECTURE.md](./UI_ARCHITECTURE.md) | Design philosophy | ~400 | Architects, reviewers, future maintainers |
| [elysia-cheat-sheet.md](./elysia-cheat-sheet.md) | API patterns | ~300 | API developers |
| [ADR-0009](./adr/0009-web-ui-architecture.md) | Decision record | ~300 | Technical leads, auditors |
| **This file** | Navigation hub | ~100 | Everyone (start here) |

---

## FAQ

### Q: Why Elysia instead of FastAPI?

**A:** Clean language boundary prevents Python imports (enforces architecture). Bun subprocess ergonomics. Faster DX.

### Q: Isn't subprocess slow?

**A:** ~50ms overhead. Legal review is human-paced (seconds per document). Not a bottleneck.

### Q: What about real-time collaboration?

**A:** Week 2 feature. Start simple (HTTP polling), add WebSockets only if needed.

### Q: Can API do more than CLI?

**A:** No. This is a feature, not a bug. Ensures parity. Want new feature? Extend CLI first, API inherits.

### Q: What if we need a database?

**A:** Filesystem IS the database (`.metadata_cache.json`, `audit.jsonl`). If needed later, add as read cache (not source of truth).

### Q: How do we handle authentication?

**A:** Week 2. JWT middleware in Elysia, include `user_id` in audit log. See [UI_IMPLEMENTATION_GUIDE.md](./UI_IMPLEMENTATION_GUIDE.md#authentication-pattern).

### Q: What about mobile?

**A:** Not v1. Legal review needs large screens. Responsive web works on tablets if needed.

---

## Testing Quick Reference

### API Test

```bash
# Health check
curl http://localhost:3000/api/health
# Expected: {"status":"ok"}

# Search
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "attorney"}'
# Expected: {"hits": [...], "total": N}
```

### UI Test

1. Open http://localhost:5173
2. Search "attorney"
3. Click result
4. View document in iframe
5. Click "Privileged" button
6. Run `rexlit audit verify` in terminal
7. Should see PRIVILEGE_DECISION entry

---

## Troubleshooting Quick Fixes

### "API won't start"

```bash
bun --version  # Must be 1.0.0+
lsof -i :3000  # Check port not in use
```

### "Search returns empty"

```bash
ls ~/.local/share/rexlit/index/  # Verify index exists
rexlit index search "test" --json  # Test CLI directly
```

### "Document won't load"

Check CORS in Elysia (add `@elysiajs/cors`), verify file path in metadata.

### "Decisions not in audit log"

```bash
cat ~/.local/share/rexlit/audit.jsonl  # Verify file exists
rexlit audit verify  # Check for errors
```

---

## Related Documentation

**RexLit Core:**
- [README.md](../README.md) - Project overview
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System design
- [CLI-GUIDE.md](../CLI-GUIDE.md) - CLI reference
- [CLAUDE.md](../CLAUDE.md) - Development guide

**ADRs:**
- [ADR-0001: Offline-First](./adr/0001-offline-first-gate.md)
- [ADR-0002: Ports/Adapters](./adr/0002-ports-adapters-import-contracts.md)
- [ADR-0003: Determinism](./adr/0003-determinism-policy.md)
- [ADR-0009: Web UI](./adr/0009-web-ui-architecture.md) ← **This decision**

---

## What We Deleted (Honor Elegance)

From the original 2-week plans, we **deleted 80%**:

- ❌ PostgreSQL/SQLite
- ❌ FastAPI Python layer
- ❌ Database migrations
- ❌ Background workers (Celery, Redis)
- ❌ Complex state sync logic
- ❌ API-CLI parity tests (they're the same now!)
- ❌ WebSockets (v1)
- ❌ Custom PDF renderers (browser handles it)
- ❌ Authentication (v1, add week 2)

**Kept only the essential 20%:**

- ✅ Search documents
- ✅ View documents
- ✅ Record decisions
- ✅ Audit trail (automatic)

**Result:** 4 hours to MVP instead of 2 weeks. 35-line API instead of 2,000.

---

## Success Metrics

### Week 1 (Must Achieve)

- [ ] API responds to all endpoints
- [ ] UI can search documents
- [ ] UI can view PDFs/images/text
- [ ] Decisions recorded in `audit.jsonl`
- [ ] **Review 10 docs faster than CLI workflow**

**If Week 1 fails:** Document why, re-evaluate approach.

**If Week 1 succeeds:** Proceed to production polish (Week 2).

---

## For Future Maintainers

### The Philosophy

This UI exists to serve legal reviewers, not to showcase technology. Every line of code is justified by user value.

### The Contract

The API's contract is the CLI's `--json` output. If you change CLI output format, version it. If you add a CLI command, the API can wrap it in 3 lines.

### The Test

"Can I explain this architecture in 30 seconds to a senior engineer?"

**Answer:** "Elysia wraps RexLit CLI as HTTP endpoints. React calls Elysia. Documents on shared filesystem. Audit automatic because CLI logs everything. Zero Python changes."

If you can't, you're over-engineering.

---

## Next Steps

### For Immediate Implementation

1. Read **[UI_QUICKSTART.md](./UI_QUICKSTART.md)**
2. Follow the 30-minute guide
3. Test with real documents
4. Report results

### For Production Deployment

1. Read **[UI_IMPLEMENTATION_GUIDE.md](./UI_IMPLEMENTATION_GUIDE.md)**
2. Build complete API + UI
3. Add authentication (Week 2)
4. Deploy to internal server

### For Architecture Review

1. Read **[UI_ARCHITECTURE.md](./UI_ARCHITECTURE.md)**
2. Read **[ADR-0009](./adr/0009-web-ui-architecture.md)**
3. Provide feedback

---

## Credits

**Design Philosophy:** Inspired by Unix philosophy (do one thing well), Git/GitHub model (CLI primary, UI wraps it), and Obsidian (files + UI = powerful).

**Key Insight:** The best code is no code. Delete aggressively.

**Result:** 93% code reduction, 95% time reduction, 100% architectural elegance.

---

**Ready to build?** Start with **[UI_QUICKSTART.md](./UI_QUICKSTART.md)** for immediate results. 🚀

---

**Last Updated:** 2025-11-08
**Status:** ✅ Documentation Complete, Ready for Implementation
