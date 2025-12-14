"""Bates registry verification utility.

This module provides verification for Bates plan JSONL files,
checking for integrity issues like duplicate IDs, missing files,
and hash mismatches.
"""

from __future__ import annotations

import json
from pathlib import Path

from rexlit.utils.hashing import compute_sha256_file


def verify_bates_registry(plan_path: Path) -> tuple[bool, list[str]]:
    """Verify integrity of a Bates registry plan.

    Validates:
    1. File exists and is readable
    2. Each record has required fields (document, sha256, bates_id)
    3. No duplicate Bates IDs
    4. No duplicate SHA-256 hashes
    5. Referenced files exist and hashes match

    Args:
        plan_path: Path to the bates_plan.jsonl file.

    Returns:
        Tuple of (is_valid, list of error messages).
        If is_valid is True, error list is empty.
    """
    errors: list[str] = []

    if not plan_path.exists():
        return False, [f"Bates plan file not found: {plan_path}"]

    seen_bates_ids: set[str] = set()
    seen_hashes: set[str] = set()
    record_count = 0

    try:
        with plan_path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"Line {line_num}: Invalid JSON - {e}")
                    continue

                record_count += 1

                # Check required fields
                if "bates_id" not in record:
                    errors.append(f"Line {line_num}: Missing 'bates_id' field")
                    continue

                if "sha256" not in record:
                    errors.append(f"Line {line_num}: Missing 'sha256' field")
                    continue

                if "document" not in record:
                    errors.append(f"Line {line_num}: Missing 'document' field")
                    continue

                bates_id = record["bates_id"]
                sha256 = record["sha256"]
                doc_path = record["document"]

                # Check for duplicate Bates IDs
                if bates_id in seen_bates_ids:
                    errors.append(f"Line {line_num}: Duplicate Bates ID '{bates_id}'")
                else:
                    seen_bates_ids.add(bates_id)

                # Check for duplicate hashes
                if sha256 in seen_hashes:
                    errors.append(f"Line {line_num}: Duplicate SHA-256 '{sha256}'")
                else:
                    seen_hashes.add(sha256)

                # Verify file exists and hash matches
                file_path = Path(doc_path)
                if not file_path.exists():
                    errors.append(
                        f"Line {line_num}: File not found - {doc_path} (Bates: {bates_id})"
                    )
                else:
                    try:
                        actual_hash = compute_sha256_file(file_path)
                        if actual_hash != sha256:
                            errors.append(
                                f"Line {line_num}: Hash mismatch for {doc_path} "
                                f"(expected {sha256[:12]}..., got {actual_hash[:12]}...)"
                            )
                    except (PermissionError, OSError) as e:
                        errors.append(
                            f"Line {line_num}: Cannot read {doc_path} - {e}"
                        )

    except OSError as e:
        return False, [f"Failed to read plan file: {e}"]

    if record_count == 0:
        errors.append("Bates plan file is empty")

    return len(errors) == 0, errors
