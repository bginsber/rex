# PII & Privilege Detection — Detailed Notes

This document collects implementation details referenced by:
- `PII_PRIVILEGE_INTEGRATION_SUMMARY.md` (executive summary)
- `Next_plan.md` (work breakdown and acceptance criteria)

Principles:
- Offline-first by default; one-time model downloads are opt-in and documented.
- Hexagonal architecture via explicit ports and adapters.
- Reuse existing extraction in `rexlit/ingest/extract.py` to avoid new I/O ports.

Port interfaces (sketch):

```python
# rexlit/app/ports/pii_detector.py
from typing import Protocol
from pydantic import BaseModel

class PIIEntity(BaseModel):
    entity_type: str
    start: int
    end: int
    score: float
    text: str

class PIIDetectorPort(Protocol):
    def detect(self, text: str, *, entities: list[str] | None = None) -> list[PIIEntity]: ...
    def supported_entities(self) -> list[str]: ...
    def is_online(self) -> bool: ...  # Always False
```

```python
# rexlit/app/ports/privilege_detector.py
from typing import Protocol
from pydantic import BaseModel

class PrivilegeMatch(BaseModel):
    start: int
    end: int
    score: float
    method: str
    trigger: str

class PrivilegeDetectorPort(Protocol):
    def detect(self, text: str, *, threshold: float = 0.75) -> list[PrivilegeMatch]: ...
    def is_online(self) -> bool: ...  # Always False
```

Text extraction reuse:

```python
from pathlib import Path
from rexlit.ingest.extract import extract_document

def extract_text(path: Path) -> str:
    return extract_document(path).text
```

CLI shape (consistent with other Typer groups):

```python
redact_app = typer.Typer(help="Redaction planning and application")
app.add_typer(redact_app, name="redact")
```

Testing guidance:
- Mock heavy deps (`AnalyzerEngine`, `SentenceTransformer`).
- Use fixtures under `tests/data/` for sample PDFs and emails.
- Keep tests offline; skip only if spaCy model is missing for integration tests.

Security:
- Never log raw PII or matched text in audit entries.
- Plans remain encrypted (Fernet key from `Settings`).

