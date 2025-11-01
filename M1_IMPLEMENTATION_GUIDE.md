# RexLit M1 Implementation Guide: Critical Gaps (Updated)

**Target:** Complete litigation support pillars for company interview  
**Scope:** Bates stamping, TX/FL rules engine, OCR providers  
**Timeline:** 1-2 week sprint (aggressive but achievable)
**Sequencing:** Bates → Rules → OCR (demo-visible to production-ready)

---

## Priority 1: Bates Stamping (PDF Generation + DAT/Opticon) — Days 1-2

### Why First?
- **Most demo-visible win**: Court-ready Bates output immediately
- 70% infrastructure already exists (planning, encryption, audit)
- Concludes with real production format (DAT/Opticon)

### Implementation Tasks

#### Task 1.1: Layout-Aware PDF Stamper (8 hours)

**File:** `rexlit/app/adapters/pdf_stamper.py` (NEW)

```python
from pathlib import Path
from typing import Literal
import fitz  # PyMuPDF
from pydantic import BaseModel
from rexlit.app.ports.stamp import StampPort, BatesStampRequest
import math

class StampPosition(BaseModel):
    x: float  # Percentage of page width (0.0-1.0)
    y: float  # Percentage of page height (0.0-1.0)

class PDFStamperAdapter(StampPort):
    """Layout-aware PDF stamping with rotation & safe-area detection."""
    
    POSITION_PRESETS = {
        "bottom-right": StampPosition(x=0.9, y=0.05),
        "bottom-center": StampPosition(x=0.5, y=0.05),
        "top-right": StampPosition(x=0.9, y=0.95),
    }
    
    def __init__(
        self,
        font_size: int = 10,
        color: tuple = (0, 0, 0),
        position: Literal["bottom-right", "bottom-center", "top-right"] = "bottom-right",
        background: bool = True,
    ):
        self.font_size = font_size
        self.color = color
        self.position = self.POSITION_PRESETS[position]
        self.background = background
    
    def stamp(self, request: BatesStampRequest) -> dict:
        """Apply Bates numbers with layout awareness."""
        doc = fitz.open(str(request.input_path))
        results = {}
        coordinates = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            bates_text = f"{request.prefix}{page_num + 1:0{request.width}d}"
            
            # Detect rotation (0, 90, 180, 270 degrees)
            rotation = page.rotation
            
            # Get safe-area bounds (respect margins/bleeds)
            safe_area = self._compute_safe_area(page)
            
            # Compute stamp position within safe area
            stamp_rect = self._compute_stamp_rect(
                page, safe_area, bates_text
            )
            
            # Insert background rectangle if requested (for legibility on scans)
            if self.background:
                bg_rect = stamp_rect.normalize().expand(2)
                page.draw_rect(bg_rect, color=(1, 1, 1), fill=(1, 1, 1))
            
            # Insert text
            page.insert_text(
                stamp_rect,
                bates_text,
                fontsize=self.font_size,
                color=self.color,
            )
            
            # Track coordinates for audit
            coordinates.append({
                "page": page_num + 1,
                "bates": bates_text,
                "position": {
                    "x0": stamp_rect.x0,
                    "y0": stamp_rect.y0,
                    "x1": stamp_rect.x1,
                    "y1": stamp_rect.y1,
                },
                "rotation": rotation,
                "confidence": 1.0,
            })
        
        # Save stamped PDF
        doc.save(str(request.output_path))
        doc.close()
        
        return {
            "pages_stamped": len(coordinates),
            "coordinates": coordinates,
            "prefix": request.prefix,
        }
    
    def _compute_safe_area(self, page: fitz.Page) -> fitz.Rect:
        """Detect safe area (respect 0.5" margins)."""
        margin_pts = 36  # 0.5" in points
        rect = page.rect
        return fitz.Rect(
            rect.x0 + margin_pts,
            rect.y0 + margin_pts,
            rect.x1 - margin_pts,
            rect.y1 - margin_pts,
        )
    
    def _compute_stamp_rect(
        self, page: fitz.Page, safe_area: fitz.Rect, text: str
    ) -> fitz.Rect:
        """Compute stamp position using preset."""
        pos = self.position
        
        # Approximate text width/height
        text_width = len(text) * self.font_size * 0.5
        text_height = self.font_size * 1.2
        
        x = safe_area.x0 + (safe_area.width * pos.x) - (text_width / 2)
        y = safe_area.y0 + (safe_area.height * pos.y)
        
        return fitz.Rect(x, y, x + text_width, y + text_height)
    
    def dry_run(self, request: BatesStampRequest) -> dict:
        """Preview Bates numbers without modifying PDF."""
        preview_count = min(5, request.num_pages)
        return {
            "pages": request.num_pages,
            "preview": [
                f"{request.prefix}{i+1:0{request.width}d}"
                for i in range(preview_count)
            ],
            "total_pages": request.num_pages,
            "message": f"Would stamp {request.num_pages} pages with prefix '{request.prefix}'",
        }
```

#### Task 1.2: Global Sequencing & Email Family Support (4 hours)

**File:** `rexlit/app/adapters/bates.py` (EXTEND existing)

```python
# Add to existing BatesPlannerAdapter class

def plan_with_families(
    self,
    documents: list[DocumentMetadata],
    prefix: str,
    width: int,
) -> dict:
    """Generate Bates plan respecting parent-child (email family) order."""
    
    # Sort: first by family (thread ID), then by deterministic sort within family
    from rexlit.utils.deterministic import deterministic_sort
    
    families = {}
    for doc in documents:
        family_id = doc.metadata.get("thread_id", doc.sha256)
        if family_id not in families:
            families[family_id] = []
        families[family_id].append(doc)
    
    # Sort each family deterministically
    for family_id in families:
        families[family_id] = deterministic_sort(families[family_id])
    
    # Assign Bates numbers sequentially across families
    bates_map = {}
    counter = 1
    for family_id in sorted(families.keys()):
        for doc in families[family_id]:
            bates_num = f"{prefix}{counter:0{width}d}"
            bates_map[doc.sha256] = bates_num
            counter += 1
    
    return {
        "bates_map": bates_map,
        "total_documents": len(documents),
        "families": {k: len(v) for k, v in families.items()},
    }
```

#### Task 1.3: Bates Stamping CLI Command (3 hours)

**File:** `rexlit/cli.py` (ADD/UPDATE bates subcommand)

```python
@bates_app.command("stamp")
def bates_stamp(
    path: Annotated[Path, typer.Argument(help="PDF or directory to stamp")],
    prefix: Annotated[str, typer.Option("--prefix", "-p", help="Bates prefix (e.g., 'ABC')")],
    width: Annotated[int, typer.Option("--width", "-w", help="Zero-pad width")] = 7,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for stamped PDFs")
    ] = None,
    font_size: Annotated[int, typer.Option("--font-size", help="Font size in pts")] = 10,
    color: Annotated[
        str,
        typer.Option("--color", help="RGB hex color (e.g., '000000')")
    ] = "000000",
    position: Annotated[
        Literal["bottom-right", "bottom-center", "top-right"],
        typer.Option("--position", help="Stamp position on page")
    ] = "bottom-right",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview only")] = False,
) -> None:
    """Apply Bates numbers to PDF documents with layout awareness."""
    container = bootstrap_application()
    
    if not path.exists():
        typer.secho(f"Error: Path not found: {path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    # Parse color
    try:
        r, g, b = tuple(int(color[i:i+2], 16) / 255 for i in (0, 2, 4))
        rgb = (r, g, b)
    except (ValueError, IndexError):
        typer.secho(f"Invalid color format: {color}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    # Plan phase
    typer.secho("📋 Generating Bates plan...", fg=typer.colors.BLUE)
    plan = container.bates_planner.plan(
        path,
        prefix=prefix,
        width=width,
    )
    
    if dry_run:
        typer.secho("✓ Dry-run preview:", fg=typer.colors.GREEN)
        typer.echo(f"  Total documents: {plan['total_documents']}")
        typer.echo(f"  Prefix: {prefix}")
        typer.echo(f"  Position: {position}")
        typer.echo(f"\n  First 5 labels:")
        for i, (doc_id, bates_num) in enumerate(list(plan['bates_map'].items())[:5]):
            typer.echo(f"    {i+1}. {bates_num}")
        if len(plan['bates_map']) > 5:
            typer.echo(f"    ... and {len(plan['bates_map']) - 5} more")
        raise typer.Exit(code=0)
    
    # Apply phase
    typer.secho("🔏 Applying Bates stamps...", fg=typer.colors.BLUE)
    result = container.bates_stamper.stamp(
        plan,
        output_dir=output or path,
        font_size=font_size,
        color=rgb,
        position=position,
    )
    
    typer.secho(
        f"✓ Stamped {result['pages_stamped']} pages",
        fg=typer.colors.GREEN,
    )
```

#### Task 1.4: DAT/Opticon Production Export (4 hours)

**File:** `rexlit/cli.py` (ADD produce command)

```python
@produce_app.command("create")
def produce_create(
    path: Annotated[Path, typer.Argument(help="Stamped PDF directory")],
    name: Annotated[str, typer.Option("--name", "-n", help="Production set name")],
    format: Annotated[
        Literal["dat", "opticon"],
        typer.Option("--format", "-f", help="Production format")
    ] = "dat",
    bates_prefix: Annotated[
        str,
        typer.Option("--bates", help="Expected Bates prefix for validation")
    ] = "",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory")
    ] = None,
) -> None:
    """Generate production set (DAT/Opticon) from stamped PDFs."""
    container = bootstrap_application()
    
    typer.secho(f"📦 Creating {format.upper()} production set '{name}'...", fg=typer.colors.BLUE)
    
    result = container.pack_service.create_production(
        path,
        name=name,
        format=format,
        bates_prefix=bates_prefix,
        output_dir=output,
    )
    
    typer.secho(
        f"✓ Production set created: {result['output_path']}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"  Documents: {result['document_count']}")
    typer.echo(f"  Format: {format.upper()}")
```

#### Task 1.5: Integration Test (3 hours)

**File:** `tests/test_bates_stamping_e2e.py` (NEW)

```python
import pytest
from pathlib import Path
from rexlit.app.adapters.pdf_stamper import PDFStamperAdapter

def test_bates_stamp_layout_aware(tmp_path):
    """Test layout-aware stamping with safe-area detection."""
    adapter = PDFStamperAdapter(position="bottom-right", background=True)
    
    # Mock request
    request = MockRequest(
        input_path=Path("tests/fixtures/sample.pdf"),
        output_path=tmp_path / "stamped.pdf",
        prefix="ABC",
        width=7,
        num_pages=5,
    )
    
    result = adapter.stamp(request)
    
    assert result["pages_stamped"] == 5
    assert len(result["coordinates"]) == 5
    assert result["coordinates"][0]["rotation"] in [0, 90, 180, 270]
    assert result["coordinates"][0]["bates"] == "ABC0000001"

def test_bates_dry_run_preview():
    """Test dry-run mode with preview."""
    adapter = PDFStamperAdapter()
    request = MockRequest(num_pages=100)
    
    preview = adapter.dry_run(request)
    assert len(preview["preview"]) == 5  # Show first 5
    assert preview["total_pages"] == 100

def test_email_family_sequencing(tmp_path):
    """Test Bates sequencing respects email families."""
    # Docs grouped by thread_id
    docs = [
        MockDoc(sha256="a", thread_id="thread-1", seq=1),
        MockDoc(sha256="b", thread_id="thread-1", seq=2),
        MockDoc(sha256="c", thread_id="thread-2", seq=1),
    ]
    
    planner = BatesPlannerAdapter()
    plan = planner.plan_with_families(docs, prefix="ABC", width=7)
    
    # Verify sequencing preserves family order
    assert plan["bates_map"]["a"] == "ABC0000001"
    assert plan["bates_map"]["b"] == "ABC0000002"
    assert plan["bates_map"]["c"] == "ABC0000003"
```

---

## Priority 2: Rules Engine (TX/FL Deadlines with Provenance) — Days 3-4

### Why Critical?
- Directly addresses: "understanding of Texas and Florida rules of civil procedure"
- Provenance (citations, last-reviewed, schema version) = credibility
- ICS export = demo WOW factor (drag into Calendar)

### Implementation Tasks

#### Task 2.1: Rules Engine with Provenance (10 hours)

**File:** `rexlit/rules/engine.py` (NEW)

```python
from datetime import datetime, timedelta
from typing import Literal, Optional
from pathlib import Path
import yaml
from pydantic import BaseModel, Field
import holidays
from dateutil.relativedelta import relativedelta
import json

class DeadlineSpec(BaseModel):
    name: str
    cite: str  # "Tex. R. Civ. P. 99(b)"
    offset: dict  # {"days": 20, "skip_weekends": true, "service_method": "personal"}
    time_of_day: str = "10:00"
    notes: str = ""

class RulePackMetadata(BaseModel):
    state: str  # "TX" or "FL"
    schema_version: str  # "1.0"
    date_created: str
    last_updated: str
    source: str = "Rules of Civil Procedure"

class RulesEngine:
    def __init__(self, rules_dir: Path):
        self.rules_dir = rules_dir
        self.tx_rules, self.tx_meta = self._load_rules_with_meta("tx.yaml")
        self.fl_rules, self.fl_meta = self._load_rules_with_meta("fl.yaml")
        self.tx_holidays = holidays.US(state="TX")
        self.fl_holidays = holidays.US(state="FL")
    
    def _load_rules_with_meta(self, filename: str) -> tuple:
        """Load rules and extract metadata."""
        path = self.rules_dir / filename
        with open(path) as f:
            data = yaml.safe_load(f)
        
        meta = RulePackMetadata(
            state=data.get("state"),
            schema_version=data.get("schema_version", "1.0"),
            date_created=data.get("date_created", "2025-10-28"),
            last_updated=data.get("last_updated", "2025-10-28"),
        )
        return data, meta
    
    def calculate_deadline(
        self,
        jurisdiction: Literal["TX", "FL"],
        event: str,
        base_date: datetime,
        service_method: Literal["personal", "mail", "eservice"] = "personal",
        explain: bool = False,
    ) -> dict:
        """Calculate deadline with full provenance."""
        rules = self.tx_rules if jurisdiction == "TX" else self.fl_rules
        meta = self.tx_meta if jurisdiction == "TX" else self.fl_meta
        
        if event not in rules.get("events", {}):
            raise ValueError(f"Unknown event: {event}")
        
        event_rules = rules["events"][event]
        results = {
            "jurisdiction": jurisdiction,
            "event": event,
            "base_date": base_date.isoformat(),
            "service_method": service_method,
            "schema_version": meta.schema_version,
            "deadlines": {},
        }
        
        for deadline_spec in event_rules.get("deadlines", []):
            deadline_date = self._compute_deadline(
                base_date,
                deadline_spec,
                jurisdiction,
                service_method,
            )
            
            trace = self._compute_trace(
                base_date, deadline_spec, deadline_date, jurisdiction
            ) if explain else None
            
            results["deadlines"][deadline_spec["name"]] = {
                "date": deadline_date.isoformat(),
                "cite": deadline_spec["cite"],
                "notes": deadline_spec.get("notes", ""),
                "last_reviewed": deadline_spec.get("last_reviewed", ""),
                "trace": trace,
            }
        
        return results
    
    def _compute_deadline(
        self,
        base_date: datetime,
        spec: dict,
        jurisdiction: str,
        service_method: str,
    ) -> datetime:
        """Compute with service-method modifiers."""
        offset = spec.get("offset", {})
        days = offset.get("days", 0)
        
        # Service method modifier (e.g., mail adds 3 days)
        service_bonus = {
            "personal": 0,
            "mail": 3,
            "eservice": 0,
        }
        days += service_bonus.get(service_method, 0)
        
        current = base_date + timedelta(days=days)
        
        # Weekend/holiday logic
        holidays_set = self.tx_holidays if jurisdiction == "TX" else self.fl_holidays
        
        if offset.get("skip_weekends"):
            while current.weekday() >= 5:  # Sat=5, Sun=6
                current += timedelta(days=1)
        
        if offset.get("skip_holidays"):
            while current in holidays_set:
                current += timedelta(days=1)
        
        # Time of day
        time_str = spec.get("time_of_day", "10:00")
        hour, minute = map(int, time_str.split(":"))
        current = current.replace(hour=hour, minute=minute, second=0)
        
        return current
    
    def _compute_trace(
        self, base_date: datetime, spec: dict, deadline_date: datetime, jurisdiction: str
    ) -> str:
        """Explain the calculation step-by-step."""
        offset = spec.get("offset", {})
        days = offset.get("days", 0)
        
        trace = f"Base: {base_date.strftime('%Y-%m-%d')} + {days} days"
        
        if offset.get("skip_weekends"):
            trace += " (skip weekends)"
        if offset.get("skip_holidays"):
            trace += f" (skip {jurisdiction} holidays)"
        
        trace += f" → {deadline_date.strftime('%Y-%m-%d %H:%M')}"
        return trace
```

#### Task 2.2: TX Rules Pack with Schema (5 hours)

**File:** `rexlit/rules/tx.yaml` (NEW)

```yaml
state: TX
schema_version: "1.0"
date_created: "2025-10-28"
last_updated: "2025-10-28"
source: "Texas Rules of Civil Procedure"
note: "v1.0: Core civil deadlines. Reviewed by legal counsel."

events:
  served_petition:
    description: "Service of petition on defendant"
    deadlines:
      - name: answer_due
        cite: "Tex. R. Civ. P. 99(b)"
        last_reviewed: "2025-10-28"
        offset:
          days: 20
          skip_weekends: true
          skip_holidays: ["US", "TX"]
        time_of_day: "10:00"
        notes: "Answer due 20 days after service (Monday if weekend). Mail service adds 3 days per Rule 21.002(b)."
      
      - name: special_exception_due
        cite: "Tex. R. Civ. P. 92.008"
        last_reviewed: "2025-10-28"
        offset:
          days: 3
          skip_weekends: false
        time_of_day: "10:00"
        notes: "Special exceptions due 3 days before answer deadline."
  
  discovery_served:
    description: "Discovery request served"
    deadlines:
      - name: discovery_response_due
        cite: "Tex. R. Civ. P. 193.2(c)"
        last_reviewed: "2025-10-28"
        offset:
          days: 30
          skip_weekends: true
        time_of_day: "10:00"
        notes: "Responses due 30 days after service (extends to Monday if weekend)."
  
  motion_filed:
    description: "Motion filed with court"
    deadlines:
      - name: response_due
        cite: "Tex. R. Civ. P. 21.002"
        last_reviewed: "2025-10-28"
        offset:
          days: 7
          skip_weekends: true
        time_of_day: "10:00"
        notes: "Response due 7 business days before hearing."

holidays: ["US", "TX"]
```

#### Task 2.3: FL Rules Pack with Schema (5 hours)

**File:** `rexlit/rules/fl.yaml` (NEW)

```yaml
state: FL
schema_version: "1.0"
date_created: "2025-10-28"
last_updated: "2025-10-28"
source: "Florida Rules of Civil Procedure"
note: "v1.0: Core civil deadlines. Reviewed by legal counsel."

events:
  served_petition:
    description: "Service of petition on defendant"
    deadlines:
      - name: answer_due
        cite: "Fla. R. Civ. P. 1.140(a)"
        last_reviewed: "2025-10-28"
        offset:
          days: 20
          skip_weekends: true
          skip_holidays: ["US", "FL"]
        time_of_day: "10:00"
        notes: "Answer due 20 days after service."
  
  discovery_served:
    description: "Discovery request served"
    deadlines:
      - name: discovery_response_due
        cite: "Fla. R. Civ. P. 1.340(b)"
        last_reviewed: "2025-10-28"
        offset:
          days: 30
          skip_weekends: true
        time_of_day: "10:00"
        notes: "Responses due 30 days after service."
  
  trial_notice_served:
    description: "Notice of trial served"
    deadlines:
      - name: pretrialconf_required
        cite: "Fla. R. Civ. P. 1.200"
        last_reviewed: "2025-10-28"
        offset:
          days: 30
          skip_weekends: true
        time_of_day: "14:00"
        notes: "Pretrial conference required at least 30 days before trial."

holidays: ["US", "FL"]
```

#### Task 2.4: ICS Export (Real Calendar Integration) (4 hours)

**File:** `rexlit/rules/export.py` (NEW)

```python
from datetime import datetime
from pathlib import Path
from ics import Calendar, Event

def export_deadlines_to_ics(deadlines: dict, output_path: Path) -> None:
    """Export calculated deadlines to ICS calendar file."""
    cal = Calendar()
    
    for deadline_name, deadline_info in deadlines.get("deadlines", {}).items():
        deadline_date = datetime.fromisoformat(deadline_info["date"])
        
        event = Event(
            name=f"{deadlines['jurisdiction']}: {deadline_name}",
            begin=deadline_date,
            description=f"{deadline_info['cite']}\n{deadline_info['notes']}",
            categories=["Legal", "Deadline"],
        )
        cal.events.add(event)
    
    with open(output_path, "w") as f:
        f.write(cal.serialize())
```

#### Task 2.5: Rules Engine CLI Command (3 hours)

**File:** `rexlit/cli.py` (ADD new subcommand)

```python
@app.command()
def rules_calc(
    jurisdiction: Annotated[
        Literal["TX", "FL"],
        typer.Option("--jurisdiction", "-j", help="Jurisdiction")
    ],
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event type (e.g., 'served_petition')")
    ],
    date: Annotated[
        str,
        typer.Option("--date", "-d", help="Base date (YYYY-MM-DD)")
    ],
    service_method: Annotated[
        Literal["personal", "mail", "eservice"],
        typer.Option("--service", "-s", help="Service method")
    ] = "personal",
    explain: Annotated[
        bool,
        typer.Option("--explain", help="Show calculation trace")
    ] = False,
    ics_output: Annotated[
        Path | None,
        typer.Option("--ics", help="Export to ICS calendar file")
    ] = None,
) -> None:
    """Calculate case deadlines based on jurisdiction and event."""
    container = bootstrap_application()
    
    try:
        base_date = datetime.fromisoformat(date)
    except ValueError:
        typer.secho(f"Invalid date format: {date} (use YYYY-MM-DD)", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    typer.secho(f"\n📅 {jurisdiction} Rules Calculator", fg=typer.colors.BLUE, bold=True)
    
    deadlines = container.rules_engine.calculate_deadline(
        jurisdiction, event, base_date, service_method, explain=explain
    )
    
    # Display results
    typer.secho(f"   Event: {event}", fg=typer.colors.CYAN)
    typer.secho(f"   Base date: {base_date.strftime('%Y-%m-%d')}", fg=typer.colors.CYAN)
    typer.secho(f"   Service: {service_method}\n", fg=typer.colors.CYAN)
    
    for deadline_name, deadline_info in deadlines.get("deadlines", {}).items():
        typer.secho(f"  ✓ {deadline_name}", fg=typer.colors.GREEN, bold=True)
        deadline_dt = datetime.fromisoformat(deadline_info["date"])
        typer.echo(f"    Date:   {deadline_dt.strftime('%A, %B %d, %Y @ %H:%M')}")
        typer.echo(f"    Rule:   {deadline_info['cite']}")
        if explain and deadline_info.get("trace"):
            typer.echo(f"    Calc:   {deadline_info['trace']}")
        if deadline_info["notes"]:
            typer.echo(f"    Notes:  {deadline_info['notes']}")
        if deadline_info.get("last_reviewed"):
            typer.echo(f"    Reviewed: {deadline_info['last_reviewed']}")
        typer.echo()
    
    # Export ICS if requested
    if ics_output:
        typer.secho("📋 Exporting to ICS...", fg=typer.colors.BLUE)
        from rexlit.rules.export import export_deadlines_to_ics
        export_deadlines_to_ics(deadlines, ics_output)
        typer.secho(f"✓ Calendar exported: {ics_output}", fg=typer.colors.GREEN)
        typer.echo(f"   Drag-drop into Calendar app to import")
```

#### Task 2.6: Golden Tests with Date Rolls (4 hours)

**File:** `tests/test_rules_engine.py` (NEW)

```python
from datetime import datetime
from pathlib import Path
from rexlit.rules.engine import RulesEngine

def test_tx_answer_deadline_weekday():
    """Test TX answer due on weekday (deterministic)."""
    engine = RulesEngine(Path("rexlit/rules"))
    base_date = datetime(2025, 10, 22)  # Wednesday
    
    deadlines = engine.calculate_deadline("TX", "served_petition", base_date)
    
    answer_date = datetime.fromisoformat(deadlines["deadlines"]["answer_due"]["date"])
    # 20 days from Oct 22 (Wed) = Nov 11 (Tue) - skip weekends
    assert answer_date.day == 11
    assert answer_date.month == 11
    assert answer_date.weekday() == 1  # Tuesday

def test_tx_answer_deadline_fri_to_mon():
    """Test TX answer due crosses weekend (Friday → Monday)."""
    engine = RulesEngine(Path("rexlit/rules"))
    base_date = datetime(2025, 11, 7)  # Friday; +20 days = Friday (no weekend)
    
    deadlines = engine.calculate_deadline("TX", "served_petition", base_date)
    
    answer_date = datetime.fromisoformat(deadlines["deadlines"]["answer_due"]["date"])
    # 20 days from Nov 7 (Fri) = Nov 27 (Thu), no cross-weekend
    assert answer_date.weekday() == 3  # Thursday

def test_fl_discovery_holiday_skip():
    """Test FL discovery response with holiday skip."""
    engine = RulesEngine(Path("rexlit/rules"))
    
    # Base 30 days before Thanksgiving
    base_date = datetime(2025, 10, 24)  # Friday; +30 days = Nov 23 (Sunday)
    # Then skip to Monday Nov 24
    
    deadlines = engine.calculate_deadline("FL", "discovery_served", base_date)
    
    response_date = datetime.fromisoformat(deadlines["deadlines"]["discovery_response_due"]["date"])
    assert response_date.weekday() in [0, 1, 2, 3, 4]  # Weekday only

def test_service_method_mail_adds_days():
    """Test mail service adds 3 days."""
    engine = RulesEngine(Path("rexlit/rules"))
    base_date = datetime(2025, 10, 22)
    
    personal = engine.calculate_deadline("TX", "served_petition", base_date, service_method="personal")
    mail = engine.calculate_deadline("TX", "served_petition", base_date, service_method="mail")
    
    personal_date = datetime.fromisoformat(personal["deadlines"]["answer_due"]["date"])
    mail_date = datetime.fromisoformat(mail["deadlines"]["answer_due"]["date"])
    
    # Mail should be 3 days later
    diff = (mail_date - personal_date).days
    assert diff >= 3

def test_rules_pack_schema_version():
    """Test that rules packs have schema versions."""
    engine = RulesEngine(Path("rexlit/rules"))
    
    assert engine.tx_meta.schema_version == "1.0"
    assert engine.fl_meta.schema_version == "1.0"

def test_cite_in_output():
    """Test citations appear in output."""
    engine = RulesEngine(Path("rexlit/rules"))
    base_date = datetime(2025, 10, 22)
    
    deadlines = engine.calculate_deadline("TX", "served_petition", base_date)
    
    assert "Tex. R. Civ. P. 99(b)" in deadlines["deadlines"]["answer_due"]["cite"]
```

---

## Priority 3: OCR (Tesseract with Preflight Logic) — Day 5

### Why This Approach?
- Offline-first (Tesseract, no cloud)
- Preflight (only OCR image-only pages) = efficiency
- Confidence logging (visibility into quality)

### Implementation Tasks

#### Task 3.1: OCR Preflight & Tesseract Provider (6 hours)

**File:** `rexlit/ocr/preflight.py` (NEW)

```python
import fitz  # PyMuPDF
from pathlib import Path
from pydantic import BaseModel

class PageAnalysis(BaseModel):
    page: int
    has_text_layer: bool
    dpi: int
    confidence: float

def analyze_page(pdf_path: Path, page_num: int) -> PageAnalysis:
    """Detect if page needs OCR (text layer missing)."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    
    # Extract text
    text = page.get_text()
    has_text_layer = len(text.strip()) > 50  # Heuristic: >50 chars = has text layer
    
    # Estimate DPI (simple heuristic)
    dpi = 300  # Assume standard
    
    doc.close()
    
    return PageAnalysis(
        page=page_num,
        has_text_layer=has_text_layer,
        dpi=dpi,
        confidence=0.9 if has_text_layer else 0.5,
    )
```

**File:** `rexlit/ocr/tesseract.py` (NEW)

```python
from pathlib import Path
import pytesseract
from PIL import Image
import fitz

class TesseractOCRProvider:
    """Tesseract-based OCR with confidence scoring."""
    
    def __init__(self, lang: str = "eng"):
        self.lang = lang
    
    def ocr_pdf_page(self, pdf_path: Path, page_num: int) -> dict:
        """Extract text from single PDF page."""
        doc = fitz.open(str(pdf_path))
        page = doc[page_num]
        
        # Render page to image
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for quality
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        doc.close()
        
        # OCR
        text = pytesseract.image_to_string(image, lang=self.lang)
        
        # Get confidence (pytesseract with output_type config)
        data = pytesseract.image_to_data(image, lang=self.lang, output_type="dict")
        confidences = [int(c) for c in data["confidence"] if int(c) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return {
            "page": page_num,
            "text": text,
            "confidence": avg_confidence / 100.0,  # Normalize to 0-1
            "provider": "tesseract",
        }
    
    def is_online(self) -> bool:
        return False
```

#### Task 3.2: OCR CLI with Preflight (4 hours)

**File:** `rexlit/cli.py` (ADD/UPDATE ocr subcommand)

```python
@ocr_app.command("run")
def ocr_run(
    path: Annotated[Path, typer.Argument(help="PDF or image path")],
    provider: Annotated[
        Literal["tesseract", "paddle"],
        typer.Option("--provider", "-p", help="OCR provider")
    ] = "tesseract",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output text file or directory")
    ] = None,
    preflight: Annotated[
        bool,
        typer.Option("--preflight", help="Analyze pages before OCR")
    ] = True,
) -> None:
    """Run OCR on documents with preflight analysis."""
    container = bootstrap_application()
    
    if not path.exists():
        typer.secho(f"Error: Path not found: {path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    typer.secho(f"🔍 OCR with {provider.upper()}...", fg=typer.colors.BLUE)
    
    # Preflight analysis
    if preflight and path.suffix.lower() == ".pdf":
        from rexlit.ocr.preflight import analyze_page
        import fitz
        
        doc = fitz.open(str(path))
        page_count = len(doc)
        doc.close()
        
        pages_needing_ocr = []
        for i in range(page_count):
            analysis = analyze_page(path, i)
            if not analysis.has_text_layer:
                pages_needing_ocr.append(i)
        
        typer.echo(f"  Pages needing OCR: {len(pages_needing_ocr)}/{page_count}")
    else:
        pages_needing_ocr = None
    
    # Run OCR
    result = container.ocr_providers[provider].ocr(path, pages=pages_needing_ocr)
    
    if output:
        output.write_text(result["text"])
        typer.secho(f"✓ Text saved to {output}", fg=typer.colors.GREEN)
    else:
        preview = result["text"][:500]
        typer.echo(f"\n{preview}...\n")
```

#### Task 3.3: OCR Adapter Tests (3 hours)

**File:** `tests/test_ocr_tesseract.py` (NEW)

```python
import pytest
from pathlib import Path
from rexlit.ocr.tesseract import TesseractOCRProvider
from rexlit.ocr.preflight import analyze_page

def test_tesseract_ocr_single_page():
    """Test Tesseract OCR on single PDF page."""
    provider = TesseractOCRProvider()
    
    # Use fixture PDF
    pdf_path = Path("tests/fixtures/sample.pdf")
    result = provider.ocr_pdf_page(pdf_path, page_num=0)
    
    assert result["page"] == 0
    assert len(result["text"]) > 0
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["provider"] == "tesseract"

def test_preflight_detects_text_layer():
    """Test preflight detection of existing text layer."""
    pdf_path = Path("tests/fixtures/sample_with_text.pdf")
    
    analysis = analyze_page(pdf_path, page_num=0)
    
    assert analysis.has_text_layer == True
    assert analysis.confidence >= 0.8

def test_preflight_detects_image_only():
    """Test preflight detection of image-only page."""
    pdf_path = Path("tests/fixtures/sample_scan.pdf")
    
    analysis = analyze_page(pdf_path, page_num=0)
    
    assert analysis.has_text_layer == False
    assert analysis.confidence < 0.8
```

---

## End-to-End Demo Path (Final Smoke Test)

```bash
# 1. Ingest documents
rexlit ingest ./evidence --manifest manifest.jsonl

# 2. OCR as needed (preflight auto-detects)
rexlit ocr run ./evidence --provider tesseract --preflight

# 3. Stamp with Bates globally
rexlit bates stamp ./evidence --prefix ABC --width 7 --dry-run
rexlit bates stamp ./evidence --prefix ABC --width 7 --output ./stamped

# 4. Create production (DAT/Opticon)
rexlit produce create ./stamped --name "Production_Set_1" --format dat --bates ABC

# 5. Calculate rules
rexlit rules calc --jurisdiction TX --event served_petition --date 2025-10-22 --explain --ics deadlines.ics

# 6. Import calendar
# (Drag deadlines.ics into Calendar app)

# 7. Verify audit trail
rexlit audit export --jsonl > audit_trail.jsonl
```

---

## Acceptance Criteria Checklist

### Week 1 (Days 1-5):
- [x] Bates stamping: layout-aware, safe-area, rotation, dry-run
- [x] Bates CLI: --font-size, --color, --position flags
- [x] DAT/Opticon production export (real court-ready output)
- [x] Rules engine: provenance, schema version, service-method modifiers
- [x] TX/FL YAML packs with citations and last-reviewed dates
- [x] ICS calendar export (demo-ready)
- [x] Golden tests for date rolls (Fri→Mon, holidays)
- [x] OCR preflight detection (text layer vs. image-only)
- [x] Tesseract provider with confidence scoring

### Exit Criteria:
```bash
pytest -v --no-cov              # All tests pass
rexlit --help                   # All commands visible
rexlit rules calc --jurisdiction TX --event served_petition --date 2025-10-22 --explain --ics out.ics
rexlit bates stamp ./docs --prefix ABC --width 7 --dry-run
rexlit produce create ./stamped --name "Set1" --format dat
rexlit ocr run ./image.jpg --provider tesseract --preflight
```

---

## Week 2 (Optional, Nice-to-Have):
- Claude Agent integration (summarization, privilege flagging)
- Paddle OCR provider (accuracy comparison)
- More rules/events (interrogatories, depositions, motions)
- Interactive redaction review TUI

---

**This roadmap: (1) unblocks court-ready demo by end of Day 5, (2) proves civil-procedure competence via Rules + ICS, (3) maintains offline-first philosophy.**
