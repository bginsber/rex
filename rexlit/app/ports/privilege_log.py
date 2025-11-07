"""Privilege log generation port interfaces and DTOs per EDRM Protocol v2.0."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class PrivilegeLogEntry(BaseModel):
    """Single privilege log entry for a withheld document.

    Follows EDRM Privilege Log Protocol v2.0 metadata-plus schema.
    See: ADR 0008 for field definitions and compliance requirements.
    """

    privlog_id: str = Field(..., description="Sequential privilege log ID (e.g., PRIVID-0001)")
    family_id: str = Field(
        ..., description="Groups related documents (email threads with attachments)"
    )
    prodbeg_doc_num: str = Field(
        ..., description="Bates number that would have been assigned if produced"
    )
    doc_date: str = Field(..., description="Document date (ISO 8601)")
    doc_time: str | None = Field(
        default=None, description="Document time (may be redacted if privileged)"
    )
    from_author: str = Field(..., description="Document author or email sender")
    to: list[str] = Field(default_factory=list, description="Primary recipients")
    cc: list[str] = Field(default_factory=list, description="Carbon copy recipients")
    bcc: list[str] = Field(default_factory=list, description="Blind carbon copy recipients")
    basis_for_claim: str = Field(
        ...,
        description="Privilege basis: 'Attorney-Client Privilege', 'Work Product', or both",
    )
    subject_filename: str | None = Field(
        default=None, description="Email subject or filename (may be redacted if privileged)"
    )
    file_ext: str = Field(..., description="File extension (MSG, PDF, DOCX, etc.)")
    parent_or_attachment: str = Field(
        ..., description="Document role: 'Parent', 'Attachment', or 'N/A'"
    )


class AttorneyList(BaseModel):
    """Known attorneys and law firms for privilege determination.

    Per EDRM Protocol v2.0 Section 9, parties should exchange lists of known
    attorneys, firms, and roles to facilitate privilege log review and reduce
    meet-and-confer burden.
    """

    attorneys: list[str] = Field(
        default_factory=list,
        description="Attorney names with affiliations (e.g., 'Smith, John (in-house)')",
    )
    firms: list[str] = Field(
        default_factory=list, description="Law firm names (e.g., 'Jones & Associates LLP')"
    )
    roles: dict[str, str] = Field(
        default_factory=dict,
        description="Email to role mapping (e.g., {'john.smith@example.com': 'in-house'})",
    )


class PrivilegeLogMetadata(BaseModel):
    """Metadata about the generated privilege log."""

    output_path: Path = Field(..., description="Path to generated privilege log file")
    format: Literal["excel", "csv"] = Field(..., description="Output format")
    entry_count: int = Field(..., description="Total number of log entries")
    family_count: int = Field(..., description="Number of document families")
    cumulative: bool = Field(
        ..., description="Whether log includes entries from previous logs"
    )
    protocol_version: str = Field(default="EDRM 2.0", description="EDRM protocol version")
    previous_log: Path | None = Field(
        default=None, description="Path to previous log if cumulative"
    )


class PrivilegeLogPort(Protocol):
    """Port interface for generating EDRM-compliant privilege logs.

    Implementations must support:
    - Metadata-plus log format per EDRM Protocol v2.0 Section 6
    - Excel and CSV export formats
    - Cumulative and incremental log generation (EDRM Section 2, 8)
    - Attorney/firm list export (EDRM Section 9)
    - Deterministic PrivLog ID assignment for reproducibility
    """

    def generate_log(
        self,
        index_path: Path,
        output_path: Path,
        *,
        format: Literal["excel", "csv"] = "excel",
        cumulative: bool = True,
        previous_log: Path | None = None,
    ) -> PrivilegeLogMetadata:
        """Generate privilege log from withheld documents in index.

        Queries index for documents marked as withheld (withheld=true), builds
        family groups, assigns sequential PrivLog IDs, and exports to Excel or CSV
        following EDRM metadata-plus schema.

        Args:
            index_path: Path to Tantivy index containing document metadata
            output_path: Path to write privilege log (Excel or CSV)
            format: Output format ("excel" or "csv")
            cumulative: Include all entries from previous_log (rolling production)
            previous_log: Path to previous privilege log (required if cumulative=True)

        Returns:
            PrivilegeLogMetadata with generation details

        Raises:
            FileNotFoundError: If index or previous_log doesn't exist
            ValueError: If cumulative=True but previous_log is None
        """
        ...

    def generate_attorney_lists(
        self,
        index_path: Path,
        output_path: Path,
    ) -> AttorneyList:
        """Export attorney and law firm lists per EDRM Section 9.

        Extracts unique attorneys and firms from withheld document metadata
        and exports to CSV for exchange with opposing counsel.

        Args:
            index_path: Path to Tantivy index
            output_path: Path to write attorney lists CSV

        Returns:
            AttorneyList with attorneys, firms, and roles
        """
        ...

    def validate_log(
        self,
        log_path: Path,
    ) -> tuple[bool, str | None]:
        """Validate privilege log against EDRM schema.

        Checks:
        - Required columns present
        - PrivLog IDs are sequential and unique
        - Family IDs are consistent
        - Bates numbers are valid format
        - Basis for claim is valid value

        Args:
            log_path: Path to privilege log file (Excel or CSV)

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        ...
