from types import SimpleNamespace

import pytest

from tools.service import ToolService


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_builtin_screen_module_skips_auto_install():
    service = ToolService(SimpleNamespace())

    result = await service._ensure_module_installed("device-1", "screen.collect")

    assert result is None


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_builtin_diag_module_skips_auto_install():
    service = ToolService(SimpleNamespace())

    result = await service._ensure_module_installed("device-1", "diag.logs.collect")

    assert result is None


@pytest.mark.no_db
def test_manifest_tool_match_supports_aliases():
    entry = {
        "tool": "dns.resolve",
        "aliases": ["network_basic.resolve", "network_basic.resolve_dns"],
    }

    assert ToolService._tool_matches_manifest_entry(entry, "dns.resolve") is True
    assert ToolService._tool_matches_manifest_entry(entry, "network_basic.resolve") is True
    assert ToolService._tool_matches_manifest_entry(entry, "network_basic.resolve_dns") is True
    assert ToolService._tool_matches_manifest_entry(entry, "network_basic.lookup") is False
