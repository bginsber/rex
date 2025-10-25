# ADR 0002: Ports/Adapters & Import Contracts

**Status:** Accepted

**Date:** 2025-10-24

**Decision Makers:** Engineering Team

---

## Context

As RexLit grows, we risk creating a tangled architecture where:
- CLI directly imports domain logic and adapters
- Domain modules depend on CLI or specific adapters
- Testing requires mocking filesystem, network, and external libraries
- Swapping implementations (e.g., Tesseract → PaddleOCR) requires changes across codebase

We need clean architectural boundaries that:
- Decouple application logic from I/O
- Enable easy testing with mock implementations
- Support pluggable adapters
- Prevent circular dependencies

## Decision

**We adopt Ports and Adapters (Hexagonal) Architecture with enforced import rules:**

### Architecture Layers

```
┌─────────────────────────────────────────────────┐
│                 CLI Layer                        │
│          (rexlit/cli.py)                        │
│   Depends on: app, bootstrap                    │
│   Forbidden: audit, ingest, index, pdf, etc.    │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│              Application Layer                   │
│        (rexlit/app/*.py)                        │
│   Orchestrates workflows, no direct I/O         │
│   Depends on: ports only                        │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│               Port Interfaces                    │
│         (rexlit/app/ports/*.py)                 │
│   Protocol definitions (LedgerPort, OCRPort)    │
│   No dependencies on implementations            │
└─────────────────────────────────────────────────┘
                      ↑
        ┌──────────────┴──────────────┐
        ↓                              ↓
┌──────────────┐              ┌──────────────┐
│   Adapters   │              │   Domain     │
│  (concrete)  │              │   Modules    │
│              │              │              │
│ audit/ledger │              │ ingest/      │
│ ocr/tesseract│              │ index/       │
│ pdf/stamper  │              │ rules/       │
└──────────────┘              └──────────────┘
```

### Import Rules (Enforced by importlinter)

1. **CLI → App Only**
   - CLI may import `rexlit.app` and `rexlit.bootstrap`
   - CLI cannot import domain modules or adapters

2. **Domain → No CLI**
   - Domain packages cannot import CLI
   - Prevents circular dependencies

3. **App → Ports Only**
   - Application services depend on port interfaces
   - Never import concrete adapters

### Implementation

```python
# Port interface
class LedgerPort(Protocol):
    def log(self, operation: str, inputs: list[str], ...) -> None: ...

# Adapter (concrete implementation)
class AuditLedger:
    def log(self, operation: str, inputs: list[str], ...) -> None:
        # Write to JSONL file
        ...

# Application service (depends on port)
class M1Pipeline:
    def __init__(self, ledger_port: LedgerPort, ...):
        self.ledger = ledger_port

# Bootstrap wires concrete adapters
def create_container(settings: Settings) -> Container:
    container.ledger_port = AuditLedger(settings.get_audit_path())
    return container
```

## Consequences

### Positive

- **Testability:** Easy to inject mock ports for testing
- **Flexibility:** Swap adapters without changing app logic
- **Clarity:** Clear architectural boundaries
- **Enforcement:** importlinter prevents violations
- **Parallelization:** Teams can work on adapters independently

### Negative

- **Boilerplate:** Port definitions + adapters + bootstrap wiring
- **Learning Curve:** Developers must understand ports/adapters pattern
- **Indirection:** More layers to navigate

### Mitigation

- **Documentation:** ADR and architecture docs explain pattern
- **Examples:** Bootstrap module shows wiring
- **CI Checks:** importlinter runs on every commit

## Alternatives Considered

### 1. Direct Dependencies

**Rejected:** Creates tight coupling, hard to test, difficult to swap implementations.

### 2. Dependency Injection Framework

**Rejected:** Over-engineering for Python. Simple bootstrap module sufficient.

### 3. Service Locator Pattern

**Rejected:** Hidden dependencies, harder to test, "magic" lookups.

## Validation

```bash
# Verify import rules
importlinter lint

# Expected output:
# ✓ CLI depends only on app and bootstrap
# ✓ Domain packages cannot import CLI
# ✓ Application layer depends only on ports
```

## References

- Hexagonal Architecture (Alistair Cockburn)
- Clean Architecture (Robert C. Martin)
- Related: ADR 0001 (Offline-First Gate)

---

**Last Updated:** 2025-10-24
