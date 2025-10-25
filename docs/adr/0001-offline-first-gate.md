# ADR 0001: Offline-First Gate

**Status:** Accepted

**Date:** 2025-10-24

**Decision Makers:** Engineering Team

---

## Context

RexLit is designed for legal e-discovery workflows where:
- Network access may be restricted or prohibited in secure environments
- Legal defensibility requires deterministic, auditable processing
- Most operations (document processing, indexing, redaction) don't require internet access
- Some features (case law lookup, online OCR) legitimately need network access

We need a clear policy for when network access is allowed and how to enforce it.

## Decision

**We adopt an offline-first architecture with explicit online mode opt-in:**

1. **Default Behavior:** All operations run offline by default
2. **Explicit Opt-In:** Network-requiring features need `--online` flag or `REXLIT_ONLINE=1` env var
3. **Early Validation:** Features check online status before execution and fail fast with clear messaging
4. **Port Segregation:** Port interfaces declare offline/online via `is_online()` method
5. **Audit Logging:** All online operations logged to audit trail with network activity details

### Implementation

```python
class OCRPort(Protocol):
    def is_online(self) -> bool:
        """Check if this adapter requires online access."""
        ...

# In CLI
def require_online(settings: Settings, online_flag: bool, feature_name: str) -> None:
    """Check if online mode is enabled, exit if not."""
    is_online = settings.online or bool(os.getenv("REXLIT_ONLINE")) or online_flag
    if not is_online:
        typer.secho(
            f"\n{feature_name} requires online mode.\n"
            f"Enable with: --online flag or REXLIT_ONLINE=1\n"
            f"Aborting.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=2)
```

## Consequences

### Positive

- **Security:** Prevents accidental network access in secure environments
- **Determinism:** Offline operations produce reproducible outputs
- **User Control:** Explicit consent required for network operations
- **Auditability:** Clear record of all network activity
- **Testing:** Easy to test offline behavior without mocking network

### Negative

- **UX Friction:** Users must explicitly enable online features
- **Discovery:** Users may not know online features exist
- **Documentation:** Need clear docs on which features require online mode

### Mitigation

- **Clear Messaging:** Informative error messages explain how to enable online mode
- **Documentation:** Prominent docs section on offline vs online features
- **Help Text:** CLI help mentions online requirements

## Alternatives Considered

### 1. Online by Default

**Rejected:** Contradicts legal e-discovery requirements for air-gapped processing. Creates risk of accidental data exfiltration.

### 2. No Online Features

**Rejected:** Legitimate use cases exist (case law lookup, cloud OCR for non-sensitive documents). Overly restrictive.

### 3. Per-Feature Flags

**Rejected:** Too granular, creates UX complexity. Single `--online` flag is simpler.

## References

- FRCP Rule 26 (e-discovery requirements)
- NIST SP 800-53 (security controls for federal information systems)
- Related: ADR 0003 (Determinism Policy)

---

**Last Updated:** 2025-10-24
