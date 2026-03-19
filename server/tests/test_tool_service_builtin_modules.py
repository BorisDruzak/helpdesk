from types import SimpleNamespace

import pytest

from tools.service import ToolService


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_builtin_screen_module_skips_auto_install():
    service = ToolService(SimpleNamespace())

    result = await service._ensure_module_installed("device-1", "screen.collect")

    assert result is None
