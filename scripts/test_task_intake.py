from scripts import navigation_catalog as nav
from scripts import task_intake


def test_build_intake_without_args_uses_current_diff(monkeypatch) -> None:
    monkeypatch.setattr(
        task_intake.nav,
        "collect_changed_paths",
        lambda **kwargs: [nav.ChangedPath(status="M", path="server/websocket/agent_handshake.py")],
    )

    payload = task_intake.build_intake()

    assert payload["input_paths"] == ["server/websocket/agent_handshake.py"]
    assert payload["recommended_mode"] == "Protocol V3 / WS"
    assert "python scripts/verify_workspace.py" in payload["checks_to_run"]


def test_task_query_routes_handshake_to_protocol_mode() -> None:
    payload = task_intake.build_intake(task="исправить handshake ws_ticket_v3")

    assert payload["recommended_mode"] == "Protocol V3 / WS"
    assert payload["recommended_playbook"] is None
    assert payload["input_paths"] == []
    assert "docs/CODEX_WORKFLOW.md" in payload["open_first"]
    assert "docs/ARCHITECTURE_BOUNDARIES.md" in payload["open_first"]
    assert "docs/CONTEXT_INDEX.md" in payload["open_first"]
    assert "docs/CODEX_WORKFLOW.md" in payload["docs_to_read"]
    assert "docs/ARCHITECTURE_BOUNDARIES.md" in payload["docs_to_read"]
    assert "docs/CONTEXT_INDEX.md" in payload["docs_to_read"]
    assert "server/docs/PROTOCOL_V3.md" in payload["docs_to_read"]


def test_task_query_routes_launcher_rollout_to_agent_updates() -> None:
    payload = task_intake.build_intake(task="обновить launcher и rollout")

    assert payload["recommended_mode"] == "Agent updates / rollout"
    assert payload["recommended_playbook"] == "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md"
    assert "python pc_agent/build_windows_release_v2.py" in payload["checks_to_run"]
    assert payload["plan_required"] is True


def test_task_query_routes_tray_behavior_to_runtime_playbook() -> None:
    payload = task_intake.build_intake(task="поправить tray close behavior")

    assert payload["recommended_mode"] == "Agent runtime / tray / logs"
    assert payload["recommended_playbook"] == "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md"
    assert "python -m pytest pc_agent/tests/test_runtime_logging.py -v --tb=short" in payload["checks_to_run"]
    assert "python scripts/manage_local_agent.py start <name> --gui --ui-port <port>" in payload["checks_to_run"]


def test_task_query_routes_new_api_route_to_docs_sync() -> None:
    payload = task_intake.build_intake(task="добавить новый API route")

    assert payload["recommended_mode"] == "Docs + CODEMAP"
    assert payload["recommended_playbook"] is None
    assert "docs/CODEX_WORKFLOW.md" in payload["open_first"]
    assert "docs/ARCHITECTURE_BOUNDARIES.md" in payload["open_first"]
    assert "docs/CONTEXT_INDEX.md" in payload["open_first"]
    assert "docs/CODEX_WORKFLOW.md" in payload["docs_to_update_if_code_changes"]
    assert "server/docs/CODEMAP.md" in payload["docs_to_update_if_code_changes"]
    assert "docs/QUICK_LOOKUP.md" in payload["docs_to_update_if_code_changes"]
    assert "docs/ARCHITECTURE_BOUNDARIES.md" in payload["docs_to_update_if_code_changes"]


def test_task_query_routes_admin_ui_review_to_web_platform() -> None:
    payload = task_intake.build_intake(task="ui review accessibility admin")

    assert payload["recommended_mode"] == "Internal web platform / React"
    assert "python scripts/bootstrap_web_toolchain.py" in payload["checks_to_run"]
    assert "GUI check via MCP at https://192.168.100.17:9443/admin" in payload["checks_to_run"]


def test_task_query_routes_context_index() -> None:
    payload = task_intake.build_intake(task="rag context index поиск по символам")

    assert payload["recommended_mode"] == "Context index / retrieval"
    assert "docs/CONTEXT_INDEX.md" in payload["open_first"]
    assert "python scripts/build_context_index.py --force" in payload["checks_to_run"]


def test_task_query_routes_russian_agent_update_aliases() -> None:
    payload = task_intake.build_intake(task="обновление агента лаунчер раскатка")

    assert payload["recommended_mode"] == "Agent updates / rollout"
    assert payload["recommended_playbook"] == "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md"


def test_task_query_routes_russian_runtime_aliases() -> None:
    payload = task_intake.build_intake(task="трей закрытие окна логи агента")

    assert payload["recommended_mode"] == "Agent runtime / tray / logs"
    assert payload["recommended_playbook"] == "pc_agent/docs/AGENT_RUNTIME_ALWAYS_ON.md"


def test_task_query_routes_russian_release_aliases() -> None:
    payload = task_intake.build_intake(task="релиз выкладка дымовой тест")

    assert payload["recommended_mode"] == "Release / deploy"
    assert payload["recommended_playbook"] == "docs/LOCAL_WORKFLOW.md"


def test_task_query_routes_russian_observer_aliases() -> None:
    payload = task_intake.build_intake(task="трасса наблюдаемость деградации")

    assert payload["recommended_mode"] == "Observer / tracing"
    assert "server/docs/OBSERVER_LAYER.md" in payload["docs_to_read"]
