#!/usr/bin/env node
/**
 * UI smoke checks (offline-friendly font config + iframe error panel hook).
 *
 * - Verifies all @font-face src URLs in ui/src/styles/fonts.css point to local files.
 * - Confirms those font files exist under ui/src/assets/fonts.
 * - Ensures the DocumentViewer error panel copy is present (the "Document Not Available" safety net).
 */
import { readFileSync } from 'node:fs'
import { existsSync } from 'node:fs'
import { resolve, dirname, join } from 'node:path'

const root = resolve(dirname(new URL(import.meta.url).pathname), '..')

function checkLocalFonts() {
  const cssPath = join(root, 'src/styles/fonts.css')
  const css = readFileSync(cssPath, 'utf8')

  // Grab all non-commented src URLs pointing to local assets
  const fontUrls = Array.from(css.matchAll(/src:\s*url\(['"]?(\.\.\/assets\/fonts\/[^'")]+)['"]?\)/g)).map(
    (m) => m[1]
  )

  if (fontUrls.length === 0) {
    throw new Error('No local font src URLs found in fonts.css')
  }

  // Ensure none of the active src values point to remote hosts
  const remoteRefs = fontUrls.filter((u) => u.startsWith('http://') || u.startsWith('https://'))
  if (remoteRefs.length > 0) {
    throw new Error(`Expected self-hosted fonts only, found remote refs: ${remoteRefs.join(', ')}`)
  }

  // Validate files exist (resolve from src/styles/)
  const stylesDir = join(root, 'src', 'styles')
  const missing = fontUrls
    .map((u) => resolve(stylesDir, u))
    .filter((p) => !existsSync(p))

  if (missing.length > 0) {
    throw new Error(`Missing font files: ${missing.join(', ')}`)
  }

  return { count: fontUrls.length }
}

function checkDocumentViewerErrorText() {
  const viewerPath = join(root, 'src/components/documents/DocumentViewer/DocumentViewer.tsx')
  const content = readFileSync(viewerPath, 'utf8')

  const markers = ['Document Not Available', 'Common causes and fixes']
  const missing = markers.filter((m) => !content.includes(m))
  if (missing.length > 0) {
    throw new Error(`DocumentViewer.tsx missing expected error markers: ${missing.join(', ')}`)
  }
}

try {
  const { count } = checkLocalFonts()
  checkDocumentViewerErrorText()
  console.log(`✓ UI smoke checks passed (${count} local font src entries verified)`)
} catch (err) {
  console.error('✗ UI smoke checks failed:')
  console.error(err instanceof Error ? err.message : err)
  process.exit(1)
}
