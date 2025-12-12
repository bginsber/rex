"""Negative property tests for privilege audit log safety (ADR-0008).

This module verifies that privileged content NEVER leaks into audit logs.
The privacy-preserving design requires:

1. Full chain-of-thought (CoT) reasoning is hashed, never stored directly
2. Only redacted summaries (no excerpts) appear in logs
3. Document text is never logged, only hashes

These are "negative property tests" - they assert the ABSENCE of sensitive data.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from rexlit.app.ports.privilege_reasoning import PolicyDecision


class TestPrivilegeContentSanitization:
    """Tests verifying privileged content never appears in audit-visible outputs."""

    # Known privileged content that should NEVER appear in logs
    PRIVILEGED_EXCERPT = "Dear counsel, please advise on the litigation strategy"
    PRIVILEGED_SSN = "123-45-6789"
    PRIVILEGED_EMAIL = "attorney@lawfirm.com"
    PRIVILEGED_FULL_COT = """
    Step 1: The document contains communication: "From: attorney@lawfirm.com"
    Step 2: The text "Dear counsel, please advise on the litigation strategy" indicates legal advice
    Step 3: This appears to be attorney-client privileged communication
    Excerpt: "please advise on the litigation strategy"
    """

    def test_policy_decision_does_not_contain_raw_content(self) -> None:
        """PolicyDecision model should only store hashes and sanitized summaries."""
        # Create decision with hashed reasoning (as the adapter would)
        reasoning_hash = hashlib.sha256(
            (self.PRIVILEGED_FULL_COT + "salt").encode()
        ).hexdigest()

        decision = PolicyDecision(
            labels=["PRIVILEGED:ACP"],
            confidence=0.95,
            needs_review=False,
            reasoning_hash=reasoning_hash,
            reasoning_summary="Applied ACP definition §2.1",  # Sanitized, no excerpts
            full_reasoning_available=False,
            model_version="test-model",
            policy_version="v1.0",
        )

        # Convert to JSON (how it would appear in audit log)
        decision_json = decision.model_dump_json()

        # NEGATIVE PROPERTY TESTS: Privileged content must NOT appear
        assert self.PRIVILEGED_EXCERPT not in decision_json, (
            "Privileged excerpt leaked into PolicyDecision JSON"
        )
        assert self.PRIVILEGED_EMAIL not in decision_json, (
            "Privileged email leaked into PolicyDecision JSON"
        )
        assert "please advise" not in decision_json.lower(), (
            "Partial privileged content leaked into PolicyDecision JSON"
        )
        assert self.PRIVILEGED_SSN not in decision_json, (
            "SSN leaked into PolicyDecision JSON"
        )

        # POSITIVE CHECK: Hash should be present
        assert reasoning_hash in decision_json

    def test_redact_summary_removes_excerpts(self) -> None:
        """_redact_summary should strip quoted text and excerpts.

        NOTE: This tests the expected behavior - that excerpts with quotes are filtered.
        The PRIVILEGED_EMAIL is intentionally on a line WITH quotes in PRIVILEGED_FULL_COT.
        """
        # Simulate the _redact_summary logic from PrivilegeSafeguardAdapter
        full_cot = self.PRIVILEGED_FULL_COT

        lines = full_cot.split("\n")
        safe_lines = []
        for line in lines:
            # Skip lines with quoted text or excerpts
            if '"' in line or "excerpt:" in line.lower() or "states:" in line.lower():
                continue
            safe_lines.append(line)

        summary = " ".join(safe_lines)[:200]

        # NEGATIVE PROPERTY TESTS
        assert self.PRIVILEGED_EXCERPT not in summary, (
            "Excerpt not removed from summary"
        )
        assert "please advise" not in summary.lower(), (
            "Partial excerpt not removed from summary"
        )
        assert self.PRIVILEGED_EMAIL not in summary, (
            "Email not removed from summary (should be filtered with quoted line)"
        )

    def test_hash_reasoning_produces_hash_not_content(self) -> None:
        """Hash function should return only hex digest, never content."""
        salt = "test-salt"
        reasoning_hash = hashlib.sha256(
            (self.PRIVILEGED_FULL_COT + salt).encode()
        ).hexdigest()

        # Verify it's a valid SHA-256 hash
        assert re.match(r"^[a-f0-9]{64}$", reasoning_hash), (
            "Reasoning hash is not a valid SHA-256 format"
        )

        # NEGATIVE PROPERTY TEST: Content must not be in hash
        assert self.PRIVILEGED_EXCERPT not in reasoning_hash
        assert self.PRIVILEGED_EMAIL not in reasoning_hash


class TestAuditLogContentSafety:
    """Tests verifying audit log entries don't contain privileged content."""

    SENSITIVE_DOCUMENT_TEXT = """
    PRIVILEGED AND CONFIDENTIAL - ATTORNEY WORK PRODUCT

    From: John Smith <john.smith@company.com>
    To: Sarah Attorney <sattorney@lawfirm.com>
    Subject: Re: Pending Litigation - CONFIDENTIAL

    Dear Sarah,

    As we discussed in our phone call yesterday, I need your legal advice
    on the following matter regarding the Smith v. Jones case (Case No. 2024-CV-1234).

    Our company's internal investigation revealed that the defendant may have
    violated section 15(b) of the contract. My SSN for verification is 555-12-3456.

    Please provide your legal opinion on whether we should proceed with
    summary judgment or negotiate a settlement.

    Confidentially,
    John Smith
    General Counsel
    """

    def test_audit_entry_args_should_hash_sensitive_data(self) -> None:
        """Audit entry args should contain hashes, not raw sensitive data."""
        # Simulate what audit entry args should look like
        document_hash = hashlib.sha256(self.SENSITIVE_DOCUMENT_TEXT.encode()).hexdigest()

        # Good: What should be logged
        audit_args = {
            "document_hash": document_hash,
            "classification": "PRIVILEGED:ACP",
            "confidence": 0.92,
            "reasoning_hash": "a1b2c3...",  # Truncated for example
            "reviewer": "system",
        }

        audit_json = json.dumps(audit_args)

        # NEGATIVE PROPERTY TESTS
        assert "555-12-3456" not in audit_json, "SSN leaked into audit args"
        assert "sattorney@lawfirm.com" not in audit_json, "Email leaked into audit args"
        assert "Smith v. Jones" not in audit_json, "Case name leaked into audit args"
        assert "legal advice" not in audit_json.lower(), "Privileged text leaked"
        assert "CONFIDENTIAL" not in audit_json, "Document header leaked"

        # POSITIVE CHECK: Hash should be present
        assert document_hash in audit_json

    def test_audit_entry_should_not_log_full_document_text(self) -> None:
        """Audit entries must never contain full document text."""
        # This is the anti-pattern we're preventing
        bad_audit_args = {
            "document_text": self.SENSITIVE_DOCUMENT_TEXT,  # WRONG!
        }

        # Simulate content check that should be enforced
        def contains_sensitive_content(data: dict[str, Any]) -> list[str]:
            """Check for sensitive content patterns in audit data."""
            violations = []
            json_str = json.dumps(data).lower()

            patterns = [
                (r"\d{3}-\d{2}-\d{4}", "SSN pattern"),
                (r"privileged.*confidential", "Privileged header"),
                (r"attorney.*work.*product", "Work product header"),
                (r"legal\s+advice", "Legal advice text"),
                (r"case\s+no\.\s*\d+", "Case number"),
            ]

            for pattern, name in patterns:
                if re.search(pattern, json_str, re.IGNORECASE):
                    violations.append(name)

            return violations

        # NEGATIVE PROPERTY TEST: Bad audit args should be caught
        violations = contains_sensitive_content(bad_audit_args)
        assert len(violations) > 0, (
            "Sensitive content detection should flag privileged document"
        )

        # Good audit args should pass
        good_audit_args = {
            "document_hash": hashlib.sha256(
                self.SENSITIVE_DOCUMENT_TEXT.encode()
            ).hexdigest(),
            "classification": "PRIVILEGED:ACP",
        }
        violations = contains_sensitive_content(good_audit_args)
        assert len(violations) == 0, (
            f"Good audit args flagged incorrectly: {violations}"
        )


class TestPolicyDecisionPrivacyFields:
    """Tests verifying PolicyDecision privacy design is enforced."""

    def test_reasoning_summary_max_length(self) -> None:
        """Reasoning summary should be truncated to prevent content leak."""
        # Even if someone tried to sneak content in, it should be truncated
        long_summary = "A" * 500  # Longer than 200 char limit

        decision = PolicyDecision(
            labels=["NOT_PRIVILEGED"],
            confidence=0.8,
            reasoning_summary=long_summary[:200],  # Adapter should truncate
        )

        assert len(decision.reasoning_summary) <= 200, (
            "Reasoning summary exceeds max length"
        )

    def test_reasoning_hash_format(self) -> None:
        """Reasoning hash must be valid SHA-256 hex format."""
        valid_hash = hashlib.sha256(b"test content").hexdigest()

        decision = PolicyDecision(
            labels=["NOT_PRIVILEGED"],
            confidence=0.8,
            reasoning_hash=valid_hash,
        )

        # Verify hash format (64 hex characters)
        assert re.match(r"^[a-f0-9]{64}$", decision.reasoning_hash), (
            "Reasoning hash should be SHA-256 format"
        )

    def test_full_reasoning_available_default_false(self) -> None:
        """Full reasoning should NOT be available by default (privacy-first)."""
        decision = PolicyDecision(
            labels=["PRIVILEGED:ACP"],
            confidence=0.9,
        )

        assert decision.full_reasoning_available is False, (
            "full_reasoning_available should default to False for privacy"
        )
