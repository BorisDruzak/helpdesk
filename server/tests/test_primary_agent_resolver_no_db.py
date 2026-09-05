from __future__ import annotations

from types import SimpleNamespace

import pytest

from registry.primary_agent_resolver import PrimaryAgentResolver


@pytest.mark.no_db
@pytest.mark.parametrize(
    ("online", "expected"),
    [
        (True, (True, "online")),
        (False, (False, "offline")),
    ],
)
def test_primary_agent_resolver_uses_runtime_presence(online: bool, expected: tuple[bool, str]) -> None:
    resolver = PrimaryAgentResolver(
        None,
        state=SimpleNamespace(is_agent_online=lambda device_id: online if device_id == "device-1" else False),
    )

    assert resolver._connection_state("device-1") == expected


@pytest.mark.no_db
def test_primary_agent_resolver_fails_closed_when_presence_is_unavailable() -> None:
    resolver = PrimaryAgentResolver(None, state=SimpleNamespace(is_agent_online=lambda _device_id: (_ for _ in ()).throw(RuntimeError())))

    assert resolver._connection_state("device-1") == (None, "unknown")
