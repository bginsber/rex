"""Helpers for mapping text offsets to bounding boxes using OCR layout sidecars."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_layout(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _normalize_bbox(bbox: list[float] | tuple[float, float, float, float], width: float, height: float) -> dict[str, float]:
    x0, y0, x1, y1 = bbox
    return {
        "x0": x0 / width if width else 0.0,
        "y0": y0 / height if height else 0.0,
        "x1": x1 / width if width else 0.0,
        "y1": y1 / height if height else 0.0,
    }


def map_highlight_boxes(
    *,
    highlight: dict[str, Any],
    document_hash: str,
    layout_dir: Path,
) -> list[dict[str, float]]:
    """Map highlight offsets to bounding boxes using a layout sidecar if available.

    Expects layout schema:
    {
      "pages": [
        {"page": 1, "width": 1000, "height": 1500,
         "spans": [{"start": 0, "end": 20, "bbox": [x0,y0,x1,y1]}]
        }
      ]
    }
    """
    sidecar = layout_dir / f"{document_hash}.layout.json"
    layout = _load_layout(sidecar)
    if not layout:
        return []

    start = highlight.get("start")
    end = highlight.get("end")
    page_num = highlight.get("page")
    if start is None or end is None:
        return []

    boxes: list[dict[str, float]] = []
    for page in layout.get("pages", []):
        if page_num is not None and page.get("page") != page_num:
            continue

        width = float(page.get("width") or 1.0)
        height = float(page.get("height") or 1.0)
        for span in page.get("spans", []):
            span_start = span.get("start")
            span_end = span.get("end")
            bbox = span.get("bbox")
            if bbox is None or span_start is None or span_end is None:
                continue
            if (span_start <= start < span_end) or (span_start < end <= span_end) or (
                start <= span_start and end >= span_end
            ):
                norm = _normalize_bbox(bbox, width, height)
                norm["page"] = page.get("page") or page_num or 1
                boxes.append(norm)

    return boxes
