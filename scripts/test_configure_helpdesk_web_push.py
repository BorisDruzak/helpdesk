from pathlib import Path
import hashlib

import pytest

from scripts.configure_helpdesk_web_push import configure_files


def test_configuration_is_private_idempotent_and_preserves_unrelated_settings(tmp_path):
    env = tmp_path / "helpdesk.env"
    original = b"APP_ENV=staging\nUNRELATED_SETTING=preserve\n"
    env.write_bytes(original)
    env.chmod(0o600)
    key = tmp_path / "vapid.pem"
    receipt = configure_files(env, key, "https://helpdesk-staging.sosnadmin.local", expected_sha256=hashlib.sha256(original).hexdigest())
    assert receipt["key_created"] is True
    assert b"UNRELATED_SETTING=preserve" in env.read_bytes()
    assert b"PRIVATE KEY" not in env.read_bytes()
    first_key = key.read_bytes()
    before = hashlib.sha256(env.read_bytes()).hexdigest()
    repeat = configure_files(env, key, "https://helpdesk-staging.sosnadmin.local", expected_sha256=before)
    assert repeat["key_created"] is False
    assert repeat["changed"] is False
    assert key.read_bytes() == first_key
    assert env.read_bytes().count(b"HELPDESK_WEB_PUSH_PRIVATE_KEY_FILE=") == 1


def test_changed_config_is_rejected_before_creating_key(tmp_path):
    env = tmp_path / "helpdesk.env"; env.write_text("UNRELATED_SETTING=preserve\n")
    key = tmp_path / "vapid.pem"
    with pytest.raises(ValueError, match="changed"):
        configure_files(env, key, "https://helpdesk-staging.sosnadmin.local", expected_sha256="0" * 64)
    assert not key.exists()


def test_symlink_configuration_or_key_is_rejected(tmp_path):
    env = tmp_path / "helpdesk.env"; env.write_text("APP_ENV=staging\n")
    key = tmp_path / "vapid.pem"
    target = tmp_path / "other.pem"; target.write_text("not a key")
    try:
        key.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation unavailable to this Windows token")
    with pytest.raises(ValueError, match="symlink"):
        configure_files(env, key, "https://helpdesk-staging.sosnadmin.local", expected_sha256=hashlib.sha256(env.read_bytes()).hexdigest())
