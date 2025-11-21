from rexlit.app.adapters.pattern_concept_adapter import PatternConceptAdapter


def test_pattern_adapter_detects_email_header():
    adapter = PatternConceptAdapter()
    text = "From: attorney@lawfirm.com\nBody text"

    findings = adapter.analyze_text(text, concepts=["EMAIL_COMMUNICATION"])

    assert any(f.concept == "EMAIL_COMMUNICATION" for f in findings)
    for f in findings:
        assert f.snippet_hash is None
        assert f.confidence >= 0.85


def test_pattern_adapter_detects_legal_advice():
    adapter = PatternConceptAdapter()
    text = "This is privileged and contains legal advice from counsel."

    findings = adapter.analyze_text(text, concepts=["LEGAL_ADVICE"])

    assert any(f.concept == "LEGAL_ADVICE" for f in findings)
    assert all(f.confidence >= 0.8 for f in findings)
