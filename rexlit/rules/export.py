"""ICS calendar export utilities for rules engine deadlines."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ics import Calendar, Event


def export_deadlines_to_ics(deadlines: dict[str, Any], output_path: Path) -> None:
    """Serialize deadline calculations to an ICS calendar file."""

    calendar = Calendar()

    for name, info in deadlines.get("deadlines", {}).items():
        date_value = info.get("date")
        if date_value is None:
            continue

        deadline_dt = datetime.fromisoformat(date_value)
        description_parts = [info.get("cite", "")]
        notes = info.get("notes")
        if notes:
            description_parts.append(notes)

        event = Event(
            name=f"{deadlines.get('jurisdiction')}: {name}",
            begin=deadline_dt,
            description="\n".join(part for part in description_parts if part),
            categories=["Legal", "Deadline"],
        )
        calendar.events.add(event)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(calendar.serialize(), encoding="utf-8")
