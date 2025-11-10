"""Tests for PIIRegexAdapter."""

import pytest

from rexlit.app.adapters.pii_regex import PIIRegexAdapter


class TestPIIRegexPatterns:
    """Test PII pattern matching."""

    def test_ssn_detection(self):
        """Test Social Security Number detection."""
        adapter = PIIRegexAdapter()
        text = "Contact 123-45-6789 for details"
        findings = adapter.analyze_text(text)

        assert len(findings) == 1
        assert findings[0].entity_type == "SSN"
        assert findings[0].text == "123-45-6789"
        assert findings[0].score == 1.0

    def test_email_detection(self):
        """Test email address detection."""
        adapter = PIIRegexAdapter()
        text = "Email: john.doe@example.com for questions"
        findings = adapter.analyze_text(text)

        assert len(findings) == 1
        assert findings[0].entity_type == "EMAIL"
        assert findings[0].text == "john.doe@example.com"

    def test_phone_detection(self):
        """Test phone number detection."""
        adapter = PIIRegexAdapter()
        text = "Call us at (555) 123-4567 or +1 555-123-4567"
        findings = adapter.analyze_text(text)

        assert len(findings) >= 1
        assert any(f.entity_type == "PHONE" for f in findings)

    def test_no_pii_detected(self):
        """Test text with no PII."""
        adapter = PIIRegexAdapter()
        text = "This is a normal document with no sensitive information."
        findings = adapter.analyze_text(text)

        assert len(findings) == 0

    def test_multiple_findings(self):
        """Test detecting multiple PII entities in one text."""
        adapter = PIIRegexAdapter()
        text = "Contact john@example.com or call 555-123-4567. SSN: 123-45-6789"
        findings = adapter.analyze_text(text)

        assert len(findings) >= 2
        entity_types = {f.entity_type for f in findings}
        assert "EMAIL" in entity_types
        assert "SSN" in entity_types

    def test_entity_filtering(self):
        """Test filtering by specific entity types."""
        adapter = PIIRegexAdapter()
        text = "Email: test@example.com and SSN: 123-45-6789"

        # Only request EMAIL findings
        findings = adapter.analyze_text(text, entities=["EMAIL"])
        assert all(f.entity_type == "EMAIL" for f in findings)

    def test_email_whitelist(self):
        """Test email domain whitelist."""
        adapter = PIIRegexAdapter(
            profile={"domain_whitelist": ["internal.com"]}
        )
        text = "internal@internal.com is fine, but external@external.com is PII"
        findings = adapter.analyze_text(text)

        # Should only find the non-whitelisted email
        assert any("external.com" in f.text for f in findings)
        assert not any("internal.com" in f.text for f in findings)

    def test_empty_profile(self):
        """Test with empty profile."""
        adapter = PIIRegexAdapter(profile={})
        text = "SSN: 123-45-6789"
        findings = adapter.analyze_text(text)

        assert len(findings) == 1
        assert findings[0].entity_type == "SSN"

    def test_supported_entities(self):
        """Test get_supported_entities returns correct list."""
        adapter = PIIRegexAdapter()
        entities = adapter.get_supported_entities()

        assert "SSN" in entities
        assert "EMAIL" in entities
        assert "PHONE" in entities

    def test_requires_online_false(self):
        """Test that adapter is always offline."""
        adapter = PIIRegexAdapter()
        assert adapter.requires_online() is False

    def test_name_detection_with_profile(self):
        """Test name detection when provided in profile."""
        adapter = PIIRegexAdapter(
            profile={"names": ["John Smith", "Jane Doe"]}
        )
        text = "Contact John Smith or Jane Doe for assistance"
        findings = adapter.analyze_text(text)

        name_findings = [f for f in findings if f.entity_type == "NAME"]
        assert len(name_findings) == 2

    def test_text_position_tracking(self):
        """Test that start/end positions are correctly tracked."""
        adapter = PIIRegexAdapter()
        text = "Contact: john@example.com here"
        findings = adapter.analyze_text(text)

        assert len(findings) == 1
        email_finding = findings[0]
        assert text[email_finding.start:email_finding.end] == "john@example.com"
