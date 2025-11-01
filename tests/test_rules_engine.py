from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from rexlit.rules.engine import RulesEngine


@pytest.fixture()
def rules_engine() -> RulesEngine:
    return RulesEngine(Path("rexlit/rules"))


def test_tx_answer_deadline_rolls_to_monday(rules_engine: RulesEngine) -> None:
    base_date = datetime(2025, 10, 20)  # Monday
    deadlines = rules_engine.calculate_deadline("TX", "served_petition", base_date)

    answer_info = deadlines["deadlines"]["answer_due"]
    answer_dt = datetime.fromisoformat(answer_info["date"])

    assert answer_dt.weekday() == 0  # Monday
    assert answer_dt.day == 10
    assert answer_info["cite"] == "Tex. R. Civ. P. 99(b)"


def test_mail_service_adds_days(rules_engine: RulesEngine) -> None:
    base_date = datetime(2025, 10, 21)

    personal = rules_engine.calculate_deadline(
        "TX",
        "served_petition",
        base_date,
        service_method="personal",
    )
    mail = rules_engine.calculate_deadline(
        "TX",
        "served_petition",
        base_date,
        service_method="mail",
    )

    personal_dt = datetime.fromisoformat(personal["deadlines"]["answer_due"]["date"])
    mail_dt = datetime.fromisoformat(mail["deadlines"]["answer_due"]["date"])

    assert (mail_dt - personal_dt).days >= 3


def test_trace_included_when_explain(rules_engine: RulesEngine) -> None:
    base_date = datetime(2025, 10, 20)
    deadlines = rules_engine.calculate_deadline(
        "TX",
        "served_petition",
        base_date,
        explain=True,
    )

    trace = deadlines["deadlines"]["answer_due"]["trace"]
    assert isinstance(trace, str)
    assert "skip weekends" in trace


def test_fl_discovery_skips_weekend(rules_engine: RulesEngine) -> None:
    base_date = datetime(2025, 10, 24)  # Friday
    deadlines = rules_engine.calculate_deadline("FL", "discovery_served", base_date)

    response_dt = datetime.fromisoformat(
        deadlines["deadlines"]["discovery_response_due"]["date"]
    )

    assert response_dt.weekday() < 5  # Monday-Friday
    assert response_dt.month == 11
