"""Minimal CLI JSON output wrapper for ADR-0004 compliance.

This module provides a simple helper for wrapping CLI JSON outputs with
schema metadata (schema_id, schema_version, producer, produced_at) as
required by ADR-0004.

Uses existing build_schema_stamp() from schema.py - no new abstractions.
"""

from __future__ import annotations

import json
from typing import Any

from rexlit.utils.schema import build_schema_stamp


def json_response(
    schema_id: str,
    schema_version: int,
    **data: Any,
) -> str:
    """Create schema-wrapped JSON response for CLI output.

    Args:
        schema_id: Identifier for the output type (e.g., "search_results").
        schema_version: Integer version for backward compatibility.
        **data: Payload data to include in the response.

    Returns:
        JSON string with schema metadata and payload.

    Example:
        >>> json_response("search_results", 1, query="test", results=[])
        {
          "schema_id": "search_results",
          "schema_version": 1,
          "producer": "rexlit-0.2.0",
          "produced_at": "2025-12-12T10:30:00+00:00",
          "query": "test",
          "results": []
        }
    """
    stamp = build_schema_stamp(schema_id=schema_id, schema_version=schema_version)
    wrapped = {
        "schema_id": stamp.schema_id,
        "schema_version": stamp.schema_version,
        "producer": stamp.producer,
        "produced_at": stamp.produced_at,
        **data,
    }
    return json.dumps(wrapped, indent=2, default=str)
