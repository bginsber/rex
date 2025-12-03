"""Tests for PatternConceptAdapter concept detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from rexlit.app.adapters.pattern_concept_adapter import PatternConceptAdapter


@pytest.fixture
def adapter() -> PatternConceptAdapter:
    return PatternConceptAdapter()


class TestSupportedConcepts:
    def test_all_five_concepts_supported(self, adapter: PatternConceptAdapter) -> None:
        supported = adapter.get_supported_concepts()
        assert "EMAIL_COMMUNICATION" in supported
        assert "LEGAL_ADVICE" in supported
        assert "KEY_PARTY" in supported
        assert "HOTDOC" in supported
        assert "RESPONSIVE" in supported

    def test_requires_offline(self, adapter: PatternConceptAdapter) -> None:
        assert adapter.requires_online() is False


class TestEmailCommunication:
    def test_detects_email_header_from(self, adapter: PatternConceptAdapter) -> None:
        text = "From: john.doe@company.com"
        findings = adapter.analyze_text(text, concepts=["EMAIL_COMMUNICATION"])
        assert len(findings) >= 1
        assert all(f.concept == "EMAIL_COMMUNICATION" for f in findings)
        assert all(f.category == "communication" for f in findings)
        assert all(f.confidence >= 0.85 for f in findings)

    def test_detects_email_header_to(self, adapter: PatternConceptAdapter) -> None:
        text = "To: attorney@lawfirm.com"
        findings = adapter.analyze_text(text, concepts=["EMAIL_COMMUNICATION"])
        assert len(findings) >= 1

    def test_detects_cc_bcc_headers(self, adapter: PatternConceptAdapter) -> None:
        text = "CC: manager@company.com\nBCC: secret@company.com"
        findings = adapter.analyze_text(text, concepts=["EMAIL_COMMUNICATION"])
        assert len(findings) >= 2

    def test_detects_standalone_email_address(self, adapter: PatternConceptAdapter) -> None:
        text = "Please contact support@example.org for assistance."
        findings = adapter.analyze_text(text, concepts=["EMAIL_COMMUNICATION"])
        assert len(findings) >= 1

    def test_email_header_has_higher_confidence(self, adapter: PatternConceptAdapter) -> None:
        text = "From: ceo@company.com"
        findings = adapter.analyze_text(text, concepts=["EMAIL_COMMUNICATION"])
        header_finding = next((f for f in findings if "From:" in text[f.start:f.end]), None)
        assert header_finding is not None
        assert header_finding.confidence >= 0.9


class TestLegalAdvice:
    def test_detects_privileged_marker(self, adapter: PatternConceptAdapter) -> None:
        text = "This document is PRIVILEGED and confidential."
        findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])
        assert len(findings) >= 1
        assert findings[0].concept == "LEGAL_ADVICE"
        assert findings[0].category == "privilege"

    def test_detects_attorney_client(self, adapter: PatternConceptAdapter) -> None:
        text = "This is protected by attorney-client privilege."
        findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])
        assert len(findings) >= 1

    def test_detects_work_product(self, adapter: PatternConceptAdapter) -> None:
        text = "Attorney work product - do not disclose."
        findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])
        assert len(findings) >= 1

    def test_detects_counsel_advises(self, adapter: PatternConceptAdapter) -> None:
        text = "Our counsel advises that we should proceed cautiously."
        findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])
        assert len(findings) >= 1

    def test_detects_litigation_hold(self, adapter: PatternConceptAdapter) -> None:
        text = "A litigation hold has been placed on these documents."
        findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])
        assert len(findings) >= 1


class TestKeyParty:
    def test_detects_plaintiff(self, adapter: PatternConceptAdapter) -> None:
        text = "The plaintiff alleges damages of $1 million."
        findings = adapter.analyze_text(text, concepts=["KEY_PARTY"])
        assert len(findings) >= 1
        assert findings[0].concept == "KEY_PARTY"
        assert findings[0].category == "entity"

    def test_detects_defendant(self, adapter: PatternConceptAdapter) -> None:
        text = "The defendant denies all allegations."
        findings = adapter.analyze_text(text, concepts=["KEY_PARTY"])
        assert len(findings) >= 1

    def test_detects_respondent_claimant(self, adapter: PatternConceptAdapter) -> None:
        text = "The respondent and claimant both appeared at the hearing."
        findings = adapter.analyze_text(text, concepts=["KEY_PARTY"])
        assert len(findings) >= 2

    def test_detects_patent_reference(self, adapter: PatternConceptAdapter) -> None:
        text = "See Patent #12345678 for technical details."
        findings = adapter.analyze_text(text, concepts=["KEY_PARTY"])
        assert len(findings) >= 1

    def test_detects_contract_reference(self, adapter: PatternConceptAdapter) -> None:
        text = "As specified in Contract No. 2024-001."
        findings = adapter.analyze_text(text, concepts=["KEY_PARTY"])
        assert len(findings) >= 1


class TestHotDoc:
    def test_detects_violate(self, adapter: PatternConceptAdapter) -> None:
        text = "I know this would violate the regulations."
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])
        assert len(findings) >= 1
        assert findings[0].concept == "HOTDOC"
        assert findings[0].category == "hotdoc"
        assert findings[0].confidence >= 0.85

    def test_detects_smoking_gun(self, adapter: PatternConceptAdapter) -> None:
        text = "This email is the smoking gun we've been looking for."
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])
        assert len(findings) >= 1

    def test_detects_destroy_shred(self, adapter: PatternConceptAdapter) -> None:
        text = "We should destroy these files and shred all copies."
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])
        assert len(findings) >= 2

    def test_detects_cover_up(self, adapter: PatternConceptAdapter) -> None:
        text = "They tried to cover up the evidence."
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])
        assert len(findings) >= 1

    def test_detects_delete_emails(self, adapter: PatternConceptAdapter) -> None:
        text = "Delete all the emails about this project."
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])
        assert len(findings) >= 1

    def test_detects_off_the_record(self, adapter: PatternConceptAdapter) -> None:
        text = "This conversation is off the record."
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])
        assert len(findings) >= 1

    def test_detects_fraud_bribe(self, adapter: PatternConceptAdapter) -> None:
        text = "This looks like fraud and possibly a bribe."
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])
        assert len(findings) >= 2

    def test_detects_shouldnt_have(self, adapter: PatternConceptAdapter) -> None:
        text = "We shouldn't have done this."
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])
        assert len(findings) >= 1


class TestResponsive:
    def test_detects_claim(self, adapter: PatternConceptAdapter) -> None:
        text = "The plaintiff's claim seeks monetary damages."
        findings = adapter.analyze_text(text, concepts=["RESPONSIVE"])
        assert len(findings) >= 1
        assert findings[0].concept == "RESPONSIVE"
        assert findings[0].category == "responsive"

    def test_detects_allegation(self, adapter: PatternConceptAdapter) -> None:
        text = "These allegations are without merit."
        findings = adapter.analyze_text(text, concepts=["RESPONSIVE"])
        assert len(findings) >= 1

    def test_detects_breach(self, adapter: PatternConceptAdapter) -> None:
        text = "This constitutes a breach of contract."
        findings = adapter.analyze_text(text, concepts=["RESPONSIVE"])
        assert len(findings) >= 1

    def test_detects_infringement(self, adapter: PatternConceptAdapter) -> None:
        text = "The patent infringement occurred in 2023."
        findings = adapter.analyze_text(text, concepts=["RESPONSIVE"])
        assert len(findings) >= 1

    def test_detects_liable_negligent(self, adapter: PatternConceptAdapter) -> None:
        text = "They may be held liable for negligent conduct."
        findings = adapter.analyze_text(text, concepts=["RESPONSIVE"])
        assert len(findings) >= 2

    def test_detects_settlement(self, adapter: PatternConceptAdapter) -> None:
        text = "We are open to settlement discussions."
        findings = adapter.analyze_text(text, concepts=["RESPONSIVE"])
        assert len(findings) >= 1

    def test_detects_discovery_subpoena(self, adapter: PatternConceptAdapter) -> None:
        text = "Respond to the discovery request and subpoena."
        findings = adapter.analyze_text(text, concepts=["RESPONSIVE"])
        assert len(findings) >= 2

    def test_detects_deposition(self, adapter: PatternConceptAdapter) -> None:
        text = "The deposition is scheduled for next week."
        findings = adapter.analyze_text(text, concepts=["RESPONSIVE"])
        assert len(findings) >= 1


class TestPageDetection:
    def test_text_analysis_accepts_page_param(self, adapter: PatternConceptAdapter) -> None:
        text = "From: test@example.com"
        findings = adapter.analyze_text(text, page=5)
        assert len(findings) >= 1
        assert all(f.page == 5 for f in findings)

    def test_text_analysis_without_page_returns_none(self, adapter: PatternConceptAdapter) -> None:
        text = "From: test@example.com"
        findings = adapter.analyze_text(text)
        assert len(findings) >= 1
        assert all(f.page is None for f in findings)

    def test_plain_text_document_uses_page_one(
        self, adapter: PatternConceptAdapter, tmp_path: Path
    ) -> None:
        doc = tmp_path / "email.txt"
        doc.write_text("From: attorney@lawfirm.com\nThis is privileged.", encoding="utf-8")

        findings = adapter.analyze_document(str(doc))
        assert len(findings) >= 1
        assert all(f.page == 1 for f in findings)


class TestThreshold:
    def test_findings_meet_threshold(self, adapter: PatternConceptAdapter) -> None:
        text = "From: test@example.com"
        findings = adapter.analyze_text(text, threshold=0.8)
        assert all(f.confidence >= 0.8 for f in findings)

    def test_low_threshold_accepted(self, adapter: PatternConceptAdapter) -> None:
        text = "From: test@example.com"
        findings = adapter.analyze_text(text, threshold=0.1)
        assert len(findings) >= 1


class TestConceptFiltering:
    def test_filters_to_requested_concepts(self, adapter: PatternConceptAdapter) -> None:
        text = "From: attorney@lawfirm.com\nThis is privileged."
        findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])
        assert all(f.concept == "LEGAL_ADVICE" for f in findings)

    def test_multiple_concepts(self, adapter: PatternConceptAdapter) -> None:
        text = "From: attorney@lawfirm.com\nThe plaintiff claims damages."
        findings = adapter.analyze_text(text, concepts=["EMAIL_COMMUNICATION", "RESPONSIVE"])
        concepts_found = {f.concept for f in findings}
        assert "EMAIL_COMMUNICATION" in concepts_found
        assert "RESPONSIVE" in concepts_found
        assert "KEY_PARTY" not in concepts_found


class TestFindingOffsets:
    def test_offsets_are_accurate(self, adapter: PatternConceptAdapter) -> None:
        text = "Hello From: test@example.com world"
        findings = adapter.analyze_text(text, concepts=["EMAIL_COMMUNICATION"])

        for f in findings:
            matched_text = text[f.start : f.end]
            # The match should contain @ (email) or "From:" (header)
            assert "@" in matched_text or "From:" in matched_text


class TestRealWorldSamples:
    def test_full_email_chain(self, adapter: PatternConceptAdapter) -> None:
        text = """
        From: john.smith@company.com
        To: attorney@lawfirm.com
        CC: cfo@company.com
        Subject: RE: Patent Infringement Claim

        Our counsel advises that we should settle this matter quickly.
        The plaintiff's allegations regarding the breach are serious.
        This communication is privileged and confidential.

        We need to preserve all documents per the litigation hold.
        """
        findings = adapter.analyze_text(text)

        concepts_found = {f.concept for f in findings}
        assert "EMAIL_COMMUNICATION" in concepts_found
        assert "LEGAL_ADVICE" in concepts_found
        assert "RESPONSIVE" in concepts_found

    def test_hot_document_sample(self, adapter: PatternConceptAdapter) -> None:
        text = """
        I know this would violate the safety regulations, but we should
        proceed anyway. Delete all emails about this and don't tell anyone.
        This could be seen as fraud if discovered.
        """
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])

        assert len(findings) >= 3  # violate, delete, fraud
        assert all(f.confidence >= 0.85 for f in findings)

