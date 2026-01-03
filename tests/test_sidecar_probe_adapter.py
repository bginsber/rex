"""Tests for SidecarProbeAdapter."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from rexlit.app.adapters.sidecar_probe_adapter import SidecarProbeAdapter
from rexlit.utils.circuit_breaker import CircuitBreakerOpen


class TestSidecarProbeAdapter:
    """Test sidecar probe adapter functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock HTTP client."""
        with patch(
            "rexlit.app.adapters.sidecar_probe_adapter.httpx.Client"
        ) as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            yield mock_instance

    def test_classify_privilege_high_score(self, mock_client):
        """Test classification with HIGH privilege score."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "document_id": "DOC001",
            "privilege_score": 0.92,
            "privilege_category": "HIGH",
            "surface_marker_flag": False,
            "confidence": 0.84,
        }
        mock_client.post.return_value = mock_response

        adapter = SidecarProbeAdapter("http://localhost:8000")
        decision = adapter.classify_privilege("Legal advice from attorney")

        assert "PRIVILEGED:PROBE" in decision.labels
        assert decision.confidence == 0.84
        assert not decision.needs_review
        assert "sidecar-probe" in decision.model_version.lower()
        assert decision.reasoning_hash  # Should have a hash
        assert "0.92" in decision.reasoning_summary

    def test_classify_privilege_medium_score_needs_review(self, mock_client):
        """Test MEDIUM category triggers needs_review."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "privilege_score": 0.65,
            "privilege_category": "MEDIUM",
            "surface_marker_flag": False,
            "confidence": 0.30,
        }
        mock_client.post.return_value = mock_response

        adapter = SidecarProbeAdapter("http://localhost:8000")
        decision = adapter.classify_privilege("Borderline document")

        assert "PRIVILEGED:PROBE" in decision.labels
        assert decision.needs_review  # MEDIUM always needs review

    def test_classify_privilege_low_score(self, mock_client):
        """Test LOW score classification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "privilege_score": 0.35,
            "privilege_category": "LOW",
            "surface_marker_flag": False,
            "confidence": 0.30,
        }
        mock_client.post.return_value = mock_response

        adapter = SidecarProbeAdapter("http://localhost:8000")
        decision = adapter.classify_privilege("Regular email")

        assert "PRIVILEGED:PROBE" not in decision.labels
        assert not decision.is_privileged

    def test_classify_privilege_unlikely(self, mock_client):
        """Test UNLIKELY classification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "privilege_score": 0.08,
            "privilege_category": "UNLIKELY",
            "surface_marker_flag": False,
            "confidence": 0.84,
        }
        mock_client.post.return_value = mock_response

        adapter = SidecarProbeAdapter("http://localhost:8000")
        decision = adapter.classify_privilege("Business meeting notes")

        assert decision.labels == []
        assert not decision.is_privileged
        assert not decision.needs_review  # High confidence, UNLIKELY

    def test_surface_marker_flag_detection(self, mock_client):
        """Test hard negative detection via surface_marker_flag."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "privilege_score": 0.18,
            "privilege_category": "UNLIKELY",
            "surface_marker_flag": True,  # Has privilege markers but not privileged
            "confidence": 0.64,
        }
        mock_client.post.return_value = mock_response

        adapter = SidecarProbeAdapter("http://localhost:8000")
        decision = adapter.classify_privilege(
            "PRIVILEGED AND CONFIDENTIAL - Please call John, he's our attorney"
        )

        assert "FLAG:SURFACE_MARKER" in decision.labels
        assert "PRIVILEGED:PROBE" not in decision.labels
        assert "Surface marker detected" in decision.reasoning_summary

    def test_empty_text_returns_error_decision(self, mock_client):
        """Test empty input handling."""
        adapter = SidecarProbeAdapter("http://localhost:8000")
        decision = adapter.classify_privilege("")

        assert decision.needs_review
        assert "Empty document text" in decision.error_message
        assert decision.confidence == 0.0

    def test_whitespace_only_text_returns_error(self, mock_client):
        """Test whitespace-only input handling."""
        adapter = SidecarProbeAdapter("http://localhost:8000")
        decision = adapter.classify_privilege("   \n\t  ")

        assert decision.needs_review
        assert "Empty document text" in decision.error_message

    def test_circuit_breaker_opens_after_failures(self, mock_client):
        """Test circuit breaker trips after consecutive failures."""
        import httpx

        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        adapter = SidecarProbeAdapter(
            "http://localhost:8000",
            circuit_breaker_threshold=2,
        )

        # First failure
        decision1 = adapter.classify_privilege("Test 1")
        assert decision1.needs_review
        assert "connection error" in decision1.error_message.lower()

        # Second failure - circuit should open
        decision2 = adapter.classify_privilege("Test 2")
        assert decision2.needs_review

        # Circuit should now be OPEN
        assert adapter.circuit_breaker.state == "OPEN"

    def test_health_check_success(self, mock_client):
        """Test health check returns status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "model_loaded": True,
            "probe_loaded": True,
            "version": "1.0.0",
        }
        mock_client.get.return_value = mock_response

        adapter = SidecarProbeAdapter("http://localhost:8000")
        health = adapter.health_check()

        assert health["status"] == "healthy"
        assert health["model_loaded"] is True
        assert health["probe_loaded"] is True

    def test_health_check_unreachable(self, mock_client):
        """Test health check when sidecar is unreachable."""
        import httpx

        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        adapter = SidecarProbeAdapter("http://localhost:8000")
        health = adapter.health_check()

        assert health["status"] == "unreachable"
        assert "error" in health

    def test_requires_online(self, mock_client):
        """Test adapter requires online mode."""
        adapter = SidecarProbeAdapter("http://localhost:8000")
        assert adapter.requires_online() is True

    def test_batch_classification(self, mock_client):
        """Test batch classification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "document_id": "DOC001",
                    "privilege_score": 0.91,
                    "privilege_category": "HIGH",
                    "confidence": 0.82,
                    "surface_marker_flag": False,
                },
                {
                    "document_id": "DOC002",
                    "privilege_score": 0.12,
                    "privilege_category": "UNLIKELY",
                    "confidence": 0.76,
                    "surface_marker_flag": False,
                },
            ],
            "total_processed": 2,
            "processing_time_ms": 150.0,
        }
        mock_client.post.return_value = mock_response

        adapter = SidecarProbeAdapter("http://localhost:8000")
        decisions = adapter.classify_batch([
            ("DOC001", "Legal advice from counsel"),
            ("DOC002", "Regular business email"),
        ])

        assert len(decisions) == 2
        assert decisions[0].is_privileged
        assert not decisions[1].is_privileged

    def test_batch_empty_list(self, mock_client):
        """Test batch with empty document list."""
        adapter = SidecarProbeAdapter("http://localhost:8000")
        decisions = adapter.classify_batch([])

        assert decisions == []

    def test_reasoning_hash_is_deterministic_for_same_input(self, mock_client):
        """Test reasoning hash is consistent for same sidecar response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "privilege_score": 0.87,
            "privilege_category": "HIGH",
            "surface_marker_flag": False,
            "confidence": 0.74,
        }
        mock_client.post.return_value = mock_response

        # Same salt for both adapters
        adapter1 = SidecarProbeAdapter("http://localhost:8000", cot_salt="test_salt")
        adapter2 = SidecarProbeAdapter("http://localhost:8000", cot_salt="test_salt")

        decision1 = adapter1.classify_privilege("Test document")
        decision2 = adapter2.classify_privilege("Test document")

        assert decision1.reasoning_hash == decision2.reasoning_hash

    def test_reasoning_hash_differs_with_different_salt(self, mock_client):
        """Test reasoning hash varies with different salt."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "privilege_score": 0.87,
            "privilege_category": "HIGH",
            "surface_marker_flag": False,
            "confidence": 0.74,
        }
        mock_client.post.return_value = mock_response

        adapter1 = SidecarProbeAdapter("http://localhost:8000", cot_salt="salt_a")
        adapter2 = SidecarProbeAdapter("http://localhost:8000", cot_salt="salt_b")

        decision1 = adapter1.classify_privilege("Test document")
        decision2 = adapter2.classify_privilege("Test document")

        assert decision1.reasoning_hash != decision2.reasoning_hash

    def test_http_error_handling(self, mock_client):
        """Test HTTP error responses are handled gracefully."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=mock_response,
        )

        adapter = SidecarProbeAdapter("http://localhost:8000")
        decision = adapter.classify_privilege("Test document")

        assert decision.needs_review
        assert "500" in decision.error_message

    def test_close_cleans_up_client(self, mock_client):
        """Test close() properly cleans up HTTP client."""
        adapter = SidecarProbeAdapter("http://localhost:8000")
        adapter.close()

        mock_client.close.assert_called_once()


class TestSidecarProbeAdapterIntegration:
    """Integration tests (skip if sidecar not available)."""

    @pytest.fixture
    def sidecar_url(self):
        """Get sidecar URL from environment."""
        url = os.getenv("REXLIT_PROBE_SIDECAR_URL")
        if not url:
            pytest.skip("REXLIT_PROBE_SIDECAR_URL not set")
        return url

    def test_real_health_check(self, sidecar_url):
        """Test real health check against running sidecar."""
        adapter = SidecarProbeAdapter(sidecar_url)
        health = adapter.health_check()

        # Should get a response (healthy, degraded, or error)
        assert "status" in health or "error" in health
        adapter.close()

    def test_real_classification(self, sidecar_url):
        """Test real classification against running sidecar."""
        adapter = SidecarProbeAdapter(sidecar_url, timeout_seconds=30.0)

        # Clearly privileged document
        decision = adapter.classify_privilege(
            "From: attorney@lawfirm.com\n"
            "Subject: Legal Opinion - Attorney-Client Privileged\n\n"
            "Dear Client,\n\n"
            "This letter constitutes my legal advice regarding your question "
            "about the contractual dispute. In my professional opinion as your "
            "legal counsel, you should proceed with the settlement..."
        )

        # Should get a real response
        assert decision.confidence >= 0.0
        assert decision.reasoning_hash  # Should have generated a hash
        adapter.close()
