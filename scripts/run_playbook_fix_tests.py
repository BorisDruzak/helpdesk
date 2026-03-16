#!/usr/bin/env python3
"""
Проверка исправлений playbook/capability без БД и без pytest conftest.
Запуск: из корня репозитория: python3 scripts/run_playbook_fix_tests.py
       или из server: python3 ../scripts/run_playbook_fix_tests.py (нужен PYTHONPATH=.)
"""
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SERVER_DIR = WORKSPACE / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
sys.path.insert(0, str(WORKSPACE))

def main():
    failed = []
    # 1. Tool metadata validation
    print("1. utils.tool_metadata_validation ...")
    try:
        from utils.tool_metadata_validation import (
            tool_has_required_metadata,
            filter_tools_production_catalog,
            REQUIRED_METADATA_KEYS,
        )
        assert not tool_has_required_metadata({"tool": "m.t", "spec": {}})
        meta = {
            "domain": "diag",
            "platforms": ["linux"],
            "risk_level": "low",
            "requires_consent": False,
            "timeout_sec": 30,
            "idempotent": True,
        }
        assert tool_has_required_metadata({"tool": "mod.tool", "spec": {"metadata": meta}})
        tools = [{"tool": "a.x", "spec": {}}, {"tool": "b.y", "spec": {"metadata": meta}}]
        out = filter_tools_production_catalog(tools)
        assert len(out) == 1 and out[0]["tool"] == "b.y"
        print("   OK")
    except Exception as e:
        print(f"   FAIL: {e}")
        failed.append(("tool_metadata_validation", e))

    # 2. Playbook capability: async + spec.metadata
    print("2. playbook_capability async + spec.metadata ...")
    try:
        from app.services.playbook_capability import check_tool_available
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch
        session = AsyncMock()
        devices_repo = AsyncMock()
        snap_repo = AsyncMock()
        device = MagicMock()
        device.os = "linux"
        devices_repo.get_by_device_id = AsyncMock(return_value=device)
        snapshot = MagicMock()
        snapshot.toolset_json = {
            "tools": [
                {"tool": "ping_check.ping_host", "spec": {"metadata": {"platforms": ["linux"]}}},
            ]
        }
        snap_repo.get_latest_snapshot = AsyncMock(return_value=snapshot)
        with patch("app.services.playbook_capability.DevicesRepo", return_value=devices_repo), \
             patch("app.services.playbook_capability.ToolsetSnapshotsRepo", return_value=snap_repo):
            ok, code, msg = asyncio.run(check_tool_available(session, "dev1", "ping_check.ping_host"))
        assert ok is True and code is None
        print("   OK")
    except Exception as e:
        print(f"   FAIL: {e}")
        failed.append(("playbook_capability", e))

    # 3. OperationsRepo.has_pending_list_tools
    print("3. OperationsRepo.PENDING_STATUSES / has_pending_list_tools ...")
    try:
        from app.repos.operations_repo import OperationsRepo
        assert hasattr(OperationsRepo, "PENDING_STATUSES")
        assert "queued" in OperationsRepo.PENDING_STATUSES
        assert "running" in OperationsRepo.PENDING_STATUSES
        print("   OK")
    except Exception as e:
        print(f"   FAIL: {e}")
        failed.append(("operations_repo", e))

    # 4. Feature flags in config
    print("4. config feature flags ...")
    try:
        import config
        assert hasattr(config, "PLAYBOOK_SCHEDULER_ENABLED")
        assert hasattr(config, "PLAYBOOK_PARALLEL_ENABLED")
        assert hasattr(config, "CAPABILITY_GATE_STRICT")
        print("   OK")
    except Exception as e:
        print(f"   FAIL: {e}")
        failed.append(("config_flags", e))

    # 5. smoke_install_and_run handler returns 410
    print("5. handle_smoke_install_and_run returns 410 ...")
    try:
        import asyncio
        from unittest.mock import MagicMock, AsyncMock
        from modules.handlers import handle_smoke_install_and_run
        req = MagicMock()
        req.json = AsyncMock(return_value={})
        resp = asyncio.run(handle_smoke_install_and_run(req))
        assert resp.status == 410
        body = __import__("json").loads(resp.body.decode() if isinstance(resp.body, bytes) else resp.body)
        assert body.get("deprecated") is True
        assert "smoke_install_and_run" in body.get("error", "")
        print("   OK")
    except Exception as e:
        print(f"   FAIL: {e}")
        failed.append(("smoke_install_and_run_410", e))

    print()
    if failed:
        print(f"FAILED: {len(failed)}")
        for name, err in failed:
            print(f"  - {name}: {err}")
        sys.exit(1)
    print("All checks OK.")
    sys.exit(0)


if __name__ == "__main__":
    main()
