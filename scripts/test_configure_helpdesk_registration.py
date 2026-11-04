import os
import stat

import pytest

from scripts.configure_helpdesk_registration import set_registration


def test_registration_preserves_other_settings_backup_and_idempotence(tmp_path):
    path = tmp_path / "helpdesk.env"
    original = b"# retained\nOIDC_ENABLED=true\nSYNTHETIC_SECRET=retained\n"
    path.write_bytes(original)
    assert set_registration(path, True)
    assert path.read_bytes() == original + b"WEB_SELF_REGISTRATION_ENABLED=true\n"
    backup, = tmp_path.glob("*.bak")
    assert backup.read_bytes() == original
    if os.name == "posix":
        assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert not set_registration(path, True)
    assert len(list(tmp_path.glob("*.bak"))) == 1
    assert set_registration(path, False)
    assert path.read_bytes() == original + b"WEB_SELF_REGISTRATION_ENABLED=false\n"


def test_registration_collapses_duplicate_settings_only(tmp_path):
    path = tmp_path / "helpdesk.env"
    path.write_text("WEB_SELF_REGISTRATION_ENABLED=false\nOTHER=1\nexport WEB_SELF_REGISTRATION_ENABLED = false\n")
    assert set_registration(path, True)
    assert path.read_text() == "OTHER=1\nWEB_SELF_REGISTRATION_ENABLED=true\n"


def test_invalid_policy_preserves_configuration(tmp_path):
    path = tmp_path / "helpdesk.env"
    path.write_bytes(b"OTHER=1\n")
    with pytest.raises(ValueError):
        set_registration(path, "true")
    assert path.read_bytes() == b"OTHER=1\n"
    assert not list(tmp_path.glob("*.bak"))
