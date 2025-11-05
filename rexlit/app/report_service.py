"""Report service for generating production reports.

Read-only service that consumes manifests and artifacts to generate reports.
"""

import csv
import html
import io
import json
import os
import tempfile
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from rexlit import __version__
from rexlit.app.m1_pipeline import PipelineStage
from rexlit.app.ports import DocumentRecord, LedgerPort, StoragePort


class ReportMetadata(BaseModel):
    """Metadata for generated report."""

    title: str
    generated_at: str
    document_count: int
    total_pages: int
    redaction_count: int
    bates_range: str | None


class ImpactReport(BaseModel):
    """Sedona Conference-aligned discovery impact summary."""

    schema_version: str = "1.0.0"
    tool_version: str
    summary: dict[str, Any]
    estimated_review: dict[str, Any]
    culling_rationale: str
    by_custodian: dict[str, dict[str, Any]]
    by_doctype: dict[str, dict[str, Any]]
    by_extension: dict[str, int]
    date_range: dict[str, Any] | None
    size_distribution: dict[str, int]
    stages: list[dict[str, Any]]
    errors: dict[str, Any]
    manifest_path: str | None
    generated_at: str


class ReportService:
    """Read-only report generation service.

    Consumes manifests and artifacts without modifying them.
    All file I/O is delegated to storage port.
    """

    def __init__(
        self,
        storage_port: StoragePort,
        ledger_port: LedgerPort,
    ):
        """Initialize report service.

        Args:
            storage_port: Filesystem operations port
            ledger_port: Audit logging port
        """
        self.storage = storage_port
        self.ledger = ledger_port

    def build_html_report(
        self,
        manifest_path: Path,
        output_path: Path,
        *,
        include_thumbnails: bool = False,
    ) -> ReportMetadata:
        """Generate HTML report from manifest.

        Args:
            manifest_path: Path to manifest JSONL
            output_path: Output path for HTML report
            include_thumbnails: Include document thumbnails

        Returns:
            ReportMetadata with summary information
        """
        # Read manifest via storage_port
        documents = list(self.storage.read_jsonl(manifest_path))

        # Calculate summary statistics
        document_count = len(documents)
        total_pages = sum(doc.get("metadata", {}).get("pages", 0) or 0 for doc in documents)
        redaction_count = sum(doc.get("redaction_count", 0) for doc in documents)

        # Extract Bates range if available
        bates_numbers = [doc.get("bates_number") for doc in documents if doc.get("bates_number")]
        bates_range = None
        if bates_numbers:
            bates_range = f"{bates_numbers[0]} - {bates_numbers[-1]}"

        # Extract date range from document mtimes
        mtimes = [doc.get("mtime") for doc in documents if doc.get("mtime")]
        date_range = None
        if mtimes:
            sorted_mtimes = sorted(mtimes)
            date_range = f"{sorted_mtimes[0][:10]} to {sorted_mtimes[-1][:10]}"

        # Generate timestamp
        generated_at = datetime.now(UTC).isoformat()

        # Generate HTML report
        html_content = self._generate_html(
            documents=documents,
            document_count=document_count,
            total_pages=total_pages,
            redaction_count=redaction_count,
            bates_range=bates_range,
            date_range=date_range,
            generated_at=generated_at,
            include_thumbnails=include_thumbnails,
        )

        # Write report via storage_port
        self.storage.write_text(output_path, html_content)

        # Log to audit
        self.ledger.log(
            operation="report_build",
            inputs=[str(manifest_path)],
            outputs=[str(output_path)],
            args={"include_thumbnails": include_thumbnails},
        )

        return ReportMetadata(
            title="Production Report",
            generated_at=generated_at,
            document_count=document_count,
            total_pages=total_pages,
            redaction_count=redaction_count,
            bates_range=bates_range,
        )

    def _generate_html(
        self,
        *,
        documents: list[dict[str, Any]],
        document_count: int,
        total_pages: int,
        redaction_count: int,
        bates_range: str | None,
        date_range: str | None,
        generated_at: str,
        include_thumbnails: bool,
    ) -> str:
        """Generate HTML report content.

        Args:
            documents: List of document records from manifest
            document_count: Total number of documents
            total_pages: Total page count across all documents
            redaction_count: Total number of redactions
            bates_range: Bates number range if available
            date_range: Document date range if available
            generated_at: ISO timestamp of report generation
            include_thumbnails: Whether to include thumbnails

        Returns:
            Complete HTML report as string
        """
        # Format generated timestamp for display
        generated_display = generated_at[:19].replace("T", " ")

        # Build document table rows
        doc_rows = []
        for idx, doc in enumerate(documents, 1):
            path_raw = doc.get("path", "Unknown")
            filename_raw = Path(path_raw).name
            size = doc.get("size", 0)
            size_kb = f"{size / 1024:.1f} KB" if size else "0 KB"
            mime_type_raw = doc.get("mime_type", "Unknown")
            custodian_raw = doc.get("custodian", "N/A")
            doctype_raw = doc.get("doctype", "N/A")
            sha256_raw = doc.get("sha256", "N/A")
            sha256_short_raw = sha256_raw[:16] + "..." if len(sha256_raw) > 16 else sha256_raw
            bates_raw = doc.get("bates_number", "N/A")
            pages = doc.get("metadata", {}).get("pages") or "N/A"

            # Optional thumbnail column
            thumbnail_cell = ""
            if include_thumbnails:
                thumbnail_cell = "<td>[Thumbnail]</td>"

            path = html.escape(path_raw)
            filename = html.escape(filename_raw)
            mime_type = html.escape(mime_type_raw or "Unknown")
            custodian = html.escape(custodian_raw or "N/A")
            doctype = html.escape(doctype_raw or "N/A")
            sha256 = html.escape(sha256_raw or "N/A")
            sha256_short = html.escape(sha256_short_raw or "N/A")
            bates = html.escape(bates_raw or "N/A")
            pages_display = html.escape(str(pages))

            doc_rows.append(
                f"""
                <tr>
                    <td>{idx}</td>
                    <td title="{path}">{filename}</td>
                    <td>{size_kb}</td>
                    <td>{mime_type}</td>
                    <td>{custodian}</td>
                    <td>{doctype}</td>
                    <td>{pages_display}</td>
                    <td title="{sha256}">{sha256_short}</td>
                    <td>{bates}</td>
                    {thumbnail_cell}
                </tr>
                """
            )

        doc_table_rows = "\n".join(doc_rows)

        # Optional thumbnail header
        thumbnail_header = "<th>Thumbnail</th>" if include_thumbnails else ""

        # Build HTML
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Production Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        header {{
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        h1 {{
            color: #2c3e50;
            font-size: 32px;
            margin-bottom: 10px;
        }}
        .meta {{
            color: #7f8c8d;
            font-size: 14px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .summary-card {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #3498db;
        }}
        .summary-card h3 {{
            color: #7f8c8d;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        .summary-card .value {{
            color: #2c3e50;
            font-size: 24px;
            font-weight: bold;
        }}
        .section {{
            margin: 40px 0;
        }}
        .section h2 {{
            color: #2c3e50;
            font-size: 24px;
            margin-bottom: 20px;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        th {{
            background: #34495e;
            color: white;
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
            font-size: 14px;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 10px 8px;
            border-bottom: 1px solid #ecf0f1;
            font-size: 13px;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            color: #7f8c8d;
            font-size: 12px;
            text-align: center;
        }}
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Production Report</h1>
            <div class="meta">Generated: {generated_display} UTC</div>
        </header>

        <section class="summary">
            <div class="summary-card">
                <h3>Documents</h3>
                <div class="value">{document_count}</div>
            </div>
            <div class="summary-card">
                <h3>Total Pages</h3>
                <div class="value">{total_pages}</div>
            </div>
            <div class="summary-card">
                <h3>Redactions</h3>
                <div class="value">{redaction_count}</div>
            </div>
            <div class="summary-card">
                <h3>Bates Range</h3>
                <div class="value" style="font-size: 16px;">{html.escape(bates_range or "N/A")}</div>
            </div>
            <div class="summary-card">
                <h3>Date Range</h3>
                <div class="value" style="font-size: 16px;">{html.escape(date_range or "N/A")}</div>
            </div>
        </section>

        <section class="section">
            <h2>Document Listing</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Filename</th>
                        <th>Size</th>
                        <th>Type</th>
                        <th>Custodian</th>
                        <th>Doctype</th>
                        <th>Pages</th>
                        <th>SHA-256</th>
                        <th>Bates</th>
                        {thumbnail_header}
                    </tr>
                </thead>
                <tbody>
                    {doc_table_rows}
                </tbody>
            </table>
        </section>

        <footer class="footer">
            <p>Report generated by RexLit - Offline-First Litigation Toolkit</p>
            <p>This report is for legal review purposes only. All information is derived from the production manifest.</p>
        </footer>
    </div>
</body>
</html>"""

        return html_content

    def build_csv_report(
        self,
        manifest_path: Path,
        output_path: Path,
    ) -> int:
        """Generate CSV report from manifest.

        Args:
            manifest_path: Path to manifest JSONL
            output_path: Output path for CSV

        Returns:
            Number of rows written (excluding header)
        """
        # Read manifest via storage_port
        records = list(self.storage.read_jsonl(manifest_path))

        # Define CSV columns per RFC 4180 for e-discovery exports
        fieldnames = [
            "DOCID",
            "PATH",
            "SHA256",
            "SIZE_BYTES",
            "MIME_TYPE",
            "DOCTYPE",
            "CUSTODIAN",
            "PAGES",
            "CREATEDATE",
            "MODIFYDATE",
            "PRODUCED_AT",
            "PRODUCER",
        ]

        # Generate CSV in memory with proper escaping
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )

        # Write header
        writer.writeheader()

        # Write data rows
        row_count = 0
        for record in records:
            # Extract metadata fields (may be nested)
            metadata = record.get("metadata", {}) or {}

            # Build CSV row with proper field mapping
            csv_row = {
                "DOCID": record.get("sha256", "")[:16],  # First 16 chars as DOCID
                "PATH": record.get("path", ""),
                "SHA256": record.get("sha256", ""),
                "SIZE_BYTES": record.get("size", ""),
                "MIME_TYPE": record.get("mime_type", ""),
                "DOCTYPE": record.get("doctype", ""),
                "CUSTODIAN": record.get("custodian") or "",
                "PAGES": metadata.get("pages") or "",
                "CREATEDATE": metadata.get("createdate") or "",
                "MODIFYDATE": metadata.get("modifydate") or "",
                "PRODUCED_AT": record.get("produced_at", ""),
                "PRODUCER": record.get("producer", ""),
            }

            writer.writerow(csv_row)
            row_count += 1

        # Write CSV via storage_port
        csv_content = output.getvalue()
        self.storage.write_text(output_path, csv_content)

        # Log to audit
        self.ledger.log(
            operation="csv_report_build",
            inputs=[str(manifest_path)],
            outputs=[str(output_path)],
            args={},
        )

        return row_count

    def build_impact_report(
        self,
        manifest_path: Path,
        *,
        discovered_count: int | None,
        stages: list[PipelineStage],
        review_rate_low: int = 50,
        review_rate_high: int = 150,
        cost_low: float = 75.0,
        cost_high: float = 200.0,
    ) -> ImpactReport:
        """Build impact discovery report by streaming manifest.

        Computes Sedona Conference-aligned metrics for proportionality negotiation
        by aggregating document metadata from the manifest.

        Args:
            manifest_path: Path to manifest.jsonl
            discovered_count: Total documents discovered (before dedupe), from stage metrics
            stages: Pipeline stages with timing/status
            review_rate_low: Low estimate for documents per hour
            review_rate_high: High estimate for documents per hour
            cost_low: Low hourly cost estimate (USD)
            cost_high: High hourly cost estimate (USD)

        Returns:
            ImpactReport with aggregated metrics
        """
        # Initialize O(1) accumulators
        unique_count = 0
        total_bytes = 0
        by_custodian: dict[str, dict[str, Any]] = {}
        by_doctype: dict[str, dict[str, Any]] = {}
        by_extension: dict[str, int] = {}
        earliest_mtime: str | None = None
        latest_mtime: str | None = None
        size_buckets = {"under_1mb": 0, "1mb_to_10mb": 0, "over_10mb": 0}

        # Stream manifest (O(k) memory where k = distinct categories)
        for record_dict in self.storage.read_jsonl(manifest_path):
            doc = DocumentRecord.model_validate(record_dict)
            unique_count += 1
            total_bytes += doc.size

            # Group by custodian
            custodian = doc.custodian or "unknown"
            if custodian not in by_custodian:
                by_custodian[custodian] = {"count": 0, "size_bytes": 0, "doctypes": {}}
            by_custodian[custodian]["count"] += 1
            by_custodian[custodian]["size_bytes"] += doc.size
            doctype = doc.doctype or "other"
            doctype_dict = by_custodian[custodian]["doctypes"]
            doctype_dict[doctype] = doctype_dict.get(doctype, 0) + 1

            # Group by doctype
            if doctype not in by_doctype:
                by_doctype[doctype] = {"count": 0, "size_bytes": 0}
            by_doctype[doctype]["count"] += 1
            by_doctype[doctype]["size_bytes"] += doc.size

            # Group by extension
            ext = doc.extension.lower()
            by_extension[ext] = by_extension.get(ext, 0) + 1

            # Track date range (min/max only, O(1))
            if doc.mtime:
                if earliest_mtime is None or doc.mtime < earliest_mtime:
                    earliest_mtime = doc.mtime
                if latest_mtime is None or doc.mtime > latest_mtime:
                    latest_mtime = doc.mtime

            # Size buckets
            size_mb = doc.size / (1024 * 1024)
            if size_mb < 1:
                size_buckets["under_1mb"] += 1
            elif size_mb <= 10:
                size_buckets["1mb_to_10mb"] += 1
            else:
                size_buckets["over_10mb"] += 1

        # Compute dedupe metrics
        if discovered_count is not None:
            duplicates_removed = discovered_count - unique_count
            dedupe_rate_pct = (
                (duplicates_removed / discovered_count * 100)
                if discovered_count > 0
                else 0.0
            )
            culling_rationale = f"{duplicates_removed} duplicates removed ({dedupe_rate_pct:.1f}% reduction). Original volume: {discovered_count} documents."
        else:
            duplicates_removed = None
            dedupe_rate_pct = None
            culling_rationale = "Deduplication metrics unavailable (discovered_count not tracked)."

        # Estimated review
        hours_low = unique_count / review_rate_high if review_rate_high > 0 else 0
        hours_high = unique_count / review_rate_low if review_rate_low > 0 else 0
        cost_low_usd = hours_low * cost_low
        cost_high_usd = hours_high * cost_high

        # Date range
        date_range = None
        if earliest_mtime and latest_mtime:
            from datetime import datetime as dt

            earliest_dt = dt.fromisoformat(earliest_mtime.replace("Z", "+00:00"))
            latest_dt = dt.fromisoformat(latest_mtime.replace("Z", "+00:00"))
            span_days = (latest_dt - earliest_dt).days
            date_range = {
                "earliest": earliest_mtime,
                "latest": latest_mtime,
                "span_days": span_days,
            }

        # Stages summary (extract duration, status, detail)
        stages_summary = [
            {
                "name": s.name,
                "status": s.status,
                "duration_seconds": s.duration_seconds,
                "detail": s.detail,
            }
            for s in stages
        ]

        # Error count from failed stages
        error_count = sum(1 for s in stages if s.status == "failed")

        # Build report
        return ImpactReport(
            tool_version=__version__,
            summary={
                "total_discovered": discovered_count,
                "unique_documents": unique_count,
                "duplicates_removed": duplicates_removed,
                "dedupe_rate_pct": dedupe_rate_pct,
                "total_size_bytes": total_bytes,
                "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            },
            estimated_review={
                "hours_low": round(hours_low, 1),
                "hours_high": round(hours_high, 1),
                "cost_low_usd": round(cost_low_usd, 2),
                "cost_high_usd": round(cost_high_usd, 2),
                "assumptions": f"{review_rate_low}-{review_rate_high} docs/hr, ${cost_low:.0f}-${cost_high:.0f}/hr",
            },
            culling_rationale=culling_rationale,
            by_custodian=by_custodian,
            by_doctype=by_doctype,
            by_extension=by_extension,
            date_range=date_range,
            size_distribution=size_buckets,
            stages=stages_summary,
            errors={"count": error_count, "skip_reasons": {}},
            manifest_path=str(manifest_path),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def write_impact_report(self, output: Path, report: ImpactReport) -> None:
        """Write impact report atomically (temp file + replace).

        Args:
            output: Output path for impact report JSON
            report: ImpactReport to write

        Raises:
            IOError: If write fails
        """
        output = output.resolve()

        # Ensure parent directory exists
        output.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write pattern (temp file + os.replace)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=output.parent, prefix=f".{output.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json_str = report.model_dump_json(indent=2)
                f.write(json_str)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, output)
        except Exception:
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise
