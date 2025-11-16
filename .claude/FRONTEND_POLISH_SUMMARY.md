# Frontend Design Enhancement Summary
**Branch**: `ui/legal-archaeology-design-integration`
**Date**: November 15, 2024

## Overview
Enhanced the RexLit web UI with atmospheric effects and polish to match the "Legal Archaeology Command Center" design aesthetic. Fixed critical SHA-256 document lookup errors caused by REXLIT_HOME misconfiguration.

## Design Enhancements

### 1. Atmospheric Background Effects (`AppLayout.module.css`)
Added immersive command center atmosphere with:

- **Gradient Mesh Background**
  - Subtle amber glow at 20% 30% (legal authority accent)
  - Cyan glow at 80% 70% (technical/active states)
  - Ultra-low opacity (0.02-0.03) for subtlety

- **Noise Texture Overlay**
  - Repeating linear gradient creating fine scan lines
  - 4px spacing with amber tint
  - 30% opacity for depth without distraction

- **Animated Scanline**
  - Horizontal amber bar slowly scanning down the viewport
  - 8-second cycle
  - 10% opacity for subtlety
  - Creates living, active command center feel

### 2. Existing Design System (Already Implemented)
The branch already had excellent foundational design:

#### Color Palette
- **Dark Command Center Theme**
  - Primary: `#0a0e14` (very dark blue-black)
  - Secondary: `#1a1f29` (dark slate)
  - Tertiary: `#242b38` (medium slate)
  - Elevated: `#2d3548` (highest elevation)

- **Legal Authority Accents**
  - Amber: `#e8b76a` (privilege, citations, Bates numbers)
  - Cyan: `#4fc3f7` (active states, selections)
  - Red: `#ff6b6b` (privileged documents)
  - Green: `#51cf66` (production documents)

#### Typography
- **Newsreader** serif - Editorial gravitas for headings and document titles
- **Manrope** sans-serif - Modern, clean UI elements
- **JetBrains Mono** - Technical precision for Bates numbers and code

#### Component Polish
- **StatusBar**: Amber scanline effect, breathing glow on Bates numbers
- **NavRail**: Icon bounce on hover, amber glow on active state
- **DocumentCard**: Staggered fade-in animations, hover transforms
- **SearchPanel**: Cyan glow on focus, button press feedback
- **DocumentViewer**: Fade-in animations, empty state with floating icon

### 3. Animation Strategy
High-impact moments with intentional restraint:
- **Page load**: Staggered reveals (50ms delays) on document cards
- **Navigation**: Slide-in effects (StatusBar, NavRail)
- **Interactions**: Elastic scales, icon bounces, ripple effects
- **Ambient**: Breathing glows on privilege indicators, subtle scanlines
- **Accessibility**: Respects `prefers-reduced-motion`

## Bug Fixes

### SHA-256 Document Lookup Error
**Issue**: `No document found for SHA-256 96b331f0f550e1d2e6efb698040e0c77ebfe4ed7de332b297e64fad3376b0f7f`

**Root Cause**: REXLIT_HOME mismatch
- Search results came from index at `~/.local/share/rexlit`
- Document file retrieval attempted to use `api/.tmp-rexlit-home/`
- Temp directory had documents but NO index

**Fix**:
1. Removed `api/.tmp-rexlit-home/` directory
2. API now uses default `~/.local/share/rexlit` (388 documents indexed)
3. Created `api/REXLIT_HOME_SETUP.md` troubleshooting guide

**Verification**:
- Default REXLIT_HOME has functional index with 388 documents
- Metadata cache confirmed: custodians (benjaminginsberg), doctypes (pdf, text)
- Temp directory removed to prevent future confusion

## Deliverables

### Enhanced Files
1. `ui/src/components/layout/AppLayout/AppLayout.module.css`
   - Atmospheric gradient mesh background
   - Noise texture overlay
   - Animated scanline effect

### New Documentation
1. `api/REXLIT_HOME_SETUP.md`
   - Comprehensive REXLIT_HOME configuration guide
   - Troubleshooting for SHA-256 errors
   - Verification steps and testing procedures

### Removed
1. `api/.tmp-rexlit-home/` (temp testing directory)

## Design Philosophy

### Aesthetic: Legal Archaeology Command Center
**Tone**: Authoritative, technical, offline-capable
**Inspiration**: Legal discovery meets industrial UI, archival preservation with modern tooling

**Key Differentiators**:
- ❌ NOT generic AI aesthetics (no Inter, no purple gradients, no cookie-cutter components)
- ✅ Distinctive serif/sans pairing (Newsreader + Manrope)
- ✅ Amber/gold authority accents (legal citations, privilege)
- ✅ Atmospheric command center effects (subtle glows, scanlines)
- ✅ Industrial precision (monospace Bates numbers, sharp borders)

### Intentional Restraint
Maximalist design with minimalist execution:
- Ultra-low opacity backgrounds (2-3%) for atmosphere without distraction
- Staggered animations (50ms delays) create delight without overwhelming
- Ambient effects (scanlines, glows) run slow (4-8 second cycles)
- Hover states provide feedback without being jarring

### Accessibility
- High contrast text (WCAG AA compliant)
- Focus visible outlines (2px cyan)
- Keyboard navigation support
- `prefers-reduced-motion` support

## Testing Recommendations

### Frontend
```bash
# Start UI dev server
cd ui
npm install  # or bun install
npm run dev  # or bun dev
```

### API
```bash
# Verify REXLIT_HOME
echo $REXLIT_HOME  # Should be ~/.local/share/rexlit or custom path

# Check index exists
ls -la ~/.local/share/rexlit/index/
cat ~/.local/share/rexlit/index/.metadata_cache.json

# Start API
cd api
bun install
REXLIT_BIN=$(which rexlit) bun run dev
```

### End-to-End Test
1. Open UI: http://localhost:5173
2. Search for documents: "test" or "*"
3. Verify:
   - Staggered fade-in animations on document cards
   - Atmospheric background with subtle gradients
   - Slow scanline moving down the viewport
   - Clicking document shows preview (no SHA-256 errors)
   - Hover effects on nav items (icon bounce)
   - Breathing glow on Bates numbers

## Next Steps (Future Work)

### Performance
- [ ] Lazy load document previews (iframe on demand)
- [ ] Virtual scrolling for 10K+ document lists
- [ ] Service worker for offline UI caching

### Polish
- [ ] Add ripple effects on button clicks
- [ ] Implement custom cursor (crosshair?) for technical feel
- [ ] Add grain overlay texture (PNG with low opacity)
- [ ] Highlight matching search terms in document viewer

### Features
- [ ] Dark/light theme toggle (current is dark-only)
- [ ] Font size preferences for document viewer
- [ ] Keyboard shortcuts (Cmd+K for search, etc.)
- [ ] Drag-and-drop document upload for indexing

## References

### Design System
- Tokens: `ui/src/styles/tokens.css`
- Fonts: `ui/src/styles/fonts.css`
- Animations: `ui/src/styles/animations.css`
- Global: `ui/src/index.css`

### ADRs
- ADR 0001: Offline-First Gate
- ADR 0002: Ports/Adapters Import Contracts
- ADR 0009: CLI-as-API Pattern

### Documentation
- `CLAUDE.md` - Project overview and development guide
- `api/CLAUDE.md` - API-specific architecture and patterns
- `api/REXLIT_HOME_SETUP.md` - REXLIT_HOME configuration and troubleshooting
