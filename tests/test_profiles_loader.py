"""Tests for profile loading utilities."""


import pytest

from rexlit.config import Settings
from rexlit.utils.profiles import load_profile


def test_load_profile_default_path_missing(tmp_path):
    """Test loading default profile when it doesn't exist."""
    settings = Settings(config_dir=tmp_path / "nonexistent")
    profile = load_profile(None, settings)

    assert profile == {}


def test_load_profile_custom_path(tmp_path):
    """Test loading profile from custom path."""
    profile_file = tmp_path / "test_profile.yaml"
    profile_file.write_text("""
pii:
  enabled_patterns: [ssn, email]
privilege:
  attorney_domains: [lawfirm.com]
""")

    settings = Settings(config_dir=tmp_path)
    profile = load_profile(profile_file, settings)

    assert "pii" in profile
    assert "privilege" in profile
    assert profile["pii"]["enabled_patterns"] == ["ssn", "email"]
    assert profile["privilege"]["attorney_domains"] == ["lawfirm.com"]


def test_load_profile_default_from_config_dir(tmp_path):
    """Test loading default profile from config directory."""
    config_dir = tmp_path / "config"
    profiles_dir = config_dir / "profiles"
    profiles_dir.mkdir(parents=True)

    profile_file = profiles_dir / "default.yaml"
    profile_file.write_text("""
pii:
  enabled_patterns: [email]
privilege:
  threshold: 0.8
""")

    settings = Settings(config_dir=config_dir)
    profile = load_profile(None, settings)

    assert profile["pii"]["enabled_patterns"] == ["email"]
    assert profile["privilege"]["threshold"] == 0.8


def test_load_profile_empty_file(tmp_path):
    """Test loading empty profile file."""
    profile_file = tmp_path / "empty.yaml"
    profile_file.write_text("")

    settings = Settings(config_dir=tmp_path)
    profile = load_profile(profile_file, settings)

    assert profile == {}


def test_load_profile_invalid_yaml(tmp_path):
    """Test loading invalid YAML raises error."""
    profile_file = tmp_path / "invalid.yaml"
    profile_file.write_text("{ invalid: yaml: }")

    settings = Settings(config_dir=tmp_path)
    with pytest.raises(ValueError):
        load_profile(profile_file, settings)


def test_load_profile_complex_structure(tmp_path):
    """Test loading complex profile structure."""
    profile_file = tmp_path / "complex.yaml"
    profile_file.write_text("""
pii:
  enabled_patterns: [ssn, email, phone]
  domain_whitelist: [internal.com, safe.org]
  domain_blacklist: [suspicious.com]
  names: [John Doe, Jane Smith]

privilege:
  attorney_domains: [lawfirm.com, legal.net, counsel.org]
  attorney_names: [Jane Smith Esq., John Counsel]
  keywords: [attorney-client, work product, legal advice]
  threshold: 0.75
""")

    settings = Settings(config_dir=tmp_path)
    profile = load_profile(profile_file, settings)

    assert len(profile["pii"]["domain_whitelist"]) == 2
    assert len(profile["privilege"]["attorney_domains"]) == 3
    assert len(profile["privilege"]["keywords"]) == 3


def test_load_profile_relative_path(tmp_path):
    """Test that absolute path resolution works."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir(parents=True)

    profile_file = profiles_dir / "test.yaml"
    profile_file.write_text("pii:\n  enabled_patterns: [ssn]")

    settings = Settings(config_dir=tmp_path)
    profile = load_profile(profile_file, settings)

    assert profile["pii"]["enabled_patterns"] == ["ssn"]
