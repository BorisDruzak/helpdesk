from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agents.agent_builds_handlers import _resolve_recommended_build, _resolve_requested_build


@pytest.mark.no_db
def test_resolve_recommended_build_prefers_assigned_rollout():
    assigned_build = SimpleNamespace(target="windows_amd64", channel="stable", version="3.1.5")
    latest_build = SimpleNamespace(target="windows_amd64", channel="stable", version="3.2.9")

    class FakeAgentBuildsRepo:
        def __init__(self, _session):
            pass

        async def get_build(self, *, target, channel, version):
            if target == "windows_amd64" and channel == "stable" and version == "3.1.5":
                return assigned_build
            return None

        async def list_builds_for_target(self, *, target):
            assert target == "windows_amd64"
            return [latest_build, assigned_build]

    class FakeAgentRolloutRepo:
        def __init__(self, _session):
            pass

        async def get_assignment(self, target):
            assert target == "windows_amd64"
            return {"target": target, "channel": "stable", "version": "3.1.5"}

    with patch("agents.agent_builds_handlers.AgentBuildsRepo", FakeAgentBuildsRepo), \
         patch("agents.agent_builds_handlers.AgentRolloutRepo", FakeAgentRolloutRepo):
        build, source, assignment = asyncio.run(
            _resolve_recommended_build(object(), target="windows_amd64")
        )

    assert build is assigned_build
    assert source == "assigned_rollout"
    assert assignment["version"] == "3.1.5"


@pytest.mark.no_db
def test_resolve_requested_build_uses_assigned_rollout_when_version_is_omitted():
    assigned_build = SimpleNamespace(target="windows_amd64", channel="stable", version="4.0.1")
    latest_build = SimpleNamespace(target="windows_amd64", channel="stable", version="4.0.9")

    class FakeAgentBuildsRepo:
        def __init__(self, _session):
            pass

        async def get_build(self, *, target, channel, version):
            if target == "windows_amd64" and channel == "stable" and version == "4.0.1":
                return assigned_build
            return None

        async def get_latest_build(self, *, target, channel):
            assert target == "windows_amd64"
            assert channel == "stable"
            return latest_build

    class FakeAgentRolloutRepo:
        def __init__(self, _session):
            pass

        async def get_assignment(self, target):
            assert target == "windows_amd64"
            return {"target": target, "channel": "stable", "version": "4.0.1"}

    with patch("agents.agent_builds_handlers.AgentBuildsRepo", FakeAgentBuildsRepo), \
         patch("agents.agent_builds_handlers.AgentRolloutRepo", FakeAgentRolloutRepo):
        build, source = asyncio.run(
            _resolve_requested_build(
                object(),
                target="windows_amd64",
                channel="stable",
                version=None,
            )
        )

    assert build is assigned_build
    assert source == "assigned_rollout"
