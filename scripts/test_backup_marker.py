from __future__ import annotations

import json
from pathlib import Path

import scripts.write_backup_status_marker as backup_marker


def test_backup_status_marker_writer(tmp_path: Path) -> None:
    output = tmp_path / "backup-status.json"

    payload = backup_marker.write_backup_status_marker(
        output=output,
        status="success",
        target="pc_client_prod",
        duration_seconds=37,
        artifact="artifacts/backups/backup.dump",
    )

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == payload
    assert persisted["status"] == "success"
    assert persisted["target"] == "pc_client_prod"
    assert persisted["duration_seconds"] == 37
    assert "password" not in str(persisted).lower()
    assert "token" not in str(persisted).lower()
