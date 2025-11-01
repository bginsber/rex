"""Rules engine with provenance-backed deadline calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import holidays
import yaml
from pydantic import BaseModel, Field, ValidationError

Jurisdiction = Literal["TX", "FL"]
ServiceMethod = Literal["personal", "mail", "eservice"]


class OffsetSpec(BaseModel):
    """Relative offset configuration for a deadline."""

    days: int = 0
    skip_weekends: bool = False
    skip_holidays: list[str] | bool = Field(default=False)

    def skip_holidays_enabled(self) -> bool:
        """Return True when holiday skipping should be applied."""
        return bool(self.skip_holidays)


class DeadlineSpec(BaseModel):
    """Single deadline entry associated with a triggering event."""

    name: str
    cite: str
    offset: OffsetSpec = Field(default_factory=OffsetSpec)
    time_of_day: str = "10:00"
    notes: str = ""
    last_reviewed: str = ""


class EventSpec(BaseModel):
    """Rule pack event containing one or more deadlines."""

    description: str = ""
    deadlines: list[DeadlineSpec] = Field(default_factory=list)


class RulePack(BaseModel):
    """Serialised rule pack including provenance metadata."""

    state: str
    schema_version: str = "1.0"
    date_created: str
    last_updated: str
    source: str = "Rules of Civil Procedure"
    note: str | None = None
    events: dict[str, EventSpec] = Field(default_factory=dict)
    holidays: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RulePackRecord:
    """Typed wrapper pairing a pack with its source path."""

    pack: RulePack
    path: Path


class RulesEngine:
    """Deadline calculator for Texas and Florida civil procedure rules."""

    _SERVICE_BONUS: dict[ServiceMethod, int] = {
        "personal": 0,
        "mail": 3,
        "eservice": 0,
    }

    def __init__(self, rules_dir: Path) -> None:
        self._rules_dir = rules_dir

        self._packs: dict[Jurisdiction, RulePackRecord] = {
            "TX": self._load_pack("tx.yaml"),
            "FL": self._load_pack("fl.yaml"),
        }

        self._holiday_sets: dict[Jurisdiction, holidays.UnitedStates] = {
            "TX": holidays.UnitedStates(subdiv="TX"),
            "FL": holidays.UnitedStates(subdiv="FL"),
        }

    def _load_pack(self, filename: str) -> RulePackRecord:
        path = (self._rules_dir / filename).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Rules pack not found: {path}")

        with path.open("r", encoding="utf-8") as handle:
            data: dict[str, Any] | None = yaml.safe_load(handle)

        if data is None:
            raise ValueError(f"Rules pack is empty: {path}")

        try:
            pack = RulePack.model_validate(data)
        except ValidationError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid rules pack at {path}: {exc}") from exc

        return RulePackRecord(pack=pack, path=path)

    def calculate_deadline(
        self,
        jurisdiction: Jurisdiction,
        event: str,
        base_date: datetime,
        service_method: ServiceMethod = "personal",
        explain: bool = False,
    ) -> dict[str, Any]:
        """Calculate deadlines for ``event`` in ``jurisdiction`` with provenance."""

        pack_record = self._packs.get(jurisdiction)
        if pack_record is None:
            raise ValueError(f"Unsupported jurisdiction: {jurisdiction}")

        event_spec = pack_record.pack.events.get(event)
        if event_spec is None:
            raise ValueError(f"Unknown event for {jurisdiction}: {event}")

        results: dict[str, Any] = {
            "jurisdiction": jurisdiction,
            "event": event,
            "base_date": base_date.isoformat(),
            "service_method": service_method,
            "schema_version": pack_record.pack.schema_version,
            "source": pack_record.pack.source,
            "metadata": {
                "state": pack_record.pack.state,
                "date_created": pack_record.pack.date_created,
                "last_updated": pack_record.pack.last_updated,
                "note": pack_record.pack.note,
                "pack_path": str(pack_record.path),
            },
            "deadlines": {},
        }

        for deadline in event_spec.deadlines:
            deadline_date = self._compute_deadline(
                base_date=base_date,
                spec=deadline,
                jurisdiction=jurisdiction,
                service_method=service_method,
            )

            trace = None
            if explain:
                trace = self._compute_trace(
                    base_date=base_date,
                    spec=deadline,
                    deadline_date=deadline_date,
                    jurisdiction=jurisdiction,
                    service_method=service_method,
                )

            results["deadlines"][deadline.name] = {
                "date": deadline_date.isoformat(),
                "cite": deadline.cite,
                "notes": deadline.notes,
                "last_reviewed": deadline.last_reviewed,
                "trace": trace,
            }

        return results

    def _compute_deadline(
        self,
        *,
        base_date: datetime,
        spec: DeadlineSpec,
        jurisdiction: Jurisdiction,
        service_method: ServiceMethod,
    ) -> datetime:
        """Apply offset rules, weekend rolls, and holiday adjustments."""

        days = spec.offset.days + self._SERVICE_BONUS.get(service_method, 0)
        current = base_date + timedelta(days=days)

        if spec.offset.skip_weekends:
            while current.weekday() >= 5:
                current += timedelta(days=1)

        if spec.offset.skip_holidays_enabled():
            holiday_set = self._holiday_sets.get(jurisdiction)
            if holiday_set is not None:
                while current.date() in holiday_set:
                    current += timedelta(days=1)

        hour, minute = self._parse_time(spec.time_of_day)
        return current.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _compute_trace(
        self,
        *,
        base_date: datetime,
        spec: DeadlineSpec,
        deadline_date: datetime,
        jurisdiction: Jurisdiction,
        service_method: ServiceMethod,
    ) -> str:
        """Generate a human-readable explanation of the calculation."""

        parts = [
            f"Base {base_date.strftime('%Y-%m-%d')}",
            f"+{spec.offset.days}d",
        ]

        bonus = self._SERVICE_BONUS.get(service_method, 0)
        if bonus:
            parts.append(f"+{bonus}d (service)")

        if spec.offset.skip_weekends:
            parts.append("skip weekends")

        if spec.offset.skip_holidays_enabled():
            parts.append(f"skip {jurisdiction} holidays")

        parts.append(f"→ {deadline_date.strftime('%Y-%m-%d %H:%M')}")
        return " ".join(parts)

    @staticmethod
    def _parse_time(value: str) -> tuple[int, int]:
        try:
            hour_str, minute_str = value.split(":", 1)
            return int(hour_str), int(minute_str)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Invalid time format '{value}'") from exc
