"""PDF stamping adapter using PyMuPDF for Bates numbering."""

from __future__ import annotations

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
        raise NotImplementedError("Redaction application is not yet implemented.")

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


