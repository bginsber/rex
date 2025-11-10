"""Utilities for parsing JSON from model outputs.

Models often wrap JSON responses in markdown code blocks or explanation text.
This module provides robust parsing that handles multiple formats.
"""

from __future__ import annotations

import json
from typing import Any


def parse_model_json_response(text: str) -> dict[str, Any]:
    """Parse JSON from model output, handling markdown code blocks and prefixes.

    The model may output JSON in several formats:
    1. Raw JSON: {"violation": 1, "labels": [...], ...}
    2. JSON in markdown code block: ```json\n{...}\n```
    3. JSON with explanation prefix: "Here is my analysis:\n{...}"
    4. JSON in last {...} block: "Some text {...}"

    Args:
        text: Model output text containing JSON

    Returns:
        Parsed JSON as dictionary

    Raises:
        ValueError: If no valid JSON can be extracted
    """
    text = text.strip()

    # Try direct JSON parse first (most common case)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract JSON from markdown code block
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    # Extract JSON from last {...} block (handles explanation prefix)
    if "{" in text and "}" in text:
        start = text.rfind("{")
        end = text.rfind("}") + 1
        if end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Could not parse JSON from response: {text[:200]}...")

