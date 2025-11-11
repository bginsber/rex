# Test Security Boundaries

This suite documents the automated coverage that protects the privilege review API against
path traversal, timeout handling, and malformed input. It complements the existing Python
integration tests by exercising the Bun-based HTTP wrapper directly.

## Test Layout

The Bun tests live in `api/tests/privilege_api.test.ts` and are grouped into three sections:

- **Path traversal safeguards (32 tests).** Verifies `ensureWithinRoot`, hash resolution, and
  the `/api/privilege/*` routes reject attempts to escape the RexLit home directory.
- **Timeout resilience (21 tests).** Exercises `runRexlit` across success, failure, and timeout
  paths to confirm timers fire, cleanup occurs, and errors carry expected messaging.
- **Input validation (15 tests).** Covers threshold, reasoning effort, and hash validation for
  the classify and explain endpoints, ensuring structured API responses for bad inputs.

Together these 68 assertions guard the security boundaries that reviewers rely on before
calling out to the CLI.

The suite also verifies that sanitized error payloads never leak absolute filesystem
paths even when the CLI returns unexpected content, ensuring API consumers only receive
generic `[path]` placeholders.

## Running the Suite

```bash
cd api
bun test
```

All tests run locally with Bun's built-in test runner—no network access is required. The
fake process helpers simulate `rexlit` output so the suite stays deterministic and fast.
