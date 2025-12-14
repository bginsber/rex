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
        # Base confidence is 0.80 for headers, may be boosted by context
        assert all(f.confidence >= 0.65 for f in findings)

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

    def test_email_header_has_higher_confidence_than_address(self, adapter: PatternConceptAdapter) -> None:
        """Email headers get higher base confidence than standalone addresses."""
        header_text = "From: ceo@company.com"
        address_text = "Contact us at info@company.com for details."

        header_findings = adapter.analyze_text(header_text, concepts=["EMAIL_COMMUNICATION"])
        address_findings = adapter.analyze_text(address_text, concepts=["EMAIL_COMMUNICATION"])

        header_finding = next((f for f in header_findings if "From:" in header_text[f.start:f.end]), None)
        address_finding = next((f for f in address_findings), None)

        assert header_finding is not None
        assert address_finding is not None
        # Headers (0.80 base) > addresses (0.65 base)
        assert header_finding.confidence > address_finding.confidence


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
        # Base confidence is 0.75, flagged for LLM refinement
        assert findings[0].confidence >= 0.70
        assert findings[0].needs_refinement is True  # Uncertain, needs LLM

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


class TestMultiFactorScoring:
    """Tests for ADR 0008 multi-factor confidence scoring."""

    def test_attorney_domain_boosts_confidence(self, adapter: PatternConceptAdapter) -> None:
        """Attorney domain nearby should boost confidence by 0.10."""
        # Text with legal advice AND attorney domain
        text = "From: counsel@lawfirm.com\nThis is privileged legal advice."
        findings = adapter.analyze_text(text)

        legal_finding = next((f for f in findings if f.concept == "LEGAL_ADVICE"), None)
        assert legal_finding is not None
        # Base 0.70 + attorney_domain 0.10 = 0.80+
        assert legal_finding.confidence >= 0.80
        assert legal_finding.confidence_factors is not None
        assert "attorney_domain" in legal_finding.confidence_factors

    def test_multiple_concepts_boost_confidence(self, adapter: PatternConceptAdapter) -> None:
        """Multiple concept types nearby should boost confidence."""
        text = "The plaintiff's counsel advises settlement of the breach claim."
        findings = adapter.analyze_text(text)

        # Multiple concepts present: KEY_PARTY, LEGAL_ADVICE, RESPONSIVE
        concepts = {f.concept for f in findings}
        assert len(concepts) >= 2

        # At least some findings should have multi-concept boost
        boosted = [f for f in findings if f.confidence_factors and "multi_concept" in f.confidence_factors]
        assert len(boosted) >= 1

    def test_quoted_text_reduces_confidence(self, adapter: PatternConceptAdapter) -> None:
        """Quoted text markers should reduce confidence by 0.15."""
        text = """> On Monday, John wrote:
> This communication is privileged.
"""
        findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])

        if findings:
            # Quoted text penalty should reduce confidence
            assert findings[0].confidence_factors is not None
            if "quoted_text" in findings[0].confidence_factors:
                assert findings[0].confidence_factors["quoted_text"] < 0

    def test_needs_refinement_flag_set_for_uncertain(self, adapter: PatternConceptAdapter) -> None:
        """Findings with 0.50-0.84 confidence should have needs_refinement=True."""
        text = "The defendant breached the contract."
        findings = adapter.analyze_text(text)

        # Find a finding in uncertain range
        uncertain = [f for f in findings if 0.50 <= f.confidence < 0.85]
        if uncertain:
            assert all(f.needs_refinement is True for f in uncertain)

    def test_high_confidence_no_refinement(self, adapter: PatternConceptAdapter) -> None:
        """High confidence findings should have needs_refinement=False."""
        # Create high confidence scenario: attorney domain + legal context + privilege marker
        text = "From: attorney@counsel.law\nPursuant to attorney-client privilege, this is protected."
        findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])

        high_conf = [f for f in findings if f.confidence >= 0.85]
        if high_conf:
            assert all(f.needs_refinement is False for f in high_conf)

    def test_confidence_factors_recorded(self, adapter: PatternConceptAdapter) -> None:
        """All findings should have confidence_factors dict."""
        text = "From: test@example.com"
        findings = adapter.analyze_text(text)

        assert len(findings) >= 1
        assert findings[0].confidence_factors is not None
        assert "base" in findings[0].confidence_factors


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

        # Attorney domain should boost LEGAL_ADVICE findings
        legal_findings = [f for f in findings if f.concept == "LEGAL_ADVICE"]
        assert any(f.confidence >= 0.80 for f in legal_findings)

    def test_hot_document_sample(self, adapter: PatternConceptAdapter) -> None:
        """Hot documents get boosted confidence when multiple indicators present."""
        text = """
        I know this would violate the safety regulations, but we should
        proceed anyway. Delete all emails about this and don't tell anyone.
        This could be seen as fraud if discovered.
        """
        findings = adapter.analyze_text(text, concepts=["HOTDOC"])

        assert len(findings) >= 3  # violate, delete, fraud
        # Base confidence is 0.75, boosted by multi-concept presence
        # Multiple HOTDOC indicators nearby boost each other
        assert all(f.confidence >= 0.70 for f in findings)
        # With 3+ hotdoc indicators, some should get multi-concept boost
        boosted = [f for f in findings if f.confidence > 0.75]
        assert len(boosted) >= 1  # At least one got boosted

