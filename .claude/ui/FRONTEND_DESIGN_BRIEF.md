# RexLit Frontend Design Brief

Path: `ui/FRONTEND_DESIGN_BRIEF.md`  
Target: **Desktop**, legal/ops environments, CLI-first users with optional UI.

---

## 1. What This Document Is

This brief defines:

- The **visual and interaction direction** for the RexLit UI.
- The **phased implementation plan** for refactoring and redesign.
- The **mapping between CLI commands and UI surfaces**, so the UI stays faithful to the deterministic core.

It is intentionally *concrete*: each phase includes TODO checklists that can be tracked in issues or used by AI coding agents.

---

## 2. Design Goals

The UI should make three things obvious the moment it loads:

1. **This is litigation infrastructure, not a generic SaaS dashboard.**
   - Serious, information-dense, and trustworthy.
   - Feels closer to a **trusted terminal** than a pastel project-management app.

2. **Offline-first and data locality are core properties.**
   - Users should always know when RexLit is in `OFFLINE` vs `ONLINE` mode.
   - Any networked behavior should feel explicitly *opt-in*, never accidental.

3. **Every action is auditable and defensible.**
   - Privilege decisions, productions, and rules calculations should look *traceable*.
   - The audit trail is a first-class feature, not a backend detail.

---

## 3. Product & User Context (Short Version)

**What RexLit is:**

An offline-first, secure UNIX litigation toolkit for e-discovery and productions:

- Document ingest & indexing (Tantivy, 100K+ docs)
- OCR (Tesseract) with preflight optimization
- Bates stamping & DAT/Opticon exports
- Privilege classification (patterns + LLM escalation)
- TX/FL rules engine with ICS export
- Tamper-evident SHA-256 audit ledger

**Primary personas:**

- **Litigation associate / contract reviewer**
  - Job: triage and classify documents for privilege/responsiveness under time pressure.
  - Environment: likely solo, or with lit support team, in a potentially air-gapped setting.
- **Litigation support / paralegal**
  - Job: run productions, verify Bates ranges, export deliverables, sanity-check audit logs.
  - Environment: shared RexLit instance, possibly multi-user (future).
- **Senior attorney / partner**
  - Job: understand and defend methodology (Methods appendix, privilege policies, audit trail).
  - Interaction: occasional, but needs to grok the whole system in 2–3 screens.

The UI should be optimized for **associate + lit support**, while still making it easy to show a partner "how this thing works" in 2–3 screens.

---

## 4. Current State (as of v0.2.0-m1)

**Existing UI: Minimal MVP**

- Single React component (App.tsx, 761 lines)
- Two-pane layout: search results sidebar + document viewer with privilege review
- Plain CSS (no framework, no component library)
- Type-safe API client in `ui/src/api/rexlit.ts`
- Functional but generic aesthetic (blue SaaS default palette)

**Existing Features:**

- ✅ Search with full-text query
- ✅ Document preview (iframe, HTML-escaped plain text)
- ✅ Privilege review with stage indicators and confidence
- ✅ Pattern match visualization
- ✅ Policy editor (load/edit/save with diff view)
- ✅ Audit trail (basic, not yet prominent)
- ❌ No Bates stamping UI
- ❌ No production export workflow
- ❌ No deadline/rules UI
- ❌ No explicit offline/online mode indicator

**Why Redesign?**

The current UI works, but it looks generic. RexLit deserves a **distinctive visual identity** that:
- Communicates domain (litigation, not SaaS)
- Emphasizes trust and auditability
- Makes offline-first an obvious feature
- Distinguishes from competitors (Discovery Crunch, Kroll Ontrack, etc.)

---

## 5. Visual Identity: "Litigation Terminal"

### 5.1 Aesthetic Direction

**Theme:** "Litigation Terminal" — a modern terminal-like workbench for evidence.

**Principles:**

- **Purposeful, not pretty.** Design should look built for lawyers, not marketers.
- **High contrast and information density.** Users need to scan fast and trust the display.
- **Offline-first visual language.** Dark theme, muted network indicators, explicit mode switching.
- **Legally evocative typography.** Serif accents (headings), mono (hashes, cites, rules), distinctive grotesk (body).

**Color System (CSS Variables):**

```css
/* Backgrounds */
--bg-main:     #0f1117;    /* Near-black, like terminal */
--bg-surface:  #161b22;    /* Slightly lighter, for panels */
--bg-hover:    #21262d;    /* On interactive elements */
--bg-selected: #388bfd15;  /* Very subtle highlight (blue tint) */

/* Accents */
--accent-amber:   #d4a574;  /* Legally meaningful (Bates, deadlines, privilege labels) */
--accent-amber-dark: #8b6914;
--accent-cyan:    #58a6ff;  /* Active states, online mode, focus */
--accent-cyan-dark: #1f6feb;

/* Status Colors */
--status-privileged:  #d0bcff;  /* Purple for ACP, work product, etc. */
--status-responsive:  #79c0ff;  /* Blue for responsive documents */
--status-redacted:    #f0883e;  /* Orange for redacted/flagged */
--status-uncertain:   #ffd700;  /* Amber for "needs review" */
--danger:             #f85149;  /* Red, sparingly used */

/* Text */
--text-primary:      #e6edf3;  /* Body text */
--text-muted:        #8b949e;  /* Labels, metadata */
--text-faint:        #6e7681;  /* Disabled, secondary info */

/* Borders & Structure */
--border-subtle:     #30363d;
--border-muted:      #21262d;
```

### 5.2 Typography (Distinctive, Not Generic)

**Font Stack:**

- **Headings (all caps, legal feel):**
  - **Primary:** Crimson Text (serif, elegant legal feel)
  - Fallback: Georgia, serif
  - Use for: `<h1>`, `<h2>` (uppercase), section labels like "CORPUS", "PRIVILEGE REVIEW", "AUDIT LEDGER"

- **Body (primary font for descriptions, labels):**
  - **Primary:** IBM Plex Sans (not Inter/Roboto—more distinctive, better letterforms)
  - Fallback: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
  - Use for: descriptions, list items, panel text, settings

- **Mono (hashes, paths, rules, CLI commands):**
  - **Primary:** Fira Code (crisp, legible, true monospace)
  - Fallback: "IBM Plex Mono", monospace
  - Use for: SHA-256 hashes, file paths, rule cites, Bates numbers (when not styled as accent), CLI commands in Run bar

**Sizing & Weights:**

```
Headings (h1, h2):    1.25–1.5rem, weight 700, Crimson Text, uppercase
Subheadings (h3):     1rem, weight 600, IBM Plex Sans
Labels/Captions:      0.75–0.85rem, weight 600, uppercase, IBM Plex Sans
Body:                 0.95–1rem, weight 400, IBM Plex Sans
Mono (code/hashes):   0.85rem, weight 500, Fira Code
```

**Why this matters:** Crimson + IBM Plex + Fira Code is a *specific* combination that avoids the "AI default" convergence on Inter/Roboto. It reads as intentional and domain-appropriate.

### 5.3 Component Styling (High Level)

**Buttons & Interactive Elements**

- Default: `--bg-surface` + `--border-subtle` border, `--text-primary`.
- Hover: `--bg-hover`.
- Active/Focus: `--border-subtle` → `--accent-cyan` border (2px), or filled with `--accent-cyan-dark`.
- Danger (e.g., delete): `--danger` background, white text.

**Search & Input Fields**

- Background: `--bg-surface`.
- Border: `--border-subtle` (1px), focus → `--accent-cyan` (2px).
- Placeholder: `--text-faint`.

**Badges & Labels**

- Privilege: `--status-privileged` bg, dark text.
- Responsive: `--status-responsive` bg, dark text.
- Redacted: `--status-redacted` bg, dark text.
- Uncertain/Needs Review: `--status-uncertain` bg, dark text.

**Audit Trail & Code**

- Mono font (Fira Code) throughout.
- Hashes: inline `<code>` with `--bg-hover` and `--text-muted` (truncated, full on hover/click).
- Paths: styled as mono, muted.
- Rule cites (TX/FL deadlines): mono, maybe with amber accent if important.

---

## 6. Information Architecture & Layout

### 6.1 Global Chrome

All screens live inside a shared **Layout Shell** (`LayoutShell.tsx`):

**Left Navigation Rail (fixed, ~220px):**

- RexLit logo/wordmark at top.
- Navigation items:
  - 🔍 **Corpus** — Search & Review (default)
  - 📋 **Review** — Privilege decisions and escalations
  - 📦 **Productions** — Bates, DAT/Opticon exports
  - ⏰ **Deadlines** — TX/FL rules, ICS calendar
  - 🔐 **Audit** — Ledger, verification, event log
  - ⚙️ **Settings** — Configuration, policies, online mode
- Mode indicator at bottom:
  - 🔒 `OFFLINE` (green or standard) OR 🌐 `ONLINE` (cyan, pulse animation on load).
  - Shows `REXLIT_HOME` path (truncated, full path on hover).

**Top "Run Bar" (fixed, ~40px):**

- Shows current operation in CLI-equivalent form when applicable:
  - e.g. `$ rexlit index search "privileged" --limit 50` (during search)
  - e.g. `$ rexlit privilege classify 4fa2…e1` (during privilege review)
  - e.g. `$ rexlit audit verify` (in audit screen)
- **Right side of run bar:**
  - Status dot (green = ok, amber = processing, red = error).
  - Offline/Online mode toggle (if not read-only).
  - Quick access to logs or help.

**Main Workspace:**

- The active screen (Corpus, Review, etc.) fills the remaining space.
- Each screen has a similar structure: control bar → lists/panels → details.

### 6.2 Screen-Level Hierarchy

Each screen follows a hierarchy:

1. **Title + Context** (e.g., "CORPUS" with doc count, custodians).
2. **Primary Controls** (search, filters, sort).
3. **Dense List/Table** (documents, events, productions).
4. **Detail Panel** (right-side or bottom drawer, optional).

**Emphasis:**

- Document state (privileged, responsive, reviewed, redacted).
- Audit status (who, when, policy version, confidence).
- System state (offline/online, policy version).

---

## 7. CLI → UI Mapping

Every major UI surface is a faithful shell over a CLI command:

| CLI Command                      | UI Surface / Screen          | Notes |
|----------------------------------|-----------------------------|-------|
| `rexlit index search …`          | Corpus / Search & Review     | Main workflow |
| `rexlit privilege classify …`    | Review panel (embedded)      | Shows privilege decision |
| `rexlit privilege explain …`     | Review panel detail          | Show reasoning |
| `rexlit privilege policy list`   | Settings → Policies tab      | List stages 1–3 |
| `rexlit privilege policy get …`  | Settings → Policy Editor     | Show policy text |
| `rexlit privilege policy apply …`| Settings → Policy Save       | Apply policy changes |
| `rexlit audit show`              | Audit → Event Log            | Show recent events |
| `rexlit audit verify`            | Audit → Verify Chain         | Verify tamper-evident chain |
| `rexlit rules calc …`            | Deadlines → Calendar         | TX/FL deadline calculator |
| `rexlit produce create …`        | Productions → Export Wizard  | DAT/Opticon, Bates setup |
| `rexlit ingest …`               | Corpus → Ingest (future)     | Import documents |

**Design principle:** If a CLI command exists, there should be a UI surface for it (even if minimal for now).

---

## 8. Phased Implementation Plan

### Phase 1 — Structural Refactor (No Major Visual Changes)

**Goal:** Make the UI modular and ready for redesign, while keeping behavior identical.

**Tasks:**

- [ ] **Extract `LayoutShell.tsx`**
  - [ ] Create component that wraps existing content.
  - [ ] Left nav rail (placeholder styling, not fancy).
  - [ ] Top run bar (show placeholder "CLI" text).
  - [ ] Pass `children` to main workspace.

- [ ] **Extract `SearchPanel.tsx`**
  - [ ] Move search input, results list from `App.tsx`.
  - [ ] Accept `results` array, `selected`, `onSelect` as props.
  - [ ] Still use current styles (minimal change).

- [ ] **Extract `DocumentViewer.tsx`**
  - [ ] Move selected doc header + iframe + snippet.

- [ ] **Extract `PrivilegeReviewPanel.tsx`**
  - [ ] Move stage indicators, confidence, metrics, pattern matches.
  - [ ] Encapsulate decision buttons ("Privileged", "Not Privileged", "Skip").

- [ ] **Extract `PolicyEditor.tsx`**
  - [ ] Move policy stage selection, textarea, validation, save.

- [ ] **Extract `AuditPanel.tsx`** (basic)
  - [ ] Create simple component that fetches and lists audit events.
  - [ ] Integrate with API (use existing or create `GET /api/audit/events`).

- [ ] **Introduce CSS design tokens in `index.css`:**

  ```css
  :root {
    /* Colors (light theme for now, to match current) */
    --bg-main: #ffffff;
    --bg-surface: #f8fafc;
    --accent-primary: #2563eb;
    --text-primary: #0f172a;
    --text-muted: #475569;
    --border-subtle: #cbd5f5;
    
    /* Typography (distinctive choices) */
    --font-body: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --font-heading: "Crimson Text", Georgia, serif;
    --font-mono: "Fira Code", "IBM Plex Mono", monospace;
    
    /* Spacing */
    --spacing-xs: 0.25rem;
    --spacing-sm: 0.5rem;
    --spacing-md: 1rem;
    --spacing-lg: 1.5rem;
  }
  ```

  - [ ] Update existing components to reference tokens instead of hardcoded colors/sizes.

**Deliverable:**

- `App.tsx` is now small, routing to major components.
- Each component is in its own file, properly typed.
- All tokens defined; design is still the same, but CSS is refactored.
- All tests pass (if any).

---

### Phase 2 — Layout & Chrome Redesign

**Goal:** Give RexLit a recognizable **workbench layout** without fully applying new visual theme yet.

**Tasks:**

**LayoutShell & Navigation**

- [ ] Implement left nav rail in `LayoutShell.tsx`:
  - [ ] `<nav>` with items for: Corpus, Review, Productions, Deadlines, Audit, Settings.
  - [ ] Active state highlighting (e.g., underline or background).
  - [ ] Implement routing or state-based navigation (initially just state, no URL routing if not already present).

- [ ] Implement top "Run bar":
  - [ ] Show current operation (e.g., `$ rexlit index search "query"` during search).
  - [ ] Show Offline/Online mode indicator:
    - [ ] Bind to environment or API status (or stub with hardcoded "OFFLINE" for now).
    - [ ] Use icon or text label.
  - [ ] Show status dot (green/amber/red).

**Screen Navigation & Structure**

- [ ] Embed Search & Review flow under "Corpus" nav item.
- [ ] Create "Review" screen (initially empty or placeholder; can be filled later with more UI for privilege escalations).
- [ ] Create "Productions" screen (placeholder for now; Bates UI comes in Phase 3).
- [ ] Create "Deadlines" screen (placeholder for TX/FL rules).
- [ ] Create "Audit" screen:
  - [ ] Basic table/list of audit events (fetch from `GET /api/audit` or `rexlit audit show --json`).
  - [ ] Columns: Type, Timestamp, Summary, Hash (truncated).
- [ ] Create "Settings" screen:
  - [ ] Policy management (embed `PolicyEditor` or tab).
  - [ ] Configuration (stub for now).
  - [ ] Online mode toggle (if writable; otherwise read-only indicator).

**Responsive Layout**

- [ ] Ensure panels don't break on narrower screens (e.g., collapse nav to hamburger below ~1024px).
- [ ] Left nav should be sticky.
- [ ] Main content should scroll if needed.

**Interaction**

- [ ] Clicking nav item changes screen.
- [ ] Current screen is highlighted in nav.
- [ ] No page reload; React state/routing handles transitions.

**Deliverable:**

- Users see a **consistent layout** (left nav + top bar) across all screens.
- Can navigate between Search, Audit, Settings, etc.
- Behavior unchanged, but structure is clearer and more scalable.

---

### Phase 3 — Visual Identity & Interaction Polish

**Goal:** Apply the "Litigation Terminal" aesthetic and improve clarity.

**Tasks:**

**Color Theme Shift**

- [ ] Update CSS tokens to "Litigation Terminal" colors (see Section 5.1):
  - [ ] `--bg-main`, `--bg-surface`, `--accent-amber`, `--accent-cyan`, `--text-primary`, etc.
  - [ ] Apply to all components.

- [ ] Update existing components:
  - [ ] Buttons: use new color scheme.
  - [ ] Badges & status labels: use `--status-privileged`, `--status-responsive`, etc.
  - [ ] Borders: use `--border-subtle`.

**Typography Refinement**

- [ ] Set global font-family:
  - [ ] `--font-body` to IBM Plex Sans (distinctive, not generic).
  - [ ] `--font-heading` to Crimson Text (serif, legal feel).
  - [ ] `--font-mono` to Fira Code (programming mono, legible).

- [ ] Update headings:
  - [ ] `<h1>`, `<h2>` in uppercase, serif (Crimson), larger size.
  - [ ] Nav labels: uppercase, serif or bold IBM Plex.

**Search & Review Screen (Corpus)**

- [ ] Restyle search results:
  - [ ] Show more metadata (Bates number if available, date, custodian, type).
  - [ ] Use mono + amber for Bates numbers.
  - [ ] Row hover: subtle background shift to `--bg-hover`.
  - [ ] Selected row: cyan underline or left border (not generic blue highlight).

- [ ] Restyle document viewer:
  - [ ] Document title in serif, large.
  - [ ] File path in mono, muted.
  - [ ] Optional: subtle margin/border to evoke legal document.

- [ ] Restyle privilege review panel:
  - [ ] Clear section header (serif, uppercase): "PRIVILEGE REVIEW" or "STAGE 1: PRIVILEGE".
  - [ ] Status labels in colored badges (privileged = purple, responsive = cyan, etc.).
  - [ ] Confidence as a visual bar or large percentage number.
  - [ ] Pattern matches in a list with clear attribution.
  - [ ] Reasoning hash: mono, truncated, full on hover.
  - [ ] Decision buttons styled distinctly (Privileged = purple, Not Privileged = cyan, Skip = amber).

**Policy Management Screen (Settings)**

- [ ] Stage tabs (1, 2, 3) clearly labeled:
  - [ ] `STAGE 1: PRIVILEGE DETERMINATION`
  - [ ] `STAGE 2: RESPONSIVENESS`
  - [ ] `STAGE 3: REDACTION`
- [ ] Policy editor area:
  - [ ] Mono font, dark background (like code editor).
  - [ ] Syntax highlighting or clear rule parsing (if applicable).
  - [ ] Validation messages inline or in a sidebar.
  - [ ] Metadata (hash, version, modified time) styled as "system info" in mono, muted.

**Audit Ledger Screen (Audit)**

- [ ] Event list in a dense, scannable format:
  - [ ] Columns: Type, Timestamp, User (if available), Summary, Hash.
  - [ ] Icons or color-coded labels for event types (e.g., `ingest`, `privilege`, `audit.verify`).
  - [ ] Hashes in mono, truncated (e.g., `4fa2…a1c`), full on click/hover.
  - [ ] Row hover: subtle background highlight.
  - [ ] Click row to open detail drawer (expand in-line or modal):
    - [ ] Full hash, full event details, chain verification result (if applicable).

- [ ] Verification UI:
  - [ ] Button to run `rexlit audit verify`.
  - [ ] Show result: "✓ Chain is valid" (green) or "✗ Chain broken at event #42" (red).

**Interaction & Animation**

- [ ] Smooth transitions between screens (fade or slide).
- [ ] Search result rows stagger on load (small CSS animation).
- [ ] Hover states on interactive elements (color + underline or border shift).
- [ ] Mode indicator (Offline/Online) animates on change (pulse or icon animation).
- [ ] Loading states for async operations (spinner, progress bar, or skeleton).

**Deliverable:**

- RexLit now **looks and feels like a purpose-built litigation tool**, not a generic dashboard.
- Dark theme, amber/cyan accents, distinctive serif/sans/mono combination.
- All screens follow the same visual language.
- Offline/Online mode is prominent and clearly understood.
- Privilege decisions, audit events, and policies look trustworthy and defensible.

---

## 9. Beyond Phase 3 (Future Screens)

Once Phase 3 is done, these can be added with the established design language:

- **Productions Screen**: Bates numbering UI, export wizard, range verification.
- **Deadlines Screen**: TX/FL rules interactive calculator, ICS export.
- **Ingest Screen**: Document upload/discovery, manifest editor.
- **Case Management**: Custodian mgmt, document types, filtering rules.

---

## 10. Non-Goals (For This Iteration)

To keep scope manageable:

- ❌ Do not turn RexLit into a multi-tenant hosted SaaS.
- ❌ Do not replace the CLI as the primary interface for power users.
- ❌ Do not redesign all workflows from scratch; we're surfacing and clarifying, not reinventing.
- ❌ Do not aim for pixel-perfect mobile; desktop/laptop is the target.
- ❌ Do not add real-time collaboration (future, maybe).
- ❌ Do not build AI-powered "smart" features yet (compliance risk).

---

## 11. How to Use This Brief

- **As a checklist** for implementation (humans or AI agents). Copy tasks into issues or PR descriptions.
- **As a reference** when evaluating PRs that touch the UI.
- **As a guardrail** to keep the design aligned with RexLit's core philosophy:
  - Offline-first
  - Deterministic
  - Audit-heavy
  - Litigation-focused
  - Trustworthy

If a visual or interaction change doesn't support those principles, it probably doesn't belong in RexLit.

---

## 12. Design Assets & Starter Code

### Files to Create/Modify

**Phase 1:**
- [ ] `ui/src/components/LayoutShell.tsx` (new)
- [ ] `ui/src/components/SearchPanel.tsx` (new, extract from App.tsx)
- [ ] `ui/src/components/DocumentViewer.tsx` (new, extract from App.tsx)
- [ ] `ui/src/components/PrivilegeReviewPanel.tsx` (new, extract from App.tsx)
- [ ] `ui/src/components/PolicyEditor.tsx` (new, extract from App.tsx)
- [ ] `ui/src/components/AuditPanel.tsx` (new)
- [ ] `ui/src/index.css` (update with tokens)

**Phase 2:**
- [ ] `ui/src/components/LayoutShell.tsx` (enhance with nav rail and run bar)
- [ ] `ui/src/screens/Corpus.tsx` (new, Search & Review wrapper)
- [ ] `ui/src/screens/Review.tsx` (new, placeholder)
- [ ] `ui/src/screens/Productions.tsx` (new, placeholder)
- [ ] `ui/src/screens/Deadlines.tsx` (new, placeholder)
- [ ] `ui/src/screens/Audit.tsx` (new, audit screen with event list)
- [ ] `ui/src/screens/Settings.tsx` (new, policies + config)
- [ ] `ui/src/App.tsx` (simplify to routing + LayoutShell)

**Phase 3:**
- [ ] Update all component CSS files with new color tokens and typography.

---

## Appendix: Glossary of Key Terms

- **Privilege**: Confidential communication between attorney and client (or attorney work product). Exempt from discovery.
- **Responsiveness**: Whether a document is relevant to the case scope.
- **Bates Numbering**: Sequential document identifiers (e.g., "Smith-0001", "Smith-0002") used in productions.
- **DAT/Opticon**: Court-standard load file formats for discovery productions.
- **Rules Engine**: TX/FL civil procedure deadline calculator (statute of limitations, response deadlines, etc.).
- **Audit Trail**: Tamper-evident log of all system operations (ingest, privilege, export, etc.).
- **Offline-First**: No network calls by default; network operations are explicit and opt-in.
- **Deterministic**: Same inputs always produce identical outputs (critical for legal defense).

