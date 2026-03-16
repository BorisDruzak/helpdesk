"""
Тесты для проверки исправлений: capability gate, handshake payload, skipped, metadata validation, list_tools debounce.
Запуск: из директории server: pytest tests/test_playbook_fixes.py -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# --- Без БД ---


class TestToolMetadataValidation:
    """Контракт metadata: обязательные поля, filter_tools_production_catalog."""

    def test_tool_has_required_metadata_missing_keys(self):
        from utils.tool_metadata_validation import tool_has_required_metadata
        # Нет spec.metadata
        assert tool_has_required_metadata({"tool": "m.t", "spec": {}}) is False
        # Часть ключей
        assert tool_has_required_metadata({
            "tool": "m.t",
            "spec": {"metadata": {"domain": "diag", "platforms": []}}
        }) is False

    def test_tool_has_required_metadata_from_spec(self):
        from utils.tool_metadata_validation import tool_has_required_metadata
        meta = {
            "domain": "diag",
            "platforms": ["linux"],
            "risk_level": "low",
            "requires_consent": False,
            "timeout_sec": 30,
            "idempotent": True,
        }
        assert tool_has_required_metadata({
            "tool": "mod.tool",
            "spec": {"metadata": meta}
        }) is True

    def test_filter_tools_production_catalog(self):
        from utils.tool_metadata_validation import filter_tools_production_catalog
        full_meta = {
            "domain": "diag",
            "platforms": [],
            "risk_level": "low",
            "requires_consent": False,
            "timeout_sec": 10,
            "idempotent": True,
        }
        tools = [
            {"tool": "a.x", "spec": {}},
            {"tool": "b.y", "spec": {"metadata": full_meta}},
        ]
        out = filter_tools_production_catalog(tools)
        assert len(out) == 1
        assert out[0]["tool"] == "b.y"


class TestPlaybookCapabilityMetadataSource:
    """Capability gate читает metadata из tool.spec.metadata."""

    @pytest.mark.asyncio
    async def test_check_tool_available_async_and_spec_metadata(self):
        from app.services.playbook_capability import check_tool_available
        session = AsyncMock()
        devices_repo = AsyncMock()
        snap_repo = AsyncMock()
        device = MagicMock()
        device.os = "linux"
        devices_repo.get_by_device_id = AsyncMock(return_value=device)
        snapshot = MagicMock()
        snapshot.toolset_json = {
            "tools": [
                {
                    "tool": "ping_check.ping_host",
                    "spec": {"metadata": {"platforms": ["linux"]}},
                }
            ]
        }
        snap_repo.get_latest_snapshot = AsyncMock(return_value=snapshot)
        with patch("app.services.playbook_capability.DevicesRepo", return_value=devices_repo), \
             patch("app.services.playbook_capability.ToolsetSnapshotsRepo", return_value=snap_repo):
            ok, code, msg = await check_tool_available(session, "dev1", "ping_check.ping_host")
        assert ok is True
        assert code is None


class TestOperationsRepoHasPendingListTools:
    """has_pending_list_tools для debounce list_tools."""

    def test_has_pending_list_tools_constants(self):
        from app.repos.operations_repo import OperationsRepo
        assert hasattr(OperationsRepo, "PENDING_STATUSES")
        assert "queued" in OperationsRepo.PENDING_STATUSES
        assert "running" in OperationsRepo.PENDING_STATUSES
