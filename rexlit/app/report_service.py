"""Report service for generating production reports.

Read-only service that consumes manifests and artifacts to generate reports.
"""

import csv
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ReportMetadata(BaseModel):
    """Metadata for generated report."""

    title: str
    generated_at: str
    document_count: int
    total_pages: int
    redaction_count: int
    bates_range: str | None


class ReportService:
    """Read-only report generation service.

    Consumes manifests and artifacts without modifying them.
    All file I/O is delegated to storage port.
    """

    def __init__(
        self,
        storage_port: Any,  # Will be typed with port interface in Workstream 2
        ledger_port: Any,
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
            path = doc.get("path", "Unknown")
            filename = Path(path).name
            size = doc.get("size", 0)
            size_kb = f"{size / 1024:.1f} KB" if size else "0 KB"
            mime_type = doc.get("mime_type", "Unknown")
            custodian = doc.get("custodian", "N/A")
            doctype = doc.get("doctype", "N/A")
            sha256 = doc.get("sha256", "N/A")
            sha256_short = sha256[:16] + "..." if len(sha256) > 16 else sha256
            bates = doc.get("bates_number", "N/A")
            pages = doc.get("metadata", {}).get("pages") or "N/A"

            # Optional thumbnail column
            thumbnail_cell = ""
            if include_thumbnails:
                thumbnail_cell = "<td>[Thumbnail]</td>"

            doc_rows.append(
                f"""
                <tr>
                    <td>{idx}</td>
                    <td title="{path}">{filename}</td>
                    <td>{size_kb}</td>
                    <td>{mime_type}</td>
                    <td>{custodian}</td>
                    <td>{doctype}</td>
                    <td>{pages}</td>
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
        html = f"""<!DOCTYPE html>
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
                <div class="value" style="font-size: 16px;">{bates_range or "N/A"}</div>
            </div>
            <div class="summary-card">
                <h3>Date Range</h3>
                <div class="value" style="font-size: 16px;">{date_range or "N/A"}</div>
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

        return html

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
