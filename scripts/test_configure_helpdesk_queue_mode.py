import pytest

from scripts.configure_helpdesk_queue_mode import set_queue_mode


def test_mode_update_preserves_other_settings_and_private_backup(tmp_path):
    path = tmp_path / "helpdesk.env"
    original = "# retained\nSYNTHETIC_OTHER=value\nTICKET_QUEUE_MODE=partitioned\n"
    path.write_text(original, encoding="utf-8")
    assert set_queue_mode(path, "unified") is True
    assert path.read_text(encoding="utf-8") == original.replace("partitioned", "unified")
    backups = list(tmp_path.glob("*.bak"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == original
    assert set_queue_mode(path, "unified") is False
    assert len(list(tmp_path.glob("*.bak"))) == 1
    assert set_queue_mode(path, "partitioned") is True
    assert path.read_text(encoding="utf-8") == original


def test_invalid_mode_does_not_change_configuration(tmp_path):
    path = tmp_path / "helpdesk.env"
    path.write_text("RETAIN=1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        set_queue_mode(path, "unknown")
    assert path.read_text(encoding="utf-8") == "RETAIN=1\n"
