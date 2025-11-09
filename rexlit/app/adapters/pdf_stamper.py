"""PDF stamping adapter using PyMuPDF for Bates numbering and redactions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import fitz  # type: ignore[import]

from rexlit.app.ports.stamp import (
    BatesStampPreview,
    BatesStampRequest,
    BatesStampResult,
    PageStampCoordinate,
    StampPort,
)


@dataclass(frozen=True)
class _StampPreset:
    """Coordinate presets expressed as percentages of the safe area."""

    x_ratio: float
    y_ratio: float


class PDFStamperAdapter(StampPort):
    """Layout-aware Bates stamping backed by PyMuPDF."""

    _LOG = logging.getLogger(__name__)
    _POSITION_PRESETS: dict[Literal["bottom-right", "bottom-center", "top-right"], _StampPreset] = {
        "bottom-right": _StampPreset(x_ratio=0.85, y_ratio=0.85),
        "bottom-center": _StampPreset(x_ratio=0.50, y_ratio=0.85),
        "top-right": _StampPreset(x_ratio=0.85, y_ratio=0.15),
    }

    def stamp(self, request: BatesStampRequest) -> BatesStampResult:  # noqa: D401
        doc = fitz.open(str(request.input_path))
        try:
            output_parent = request.output_path.parent
            output_parent.mkdir(parents=True, exist_ok=True)

            current_number = request.start_number
            coordinates: list[PageStampCoordinate] = []

            for page_index in range(doc.page_count):
                page = doc[page_index]
                label = self._format_label(request.prefix, current_number, request.width)

                safe_area = self._compute_safe_area(page)
                preset = self._POSITION_PRESETS[request.position]
                stamp_rect = self._compute_stamp_rect(
                    page, safe_area, preset, request.font_size, label
                )

                if request.background:
                    self._draw_background(page, stamp_rect)

                self._draw_label(page, stamp_rect, label, request.font_size, request.color)

                coordinates.append(
                    PageStampCoordinate(
                        page=page_index + 1,
                        label=label,
                        position={
                            "x0": float(stamp_rect.x0),
                            "y0": float(stamp_rect.y0),
                            "x1": float(stamp_rect.x1),
                            "y1": float(stamp_rect.y1),
                        },
                        rotation=int(page.rotation or 0),
                        confidence=1.0,
                    )
                )

                current_number += 1

            doc.save(str(request.output_path))
        finally:
            doc.close()

        end_number = current_number - 1
        return BatesStampResult(
            input_path=request.input_path,
            output_path=request.output_path,
            pages_stamped=len(coordinates),
            start_number=request.start_number,
            end_number=end_number,
            start_label=self._format_label(request.prefix, request.start_number, request.width),
            end_label=self._format_label(request.prefix, end_number, request.width),
            prefix=request.prefix,
            width=request.width,
            coordinates=coordinates,
        )

    def dry_run(self, request: BatesStampRequest) -> BatesStampPreview:
        page_count = self.get_page_count(request.input_path)
        max_preview = min(5, page_count)
        preview_labels = [
            self._format_label(request.prefix, request.start_number + i, request.width)
            for i in range(max_preview)
        ]
        return BatesStampPreview(
            input_path=request.input_path,
            total_pages=page_count,
            start_number=request.start_number,
            prefix=request.prefix,
            width=request.width,
            preview_labels=preview_labels,
        )

    def apply_redactions(
        self,
        path: Path,
        output_path: Path,
        redactions: list[dict[str, Any]],
    ) -> int:
        if not redactions:
            # Still copy the document to the requested destination
            return self._copy_without_changes(path, output_path)

        doc = fitz.open(str(path))
        applied = 0

        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Track rectangles per page before applying annotations.
            page_rects: dict[int, list[fitz.Rect]] = {}
            unspecified: list[dict[str, Any]] = []

            for entry in redactions:
                page_idx = entry.get("page")
                if isinstance(page_idx, int) and page_idx >= 0:
                    if page_idx >= doc.page_count:
                        self._LOG.warning(
                            "Skipping redaction targeting page %s (document has %s pages)",
                            page_idx,
                            doc.page_count,
                        )
                        continue
                    rects = self._resolve_rects(doc[page_idx], entry)
                    if rects:
                        page_rects.setdefault(page_idx, []).extend(rects)
                        applied += len(rects)
                    else:
                        self._LOG.warning(
                            "No matching text found for redaction on page %s: %s",
                            page_idx,
                            entry.get("entity_type", "unknown"),
                        )
                else:
                    unspecified.append(entry)

            # Attempt to resolve unspecified redactions by scanning all pages.
            for entry in unspecified:
                matched = False
                for page_idx in range(doc.page_count):
                    rects = self._resolve_rects(doc[page_idx], entry)
                    if rects:
                        page_rects.setdefault(page_idx, []).extend(rects)
                        applied += len(rects)
                        matched = True
                        break
                if not matched:
                    self._LOG.warning(
                        "Unable to locate text for redaction entity %s",
                        entry.get("entity_type", "unknown"),
                    )

            # Apply annotations page-by-page.
            for page_idx, rect_list in page_rects.items():
                if not rect_list:
                    continue
                page = doc[page_idx]
                rotation = int(page.rotation or 0)
                if rotation % 360 != 0:
                    self._LOG.warning(
                        "Page %s is rotated %s°, redactions may be skipped or require manual review",
                        page_idx,
                        rotation,
                    )
                for rect in rect_list:
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                page.apply_redactions()

            doc.save(str(output_path))
        finally:
            doc.close()

        return applied

    def get_page_count(self, path: Path) -> int:
        doc = fitz.open(str(path))
        try:
            return doc.page_count
        finally:
            doc.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_safe_area(self, page: fitz.Page) -> fitz.Rect:
        margin_pts = 36  # half inch margin
        rect = page.rect
        return fitz.Rect(
            rect.x0 + margin_pts,
            rect.y0 + margin_pts,
            rect.x1 - margin_pts,
            rect.y1 - margin_pts,
        )

    def _compute_stamp_rect(
        self,
        page: fitz.Page,
        safe_area: fitz.Rect,
        preset: _StampPreset,
        font_size: int,
        label: str,
    ) -> fitz.Rect:
        text_width = max(font_size * 0.5 * len(label), font_size * 2)
        text_height = font_size * 1.2

        x_center = safe_area.x0 + (safe_area.width * preset.x_ratio)
        y_baseline = safe_area.y0 + (safe_area.height * preset.y_ratio)

        x0 = x_center - (text_width / 2)
        y0 = y_baseline - text_height
        x1 = x_center + (text_width / 2)
        y1 = y_baseline

        return fitz.Rect(x0, y0, x1, y1)

    def _draw_background(self, page: fitz.Page, rect: fitz.Rect) -> None:
        padding = 2
        background_rect = fitz.Rect(
            rect.x0 - padding,
            rect.y0 - padding,
            rect.x1 + padding,
            rect.y1 + padding,
        )
        page.draw_rect(background_rect, color=(1, 1, 1), fill=(1, 1, 1))

    def _draw_label(
        self,
        page: fitz.Page,
        rect: fitz.Rect,
        label: str,
        font_size: int,
        color: tuple[float, float, float],
    ) -> None:
        r, g, b = (max(0.0, min(1.0, component)) for component in color)
        inserted = page.insert_textbox(
            rect,
            label,
            fontsize=font_size,
            color=(r, g, b),
            align=fitz.TEXT_ALIGN_CENTER,
            overlay=True,
        )
        if inserted <= 0:
            baseline = fitz.Point(rect.x0, rect.y1 - (font_size * 0.2))
            page.insert_text(
                baseline,
                label,
                fontsize=font_size,
                color=(r, g, b),
                overlay=True,
            )

    def _format_label(self, prefix: str, number: int, width: int) -> str:
        digits = max(1, width)
        return f"{prefix}{number:0{digits}d}"

    # ------------------------------------------------------------------
    # Redaction helpers
    # ------------------------------------------------------------------

    def _resolve_rects(self, page: fitz.Page, redaction: dict[str, Any]) -> list[fitz.Rect]:
        """Return bounding rectangles for a single redaction entry."""

        rects: list[fitz.Rect] = []

        start = redaction.get("start")
        end = redaction.get("end")
        if isinstance(start, int) and isinstance(end, int) and end > start:
            bbox = self._char_offset_to_bbox(page, start, end)
            if bbox is not None:
                rects.append(bbox)
                return rects

        text = (redaction.get("text") or "").strip()
        if text and text != "***":
            search_rects = self._find_text_bbox(page, text)
            if search_rects:
                rects.extend(search_rects)

        return rects

    def _find_text_bbox(
        self,
        page: fitz.Page,
        search_text: str,
        *,
        case_sensitive: bool = False,
    ) -> list[fitz.Rect]:
        """Find bounding boxes for occurrences of ``search_text``."""

        try:
            rects = page.search_for(search_text)
        except ValueError:
            rects = []
        return rects or []

    def _char_offset_to_bbox(
        self,
        page: fitz.Page,
        start_char: int,
        end_char: int,
    ) -> fitz.Rect | None:
        """Convert character offsets on a page to a bounding box."""

        text_dict = page.get_text("dict")
        char_index = 0
        rect: fitz.Rect | None = None

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text:
                        continue
                    span_len = len(span_text)
                    span_start = char_index
                    span_end = char_index + span_len
                    if span_end <= start_char:
                        char_index += span_len
                        continue

                    if span_start >= end_char:
                        # We've surpassed the target range.
                        if rect is not None:
                            return rect
                        return None

                    current_rect = fitz.Rect(span["bbox"])
                    rect = current_rect if rect is None else rect | current_rect
                    char_index += span_len

        return rect

    def _copy_without_changes(self, source: Path, destination: Path) -> int:
        """Fallback when no redactions are supplied."""

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(str(source))
        try:
            doc.save(str(destination))
        finally:
            doc.close()
        return 0
