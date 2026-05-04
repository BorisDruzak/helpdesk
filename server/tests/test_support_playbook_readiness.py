from types import SimpleNamespace

from web_api.support_handlers import (
    _build_operation_display,
    _build_playbook_launch_readiness,
)


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
    assert readiness.missing_tools == ["ip_address.get_ip", "diag.logs.collect"]
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


def test_operation_display_marks_logical_failed_result():
    operation = SimpleNamespace(
        status="succeeded",
        result_summary="{'ok': False, 'error_code': 'MISSING_TARGET', 'error': 'target is required'}",
        error_message=None,
    )

    display_status, display_label = _build_operation_display(operation)

    assert display_status == "failed"
    assert display_label == "Ошибка результата: MISSING_TARGET"
