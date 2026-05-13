from __future__ import annotations

import pytest

from diagnostics.capability_models import EXECUTION_TARGETS, READINESS_STATUSES, CapabilityDescriptor
from diagnostics.readiness import CapabilityReadinessService, ReadinessContext


pytestmark = [pytest.mark.no_db]


def _recipe_capability(**overrides) -> CapabilityDescriptor:
    values = {
        "id": "endpoint.spooler.status",
        "title": "Check print spooler",
        "provider_id": "agent_recipe_runner",
        "provider_type": "agent_recipe_runner",
        "execution_target": "agent_recipe",
        "requires_device": True,
        "requires_agent_online": True,
        "install_required_on_agent": False,
        "supports_auto_install": True,
        "platforms": ["win32"],
        "source": "agent_recipe",
        "evidence": {
            "produces_evidence": True,
            "kind": "endpoint.service",
            "domain": "endpoint",
            "perspective": "endpoint",
            "passport_eligible": True,
        },
        "runner_provider_id": "agent_recipe_runner",
        "min_runner_version": "1.0.0",
        "primitive_id": "service.status",
        "primitive_version": "1.0",
    }
    values.update(overrides)
    return CapabilityDescriptor(**values)


class _State:
    def __init__(self, online: bool = True):
        self.online = online

    def is_agent_online(self, _device_id: str) -> bool:
        return self.online


def test_agent_recipe_target_and_readiness_statuses_are_first_class():
    assert "agent_recipe" in EXECUTION_TARGETS
    for status in (
        "runner_not_installed",
        "runner_install_required",
        "runner_installing",
        "runner_outdated",
        "primitive_not_supported",
        "recipe_not_published",
    ):
        assert status in READINESS_STATUSES


@pytest.mark.asyncio
async def test_agent_recipe_readiness_handles_runner_states():
    service = CapabilityReadinessService(state=_State(online=True))
    cap = _recipe_capability()

    no_device = await service.get_readiness(cap, ReadinessContext(ticket_id="ticket-1"))
    offline = await CapabilityReadinessService(state=_State(online=False)).get_readiness(
        cap,
        ReadinessContext(ticket_id="ticket-1", device_id="device-1"),
    )
    unsupported = await service.get_readiness(
        cap,
        ReadinessContext(ticket_id="ticket-1", device_id="device-1", device_platform="linux"),
    )
    missing_runner = await service.get_readiness(
        cap,
        ReadinessContext(ticket_id="ticket-1", device_id="device-1", device_platform="win32"),
    )
    installing_runner = await service.get_readiness(
        cap,
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            installed_modules={"agent_recipe_runner": {"version": "1.0.0", "active": False, "state": "installing"}},
        ),
    )
    outdated_runner = await service.get_readiness(
        cap,
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            installed_modules={"agent_recipe_runner": {"version": "0.9.0", "active": True, "state": "active"}},
        ),
    )
    missing_primitive = await service.get_readiness(
        cap,
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            installed_modules={"agent_recipe_runner": {"version": "1.0.0", "active": True, "state": "active"}},
            dependency_status={"agent_recipe_runner:service.status": False},
        ),
    )
    available = await service.get_readiness(
        cap,
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            installed_modules={"agent_recipe_runner": {"version": "1.0.0", "active": True, "state": "active"}},
            dependency_status={"agent_recipe_runner:service.status": True},
        ),
    )

    assert no_device.readiness == "unavailable"
    assert offline.readiness == "agent_offline"
    assert unsupported.readiness == "unsupported_platform"
    assert missing_runner.readiness == "runner_not_installed"
    assert "install_runner" in missing_runner.actions
    assert installing_runner.readiness == "runner_installing"
    assert outdated_runner.readiness == "runner_outdated"
    assert "upgrade_runner" in outdated_runner.actions
    assert missing_primitive.readiness == "primitive_not_supported"
    assert available.readiness == "available"
    assert "run" in available.actions
