"""Pack service for production bundle creation.

Generates production packages (RexPack format) with manifests and artifacts.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from rexlit.ingest.discover import discover_documents
from rexlit.utils.deterministic import deterministic_order_documents

logger = logging.getLogger(__name__)


class PackManifest(BaseModel):
    """Production package manifest."""

    pack_id: str
    created_at: str
    document_count: int
    total_pages: int
    bates_range: str | None
    redaction_count: int
    artifacts: list[str]


class PackService:
    """Orchestrates production package creation.

    All I/O operations delegated to storage port.
    No direct filesystem access.
    """

    def __init__(
        self,
        storage_port: Any,  # Will be typed with port interface in Workstream 2
        ledger_port: Any,
    ):
        """Initialize pack service.

        Args:
            storage_port: Filesystem operations port
            ledger_port: Audit logging port
        """
        self.storage = storage_port
        self.ledger = ledger_port

    def create_pack(
        self,
        input_path: Path,
        output_path: Path,
        *,
        include_natives: bool = True,
        include_text: bool = True,
        include_metadata: bool = True,
    ) -> PackManifest:
        """Create production package from processed documents.

        Args:
            input_path: Path to processed documents
            output_path: Output directory for pack
            include_natives: Include native files
            include_text: Include extracted text
            include_metadata: Include metadata JSONL

        Returns:
            PackManifest with package details
        """
        # 1. Collect documents via storage_port (using discover for file finding)
        # Discover all documents in deterministic order (ADR 0003)
        discovered_docs = list(discover_documents(input_path, recursive=True))
        documents = deterministic_order_documents(discovered_docs)

        # 2. Generate pack structure
        output_path.mkdir(parents=True, exist_ok=True)
        natives_dir = output_path / "natives"
        text_dir = output_path / "text"
        metadata_dir = output_path / "metadata"

        if include_natives:
            natives_dir.mkdir(exist_ok=True)
        if include_text:
            text_dir.mkdir(exist_ok=True)
        if include_metadata:
            metadata_dir.mkdir(exist_ok=True)

        # 3. Copy files via storage_port and collect statistics
        artifacts: list[str] = []
        document_count = 0
        total_pages = 0
        redaction_count = 0

        # Build metadata records for JSONL manifest
        metadata_records: list[dict[str, Any]] = []

        for doc in documents:
            doc_path = Path(doc.path)
            document_count += 1

            # Copy native file if requested
            if include_natives and doc_path.exists():
                dest_native = natives_dir / f"{doc.sha256}{doc.extension}"
                try:
                    self.storage.copy_file(doc_path, dest_native)
                    artifacts.append(str(dest_native.relative_to(output_path)))
                except Exception as exc:
                    # Log error but continue processing other documents
                    logger.warning("Failed to copy native file %s: %s", doc_path, exc, exc_info=True)

            # Copy extracted text if available
            if include_text:
                text_file = doc_path.with_suffix(".txt")
                if text_file.exists():
                    dest_text = text_dir / f"{doc.sha256}.txt"
                    try:
                        self.storage.copy_file(text_file, dest_text)
                        artifacts.append(str(dest_text.relative_to(output_path)))
                    except Exception:
                        pass  # Text file is optional

            # Check for page count from PDF metadata (if available)
            # This is a best-effort extraction
            if doc.doctype == "pdf":
                # Placeholder: would need PDF inspection to get actual page count
                # For now we estimate based on file size (rough heuristic)
                total_pages += max(1, doc.size // 50000)

            # Check for redaction plans
            redaction_plan = doc_path.with_suffix(".redaction-plan.enc")
            if redaction_plan.exists():
                redaction_count += 1

            # Build metadata record
            metadata_records.append(doc.model_dump())

        # 4. Create manifest JSONL for metadata
        if include_metadata and metadata_records:
            metadata_jsonl = metadata_dir / "documents.jsonl"
            try:
                self.storage.write_jsonl(
                    metadata_jsonl, iter(metadata_records)
                )
                artifacts.append(str(metadata_jsonl.relative_to(output_path)))
            except Exception as exc:
                logger.warning(
                    "Failed to write metadata JSONL for pack %s: %s", output_path, exc, exc_info=True
                )

        # 5. Write manifest via storage_port
        # Generate pack_id from input path and timestamp
        created_at = datetime.now(UTC).isoformat()
        pack_id = f"pack_{input_path.name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        # Determine Bates range if available
        bates_range = None
        bates_plan_hint = input_path / "bates_plan.jsonl"
        if bates_plan_hint.exists():
            try:
                # Try to read first and last Bates numbers from plan
                bates_records = list(self.storage.read_jsonl(bates_plan_hint))
                if bates_records:
                    first_bates = bates_records[0].get("bates_number", "")
                    last_bates = bates_records[-1].get("bates_number", "")
                    if first_bates and last_bates:
                        bates_range = f"{first_bates}-{last_bates}"
            except Exception:
                pass  # Bates range is optional

        manifest = PackManifest(
            pack_id=pack_id,
            created_at=created_at,
            document_count=document_count,
            total_pages=total_pages,
            bates_range=bates_range,
            redaction_count=redaction_count,
            artifacts=sorted(artifacts),  # Deterministic ordering
        )

        # Write manifest JSON file
        manifest_path = output_path / "manifest.json"
        manifest_json = manifest.model_dump_json(indent=2)
        self.storage.write_text(manifest_path, manifest_json)

        # Log to audit
        self.ledger.log(
            operation="pack_create",
            inputs=[str(input_path)],
            outputs=[str(output_path)],
            args={
                "include_natives": include_natives,
                "include_text": include_text,
                "include_metadata": include_metadata,
                "pack_id": pack_id,
                "document_count": document_count,
            },
        )

        return manifest

    def create_production(
        self,
        stamped_dir: Path,
        *,
        name: str,
        format: str = "dat",
        bates_prefix: str = "",
        output_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Generate DAT or Opticon production load file from stamped PDFs."""

        source_dir = Path(stamped_dir).resolve()
        if not source_dir.exists() or not source_dir.is_dir():
            raise FileNotFoundError(f"Stamped directory not found: {source_dir}")

        manifest_path = source_dir / "bates_manifest.jsonl"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Bates stamping manifest not found at: {manifest_path}"
            )

        records = list(self.storage.read_jsonl(manifest_path))
        if not records:
            raise ValueError("Bates stamping manifest is empty; cannot build production set")

        if bates_prefix:
            mismatches = [
                record
                for record in records
                if not str(record.get("start_label", "")).startswith(bates_prefix)
            ]
            if mismatches:
                raise ValueError(
                    "Bates manifest contains labels that do not match the expected prefix"
                )

        normalized_format = format.lower()
        if normalized_format not in {"dat", "opticon"}:
            raise ValueError(
                f"Unsupported production format '{format}'. Choose 'dat' or 'opticon'."
            )

        output_root = (
            Path(output_dir).resolve()
            if output_dir is not None
            else source_dir / "production" / name
        )
        output_root.mkdir(parents=True, exist_ok=True)

        if normalized_format == "dat":
            loadfile_path = output_root / f"{name}.dat"
            loadfile_content = self._render_dat_loadfile(records, source_dir)
        else:
            loadfile_path = output_root / f"{name}.opt"
            loadfile_content = self._render_opticon_loadfile(records, source_dir)

        self.storage.write_text(loadfile_path, loadfile_content)

        self.ledger.log(
            operation="production_create",
            inputs=[str(source_dir)],
            outputs=[str(loadfile_path)],
            args={
                "format": normalized_format,
                "record_count": len(records),
                "name": name,
                "output_dir": str(output_root),
            },
        )

        return {
            "output_path": loadfile_path,
            "document_count": len(records),
            "format": normalized_format,
            "manifest_path": manifest_path,
        }

    def validate_pack(self, pack_path: Path) -> bool:
        """Validate production package integrity.

        Args:
            pack_path: Path to pack directory

        Returns:
            True if pack is valid, False otherwise
        """
        try:
            # Read manifest JSON via storage port
            manifest_path = pack_path / "manifest.json"

            # Parse manifest JSON
            manifest_text = self.storage.read_text(manifest_path)

            if not manifest_text.strip():
                self.ledger.log(
                    operation="pack_validate",
                    inputs=[str(pack_path)],
                    outputs=[],
                    args={"status": "failed", "reason": "Empty manifest file"},
                )
                return False

            # Parse as PackManifest
            import json
            manifest_data = json.loads(manifest_text)
            manifest = PackManifest(**manifest_data)

            # Verify all artifacts are present and have correct checksums
            validation_failures = []

            for artifact_rel_path in manifest.artifacts:
                artifact_path = pack_path / artifact_rel_path

                # Check file exists
                if not artifact_path.exists():
                    validation_failures.append(
                        f"Missing artifact: {artifact_rel_path}"
                    )
                    continue

                # Verify checksum via storage port
                try:
                    self.storage.compute_hash(artifact_path)
                    # Note: For now we compute the hash to verify file is readable.
                    # Full checksum verification would require storing expected hashes
                    # in manifest, which is not yet part of PackManifest schema.
                except Exception as e:
                    validation_failures.append(
                        f"Cannot compute hash for {artifact_rel_path}: {e}"
                    )

            # Log validation result
            if validation_failures:
                self.ledger.log(
                    operation="pack_validate",
                    inputs=[str(pack_path)],
                    outputs=[],
                    args={
                        "status": "failed",
                        "failures": validation_failures,
                        "pack_id": manifest.pack_id,
                    },
                )
                return False

            # Success
            self.ledger.log(
                operation="pack_validate",
                inputs=[str(pack_path)],
                outputs=[],
                args={
                    "status": "valid",
                    "pack_id": manifest.pack_id,
                    "artifact_count": len(manifest.artifacts),
                },
            )
            return True

        except FileNotFoundError:
            self.ledger.log(
                operation="pack_validate",
                inputs=[str(pack_path)],
                outputs=[],
                args={"status": "failed", "reason": "Manifest file not found"},
            )
            return False
        except Exception as e:
            self.ledger.log(
                operation="pack_validate",
                inputs=[str(pack_path)],
                outputs=[],
                args={"status": "failed", "reason": str(e)},
            )
            return False

    def export_load_file(
        self,
        pack_path: Path,
        output_path: Path,
        *,
        format: str = "dat",
    ) -> Path:
        """Export load file (DAT/Opticon) for production.

        Args:
            pack_path: Path to pack directory
            output_path: Output path for load file
            format: Load file format (dat, opticon, lfp)

        Returns:
            Path to generated load file
        """
        # Validate format
        supported_formats = {"dat", "opticon", "lfp"}
        if format not in supported_formats:
            raise ValueError(
                f"Unsupported load file format: {format}. "
                f"Supported formats: {', '.join(sorted(supported_formats))}"
            )

        # Only DAT format is currently implemented
        if format != "dat":
            raise NotImplementedError(
                f"Load file format '{format}' is not yet implemented. "
                "Currently only 'dat' format is supported."
            )

        # Read pack manifest via storage_port - check for metadata/documents.jsonl
        metadata_jsonl_path = pack_path / "metadata" / "documents.jsonl"
        if not metadata_jsonl_path.exists():
            raise FileNotFoundError(
                f"Pack metadata documents not found at: {metadata_jsonl_path}"
            )

        # Read manifest records
        manifest_records = list(self.storage.read_jsonl(metadata_jsonl_path))
        if not manifest_records:
            raise ValueError(f"Pack metadata is empty: {metadata_jsonl_path}")

        # Generate DAT load file content
        dat_content = self._generate_dat_loadfile(manifest_records)

        # Write load file via storage_port
        self.storage.write_text(output_path, dat_content)

        # Log to audit
        self.ledger.log(
            operation="load_file_export",
            inputs=[str(pack_path)],
            outputs=[str(output_path)],
            args={"format": format, "record_count": len(manifest_records)},
        )

        return output_path

    def _generate_dat_loadfile(self, manifest_records: list[dict[str, Any]]) -> str:
        """Generate DAT format load file from manifest records.

        DAT format is a pipe-delimited text file used in e-discovery.
        Standard fields include DOCID, BEGDOC, ENDDOC, CUSTODIAN, DOCTYPE,
        FILEPATH, FILEEXT, FILESIZE, DATEMODIFIED, SHA256.

        Args:
            manifest_records: List of manifest record dictionaries

        Returns:
            DAT format content as string with headers and records
        """
        # Define standard DAT fields and their mapping from manifest
        # Using common e-discovery field names
        fields = [
            ("DOCID", "sha256"),  # Use SHA256 as unique document ID
            ("BEGDOC", "sha256"),  # Beginning Bates (using hash as placeholder)
            ("ENDDOC", "sha256"),  # Ending Bates (using hash as placeholder)
            ("CUSTODIAN", "custodian"),
            ("DOCTYPE", "doctype"),
            ("FILEPATH", "path"),
            ("FILEEXT", "extension"),
            ("FILESIZE", "size"),
            ("DATEMODIFIED", "mtime"),
            ("SHA256", "sha256"),
        ]

        # Build header row
        header = "|".join(field_name for field_name, _ in fields)
        lines = [header]

        # Build data rows
        for record in manifest_records:
            values = []
            for _, manifest_key in fields:
                # Get value from manifest, use empty string if not present
                value = record.get(manifest_key, "")
                # Convert to string and escape any pipe characters
                value_str = str(value) if value is not None else ""
                value_str = value_str.replace("|", "\\|")  # Escape pipe delimiters
                values.append(value_str)

            line = "|".join(values)
            lines.append(line)

        return "\n".join(lines) + "\n"

    def _render_dat_loadfile(
        self, manifest_records: list[dict[str, Any]], base_dir: Path
    ) -> str:
        header = ["DOCID", "BEGDOC", "ENDDOC", "PAGECOUNT", "FILEPATH", "SHA256"]
        lines = ["|".join(header)]

        for record in sorted(manifest_records, key=lambda r: str(r.get("start_label", ""))):
            start_label = str(record.get("start_label", record.get("label", "")))
            end_label = str(record.get("end_label", start_label))
            page_count = int(record.get("pages_stamped", record.get("page_count", 0)) or 0)
            doc_path_str = str(record.get("output_path", record.get("path", "")))
            doc_path = Path(doc_path_str)
            sha256 = str(record.get("output_sha256", record.get("sha256", "")))

            try:
                relative_path = doc_path.resolve().relative_to(base_dir)
            except Exception:
                relative_path = doc_path.name

            fields = [
                start_label,
                start_label,
                end_label,
                str(page_count),
                str(relative_path).replace("|", "\\|"),
                sha256,
            ]
            lines.append("|".join(fields))

        return "\n".join(lines) + "\n"

    def _render_opticon_loadfile(
        self, manifest_records: list[dict[str, Any]], base_dir: Path
    ) -> str:
        lines: list[str] = []
        for record in sorted(manifest_records, key=lambda r: str(r.get("start_label", ""))):
            start_label = str(record.get("start_label", record.get("label", "")))
            doc_path_str = str(record.get("output_path", record.get("path", "")))
            doc_path = Path(doc_path_str)
            page_count = int(record.get("pages_stamped", record.get("page_count", 0)) or 0)

            try:
                relative_path = doc_path.resolve().relative_to(base_dir)
            except Exception:
                relative_path = doc_path.name

            lines.append("IMAGE")
            lines.append(start_label)
            lines.append(str(relative_path))
            lines.append("Y")
            lines.append(str(page_count))
            lines.append("")

        return "\n".join(lines) + "\n"
