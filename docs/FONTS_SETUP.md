# RexLit Font Setup Guide

## Overview

RexLit uses three carefully selected Google Fonts for the web UI:

1. **Newsreader** (serif) - Editorial titles and headings
2. **Manrope** (sans-serif) - UI controls and body text
3. **JetBrains Mono** (monospace) - Bates numbers, audit IDs, code

This guide explains how to set up **self-hosted fonts** for offline-first operation.

## Current Status

✅ **CSS Configuration**: Fonts configured for self-hosting
❌ **Font Files**: Need to be downloaded (see below)

The app currently uses fallback fonts (Georgia, system sans-serif, Courier New) while waiting for font files.

## Font Requirements

### By Font

| Font | Weights | Size (WOFF2) | Purpose |
|------|---------|-------------|---------|
| Newsreader | 400, 500, 700 | ~50KB | Document titles, headings |
| Manrope | 400, 500, 600 | ~40KB | UI text, buttons, labels |
| JetBrains Mono | 400, 500 | ~40KB | Bates stamps, codes |
| **Total** | - | **~130KB** | |

## Setup Instructions

### Option 1: Automated Download (Recommended)

Run the provided script from the repo root:

```bash
bash scripts/download-fonts.sh
```

This script will:
1. Create font directories in `ui/src/assets/fonts/`
2. Download WOFF2 files from Google Fonts CDN
3. Organize files by font family
4. Verify downloaded files

**Duration**: ~10-30 seconds depending on connection speed

**Network Requirements**:
- Access to `fonts.googleapis.com`
- Outbound HTTPS (port 443)
- ~150KB data transfer

### Option 2: Manual Download

If the script fails, download fonts manually:

#### 1. Create Directory Structure
```bash
mkdir -p ui/src/assets/fonts/{newsreader,manrope,jetbrains-mono}
```

#### 2. Download Files

Visit each Google Fonts page and download WOFF2 files:

**Newsreader**:
- Page: https://fonts.google.com/specimen/Newsreader
- Weights needed: Regular (400), Medium (500), Bold (700)
- Files to download (or copy URLs):
  - `newsreader-[hash].woff2` for weight 400
  - `newsreader-[hash].woff2` for weight 500
  - `newsreader-[hash].woff2` for weight 700

**Manrope**:
- Page: https://fonts.google.com/specimen/Manrope
- Weights needed: Regular (400), Medium (500), SemiBold (600)
- Files to download:
  - `manrope-[hash].woff2` for weight 400
  - `manrope-[hash].woff2` for weight 500
  - `manrope-[hash].woff2` for weight 600

**JetBrains Mono**:
- Page: https://fonts.google.com/specimen/JetBrains+Mono
- Weights needed: Regular (400), Medium (500)
- Files to download:
  - `jetbrainsmono-[hash].woff2` for weight 400
  - `jetbrainsmono-[hash].woff2` for weight 500

#### 3. Organize Files

Place downloaded files in the appropriate directories:

```
ui/src/assets/fonts/
├── newsreader/
│   ├── newsreader-[hash1].woff2  (weight 400)
│   ├── newsreader-[hash2].woff2  (weight 500)
│   └── newsreader-[hash3].woff2  (weight 700)
├── manrope/
│   ├── manrope-[hash1].woff2     (weight 400)
│   ├── manrope-[hash2].woff2     (weight 500)
│   └── manrope-[hash3].woff2     (weight 600)
└── jetbrains-mono/
    ├── jetbrainsmono-[hash1].woff2  (weight 400)
    └── jetbrainsmono-[hash2].woff2  (weight 500)
```

The hashes in filenames vary (they're content hashes from Google). Just download the WOFF2 files and place them in the correct directories—the `@font-face` declarations in `ui/src/styles/fonts.css` will find them by directory.

## Verification

After placing font files, verify the setup:

### Check Files Exist
```bash
find ui/src/assets/fonts -type f -name "*.woff2" | wc -l
# Should output: 8 (3 Newsreader + 3 Manrope + 2 JetBrains Mono)

ls -lh ui/src/assets/fonts/*/
# Should show ~130KB total
```

### Test in Dev Server
```bash
cd ui
npm run dev  # or: bun dev
```

Then check:
1. **Network tab** in DevTools (F12)
   - You should see `.woff2` files loading from `http://localhost:5173/src/assets/fonts/`
   - NOT from `fonts.googleapis.com`

2. **Visual inspection**
   - Titles should display in serif (Newsreader)
   - UI labels should display in clean sans-serif (Manrope)
   - Bates numbers should be monospace (JetBrains Mono)

3. **Console errors**
   - No 404 errors for `.woff2` files
   - No font loading warnings

## Troubleshooting

### Fonts still loading from CDN

**Problem**: Network tab shows `fonts.googleapis.com` requests

**Solution**: Check that:
1. Font files exist: `ls ui/src/assets/fonts/*/`
2. CSS paths are correct: `grep "url\(" ui/src/styles/fonts.css`
3. Dev server is serving the `ui/src/` directory
4. Hard refresh browser cache: `Ctrl+Shift+R` or `Cmd+Shift+R`

### Font files download incorrectly

**Problem**: Files are 0 bytes or can't be opened

**Solution**:
1. Re-download manually from Google Fonts page
2. Verify file size: WOFF2 files should be 5-20KB each
3. Check downloads started (not blocked by firewall)

### Build fails after adding fonts

**Problem**: `npm run build` errors referencing missing fonts

**Solution**:
1. Fonts are optional for dev/test
2. If production build is required, ensure font files are present before build
3. Check Vite configuration in `vite.config.ts` includes assets directory

## Performance Impact

### Current (Fallback Fonts)
- ✓ App loads immediately
- ✗ Visual appearance differs from design
- ✗ Offline operation uses system fallbacks

### After Font Setup (Local WOFF2)
- ✓ App loads immediately (fonts from local server)
- ✓ Visual appearance matches design exactly
- ✓ Fonts available offline with no CDN dependency
- **Latency**: ~50ms (vs 350-1000ms with CDN)
- **Bundle**: +130KB (acceptable trade-off)

## Architecture

The font setup reflects RexLit's **offline-first philosophy** (ADR 0001):

```
Previous (CDN):
User → Browser → Google Fonts CDN → WOFF2 files
(350-1000ms latency, network required)

Now (Self-Hosted):
User → Browser → Local Dev Server → WOFF2 files
(~50ms latency, offline-capable)
```

## Files Modified

- `ui/src/styles/fonts.css` - Uncommented @font-face declarations, removed CDN imports
- `ui/src/assets/fonts/` - Directory structure created (8 WOFF2 files to be added)
- `scripts/download-fonts.sh` - Helper script for batch download

## Related Documentation

- `.claude/code-reviews/CODEBASE_QUICK_REFERENCE.md` - UI architecture
- `docs/UI_*.md` - Web UI design specifications
- `CLAUDE.md` - ADR 0001 (Offline-First Gate)

## Questions?

Refer to:
1. `scripts/download-fonts.sh` - Implementation details
2. `ui/src/styles/fonts.css` - CSS @font-face specifications
3. `ui/src/styles/tokens.css` - Design system tokens (fallback fonts)
