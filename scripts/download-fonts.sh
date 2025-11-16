#!/bin/bash
# ============================================
# RexLit Font Download Script
# Downloads WOFF2 fonts from Google Fonts
# Run this locally on your machine
# ============================================

set -e

FONTS_DIR="ui/src/assets/fonts"
echo "Creating font directories..."
mkdir -p "$FONTS_DIR/newsreader"
mkdir -p "$FONTS_DIR/manrope"
mkdir -p "$FONTS_DIR/jetbrains-mono"

# Function to download fonts from Google Fonts CSS
download_fonts() {
  local font_name=$1
  local font_spec=$2
  local target_dir=$3

  echo ""
  echo "Downloading $font_name fonts..."

  # Fetch the CSS from Google Fonts with proper User-Agent
  local css=$(curl -s -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
    "https://fonts.googleapis.com/css2?family=$font_spec&display=swap")

  # Extract WOFF2 URLs and download each one
  echo "$css" | grep -oP 'https://[^"]+\.woff2' | while read url; do
    # Extract filename from URL (format: NAME-HASH.woff2)
    filename=$(basename "$url")
    echo "  Downloading: $filename"
    curl -s "$url" -o "$target_dir/$filename"

    # Verify file was downloaded
    if [ -f "$target_dir/$filename" ]; then
      filesize=$(stat -f%z "$target_dir/$filename" 2>/dev/null || stat -c%s "$target_dir/$filename" 2>/dev/null)
      echo "    ✓ Downloaded ($filesize bytes)"
    else
      echo "    ✗ Failed to download!"
      exit 1
    fi
  done
}

# Download each font family
download_fonts "Newsreader" "Newsreader:wght@400;500;700" "$FONTS_DIR/newsreader"
download_fonts "Manrope" "Manrope:wght@400;500;600" "$FONTS_DIR/manrope"
download_fonts "JetBrains Mono" "JetBrains+Mono:wght@400;500" "$FONTS_DIR/jetbrains-mono"

echo ""
echo "✓ Font download complete!"
echo ""
echo "Next steps:"
echo "  1. Verify fonts are in place: ls -la $FONTS_DIR"
echo "  2. Uncomment @font-face blocks in ui/src/styles/fonts.css"
echo "  3. Comment out @import statements in ui/src/styles/fonts.css"
echo "  4. Run: npm run dev (or bun dev) to test"
echo ""
