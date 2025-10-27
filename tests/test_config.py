from rexlit.config import Settings


def test_anthropic_api_key_persisted_encrypted(tmp_path):
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"

    settings = Settings(
        data_dir=data_dir,
        config_dir=config_dir,
        anthropic_api_key="sk-ant-test",
    )

    stored_path = config_dir / "secrets" / "anthropic.api.enc"
    assert stored_path.exists()
    # Ciphertext should not contain the plaintext secret.
    assert b"sk-ant-test" not in stored_path.read_bytes()

    # Plaintext value is available via accessor but not stored on the model.
    assert settings.get_anthropic_api_key() == "sk-ant-test"
    assert settings.anthropic_api_key is None


def test_api_key_round_trip_across_instances(tmp_path):
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"

    settings = Settings(data_dir=data_dir, config_dir=config_dir)
    settings.store_api_key("deepseek", "sk-deepseek-test")

    fresh_settings = Settings(data_dir=data_dir, config_dir=config_dir)
    assert fresh_settings.get_deepseek_api_key() == "sk-deepseek-test"
