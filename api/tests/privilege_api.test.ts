import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test } from 'bun:test'
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'

// Use same test home as index.test.ts to avoid module caching issues
const testHome = join(process.cwd(), '.tmp-rexlit-home')
Bun.env.REXLIT_HOME = testHome
Bun.env.REXLIT_BIN = 'rexlit'

const modPromise = import('../index')

let ensureWithinRoot: (path: string) => string
let resolveDocumentPath: (body: any) => Promise<string>
let runRexlit: (args: string[], options?: { timeoutMs?: number }) => Promise<unknown>
let setRunRexlitImplementation: (impl?: (...args: any[]) => Promise<unknown>) => void
let sanitizeErrorMessage: (message: string) => string
let createApp: () => any
let buildStageStatus: (decision: any) => any[]
let ALLOWED_REASONING_EFFORTS: Set<string>
let REXLIT_HOME: string
let ROOT_PREFIX: string
let CANONICAL_ROOT: string

beforeAll(async () => {
  const mod = await modPromise
  ensureWithinRoot = mod.ensureWithinRoot
  resolveDocumentPath = mod.resolveDocumentPath
  runRexlit = mod.runRexlit
  setRunRexlitImplementation = mod.__setRunRexlitImplementation
  sanitizeErrorMessage = mod.sanitizeErrorMessage
  createApp = mod.createApp
  buildStageStatus = mod.buildStageStatus
  ALLOWED_REASONING_EFFORTS = mod.ALLOWED_REASONING_EFFORTS
  REXLIT_HOME = mod.REXLIT_HOME
  ROOT_PREFIX = mod.ROOT_PREFIX
  CANONICAL_ROOT = mod.ROOT_PREFIX.slice(0, -1)
})

afterAll(() => {
  // Don't delete testHome since it's shared with other test files
  // It will be cleaned up by index.test.ts or manually
})

afterEach(() => {
  setRunRexlitImplementation()
  Bun.spawn = originalSpawn
})

const originalSpawn = Bun.spawn

function createFakeProcess({
  stdout = '',
  stderr = '',
  exitCode = 0,
  delayMs = 0,
  onKill
}: {
  stdout?: string
  stderr?: string
  exitCode?: number
  delayMs?: number
  onKill?: () => void
}) {
  let killed = false
  const encoder = new TextEncoder()
  const stdoutStream = new ReadableStream({
    start(controller) {
      setTimeout(() => {
        controller.enqueue(encoder.encode(stdout))
        controller.close()
      }, delayMs)
    }
  })
  const stderrStream = new ReadableStream({
    start(controller) {
      setTimeout(() => {
        controller.enqueue(encoder.encode(stderr))
        controller.close()
      }, delayMs)
    }
  })
  return {
    stdout: stdoutStream,
    stderr: stderrStream,
    exited: new Promise<number>((resolve) => {
      setTimeout(() => resolve(exitCode), delayMs)
    }),
    kill() {
      killed = true
      if (onKill) {
        onKill()
      }
    },
    get killed() {
      return killed
    }
  }
}

function createFile(relative: string, content = 'data') {
  const target = resolve(testHome, relative)
  mkdirSync(resolve(target, '..'), { recursive: true })
  writeFileSync(target, content)
  return target
}

describe('path traversal safeguards', () => {
  const safeCases = [
    { label: 'root path allowed', input: testHome },
    { label: 'nested path allowed', input: resolve(testHome, 'docs/file.txt') },
    { label: 'nested directory', input: resolve(testHome, 'nested/dir/document.txt') },
    { label: 'dot segments inside root', input: resolve(testHome, 'a/./b/../c.txt') },
    { label: 'trailing slash root', input: `${testHome}/` },
    { label: 'uppercase path', input: resolve(testHome, 'UPPER/case.doc') },
    { label: 'long nested path', input: resolve(testHome, 'a/b/c/d/e/f/g/h/i/j.txt') },
    { label: 'path with spaces', input: resolve(testHome, 'folder name/file.txt') },
    { label: 'path with unicode', input: resolve(testHome, '案例/檔案.txt') },
    { label: 'path with numbers', input: resolve(testHome, '123/456/789.txt') }
  ]

  safeCases.forEach((testCase, index) => {
    test(`allows safe path #${index + 1}: ${testCase.label}`, () => {
      const normalized = ensureWithinRoot(testCase.input)
      expect(
        normalized === CANONICAL_ROOT || normalized.startsWith(ROOT_PREFIX)
      ).toBe(true)
    })
  })

  const unsafeCases = [
    { label: 'absolute path outside root', input: '/etc/passwd' },
    { label: 'parent traversal escaping root', input: resolve(testHome, '../secret.txt') },
    { label: 'double parent traversal', input: resolve(testHome, '../../etc/shadow') },
    { label: 'relative parent traversal', input: '../evil.txt' },
    { label: 'windows style traversal', input: `${testHome}\\..\\..\\windows\\system32` },
    { label: 'mixed separators', input: `${testHome}/../outside` },
    { label: 'network path attempt', input: '//network/share/file.txt' },
    { label: 'empty path rejected', input: '' },
    { label: 'single dot path resolves outside', input: '.' },
    { label: 'relative root bypass', input: './../../../etc/passwd' }
  ]

  unsafeCases.forEach((testCase, index) => {
    test(`rejects unsafe path #${index + 1}: ${testCase.label}`, () => {
      expect(() => ensureWithinRoot(testCase.input)).toThrow('Path traversal detected')
    })
  })

  test('ensureWithinRoot normalizes dot segments within root', () => {
    const raw = `${testHome}/docs/../legal/./note.txt`
    const expected = ensureWithinRoot(resolve(testHome, 'legal/note.txt'))
    expect(ensureWithinRoot(raw)).toBe(expected)
  })

  test('resolveDocumentPath returns normalized absolute path for relative input', async () => {
    const relative = 'documents/email.txt'
    const file = createFile(relative)
    expect(await resolveDocumentPath({ path: relative })).toBe(ensureWithinRoot(file))
  })

  test('resolveDocumentPath trims whitespace paths', async () => {
    const relative = 'docs/trimmed.txt'
    const file = createFile(relative)
    expect(await resolveDocumentPath({ path: `  ${relative}  ` })).toBe(ensureWithinRoot(file))
  })

  test('resolveDocumentPath rejects empty path', async () => {
    await expect(resolveDocumentPath({ path: '   ' })).rejects.toThrow(
      'Either hash or path is required'
    )
  })

  test('resolveDocumentPath rejects non-string hash', async () => {
    await expect(resolveDocumentPath({ hash: 123 })).rejects.toThrow(
      'hash must be provided as a string'
    )
  })

  test('resolveDocumentPath rejects traversal from hash metadata', async () => {
    setRunRexlitImplementation(async (args: string[]) => {
      if (args[0] === 'index' && args[1] === 'get') {
        return { path: '/etc/passwd' }
      }
      return {}
    })
    await expect(resolveDocumentPath({ hash: 'abc' })).rejects.toThrow(
      'Path traversal detected'
    )
  })

  test('resolveDocumentPath resolves hash within root', async () => {
    const absolute = createFile('hash/safe.txt')
    setRunRexlitImplementation(async (args: string[]) => {
      if (args[0] === 'index' && args[1] === 'get') {
        return { path: absolute }
      }
      return {}
    })
    await expect(resolveDocumentPath({ hash: 'safe-hash' })).resolves.toBe(
      ensureWithinRoot(absolute)
    )
  })
})

describe('runRexlit timeout handling', () => {
  let killCount: number

  beforeEach(() => {
    killCount = 0
  })

  test('returns parsed JSON when process succeeds before timeout', async () => {
    Bun.spawn = () =>
      createFakeProcess({ stdout: JSON.stringify({ ok: true }), delayMs: 1 }) as any
    const result = await runRexlit(['privilege', 'classify', '--json'])
    expect(result).toEqual({ ok: true })
  })

  test('returns stdout string when not requesting JSON', async () => {
    Bun.spawn = () => createFakeProcess({ stdout: 'plain output', delayMs: 1 }) as any
    const result = await runRexlit(['privilege', 'classify'])
    expect(result).toBe('plain output')
  })

  test('throws error for non-zero exit codes', async () => {
    Bun.spawn = () =>
      createFakeProcess({ stderr: 'bad error', exitCode: 2, delayMs: 1 }) as any
    await expect(runRexlit(['privilege'])).rejects.toThrow('failed: bad error')
  })

  test('throws timeout error when process exceeds limit', async () => {
    Bun.spawn = () =>
      createFakeProcess({ stdout: '{}', delayMs: 50, onKill: () => killCount++ }) as any
    await expect(runRexlit(['slow'], { timeoutMs: 10 })).rejects.toThrow('timed out')
    expect(killCount).toBeGreaterThanOrEqual(1)
  })

  test('timeout message includes duration in seconds', async () => {
    Bun.spawn = () =>
      createFakeProcess({ stdout: '{}', delayMs: 2500, onKill: () => (killCount += 1) }) as any
    await expect(runRexlit(['slow'], { timeoutMs: 1500 })).rejects.toThrow('after 2s')
  })

  test('timeout uses unknown when duration not provided', async () => {
    Bun.spawn = () =>
      createFakeProcess({ stdout: '{}', delayMs: 1500, onKill: () => (killCount += 1) }) as any
    await expect(runRexlit(['slow'], { timeoutMs: 200 })).rejects.toThrow('unknown')
  })

  test('does not timeout when process finishes quickly', async () => {
    Bun.spawn = () => createFakeProcess({ stdout: '{}', delayMs: 1 }) as any
    await expect(runRexlit(['fast', '--json'], { timeoutMs: 1000 })).resolves.toEqual({})
  })

  test('clears timeout when process succeeds', async () => {
    Bun.spawn = () => createFakeProcess({ stdout: '{}', delayMs: 5 }) as any
    await expect(runRexlit(['fast', '--json'], { timeoutMs: 50 })).resolves.toEqual({})
  })

  test('propagates spawn errors directly', async () => {
    Bun.spawn = () => {
      throw new Error('spawn failed')
    }
    await expect(runRexlit(['oops'])).rejects.toThrow('spawn failed')
  })

  test('handles stderr text in timeout rejection path', async () => {
    Bun.spawn = () =>
      createFakeProcess({ stderr: 'error info', delayMs: 20, onKill: () => killCount++ }) as any
    await expect(runRexlit(['cmd'], { timeoutMs: 5 })).rejects.toThrow('timed out')
    expect(killCount).toBeGreaterThanOrEqual(1)
  })

  test('multiple sequential calls restore spawn implementation', async () => {
    Bun.spawn = () => createFakeProcess({ stdout: '{}', delayMs: 1 }) as any
    await runRexlit(['first'], { timeoutMs: 20 })
    Bun.spawn = () => createFakeProcess({ stdout: JSON.stringify({ ok: 2 }), delayMs: 1 }) as any
    await expect(runRexlit(['second', '--json'], { timeoutMs: 20 })).resolves.toEqual({ ok: 2 })
  })

  test('timeout error mentions command arguments', async () => {
    Bun.spawn = () => createFakeProcess({ stdout: '{}', delayMs: 50 }) as any
    await expect(runRexlit(['privilege', 'classify'], { timeoutMs: 5 })).rejects.toThrow(
      'rexlit privilege classify'
    )
  })

  test('non-json output returns trimmed string', async () => {
    Bun.spawn = () => createFakeProcess({ stdout: ' done ', delayMs: 1 }) as any
    const result = await runRexlit(['noop'])
    expect(result).toBe(' done ')
  })

  test('timeout still throws even if exit resolves quickly afterwards', async () => {
    Bun.spawn = () =>
      createFakeProcess({ stdout: '{}', delayMs: 20, onKill: () => killCount++ }) as any
    await expect(runRexlit(['slow'], { timeoutMs: 5 })).rejects.toThrow('timed out')
    expect(killCount).toBeGreaterThan(0)
  })

  test('timeout rounding rounds to nearest second', async () => {
    Bun.spawn = () =>
      createFakeProcess({ stdout: '{}', delayMs: 3000, onKill: () => (killCount += 1) }) as any
    await expect(runRexlit(['slow'], { timeoutMs: 1499 })).rejects.toThrow('after 1s')
  })

  test('does not kill process when it finishes before timeout', async () => {
    let killed = false
    Bun.spawn = () =>
      createFakeProcess({ stdout: '{}', delayMs: 5, onKill: () => (killed = true) }) as any
    await runRexlit(['fast'], { timeoutMs: 100 })
    expect(killed).toBe(false)
  })

  test('handles undefined timeout without triggering kill', async () => {
    Bun.spawn = () =>
      createFakeProcess({ stdout: '{}', delayMs: 20, onKill: () => (killCount += 1) }) as any
    await runRexlit(['fast'])
    expect(killCount).toBe(0)
  })
})

describe('input validation and API responses', () => {
  beforeEach(() => {
    setRunRexlitImplementation(async (args: string[]) => {
      if (args[0] === 'index' && args[1] === 'get') {
        return { path: createFile('api/input/valid.txt') }
      }
      if (args[0] === 'privilege' && args[1] === 'classify') {
        return { labels: ['PRIVILEGED'], needs_review: false }
      }
      if (args[0] === 'privilege' && args[1] === 'explain') {
        return { labels: ['PRIVILEGED'], reasoning_effort: 'high' }
      }
      return {}
    })
  })

  test('classify rejects missing body', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
    )
    expect(response.status).toBe(400)
    const data = await response.json()
    expect(data.error.message).toContain('Either hash or path is required')
  })

  test('classify rejects invalid threshold type', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt', threshold: 'nope' })
      })
    )
    expect(response.status).toBe(400)
    const data = await response.json()
    expect(data.error.message).toContain('threshold must be a number')
  })

  test('classify rejects non-string path inputs', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 42 })
      })
    )
    expect(response.status).toBe(400)
    const data = await response.json()
    expect(data.error.message).toContain('Either hash or path is required')
  })

  test('classify rejects threshold below zero', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt', threshold: -0.1 })
      })
    )
    expect(response.status).toBe(400)
  })

  test('classify rejects threshold above one', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt', threshold: 1.5 })
      })
    )
    expect(response.status).toBe(400)
  })

  test('classify rejects invalid reasoning effort', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt', reasoning_effort: 'extreme' })
      })
    )
    expect(response.status).toBe(400)
  })

  test('classify returns decision with valid payload', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt', threshold: 0.5 })
      })
    )
    expect(response.status).toBe(200)
    const data = await response.json()
    expect(data.decision.labels).toEqual(['PRIVILEGED'])
  })

  test('classify accepts uppercase reasoning effort values', async () => {
    const observed: string[][] = []
    setRunRexlitImplementation(async (args: string[]) => {
      observed.push(args)
      if (args[0] === 'index' && args[1] === 'get') {
        return { path: createFile('api/input/upper.txt') }
      }
      return { labels: [] }
    })
    const app = createApp()
    await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/upper.txt', reasoning_effort: 'HIGH' })
      })
    )
    const classifyArgs = observed.find((item) => item[0] === 'privilege')
    expect(classifyArgs?.includes('high')).toBe(true)
  })

  test('classify handles hash metadata missing path', async () => {
    setRunRexlitImplementation(async (args: string[]) => {
      if (args[0] === 'index' && args[1] === 'get') {
        return {}
      }
      return { labels: [] }
    })
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hash: 'missing' })
      })
    )
    expect(response.status).toBe(404)
  })

  test('classify rejects traversal path input', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: '../escape.txt' })
      })
    )
    expect(response.status).toBe(400)
  })

  test('explain returns decision payload', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt' })
      })
    )
    expect(response.status).toBe(200)
    const data = await response.json()
    expect(data.decision.reasoning_effort).toBe('high')
  })

  test('explain rejects missing body', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
    )
    expect(response.status).toBe(400)
  })

  test('explain returns 400 for invalid reasoning effort request', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt', reasoning_effort: 'invalid' })
      })
    )
    expect(response.status).toBe(400)
  })

  test('classify surfaces sanitized path traversal error', async () => {
    setRunRexlitImplementation(async () => {
      throw new Error(`${REXLIT_HOME}/secret/leak`)
    })
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt' })
      })
    )
    const data = await response.json()
    expect(data.error.message.includes('[REXLIT_HOME]')).toBe(true)
  })

  test('sanitizeErrorMessage scrubs external paths', () => {
    const message = '/tmp/secret/path'
    expect(sanitizeErrorMessage(message)).toBe('[path]')
  })

  test('buildStageStatus returns responsiveness stage skipped by default', () => {
    const stages = buildStageStatus({ labels: ['PRIVILEGED'] })
    expect(stages[1].status).toBe('skipped')
  })

  test('buildStageStatus marks redaction when spans present', () => {
    const stages = buildStageStatus({ redaction_spans: [{ start: 0, end: 1 }] })
    expect(stages[2].status).toBe('completed')
  })

  test('allowed reasoning efforts include medium', () => {
    expect(ALLOWED_REASONING_EFFORTS.has('medium')).toBe(true)
  })

  test('explain returns 404 when hash metadata missing path', async () => {
    setRunRexlitImplementation(async (args: string[]) => {
      if (args[0] === 'index' && args[1] === 'get') {
        return {}
      }
      return { labels: [] }
    })
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hash: 'missing' })
      })
    )
    expect(response.status).toBe(404)
  })

  test('explain rejects traversal through hash metadata', async () => {
    setRunRexlitImplementation(async (args: string[]) => {
      if (args[0] === 'index' && args[1] === 'get') {
        return { path: '/etc/shadow' }
      }
      return { labels: [] }
    })
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hash: 'bad' })
      })
    )
    expect(response.status).toBe(400)
  })

  test('document download rejects symlink that escapes root', async () => {
    const outsideDir = mkdtempSync(join(tmpdir(), 'rexlit-doc-outside-'))
    const outsideFile = join(outsideDir, 'secret.txt')
    writeFileSync(outsideFile, 'top secret')

    const linkPath = resolve(testHome, 'docs', 'outside-link.txt')
    mkdirSync(resolve(linkPath, '..'), { recursive: true })
    symlinkSync(outsideFile, linkPath)

    setRunRexlitImplementation(async (args: string[]) => {
      if (args[0] === 'index' && args[1] === 'get') {
        return { path: linkPath }
      }
      throw new Error('unexpected CLI invocation')
    })

    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/documents/leak/file')
    )

    expect(response.status).not.toBe(200)
    const payload = await response.json()
    expect(payload.error.message).toContain('Path traversal detected')
    rmSync(outsideDir, { recursive: true, force: true })
  })

  test('classify returns sanitized pattern matches', async () => {
    setRunRexlitImplementation(async (args: string[]) => {
      if (args[0] === 'privilege' && args[1] === 'classify') {
        return {
          labels: ['PRIVILEGED'],
          pattern_matches: [
            {
              rule: 'domain',
              confidence: 0.9,
              snippet: 'attorney.com',
              stage: 'pattern',
              file_path: '/etc/passwd'
            },
            {
              rule: 5,
              snippet: '/tmp/leak',
              directory: '/tmp'
            }
          ]
        }
      }
      if (args[0] === 'index' && args[1] === 'get') {
        return { path: createFile('api/input/valid2.txt') }
      }
      return {}
    })
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid2.txt' })
      })
    )
    const data = await response.json()
    expect(data.pattern_matches).toEqual([
      { rule: 'domain', confidence: 0.9, snippet: 'attorney.com', stage: 'pattern' }
    ])
  })

  test('classify drops snippet text that looks like filesystem paths', async () => {
    setRunRexlitImplementation(async (args: string[]) => {
      if (args[0] === 'privilege' && args[1] === 'classify') {
        return {
          labels: ['PRIVILEGED'],
          pattern_matches: [
            { rule: 'unsafe', snippet: '/tmp/secret', stage: 'pattern' }
          ]
        }
      }
      if (args[0] === 'index' && args[1] === 'get') {
        return { path: createFile('api/input/pathy.txt') }
      }
      return {}
    })
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/pathy.txt' })
      })
    )
    const data = await response.json()
    expect(data.pattern_matches).toHaveLength(1)
    expect(data.pattern_matches[0].rule).toBe('unsafe')
    expect(data.pattern_matches[0].stage).toBe('pattern')
    expect('snippet' in data.pattern_matches[0]).toBe(false)
  })

  test('classify returns 504 when runRexlit times out', async () => {
    setRunRexlitImplementation(async () => {
      throw new Error('timed out after 2s')
    })
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt' })
      })
    )
    expect(response.status).toBe(504)
  })

  test('explain returns 504 when runRexlit times out', async () => {
    setRunRexlitImplementation(async () => {
      throw new Error('timed out after 3s')
    })
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: 'api/input/valid.txt' })
      })
    )
    expect(response.status).toBe(504)
  })

  test('explain rejects non-string hash values', async () => {
    const app = createApp()
    const response = await app.handle(
      new Request('http://localhost/api/privilege/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hash: 12345 })
      })
    )
    expect(response.status).toBe(400)
    const data = await response.json()
    expect(data.error.message).toContain('hash must be provided as a string')
  })
})
