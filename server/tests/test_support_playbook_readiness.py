from types import SimpleNamespace

from web_api.support_handlers import (
    _build_operation_display,
    _build_playbook_launch_readiness,
)
import pytest


pytestmark = pytest.mark.db_cleanup("tickets")

def test_playbook_readiness_blocks_missing_tools_and_required_params():
    manifest = {
        "blocks": [
            {
                "tool": "network.ping",
                "params": {},
                "tool_manifest": {
                    "params_schema": {
                        "type": "object",
                        "required": ["target"],
                        "properties": {"target": {"type": "string"}},
                    }
                },
            }
        ],
        "required_tools": [
            {"tool": "network.ping", "params_schema": {"type": "object"}},
            {"tool": "ip_address.get_ip"},
            {"tool": "diag.logs.collect"},
        ],
    }

    readiness = _build_playbook_launch_readiness(
        manifest,
        device_id="device-1",
        available_tool_names={"network.ping"},
    )

    assert readiness.can_run is False
    assert readiness.missing_tools == ["ip_address.get_ip"]
    assert readiness.missing_params == ["network.ping.target"]
    assert "Недоступны инструменты" in readiness.label
    assert "Не заполнены параметры" in readiness.label


def test_playbook_readiness_allows_server_installable_tools():
    manifest = {
        "required_tools": [
            {"tool": "network.ping"},
            {"tool": "system.collect"},
        ],
    }

    readiness = _build_playbook_launch_readiness(
        manifest,
        device_id="device-1",
        available_tool_names={"network.ping", "system.collect"},
    )

    assert readiness.can_run is True
    assert readiness.missing_tools == []
    assert readiness.label == "Готов к запуску"


def test_playbook_readiness_does_not_require_agent_toolset_for_non_agent_capabilities():
    manifest = {
        "required_capabilities": [
            {"capability_id": "server.http.request", "execution_target": "server_builtin"},
            {"capability_id": "observer.ticket.summary", "execution_target": "observer_query"},
            {"capability_id": "endpoint.http.request", "execution_target": "agent_managed_module"},
        ],
        "blocks": [
            {
                "capability_id": "server.http.request",
                "execution_target": "server_builtin",
                "params": {},
                "tool_manifest": {
                    "params_schema": {
                        "type": "object",
                        "required": ["url"],
                        "properties": {"url": {"type": "string"}},
                    }
                },
            }
        ],
    }

    readiness = _build_playbook_launch_readiness(
        manifest,
        device_id="device-1",
        available_tool_names=set(),
    )

    assert readiness.can_run is False
    assert readiness.missing_tools == ["endpoint.http.request"]
    assert readiness.missing_params == ["server.http.request.url"]


def test_operation_display_marks_logical_failed_result():
    operation = SimpleNamespace(
        status="succeeded",
        result_summary="{'ok': False, 'error_code': 'MISSING_TARGET', 'error': 'target is required'}",
        error_message=None,
    )

    display_status, display_label = _build_operation_display(operation)

    assert display_status == "failed"
    assert display_label == "Ошибка результата: MISSING_TARGET"
