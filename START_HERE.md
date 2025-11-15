# RexLit Frontend Redesign: Start Here

Welcome! You're about to redesign the RexLit UI. This file points you to everything you need.

---

## TL;DR

**RexLit** is an offline-first litigation toolkit. The current UI is generic blue SaaS. We want a distinctive **"Litigation Terminal"** aesthetic (dark theme, amber/cyan accents, distinctive typography).

**Three new documents have been created for you:**

1. **[ui/FRONTEND_DESIGN_BRIEF.md](./ui/FRONTEND_DESIGN_BRIEF.md)** — Complete design spec (22 KB)
2. **[CODEBASE_OVERVIEW.md](./CODEBASE_OVERVIEW.md)** — Architecture & codebase guide (17 KB)
3. **[EXPLORATION_SUMMARY.md](./EXPLORATION_SUMMARY.md)** — Quick reference (13 KB)

**Read them in this order:**
1. EXPLORATION_SUMMARY.md (10 min) — Get oriented
2. ui/FRONTEND_DESIGN_BRIEF.md (20 min) — Understand design direction
3. CODEBASE_OVERVIEW.md (20 min) — Understand the code
4. Start Phase 1 refactor (extract components, define tokens)

---

## What is RexLit?

An offline-first, legally-defensible e-discovery toolkit for litigation:

- **Ingest** documents (PDFs, DOCX, emails, text)
- **Index** with Tantivy (100K+ docs in 4–6 hours)
- **Review** with privilege classification (pattern + LLM)
- **Produce** with Bates stamping and exports (DAT/Opticon)
- **Audit** with tamper-evident SHA-256 ledger

**Key Philosophy:**
- Offline-first (no network calls without explicit opt-in)
- Deterministic (same inputs → same outputs)
- Audit-heavy (every action logged with cryptographic proof)
- CLI-first (web UI is optional enhancement)

---

## Current Frontend State

**What exists:**
- Single React component (App.tsx, 761 lines)
- Generic blue SaaS theme
- Two-pane layout: search sidebar + document viewer
- Privilege review, policy editor, basic audit trail

**Problem:** Looks like any other SaaS app. Doesn't communicate "litigation infrastructure."

---

## Desired Aesthetic: "Litigation Terminal"

A **dark, terminal-adjacent workbench** for legal evidence processing.

**Visual Identity:**
- Dark theme (#0f1117, #161b22 backgrounds)
- Amber (#d4a574) for legally meaningful things (Bates, privileges, deadlines)
- Cyan (#58a6ff) for active states and online mode
- Distinctive typography:
  - **Crimson Text** (serif, headings)
  - **IBM Plex Sans** (body, distinctive)
  - **Fira Code** (mono, hashes/paths/rules)
- High contrast, information-dense layout
- Always-visible offline/online mode indicator

**Why?**
1. Differentiates from competitors
2. Builds trust (looks built for lawyers, not marketers)
3. Emphasizes offline-first philosophy
4. Highlights auditability (audit trail is first-class)

---

## Design Principles (Your North Star)

When making design decisions, ask:

| Question | YES ✓ | NO ✗ |
|----------|-------|------|
| **Communicates litigation infrastructure?** | Amber, cyan, serif | Pastels, generic fonts |
| **Supports offline-first?** | Mode indicator prominent | Hidden offline state |
| **Makes audit defensible?** | Hashes visible | Audit trail hidden |
| **Information-dense?** | Lots of metadata, scannable | Minimalist, hidden details |
| **Would a lawyer trust this?** | Professional, serious, purpose-built | Generic SaaS aesthetic |

---

## 3-Phase Implementation Plan

### Phase 1: Structural Refactor
**Duration:** 1–2 sprints  
**Visual Changes:** None (keep blue theme)  
**Goal:** Make App.tsx modular, define design tokens

**Deliverables:**
- Extract components (LayoutShell, SearchPanel, DocumentViewer, etc.)
- Define CSS variables (colors, fonts, spacing)
- Behavior identical to current
- All tokens in place for Phase 2/3

**See:** `ui/FRONTEND_DESIGN_BRIEF.md` Phase 1 section for detailed TODOs

### Phase 2: Layout & Chrome Redesign
**Duration:** 1–2 sprints  
**Visual Changes:** Minimal (new layout, same colors)  
**Goal:** Create consistent workbench layout

**Deliverables:**
- Left navigation rail (Corpus, Audit, Settings, etc.)
- Top "Run bar" (shows CLI command, mode indicator)
- Screen wrappers for each section
- Navigation between screens works

**See:** `ui/FRONTEND_DESIGN_BRIEF.md` Phase 2 section for detailed TODOs

### Phase 3: Visual Identity & Polish
**Duration:** 2–3 sprints  
**Visual Changes:** Complete (dark theme, new typography)  
**Goal:** Apply "Litigation Terminal" aesthetic

**Deliverables:**
- Dark theme applied globally
- Typography updated (Crimson, IBM Plex, Fira Code)
- All components restyled
- Animations and polish
- Audit trail UI enhanced

**See:** `ui/FRONTEND_DESIGN_BRIEF.md` Phase 3 section for detailed TODOs

---

## How to Get Started

### Step 1: Read Documentation (1 hour)

1. **EXPLORATION_SUMMARY.md** (10 min)
   - Quick overview of RexLit
   - Current state vs. desired aesthetic
   - Architecture highlights

2. **ui/FRONTEND_DESIGN_BRIEF.md** (20 min)
   - Complete design spec
   - Color system
   - Typography guidelines
   - Phased plan with TODOs

3. **CODEBASE_OVERVIEW.md** (20 min)
   - Architecture & directory structure
   - Key files and workflows
   - Testing guidelines

### Step 2: Understand Current Code (30 min)

1. Review **ui/src/App.tsx** (761 lines)
   - See what exists
   - Understand component structure
   - Note areas for refactoring

2. Review **ui/src/App.css** (10 KB)
   - See current styling approach
   - Note hardcoded colors/values
   - Plan for token extraction

3. Review **ui/src/api/rexlit.ts**
   - See type definitions
   - Understand API client

### Step 3: Plan Phase 1 (1 hour)

1. Open `ui/FRONTEND_DESIGN_BRIEF.md` Phase 1 section
2. Create a feature branch: `git checkout -b phase-1-structural-refactor`
3. Follow the TODO checklist:
   - Extract components one by one
   - Define CSS variables
   - Update components to use tokens
   - Test behavior is identical

### Step 4: Start Implementing

Begin with Phase 1, extracting components:
- `LayoutShell.tsx` (shared layout structure)
- `SearchPanel.tsx` (search sidebar)
- `DocumentViewer.tsx` (document preview)
- `PrivilegeReviewPanel.tsx` (privilege review section)
- `PolicyEditor.tsx` (policy management)
- `AuditPanel.tsx` (audit trail)

Then update App.tsx to use these components and CSS variables.

---

## Important Files

### Documentation (Read in This Order)
1. **EXPLORATION_SUMMARY.md** ← Start here (quick overview)
2. **ui/FRONTEND_DESIGN_BRIEF.md** ← Design spec with TODOs
3. **CODEBASE_OVERVIEW.md** ← Codebase guide
4. **README.md** ← Project overview
5. **ARCHITECTURE.md** ← System design
6. **CLAUDE.md** ← Development guidelines

### Code (Key Files)
- **ui/src/App.tsx** (761 lines) — main component, will refactor
- **ui/src/api/rexlit.ts** — type definitions + API client
- **ui/src/App.css** — current styling (will refactor into tokens)
- **api/index.ts** (500 lines) — REST API endpoints
- **rexlit/cli.py** (~400 lines) — CLI entry point
- **tests/** — 146 tests showing expected behavior

---

## Color System (Phase 3 Reference)

```css
/* Backgrounds (Dark Theme) */
--bg-main: #0f1117;        /* Near-black, terminal-like */
--bg-surface: #161b22;     /* Slightly lighter, for panels */
--bg-hover: #21262d;       /* Interactive element hover */

/* Accents */
--accent-amber: #d4a574;   /* Legally meaningful (Bates, privileges, deadlines) */
--accent-cyan: #58a6ff;    /* Active states, online mode, focus */

/* Status Colors */
--status-privileged: #d0bcff;   /* Purple for ACP */
--status-responsive: #79c0ff;   /* Blue for responsive */
--status-redacted: #f0883e;     /* Orange for redacted */
--status-uncertain: #ffd700;    /* Amber for "needs review" */
--danger: #f85149;              /* Red, sparingly used */

/* Text */
--text-primary: #e6edf3;   /* Body text */
--text-muted: #8b949e;    /* Labels, metadata */
--text-faint: #6e7681;    /* Disabled, secondary info */

/* Borders */
--border-subtle: #30363d;
--border-muted: #21262d;
```

---

## Typography (Phase 3 Reference)

**Headings (h1, h2):**
- Font: Crimson Text (serif, elegant legal feel)
- Style: Uppercase, 1.25–1.5rem, weight 700

**Body:**
- Font: IBM Plex Sans (distinctive, not generic)
- Style: 0.95–1rem, weight 400

**Mono:**
- Font: Fira Code (crisp programming font)
- Style: 0.85rem, weight 500
- Use for: Hashes, paths, rule cites, Bates numbers, CLI commands

---

## Questions?

**Questions about design direction?**
- See: `ui/FRONTEND_DESIGN_BRIEF.md` Section 5 (Visual Identity) and Section 8 (Design Principles)

**Questions about codebase?**
- See: `CODEBASE_OVERVIEW.md`

**Questions about specific files?**
- See: `CODEBASE_OVERVIEW.md` section "Important Files by Topic"

**Questions about implementation?**
- See: `ui/FRONTEND_DESIGN_BRIEF.md` Phase 1, 2, or 3 sections with detailed TODOs

---

## Next Steps

1. ✅ Read EXPLORATION_SUMMARY.md (this gives you context)
2. ✅ Read ui/FRONTEND_DESIGN_BRIEF.md (this is your spec)
3. ✅ Read CODEBASE_OVERVIEW.md (this is your guide)
4. ✅ Review ui/src/App.tsx and App.css (understand current structure)
5. ⬜ Start Phase 1: Extract components, define tokens
6. ⬜ After Phase 1: Phase 2 (layout redesign)
7. ⬜ After Phase 2: Phase 3 (visual identity)

---

## Status

- **Exploration:** ✅ Complete
- **Documentation:** ✅ Complete
- **Design Spec:** ✅ Complete
- **Codebase Guide:** ✅ Complete
- **Ready to Start Phase 1:** ✅ Yes

Good luck! 🚀

