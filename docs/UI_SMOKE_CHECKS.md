# UI Smoke Checks

Quick manual checks to confirm the Legal Archaeology UI serves fonts offline and handles document iframe errors gracefully.

## Offline font loading
- Start the dev server from `ui/`: `npm run dev` (or `bun run dev`), with fonts already downloaded via `scripts/download-fonts.sh`.
- In the browser devtools, set Network to **Offline** and hard-refresh the app. Ensure text renders with the expected typefaces (Newsreader, Manrope, JetBrains Mono) and no font downloads hit the network tab. The sources should point to `ui/src/assets/fonts/…` paths.
- Switch Network to **Fast 3G** and confirm there are no blocking requests to `fonts.googleapis.com` or `fonts.gstatic.com`; UI should stay legible without flashes of unstyled text.

## Document viewer error handling
- From the UI search, click a result whose file is missing or whose index entry is stale (or temporarily move one document out of place).
- The iframe should render the friendly “Document Not Available” panel instead of a blank page: red warning title, error reason, and the expandable “Common causes and fixes” list.
- Restore the file and confirm the iframe loads the document normally on refresh.
