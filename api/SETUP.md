# API Test Setup Guide

## Quick Start

1. **Install Bun** (if not already installed):
   ```bash
   curl -fsSL https://bun.sh/install | bash
   ```

2. **Install dependencies:**
   ```bash
   cd api
   bun install
   ```

3. **Run tests:**
   ```bash
   bun test index.test.ts
   ```

## Installing Bun

### macOS

**Option 1: Official installer (recommended)**
```bash
curl -fsSL https://bun.sh/install | bash
```

**Option 2: Homebrew**
```bash
brew install bun
```

**Option 3: npm**
```bash
npm install -g bun
```

### Linux

```bash
curl -fsSL https://bun.sh/install | bash
```

### Windows

Bun supports Windows via WSL. Install WSL first, then:
```bash
curl -fsSL https://bun.sh/install | bash
```

## Verifying Installation

```bash
bun --version
# Should output: bun 1.x.x
```

## Troubleshooting

### "command not found: bun"

After installing, you may need to:
1. Restart your terminal
2. Add Bun to your PATH:
   ```bash
   export PATH="$HOME/.bun/bin:$PATH"
   ```
   Add this to your `~/.zshrc` or `~/.bashrc` for persistence

### "Permission denied"

If you get permission errors:
```bash
chmod +x ~/.bun/bin/bun
```

### Alternative: Use Node.js with Vitest

If you can't install Bun, you can adapt the tests to use Node.js + Vitest:

1. Install dependencies:
   ```bash
   npm install -D vitest @types/node
   ```

2. Update `index.test.ts` imports:
   ```typescript
   import { describe, it, expect, beforeEach, vi } from 'vitest'
   ```

3. Run with:
   ```bash
   npx vitest index.test.ts
   ```

However, note that the actual API code (`index.ts`) requires Bun runtime, so you'll need Bun to run the API server itself.

## Running Specific Test Suites

```bash
# Run all tests
bun test index.test.ts

# Run only path traversal tests
bun test index.test.ts -t "Path Traversal"

# Run only timeout tests
bun test index.test.ts -t "Timeout"

# Run with verbose output
bun test index.test.ts --verbose
```

## CI/CD Integration

For GitHub Actions, add this to your workflow:

```yaml
- name: Setup Bun
  uses: oven-sh/setup-bun@v1
  with:
    bun-version: latest

- name: Install dependencies
  run: cd api && bun install

- name: Run tests
  run: cd api && bun test index.test.ts
```

