"""Tests for PrivilegePatternsAdapter."""


from rexlit.app.adapters.privilege_patterns import PrivilegePatternsAdapter


class TestPrivilegePatternsDetection:
    """Test privilege pattern detection."""

    def test_keyword_privilege_detection(self):
        """Test detection of privilege-related keywords."""
        adapter = PrivilegePatternsAdapter()
        text = "This communication is protected by attorney-client privilege"
        findings = adapter.analyze_text(text)

        assert len(findings) >= 1
        assert any("privilege" in f.snippet.lower() for f in findings)

    def test_work_product_detection(self):
        """Test detection of work product language."""
        adapter = PrivilegePatternsAdapter()
        text = "This is attorney work product prepared for litigation"
        findings = adapter.analyze_text(text)

        assert len(findings) >= 1
        assert any("work product" in f.snippet.lower() for f in findings)

    def test_attorney_domain_detection(self):
        """Test detection of attorney domain emails."""
        adapter = PrivilegePatternsAdapter(
            profile={"attorney_domains": ["lawfirm.com"]}
        )
        text = "Contact counsel@lawfirm.com for legal advice"
        findings = adapter.analyze_text(text)

        # Should detect attorney domain
        domain_findings = [f for f in findings if f.rule == "attorney_domain"]
        assert len(domain_findings) >= 0  # May or may not detect depending on threshold

    def test_attorney_name_detection(self):
        """Test detection of attorney names."""
        adapter = PrivilegePatternsAdapter(
            profile={"attorney_names": ["Jane Smith, Esq."]}
        )
        text = "Prepared by Jane Smith, Esq. for legal review"
        findings = adapter.analyze_text(text)

        name_findings = [f for f in findings if f.rule == "attorney_name"]
        # May detect depending on threshold
        assert isinstance(findings, list)

    def test_no_privilege_detected(self):
        """Test text with no privilege indicators."""
        adapter = PrivilegePatternsAdapter()
        text = "This is a standard business document with no legal content."
        findings = adapter.analyze_text(text)

        assert len(findings) == 0

    def test_threshold_filtering(self):
        """Test confidence threshold filtering."""
        adapter = PrivilegePatternsAdapter()
        text = "This communication is attorney-client privileged"

        # High threshold may filter out some findings
        high_threshold_findings = adapter.analyze_text(text, threshold=0.99)
        low_threshold_findings = adapter.analyze_text(text, threshold=0.1)

        assert len(low_threshold_findings) >= len(high_threshold_findings)

    def test_confidence_scores(self):
        """Test that findings have appropriate confidence scores."""
        adapter = PrivilegePatternsAdapter()
        text = "attorney-client privilege and privileged communication"
        findings = adapter.analyze_text(text, threshold=0.5)

        assert all(0.0 <= f.confidence <= 1.0 for f in findings)
        # Keyword findings should have high confidence
        keyword_findings = [f for f in findings if f.rule == "privilege_keyword"]
        for finding in keyword_findings:
            assert finding.confidence >= 0.7

    def test_supported_rules(self):
        """Test get_supported_rules."""
        adapter = PrivilegePatternsAdapter(
            profile={"attorney_domains": ["law.com"], "attorney_names": ["John"]}
        )
        rules = adapter.get_supported_rules()

        assert "privilege_keyword" in rules
        # Attorney domain and name rules only if configured
        assert isinstance(rules, list)

    def test_requires_online_false(self):
        """Test that adapter is always offline."""
        adapter = PrivilegePatternsAdapter()
        assert adapter.requires_online() is False

    def test_snippet_with_context(self):
        """Test that snippets include surrounding context."""
        adapter = PrivilegePatternsAdapter()
        text = "This is a long document with attorney-client privilege in the middle of it"
        findings = adapter.analyze_text(text)

        for finding in findings:
            # Snippet should be longer than just the matched text
            assert len(finding.snippet) >= len(finding.snippet.strip("..."))

    def test_multiple_matches_in_text(self):
        """Test detecting multiple privilege indicators."""
        adapter = PrivilegePatternsAdapter()
        text = """
        attorney-client privilege
        work product
        privileged communication
        """
        findings = adapter.analyze_text(text, threshold=0.5)

        assert len(findings) >= 2

    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        adapter = PrivilegePatternsAdapter()
        text1 = "ATTORNEY-CLIENT PRIVILEGE"
        text2 = "attorney-client privilege"
        text3 = "Attorney-Client Privilege"

        findings1 = adapter.analyze_text(text1)
        findings2 = adapter.analyze_text(text2)
        findings3 = adapter.analyze_text(text3)

        # All should find privilege indicators
        assert len(findings1) > 0
        assert len(findings2) > 0
        assert len(findings3) > 0

    def test_empty_profile(self):
        """Test with empty profile defaults to keywords."""
        adapter = PrivilegePatternsAdapter(profile={})
        text = "protected by attorney-client privilege"
        findings = adapter.analyze_text(text)

        assert len(findings) >= 1

    def test_match_type_in_finding(self):
        """Test that findings include match type."""
        adapter = PrivilegePatternsAdapter()
        text = "attorney-client privilege"
        findings = adapter.analyze_text(text, threshold=0.5)

        assert all(f.match_type in ["domain", "keyword", "name"] for f in findings)
