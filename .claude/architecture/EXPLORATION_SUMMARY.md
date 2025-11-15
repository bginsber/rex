# RexLit Codebase Exploration Summary

**Date:** November 13, 2025  
**Exploration Status:** ✅ Complete  
**Documentation Status:** ✅ Complete  

---

## Quick Navigation

### Design & Planning Documents (NEW)

1. **[ui/FRONTEND_DESIGN_BRIEF.md](./ui/FRONTEND_DESIGN_BRIEF.md)** (22 KB)
   - Complete visual and interaction direction for RexLit redesign
   - Aesthetic: "Litigation Terminal" (dark theme, amber/cyan accents, distinctive typography)
   - Phased implementation plan (Phase 1: Refactor, Phase 2: Layout, Phase 3: Polish)
   - Detailed TODO checklists for each phase
   - Color system, typography guidelines, and component styling
   - **Start here if you're designing the frontend**

2. **[CODEBASE_OVERVIEW.md](./CODEBASE_OVERVIEW.md)** (17 KB)
   - Complete architecture overview and codebase guide
   - Directory structure with explanations
   - Hexagonal architecture (ports & adapters)
   - Key workflows (Search & Review, Policy Management, Audit)
   - Testing guidelines and development commands
   - File index organized by topic
   - **Start here if you're understanding the codebase**

### Existing Documentation (Reference)

3. **[README.md](./README.md)** — Project overview, installation, quick start
4. **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Detailed system design
5. **[CLAUDE.md](./CLAUDE.md)** — Development guidelines for Claude Code
6. **[CLI-GUIDE.md](./CLI-GUIDE.md)** — Complete CLI command reference
7. **[SECURITY.md](./SECURITY.md)** — Security posture and threat model

---

## What is RexLit?

**An offline-first, legally-defensible e-discovery toolkit for litigation.**

**Core Functions:**
- Document ingest & indexing (Tantivy, 100K+ docs in 4–6 hours)
- Privilege classification (pattern + LLM, with audit trail)
- Bates stamping & production exports (DAT/Opticon)
- TX/FL rules engine (deadline tracking)
- Tamper-evident audit ledger (SHA-256 hash chaining)

**Key Philosophy:**
- Offline-first by default (no network calls without explicit opt-in)
- Deterministic processing (same inputs → identical outputs)
- Audit-heavy (every action logged with cryptographic proof)
- CLI-primary (web UI is optional enhancement)

**Current Status:** v0.2.0-m1, Phase 2 complete, 146 tests passing (100%)

---

## Current Frontend State

### What Exists
- Single React component (App.tsx, 761 lines)
- Two-pane layout: search sidebar + document viewer
- Privilege review with stage indicators and confidence
- Policy editor for 3-stage pipeline (Privilege, Responsiveness, Redaction)
- Basic audit trail list

### Current Aesthetic
- Generic blue SaaS theme (#2563eb primary, #f8fafc background)
- Standard typography (Inter, system fonts)
- Functional but undifferentiated

### Problem
❌ Looks like any other SaaS app (project mgmt, CRM, etc.)  
❌ Doesn't communicate "litigation infrastructure"  
❌ No visual emphasis on offline-first, audit trail, or legal domain  

---

## Desired Aesthetic: "Litigation Terminal"

### Core Identity
A **dark, terminal-adjacent workbench** for legal evidence processing.

**Visual Characteristics:**
- Dark theme (near-black backgrounds, like a terminal)
- Amber + Cyan accents (amber = legally meaningful, cyan = active)
- Distinctive typography (Crimson Text serif, IBM Plex Sans body, Fira Code mono)
- High contrast, information-dense layout
- Always-visible offline/online mode indicator

### Why This Direction?
1. **Differentiates** from competitors (Relativity, Discovery Crunch, etc.)
2. **Builds trust** (looks built for lawyers, not marketers)
3. **Emphasizes offline-first** (dark theme = air-gapped reliability)
4. **Highlights auditability** (dense layout shows decisions are traceable)

### Design Principles (Your North Star)

When making design decisions, ask:

| Principle | YES ✓ | NO ✗ |
|-----------|-------|------|
| **Communicates litigation infrastructure?** | Amber, cyan, serif | Pastels, generic fonts |
| **Supports offline-first?** | Mode indicator prominent | Hidden offline state |
| **Makes audit defensible?** | Hashes visible, chain clear | Audit trail hidden |
| **Is information-dense?** | Lots of metadata, scannable | Minimalist, hidden details |
| **Would a lawyer trust this?** | Professional, serious, purpose-built | Generic SaaS aesthetic |

---

## Phased Implementation Plan

### Phase 1: Structural Refactor
**Duration:** 1–2 sprints  
**Visual Changes:** None (keep blue theme)  
**Goal:** Make App.tsx modular, define design tokens

**Deliverables:**
- Extract `LayoutShell.tsx`, `SearchPanel.tsx`, `DocumentViewer.tsx`, `PrivilegeReviewPanel.tsx`, `PolicyEditor.tsx`, `AuditPanel.tsx`
- Define CSS variables (colors, fonts, spacing)
- Update components to reference tokens
- Behavior identical to current

**TODOs:** See `ui/FRONTEND_DESIGN_BRIEF.md` Phase 1 section

### Phase 2: Layout & Chrome Redesign
**Duration:** 1–2 sprints  
**Visual Changes:** Minimal (same color palette, new layout)  
**Goal:** Create consistent workbench layout

**Deliverables:**
- Left navigation rail (Corpus, Audit, Settings, etc.)
- Top "Run bar" (shows CLI command, mode indicator)
- Screen wrappers (Corpus.tsx, Audit.tsx, Settings.tsx, etc.)
- All screens accessible from nav

**TODOs:** See `ui/FRONTEND_DESIGN_BRIEF.md` Phase 2 section

### Phase 3: Visual Identity & Polish
**Duration:** 2–3 sprints  
**Visual Changes:** Complete (dark theme, amber/cyan, new typography)  
**Goal:** Apply "Litigation Terminal" aesthetic

**Deliverables:**
- Dark theme (near-black backgrounds, amber/cyan accents)
- Distinctive typography (Crimson Text, IBM Plex Sans, Fira Code)
- Restyle all components (buttons, badges, search results, etc.)
- Add animations (stagger, transitions, pulse)
- Enhance audit trail UI (hash display, verification)

**TODOs:** See `ui/FRONTEND_DESIGN_BRIEF.md` Phase 3 section

---

## Color System (Phase 3)

```css
/* Backgrounds */
--bg-main:     #0f1117;    /* Near-black, terminal-like */
--bg-surface:  #161b22;    /* Slightly lighter, for panels */
--bg-hover:    #21262d;    /* Interactive element hover */

/* Accents */
--accent-amber:    #d4a574;  /* Legally meaningful (Bates, deadlines, privilege) */
--accent-amber-dark: #8b6914;
--accent-cyan:     #58a6ff;  /* Active states, online mode, focus */
--accent-cyan-dark: #1f6feb;

/* Status Colors */
--status-privileged:  #d0bcff;  /* Purple for ACP, work product */
--status-responsive:  #79c0ff;  /* Blue for responsive documents */
--status-redacted:    #f0883e;  /* Orange for redacted/flagged */
--status-uncertain:   #ffd700;  /* Amber for "needs review" */
--danger:             #f85149;  /* Red, sparingly used */

/* Text */
--text-primary:      #e6edf3;  /* Body text */
--text-muted:        #8b949e;  /* Labels, metadata */
--text-faint:        #6e7681;  /* Disabled, secondary info */

/* Borders */
--border-subtle:     #30363d;
--border-muted:      #21262d;
```

---

## Typography (Distinctive)

### Headings (h1, h2)
- **Primary:** Crimson Text (serif, elegant legal feel)
- Fallback: Georgia, serif
- Style: uppercase, 1.25–1.5rem, weight 700
- Use for: section titles ("CORPUS", "PRIVILEGE REVIEW", "AUDIT LEDGER")

### Body
- **Primary:** IBM Plex Sans (distinctive, not generic Inter/Roboto)
- Fallback: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
- Style: 0.95–1rem, weight 400
- Use for: descriptions, list items, panel text, settings

### Mono
- **Primary:** Fira Code (crisp, legible, true monospace)
- Fallback: "IBM Plex Mono", monospace
- Style: 0.85rem, weight 500
- Use for: SHA-256 hashes, file paths, rule cites, Bates numbers, CLI commands

**Why This Matters:** Crimson + IBM Plex + Fira Code is a specific combination that avoids the "AI default" convergence on Inter/Roboto. It reads as intentional and domain-appropriate.

---

## Architecture Insights (Why This Affects Design)

### Hexagonal Architecture
```
CLI (rexlit/cli.py)
  ↓ depends on
Bootstrap (rexlit/bootstrap.py)
  ↓ creates
Application Services (rexlit/app/*.py)
  ↓ depends on
Port Interfaces (rexlit/app/ports/*.py)
  ↑ implemented by
Adapters (rexlit/app/adapters/*.py)
```
**Design Implication:** UI should have clear Screen → Service → Data separation.

### Three-Stage Privilege Pipeline
```
Document → Pattern Matching (offline, <1s)
         → If 85%+ confidence: DONE
         → If 50-84%: LLM Escalation (Groq/OpenAI)
         → Result logged with hashed reasoning
```
**Design Implication:** Review panel should show which stage decision came from.

### Offline-First Gate
```python
require_online()  # Explicitly opt into network calls
```
**Design Implication:** UI must always show OFFLINE vs ONLINE mode with explicit switching.

### Audit Trail (SHA-256 Chain)
```
Event 1 → SHA256("ingest doc.pdf")
Event 2 → SHA256("privilege_classify + Event1_hash")
...if any event changes, entire chain breaks (legally defensible)
```
**Design Implication:** Audit trail is first-class feature, not hidden. Show hashes, verify chain.

---

## Key Technical Details

### API Endpoints (Already Exist)
- `POST /api/search` — Full-text search
- `GET /api/documents/:hash/file` — Document preview
- `POST /api/privilege/classify` — Privilege review
- `GET /api/privilege/policy/:stage` — Policy text
- `POST /api/privilege/policy/:stage` — Save policy
- `GET /api/audit` — Audit events
- `POST /api/audit/verify` — Verify chain integrity

**All types defined in `ui/src/api/rexlit.ts`**

### Stack (Current)
- React 19.1.1 ✓
- TypeScript 5.9 (strict mode) ✓
- Vite 7 (fast dev) ✓
- Plain CSS (no framework)

### Stack (Recommend Adding)
- Component library? (Radix UI, Headless UI)
- Typography system? (Font imports, CSS variable scale)
- Design tokens? (CSS variables for theme)

---

## Important Files by Topic

### Start With These
1. **ui/FRONTEND_DESIGN_BRIEF.md** — Complete design spec
2. **CODEBASE_OVERVIEW.md** — Codebase guide
3. **ui/src/App.tsx** (761 lines) — Current UI (will refactor)
4. **ui/src/api/rexlit.ts** — Type definitions

### Understand the System
- **rexlit/cli.py** (~400 lines) — CLI entry point
- **rexlit/app/privilege_service.py** — Privilege orchestrator
- **api/index.ts** (500 lines) — REST API
- **tests/** — 146 tests showing expected behavior

### Reference
- README.md — Overview
- ARCHITECTURE.md — System design
- CLAUDE.md — Development guidelines
- SECURITY.md — Security posture

---

## Next Steps

### For Designers/Developers

1. **Read** `ui/FRONTEND_DESIGN_BRIEF.md` (20 min)
2. **Read** `CODEBASE_OVERVIEW.md` (20 min)
3. **Review** `ui/src/App.tsx` (understand current structure)
4. **Plan** Phase 1 refactor:
   - Extract components
   - Define CSS variables
   - Keep blue aesthetic (just refactored)
5. **Iterate** with team on "Litigation Terminal" direction

### Phase 1 TODO Checklist

**Extract Components:**
- [ ] Create `LayoutShell.tsx`
- [ ] Extract `SearchPanel.tsx`
- [ ] Extract `DocumentViewer.tsx`
- [ ] Extract `PrivilegeReviewPanel.tsx`
- [ ] Extract `PolicyEditor.tsx`
- [ ] Extract `AuditPanel.tsx`

**Define Tokens:**
- [ ] CSS variables for colors
- [ ] CSS variables for typography
- [ ] CSS variables for spacing
- [ ] Update components to use tokens

**Test:**
- [ ] Behavior identical to current
- [ ] All components render
- [ ] No visual changes (intentional)

---

## Questions & Guardrails

### When Making Design Decisions

1. **Does this communicate litigation infrastructure?**
   - YES: amber accents, serif headings, dark theme
   - NO: pastels, rounded corners, generic sans-serif

2. **Does this support offline-first philosophy?**
   - YES: mode indicator prominent, network status visible
   - NO: hidden offline state, accidental network calls

3. **Does this make the audit trail trustworthy?**
   - YES: hashes visible, chain status clear, verification UI
   - NO: audit trail hidden, no hash display, unclear status

4. **Is the layout information-dense?**
   - YES: lots of metadata visible, scannable at a glance
   - NO: minimalist with hidden details, lots of white space

5. **Would a lawyer trust this system?**
   - YES: professional, serious, purpose-built for their domain
   - NO: generic SaaS aesthetic, looks like any other app

### Non-Goals (Out of Scope)
- ❌ Multi-tenant SaaS
- ❌ Replace CLI as primary interface
- ❌ Redesign all workflows from scratch
- ❌ Pixel-perfect mobile support
- ❌ Real-time collaboration (future)
- ❌ AI-powered "smart" features (compliance risk)

---

## Summary

You now have everything needed to design and implement the RexLit frontend redesign:

✅ **Design Direction** — "Litigation Terminal" aesthetic  
✅ **Color System** — Dark theme with amber/cyan accents  
✅ **Typography** — Distinctive Crimson/IBM Plex/Fira Code combination  
✅ **Implementation Plan** — 3 phased approach with detailed TODOs  
✅ **Architecture Understanding** — How design supports technical choices  
✅ **Code Overview** — Where to look for key functionality  
✅ **Guardrails** — Design principles to maintain throughout  

**You're ready to start Phase 1.**

Good luck! 🚀

---

## Document Manifest

| Document | Purpose | Location |
|----------|---------|----------|
| FRONTEND_DESIGN_BRIEF.md | Design spec, color system, typography, phased plan | `ui/` |
| CODEBASE_OVERVIEW.md | Architecture, file structure, key files | root |
| EXPLORATION_SUMMARY.md | This document, quick navigation | root |
| README.md | Project overview, installation, quick start | root |
| ARCHITECTURE.md | Detailed system design | root |
| CLAUDE.md | Development guidelines | root |
| CLI-GUIDE.md | CLI command reference | root |
| SECURITY.md | Security posture | root |

