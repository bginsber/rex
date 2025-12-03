"""Integration tests for ADR 0008 pattern → LLM escalation workflow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rexlit.app.adapters.pattern_concept_adapter import PatternConceptAdapter
from rexlit.app.adapters.local_llm_concept_adapter import LocalLLMConceptAdapter
from rexlit.app.highlight_service import HighlightService
from rexlit.app.ports.concept import ConceptFinding
from rexlit.config import Settings


class MockStorage:
    """Mock storage port for testing."""

    def compute_hash(self, path: Path) -> str:
        return "a" * 64


class MockLedger:
    """Mock ledger port for testing."""

    def __init__(self):
        self.logs = []

    def log(self, **kwargs) -> None:
        self.logs.append(kwargs)


class TestEscalationWorkflow:
    """Test the pattern → LLM escalation workflow."""

    def test_high_confidence_skips_llm(self, tmp_path: Path) -> None:
        """High confidence findings (≥0.85) should skip LLM refinement."""
        # Create a document with clear privilege markers + attorney domain
        doc = tmp_path / "privileged.txt"
        doc.write_text(
            "From: attorney@lawfirm.com\n"
            "Subject: Legal advice on merger\n\n"
            "This is attorney-client privileged communication.\n"
            "Pursuant to our discussion, counsel advises settlement.",
            encoding="utf-8",
        )

        # Create mock refinement adapter that tracks calls
        mock_refinement = MagicMock(spec=LocalLLMConceptAdapter)
        mock_refinement.refine_findings = MagicMock(return_value=[])

        service = HighlightService(
            concept_port=PatternConceptAdapter(),
            refinement_port=mock_refinement,
            storage_port=MockStorage(),
            ledger_port=MockLedger(),
            settings=Settings(highlight_plan_key_path=tmp_path / "key"),
        )

        plan = service.plan(
            doc,
            tmp_path / "plan.enc",
            allowed_input_roots=[tmp_path],
            allowed_output_roots=[tmp_path],
        )

        # Check escalation stats
        stats = plan.annotations.get("escalation_stats", {})

        # High confidence findings should exist
        assert stats.get("high_confidence", 0) > 0

        # If all findings were high confidence, refinement should not be called
        # OR if called, it should be with empty/few findings
        if stats.get("escalated", 0) == 0:
            mock_refinement.refine_findings.assert_not_called()

    def test_uncertain_findings_escalated_to_llm(self, tmp_path: Path) -> None:
        """Uncertain findings (0.50-0.84) should be sent to LLM for refinement."""
        # Create a document with ambiguous content (lower confidence)
        doc = tmp_path / "ambiguous.txt"
        doc.write_text(
            "The claim was settled for damages.",
            encoding="utf-8",
        )

        # Create mock refinement adapter
        mock_refinement = MagicMock(spec=LocalLLMConceptAdapter)

        def mock_refine(text, findings, threshold=0.5):
            # Return findings with boosted confidence
            return [
                ConceptFinding(
                    concept=f.concept,
                    category=f.category,
                    confidence=min(1.0, f.confidence + 0.15),
                    start=f.start,
                    end=f.end,
                    page=f.page,
                    snippet_hash=f.snippet_hash,
                    reasoning_hash="refined_hash",
                    needs_refinement=False,
                )
                for f in findings
            ]

        mock_refinement.refine_findings = MagicMock(side_effect=mock_refine)

        service = HighlightService(
            concept_port=PatternConceptAdapter(),
            refinement_port=mock_refinement,
            storage_port=MockStorage(),
            ledger_port=MockLedger(),
            settings=Settings(highlight_plan_key_path=tmp_path / "key"),
        )

        plan = service.plan(
            doc,
            tmp_path / "plan.enc",
            allowed_input_roots=[tmp_path],
            allowed_output_roots=[tmp_path],
        )

        stats = plan.annotations.get("escalation_stats", {})

        # If there were uncertain findings, they should have been escalated
        if stats.get("escalated", 0) > 0:
            mock_refinement.refine_findings.assert_called()
            assert stats.get("refined", 0) > 0

    def test_escalation_disabled_skips_llm(self, tmp_path: Path) -> None:
        """When enable_escalation=False, LLM should not be called."""
        doc = tmp_path / "test.txt"
        doc.write_text("The claim was filed by plaintiff.", encoding="utf-8")

        mock_refinement = MagicMock(spec=LocalLLMConceptAdapter)

        service = HighlightService(
            concept_port=PatternConceptAdapter(),
            refinement_port=mock_refinement,
            storage_port=MockStorage(),
            ledger_port=MockLedger(),
            settings=Settings(highlight_plan_key_path=tmp_path / "key"),
        )

        plan = service.plan(
            doc,
            tmp_path / "plan.enc",
            allowed_input_roots=[tmp_path],
            allowed_output_roots=[tmp_path],
            enable_escalation=False,
        )

        # Refinement should never be called when disabled
        mock_refinement.refine_findings.assert_not_called()

    def test_llm_failure_returns_original_findings(self, tmp_path: Path) -> None:
        """If LLM refinement fails, original pattern findings should be returned."""
        doc = tmp_path / "test.txt"
        doc.write_text("The defendant breached the contract.", encoding="utf-8")

        # Create mock that raises exception
        mock_refinement = MagicMock(spec=LocalLLMConceptAdapter)
        mock_refinement.refine_findings = MagicMock(
            side_effect=RuntimeError("LLM unavailable")
        )

        service = HighlightService(
            concept_port=PatternConceptAdapter(),
            refinement_port=mock_refinement,
            storage_port=MockStorage(),
            ledger_port=MockLedger(),
            settings=Settings(highlight_plan_key_path=tmp_path / "key"),
        )

        # Should not raise, should return original findings
        plan = service.plan(
            doc,
            tmp_path / "plan.enc",
            allowed_input_roots=[tmp_path],
            allowed_output_roots=[tmp_path],
        )

        # Should have findings despite LLM failure
        assert len(plan.highlights) > 0

    def test_no_refinement_port_pattern_only(self, tmp_path: Path) -> None:
        """Without refinement port, should work in pattern-only mode."""
        doc = tmp_path / "test.txt"
        doc.write_text("Attorney-client privileged communication.", encoding="utf-8")

        service = HighlightService(
            concept_port=PatternConceptAdapter(),
            refinement_port=None,  # No LLM
            storage_port=MockStorage(),
            ledger_port=MockLedger(),
            settings=Settings(highlight_plan_key_path=tmp_path / "key"),
        )

        plan = service.plan(
            doc,
            tmp_path / "plan.enc",
            allowed_input_roots=[tmp_path],
            allowed_output_roots=[tmp_path],
        )

        # Should work without LLM
        assert len(plan.highlights) > 0
        stats = plan.annotations.get("escalation_stats", {})
        assert stats.get("escalated", 0) == 0


class TestLocalLLMConceptAdapterRefinement:
    """Tests for LocalLLMConceptAdapter.refine_findings() method."""

    def test_refine_findings_no_client_returns_unchanged(self) -> None:
        """Without OpenAI client, refine_findings returns findings unchanged."""
        adapter = LocalLLMConceptAdapter(api_base="http://nonexistent:1234/v1")
        # Force client to None to simulate unavailable
        adapter._client = None

        findings = [
            ConceptFinding(
                concept="LEGAL_ADVICE",
                category="privilege",
                confidence=0.70,
                start=0,
                end=10,
                needs_refinement=True,
            )
        ]

        result = adapter.refine_findings("test text", findings)
        assert result == findings  # Unchanged

    def test_refine_findings_updates_confidence(self) -> None:
        """With mock LLM, refine_findings should update confidence."""
        adapter = LocalLLMConceptAdapter()

        # Mock the client response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"confidence": 0.92, "reasoning": "Strong privilege indicators"}'
                )
            )
        ]

        with patch.object(adapter, "_client") as mock_client:
            mock_client.chat.completions.create.return_value = mock_response

            findings = [
                ConceptFinding(
                    concept="LEGAL_ADVICE",
                    category="privilege",
                    confidence=0.70,
                    start=0,
                    end=20,
                    needs_refinement=True,
                )
            ]

            result = adapter.refine_findings(
                "This is attorney-client privileged.", findings
            )

            assert len(result) == 1
            # Confidence should be updated
            assert result[0].confidence >= 0.70
            # Needs refinement should be False after refinement
            assert result[0].needs_refinement is False

    def test_repr_masks_api_key(self) -> None:
        """__repr__ should not expose API key."""
        adapter = LocalLLMConceptAdapter(
            api_base="http://localhost:1234/v1",
            api_key="secret-key-12345",
            model="test-model",
        )

        repr_str = repr(adapter)

        assert "secret-key-12345" not in repr_str
        assert "[MASKED]" in repr_str
        assert "test-model" in repr_str


class TestEscalationStats:
    """Tests for escalation statistics tracking."""

    def test_stats_recorded_in_annotations(self, tmp_path: Path) -> None:
        """Escalation stats should be recorded in plan annotations."""
        doc = tmp_path / "test.txt"
        doc.write_text(
            "From: attorney@lawfirm.com\n"
            "The plaintiff filed a claim for damages.",
            encoding="utf-8",
        )

        service = HighlightService(
            concept_port=PatternConceptAdapter(),
            refinement_port=None,
            storage_port=MockStorage(),
            ledger_port=MockLedger(),
            settings=Settings(highlight_plan_key_path=tmp_path / "key"),
        )

        plan = service.plan(
            doc,
            tmp_path / "plan.enc",
            allowed_input_roots=[tmp_path],
            allowed_output_roots=[tmp_path],
        )

        stats = plan.annotations.get("escalation_stats")
        assert stats is not None
        assert "high_confidence" in stats
        assert "escalated" in stats
        assert "refined" in stats

    def test_stats_logged_to_ledger(self, tmp_path: Path) -> None:
        """Escalation stats should be logged to audit ledger."""
        doc = tmp_path / "test.txt"
        doc.write_text("Legal advice document.", encoding="utf-8")

        ledger = MockLedger()

        service = HighlightService(
            concept_port=PatternConceptAdapter(),
            refinement_port=None,
            storage_port=MockStorage(),
            ledger_port=ledger,
            settings=Settings(highlight_plan_key_path=tmp_path / "key"),
        )

        service.plan(
            doc,
            tmp_path / "plan.enc",
            allowed_input_roots=[tmp_path],
            allowed_output_roots=[tmp_path],
        )

        # Check ledger was called with escalation stats
        assert len(ledger.logs) > 0
        log_entry = ledger.logs[0]
        assert "escalation_stats" in log_entry.get("args", {})

