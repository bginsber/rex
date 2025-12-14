# Installation Guide

This guide covers RexLit installation for development and production use.

## Prerequisites

- Python 3.11+ (3.12 also supported)
- pip or uv package manager
- Git

## Quick Install

```bash
# Clone the repository
git clone https://github.com/bginsber/rex.git
cd rex

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install with development dependencies
pip install -e '.[dev]'
```

## Verify Installation

```bash
# Check CLI is available
rexlit --version

# View available commands
rexlit --help

# Run test suite to verify environment
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -v --no-cov
```

## Alternative: Install with uv

[uv](https://github.com/astral-sh/uv) provides faster dependency resolution:

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync all dependencies including dev extras
uv sync --extra dev
```

## Optional Components

### OCR Support (Tesseract)

For document OCR functionality:

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Install Python bindings
pip install -e '.[ocr-tesseract]'

# Verify
tesseract --version
rexlit ocr run --help
```

### Dense/Hybrid Search (Kanon 2)

For semantic search capabilities (requires network):

```bash
# Set API key
export ISAACUS_API_KEY="your-key-here"

# Build with dense embeddings
rexlit --online index build ./docs --dense

# Search with hybrid mode
rexlit --online index search "query" --mode hybrid
```

### Web UI (Experimental)

```bash
# Install Bun (Node.js runtime)
curl -fsSL https://bun.sh/install | bash

# Start API server
cd api && bun install
REXLIT_HOME=$HOME/.local/share/rexlit bun run index.ts

# Start React UI (new terminal)
cd ui && bun install && bun dev
```

## Configuration

RexLit uses environment variables for configuration. See [FEATURE_FLAGS.md](FEATURE_FLAGS.md) for the complete reference.

Key settings:

```bash
# Data directory (indexes, manifests, audit logs)
export REXLIT_HOME=~/.local/share/rexlit

# Enable network features (default: disabled)
export REXLIT_ONLINE=1

# Parallel worker count (default: cpu_count - 1)
export REXLIT_WORKERS=4
```

## Troubleshooting

### "command not found: rexlit"

Activate your virtual environment:

```bash
source .venv/bin/activate
```

Or ensure the virtual environment's bin directory is in your PATH.

### Permission errors on REXLIT_HOME

Create the directory manually with correct permissions:

```bash
export REXLIT_HOME=~/.local/share/rexlit
mkdir -p $REXLIT_HOME
chmod 700 $REXLIT_HOME
```

### ImportError: No module named 'tantivy'

Reinstall with development dependencies:

```bash
pip install -e '.[dev]'
# or
uv sync --extra dev
```

### TesseractNotFoundError

Install the Tesseract binary for your platform:

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Verify installation
tesseract --version
```

### Tests fail with "No module named X"

Ensure all extras are installed:

```bash
pip install -e '.[dev,ocr-tesseract]'
# or
uv sync --extra dev --extra ocr-tesseract
```

### Audit verification fails

Check the audit log for integrity issues:

```bash
rexlit audit show --tail 20
rexlit audit verify
```

If tampered, regenerate from trusted manifests.

## Uninstall

```bash
# Remove virtual environment
rm -rf .venv

# Remove data directory (optional - deletes all indexes and audit logs)
rm -rf ~/.local/share/rexlit
```

## Next Steps

- [CLI-GUIDE.md](../CLI-GUIDE.md) - Complete command reference
- [FEATURE_FLAGS.md](FEATURE_FLAGS.md) - Environment variable reference
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System design overview
