"""Tests to enforce ADR-0002 import contracts via importlinter.

This module ensures the hexagonal architecture boundaries defined in ADR-0002
are continuously enforced. The contracts are configured in pyproject.toml
under [tool.importlinter.contracts].

If this test fails, it means a new import was added that violates the
ports/adapters architecture. Check the importlinter output to see which
contract was broken and fix the import.

Known tech debt (documented in pyproject.toml ignore_imports):
- CLI directly imports index.search, ingest.extract, rules.export
- Index domain directly imports HNSWAdapter

These should be refactored to go through the app layer.
"""

from __future__ import annotations

import subprocess
import sys


def test_importlinter_contracts_enforced() -> None:
    """Verify all ADR-0002 import contracts pass.

    This test runs importlinter (lint-imports) and asserts all contracts
    defined in pyproject.toml are kept. Any broken contract indicates
    an architectural violation that should be fixed before merging.

    Run manually: uv run lint-imports
    """
    # Use the lint-imports entry point (installed by import-linter package)
    import shutil

    lint_imports = shutil.which("lint-imports")
    if lint_imports is None:
        # Fallback to virtualenv bin directory
        from pathlib import Path

        venv_bin = Path(sys.executable).parent
        lint_imports = str(venv_bin / "lint-imports")

    result = subprocess.run(
        [lint_imports],
        capture_output=True,
        text=True,
    )

    # importlinter returns 0 if all contracts pass, 1 if any broken
    if result.returncode != 0:
        # Include both stdout and stderr for debugging
        output = result.stdout + "\n" + result.stderr
        raise AssertionError(
            f"Import contracts violated (ADR-0002).\n"
            f"Run 'uv run lint-imports' for details.\n\n"
            f"Output:\n{output}"
        )

    # Sanity check: ensure we actually checked contracts
    assert "Contracts:" in result.stdout, (
        "Unexpected importlinter output - missing 'Contracts:' summary. "
        f"Got: {result.stdout[:500]}"
    )
    assert "0 broken" in result.stdout or "kept, 0 broken" in result.stdout, (
        f"Contract status unclear. Output: {result.stdout[:500]}"
    )
