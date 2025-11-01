"""End-to-end tests for Bates stamping and production export."""

from __future__ import annotations

from pathlib import Path

import fitz  # type: ignore[import]

from rexlit.app.adapters.bates import SequentialBatesPlanner
from rexlit.app.adapters.pdf_stamper import PDFStamperAdapter
from rexlit.app.ports.stamp import BatesStampRequest
from rexlit.bootstrap import bootstrap_application
from rexlit.config import Settings


def _create_sample_pdf(path: Path, pages: int = 5) -> None:
    doc = fitz.open()
    try:
        for index in range(pages):
            page = doc.new_page()
            page.insert_text((72, 72), f"Sample Page {index + 1}")
        doc.save(str(path))
    finally:
        doc.close()


def test_pdf_stamper_layout_aware(temp_dir: Path) -> None:
    source = temp_dir / "source.pdf"
    output = temp_dir / "stamped.pdf"
    _create_sample_pdf(source, pages=5)

    adapter = PDFStamperAdapter()
    request = BatesStampRequest(
        input_path=source,
        output_path=output,
        prefix="ABC",
        start_number=1,
        width=7,
        position="bottom-right",
        font_size=12,
        color=(0.0, 0.0, 0.0),
    )

    result = adapter.stamp(request)

    assert result.pages_stamped == 5
    assert result.start_label == "ABC0000001"
    assert result.end_label == "ABC0000005"
    assert output.exists()

    stamped = fitz.open(str(output))
    try:
        first_page_text = stamped[0].get_text()
    finally:
        stamped.close()

    assert "ABC0000001" in first_page_text


def test_pdf_stamper_dry_run_preview(temp_dir: Path) -> None:
    source = temp_dir / "preview.pdf"
    _create_sample_pdf(source, pages=10)

    adapter = PDFStamperAdapter()
    request = BatesStampRequest(
        input_path=source,
        output_path=temp_dir / "preview_out.pdf",
        prefix="XYZ",
        start_number=5,
        width=6,
    )

    preview = adapter.dry_run(request)

    assert preview.total_pages == 10
    assert preview.preview_labels[:3] == ["XYZ000005", "XYZ000006", "XYZ000007"]


def test_plan_with_families_orders_documents(temp_dir: Path) -> None:
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    planner = SequentialBatesPlanner(settings=settings)

    class MockDoc:
        def __init__(self, path: Path, sha: str, thread: str) -> None:
            self.path = str(path)
            self.sha256 = sha
            self.extension = ".pdf"
            self.mtime = "2025-10-28T10:00:00Z"
            self.metadata = {"thread_id": thread}

    docs = [
        MockDoc(temp_dir / "doc1.pdf", "sha-a", "thread-2"),
        MockDoc(temp_dir / "doc2.pdf", "sha-b", "thread-1"),
        MockDoc(temp_dir / "doc3.pdf", "sha-c", "thread-1"),
    ]

    plan = planner.plan_with_families(docs, prefix="ABC", width=7, separator="")

    assert plan["families"] == {"thread-1": 2, "thread-2": 1}
    ordered_shas = [entry["sha256"] for entry in plan["ordered_documents"]]
    assert ordered_shas == ["sha-b", "sha-c", "sha-a"]


def test_pack_service_create_production_from_manifest(temp_dir: Path) -> None:
    settings = Settings(
        data_dir=temp_dir / "data",
        config_dir=temp_dir / "config",
        audit_enabled=False,
    )
    container = bootstrap_application(settings=settings)

    stamped_dir = temp_dir / "stamped"
    stamped_dir.mkdir()

    source_pdf = stamped_dir / "doc.pdf"
    output_pdf = stamped_dir / "doc_stamped.pdf"
    _create_sample_pdf(source_pdf, pages=3)

    request = BatesStampRequest(
        input_path=source_pdf,
        output_path=output_pdf,
        prefix="ABC",
        start_number=1,
        width=7,
    )
    result = container.bates_stamper.stamp(request)
    output_hash = container.storage_port.compute_hash(output_pdf)

    manifest_record = {
        "input_path": str(result.input_path),
        "output_path": str(result.output_path),
        "sha256": output_hash,
        "family_id": None,
        "prefix": result.prefix,
        "width": result.width,
        "start_number": result.start_number,
        "end_number": result.end_number,
        "start_label": result.start_label,
        "end_label": result.end_label,
        "pages_stamped": result.pages_stamped,
        "coordinates": [coord.model_dump(mode="json") for coord in result.coordinates],
        "output_sha256": output_hash,
    }

    manifest_path = stamped_dir / "bates_manifest.jsonl"
    container.storage_port.write_jsonl(manifest_path, iter([manifest_record]))

    production = container.pack_service.create_production(
        stamped_dir,
        name="prod_set",
        format="dat",
        bates_prefix="ABC",
    )

    dat_path = production["output_path"]
    assert dat_path.exists()
    dat_contents = dat_path.read_text(encoding="utf-8")
    assert "ABC0000001" in dat_contents

    opt_production = container.pack_service.create_production(
        stamped_dir,
        name="prod_set_opt",
        format="opticon",
    )
    assert opt_production["output_path"].exists()

