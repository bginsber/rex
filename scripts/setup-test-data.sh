#!/bin/bash
# Setup script for RexLit test data submodule
# This script initializes and updates the test data submodule

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SAMPLE_DOCS_PATH="$REPO_ROOT/rexlit/docs/sample-docs"

echo "🔧 RexLit Test Data Setup"
echo "========================="
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Check if .gitmodules exists
if [ ! -f "$REPO_ROOT/.gitmodules" ]; then
    echo "❌ Error: .gitmodules not found. Are you in the RexLit repository root?"
    exit 1
fi

echo "📦 Initializing git submodules..."
git submodule update --init --recursive

if [ -d "$SAMPLE_DOCS_PATH" ] && [ -f "$SAMPLE_DOCS_PATH/README.md" ]; then
    echo ""
    echo "✅ Test data submodule initialized successfully!"
    echo ""
    echo "📁 Test data location: $SAMPLE_DOCS_PATH"
    echo ""
    
    # Count files
    FILE_COUNT=$(find "$SAMPLE_DOCS_PATH" -type f | wc -l | tr -d ' ')
    echo "📊 Files available: $FILE_COUNT"
    echo ""
    echo "💡 Usage examples:"
    echo "   rexlit ingest ./rexlit/docs/sample-docs --manifest out.jsonl"
    echo "   rexlit index build ./rexlit/docs/sample-docs"
    echo ""
else
    echo ""
    echo "⚠️  Warning: Test data directory not found at expected location"
    echo "   Expected: $SAMPLE_DOCS_PATH"
    echo ""
    echo "💡 Try running: git submodule update --init --recursive"
    exit 1
fi

