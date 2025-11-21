from pathlib import Path

import pytest

from rexlit.utils.paths import validate_input_root, validate_output_root


def test_validate_input_root_rejects_outside(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)

    with pytest.raises(ValueError):
        validate_input_root(outside, [tmp_path])


def test_validate_output_root_accepts_within(tmp_path: Path) -> None:
    target = tmp_path / "out" / "file.txt"
    target.parent.mkdir(parents=True, exist_ok=True)

    resolved = validate_output_root(target, [tmp_path])
    assert resolved == target.resolve()


def test_validate_output_root_no_allowed_roots(tmp_path: Path) -> None:
    target = tmp_path / "free" / "file.txt"
    result = validate_output_root(target, [])
    assert result == target.resolve()
