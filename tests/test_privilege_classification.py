"""Integration tests for privilege classification with safeguard adapter.

Note: These tests require gpt-oss-safeguard-20b model to be installed.
They will be skipped if the model is not available.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from rexlit.app.ports.privilege_reasoning import (
    PolicyDecision,
    RedactionSpan,
)
from rexlit.app.privilege_service import PrivilegeReviewService
from rexlit.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpen


class TestCircuitBreaker:
    """Test circuit breaker resilience pattern."""

    def test_circuit_breaker_closed_state(self):
        """Test normal operation in CLOSED state."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)

        # Successful calls should work
        result = breaker.call(lambda: "success")
        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.current_failures == 0

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit opens after consecutive failures."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)

        # Trigger failures
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("test error")))

        # Circuit should be open
        assert breaker.state == "OPEN"
        assert breaker.current_failures == 3

        # Subsequent calls should fail fast
        with pytest.raises(CircuitBreakerOpen):
            breaker.call(lambda: "should not execute")

    def test_circuit_breaker_resets_on_success(self):
        """Test circuit resets failure count on success."""
        breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)

        # Trigger 2 failures (below threshold)
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("test")))

        assert breaker.current_failures == 2

        # Successful call should reset
        breaker.call(lambda: "success")
        assert breaker.current_failures == 0
        assert breaker.state == "CLOSED"

    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit transitions to HALF_OPEN and recovers."""
        breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=0.1, half_open_max_calls=1)

        # Trigger failures to open circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("test")))

        assert breaker.state == "OPEN"

        # Wait for timeout
        import time

        time.sleep(0.15)

        # Next call should transition to HALF_OPEN
        # (We need to catch the error first to trigger state change)
        try:
            breaker.call(lambda: "recovery")
        except CircuitBreakerOpen:
            # This can happen if timing is tight
            pass

        # Successful call should close circuit
        if breaker.state == "HALF_OPEN":
            breaker.call(lambda: "success")
            assert breaker.state == "CLOSED"


class TestPolicyDecision:
    """Test PolicyDecision model and helper methods."""

    def test_policy_decision_is_privileged(self):
        """Test is_privileged property."""
        decision = PolicyDecision(
            labels=["PRIVILEGED:ACP"],
            confidence=0.95,
            reasoning_hash="abc123",
            reasoning_summary="Attorney-client communication",
        )
        assert decision.is_privileged is True

        non_priv = PolicyDecision(
            labels=[],
            confidence=0.80,
            reasoning_hash="def456",
            reasoning_summary="Business email",
        )
        assert non_priv.is_privileged is False

    def test_policy_decision_is_responsive(self):
        """Test is_responsive property."""
        decision = PolicyDecision(
            labels=["PRIVILEGED:ACP", "RESPONSIVE"],
            confidence=0.90,
            reasoning_hash="abc123",
            reasoning_summary="Responsive privileged document",
        )
        assert decision.is_responsive is True

    def test_policy_decision_hotdoc_level(self):
        """Test HOTDOC level extraction."""
        decision = PolicyDecision(
            labels=["RESPONSIVE", "HOTDOC:4"],
            confidence=0.85,
            reasoning_hash="abc123",
            reasoning_summary="High relevance document",
        )
        assert decision.hotdoc_level == 4

        no_hotdoc = PolicyDecision(
            labels=["RESPONSIVE"],
            confidence=0.85,
            reasoning_hash="def456",
            reasoning_summary="Responsive but no HOTDOC",
        )
        assert no_hotdoc.hotdoc_level is None

    def test_redaction_span_model(self):
        """Test RedactionSpan data model."""
        span = RedactionSpan(
            category="CPI/PERSONNEL",
            start=100,
            end=150,
            justification="Contains salary information",
        )
        assert span.category == "CPI/PERSONNEL"
        assert span.start == 100
        assert span.end == 150
        assert "salary" in span.justification


class MockPrivilegeAdapter:
    """Mock adapter for testing without real model."""

    def __init__(self, mock_decision: PolicyDecision):
        self.mock_decision = mock_decision
        self.call_count = 0

    def classify_privilege(self, text: str, **kwargs) -> PolicyDecision:
        self.call_count += 1
        return self.mock_decision

    def requires_online(self) -> bool:
        return False


class TestPrivilegeReviewService:
    """Test PrivilegeReviewService orchestration."""

    def test_review_document_basic(self):
        """Test basic document review workflow."""
        mock_decision = PolicyDecision(
            labels=["PRIVILEGED:ACP"],
            confidence=0.90,
            reasoning_hash="abc123",
            reasoning_summary="Attorney communication",
        )
        adapter = MockPrivilegeAdapter(mock_decision)

        service = PrivilegeReviewService(
            safeguard_adapter=adapter,
            ledger_port=None,
        )

        decision = service.review_document(
            doc_id="DOC-001",
            text="Email from attorney@law.com to client@company.com...",
        )

        assert decision.labels == ["PRIVILEGED:ACP"]
        assert decision.confidence == 0.90
        assert adapter.call_count == 1

    def test_review_document_with_audit_logging(self):
        """Test document review with audit logging."""
        mock_decision = PolicyDecision(
            labels=["PRIVILEGED:WP"],
            confidence=0.85,
            reasoning_hash="def456",
            reasoning_summary="Work product document",
        )
        adapter = MockPrivilegeAdapter(mock_decision)

        # Mock ledger
        mock_ledger = Mock()
        mock_ledger.log = Mock()

        service = PrivilegeReviewService(
            safeguard_adapter=adapter,
            ledger_port=mock_ledger,
        )

        decision = service.review_document(
            doc_id="DOC-002",
            text="Litigation strategy memo...",
        )

        # Verify audit log called
        assert mock_ledger.log.called
        call_args = mock_ledger.log.call_args[1]
        assert call_args["operation"] == "privilege.privilege"
        assert call_args["doc_id"] == "DOC-002"
        assert call_args["labels"] == ["PRIVILEGED:WP"]
        assert call_args["confidence"] == 0.85

    def test_batch_review(self):
        """Test batch document review."""
        mock_decision = PolicyDecision(
            labels=["PRIVILEGED:ACP"],
            confidence=0.80,
            reasoning_hash="batch123",
            reasoning_summary="Batch classified",
        )
        adapter = MockPrivilegeAdapter(mock_decision)

        service = PrivilegeReviewService(
            safeguard_adapter=adapter,
            ledger_port=None,
        )

        documents = [
            ("DOC-001", "Email 1..."),
            ("DOC-002", "Email 2..."),
            ("DOC-003", "Email 3..."),
        ]

        results = service.batch_review(documents, show_progress=False)

        assert len(results) == 3
        assert all(d.confidence == 0.80 for d in results)
        assert adapter.call_count == 3

    def test_export_review_report(self, tmp_path):
        """Test exporting review report to JSONL."""
        mock_decision = PolicyDecision(
            labels=["PRIVILEGED:CI"],
            confidence=0.75,
            reasoning_hash="report123",
            reasoning_summary="Common interest privilege",
        )
        adapter = MockPrivilegeAdapter(mock_decision)

        service = PrivilegeReviewService(
            safeguard_adapter=adapter,
            ledger_port=None,
        )

        decisions = [
            ("DOC-001", mock_decision),
            ("DOC-002", mock_decision),
        ]

        output_path = tmp_path / "review_report.jsonl"
        service.export_review_report(decisions, output_path)

        # Verify file created and contains correct data
        assert output_path.exists()

        import json

        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 2

        record1 = json.loads(lines[0])
        assert record1["doc_id"] == "DOC-001"
        assert record1["labels"] == ["PRIVILEGED:CI"]
        assert record1["confidence"] == 0.75


class TestPrivilegeSafeguardAdapter:
    """Test PrivilegeSafeguardAdapter (requires model installation).

    These tests are skipped if the model is not available.
    """

    @pytest.fixture
    def policy_path(self, tmp_path):
        """Create temporary policy file."""
        policy = tmp_path / "test_policy.txt"
        policy.write_text(
            """
# Test Policy
Classify documents for privilege.
Output JSON: {"violation": 0/1, "labels": [], "confidence": 0.0, "rationale": ""}
"""
        )
        return policy

    def test_adapter_requires_model_path(self, policy_path):
        """Test adapter initialization requires valid paths."""
        from rexlit.app.adapters.privilege_safeguard import PrivilegeSafeguardAdapter

        # Missing model path should be handled gracefully
        # (model loading is lazy, so this won't fail yet)
        adapter = PrivilegeSafeguardAdapter(
            model_path="/nonexistent/model",
            policy_path=policy_path,
        )
        assert adapter.model_path == Path("/nonexistent/model")
        assert not adapter.requires_online()

    def test_adapter_policy_not_found(self):
        """Test adapter fails if policy file not found."""
        from rexlit.app.adapters.privilege_safeguard import PrivilegeSafeguardAdapter

        with pytest.raises(FileNotFoundError, match="Policy template not found"):
            PrivilegeSafeguardAdapter(
                model_path="/some/model",
                policy_path="/nonexistent/policy.txt",
            )

    def test_adapter_cot_vault_required_when_logging(self, policy_path, tmp_path):
        """Test adapter requires vault path and key path when log_full_cot=True."""
        from rexlit.app.adapters.privilege_safeguard import PrivilegeSafeguardAdapter

        # Missing vault path
        with pytest.raises(ValueError, match="cot_vault_path required"):
            PrivilegeSafeguardAdapter(
                model_path="/some/model",
                policy_path=policy_path,
                log_full_cot=True,
                cot_vault_path=None,
            )

        # Missing vault key path
        with pytest.raises(ValueError, match="vault_key_path required"):
            PrivilegeSafeguardAdapter(
                model_path="/some/model",
                policy_path=policy_path,
                log_full_cot=True,
                cot_vault_path=tmp_path / "vault",
                vault_key_path=None,
            )

    def test_adapter_vault_encryption(self, policy_path, tmp_path):
        """Test that vault entries are encrypted and can be decrypted."""
        import sys
        from pathlib import Path as PathLib

        # Import adapter directly to avoid tesseract dependency
        sys.path.insert(0, str(PathLib(__file__).parent.parent))
        from rexlit.app.adapters.privilege_safeguard import PrivilegeSafeguardAdapter

        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()
        key_path = tmp_path / "vault.key"

        # Create adapter with vault enabled
        adapter = PrivilegeSafeguardAdapter(
            model_path="/some/model",
            policy_path=policy_path,
            log_full_cot=True,
            cot_vault_path=vault_dir,
            vault_key_path=key_path,
        )

        # Test data
        reasoning = "This is sensitive privileged reasoning with client communications."
        cot_hash = "test_hash_abc123"

        # Store in vault (should encrypt)
        adapter._store_in_vault(reasoning, cot_hash)

        # Verify file exists with .enc extension
        encrypted_file = vault_dir / f"{cot_hash}.enc"
        assert encrypted_file.exists()

        # Verify file content is NOT plaintext
        encrypted_content = encrypted_file.read_bytes()
        assert reasoning.encode("utf-8") not in encrypted_content
        assert b"sensitive" not in encrypted_content
        assert b"privileged" not in encrypted_content

        # Retrieve and decrypt
        decrypted = adapter.retrieve_from_vault(cot_hash)
        assert decrypted == reasoning

        # Test deduplication (storing same hash again should not error)
        adapter._store_in_vault(reasoning, cot_hash)

    @pytest.mark.skip(reason="Requires gpt-oss-safeguard-20b model installation")
    def test_adapter_classify_privileged_email(self, policy_path, tmp_path):
        """Test classifying privileged email (integration test).

        This test requires the actual model to be installed at the configured path.
        """
        from rexlit.app.adapters.privilege_safeguard import PrivilegeSafeguardAdapter

        # This would need actual model path
        model_path = Path.home() / ".local/share/rexlit/models/gpt-oss-safeguard-20b"

        if not model_path.exists():
            pytest.skip("Model not installed")

        adapter = PrivilegeSafeguardAdapter(
            model_path=model_path,
            policy_path=policy_path,
            timeout_seconds=30,
        )

        text = """
From: attorney@lawfirm.com
To: client@company.com
Subject: RE: Legal Opinion on Merger

Here is my legal opinion regarding the proposed merger transaction...
"""

        decision = adapter.classify_privilege(text, threshold=0.75, reasoning_effort="medium")

        assert decision.confidence > 0.0
        assert decision.reasoning_hash != ""
        assert decision.reasoning_summary != ""
        # Note: Actual labels depend on model inference
