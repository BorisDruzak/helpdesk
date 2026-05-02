import json
import sqlite3
from pathlib import Path

from scripts import context_index


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sample_workspace(tmp_path: Path) -> Path:
    _write(
        tmp_path / "AGENTS.md",
        "# AGENTS\n\n## Workflow\n\nRead CODEX_WORKFLOW before edits.\n",
    )
    _write(
        tmp_path / "docs" / "CONTEXT_INDEX.md",
        "# Context Index\n\n## Commands\n\nSearch examples mention run_tool command_result observer for smoke checks.\n",
    )
    _write(
        tmp_path / "docs" / "QUICK_LOOKUP.md",
        "# QUICK_LOOKUP\n\n## Modules\n\nStart with run_tool and module registry.\n",
    )
    _write(
        tmp_path / "docs" / "ARCHITECTURE_BOUNDARIES.md",
        "# Architecture Boundaries\n\n## Contract Surfaces\n\nProtocol V3 and Tool contract are cross-cutting.\n",
    )
    _write(
        tmp_path / "server" / "docs" / "CODEMAP.md",
        "# CODEMAP (server)\n\n## WebSocket\n\ncommand_result and outbox_ack live in websocket services.\n",
    )
    _write(
        tmp_path / "server" / "routes.py",
        "from aiohttp import web\n\n"
        "def setup_routes(app):\n"
        "    app.add_routes([\n"
        "        web.post('/api/tools/run', handle_run_tool),\n"
        "        web.get('/ws', websocket_handler),\n"
        "    ])\n",
    )
    _write(
        tmp_path / "server" / "tools" / "service.py",
        "class ToolExecutionService:\n"
        "    async def run_tool(self, tool_name: str):\n"
        "        return {'status': 'ok'}\n",
    )
    _write(
        tmp_path / "pc_agent" / "core" / "orchestrator.py",
        "def command_result_handler(payload):\n"
        "    return payload\n",
    )
    _write(
        tmp_path / "server" / "tests" / "test_tool_runtime.py",
        "def test_run_tool_records_command_result():\n"
        "    assert 'command_result'\n",
    )
    _write(
        tmp_path / "artifacts" / "noise.md",
        "# Noise\n\nThis run_tool text must not be indexed.\n",
    )
    return tmp_path


def test_build_index_includes_docs_routes_symbols_and_excludes_artifacts(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    db_path = tmp_path / "index.sqlite"

    stats = context_index.build_index(workspace=workspace, db_path=db_path, force=True)

    assert stats["docs"] >= 4
    assert stats["chunks"] >= 4
    assert stats["routes"] == 2
    assert stats["symbols"] >= 3
    assert stats["fts_enabled"] in {True, False}

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("select kind, path, name from items order by kind, path, name").fetchall()

    assert ("route", "server/routes.py", "POST /api/tools/run") in rows
    assert ("test", "server/tests/test_tool_runtime.py", "test_run_tool_records_command_result") in rows
    assert ("symbol", "server/tools/service.py", "ToolExecutionService") in rows
    assert ("symbol", "server/tools/service.py", "ToolExecutionService.run_tool") in rows
    assert all("artifacts/" not in row[1].replace("\\", "/") for row in rows)


def test_search_returns_ranked_docs_symbols_and_routes(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    db_path = tmp_path / "index.sqlite"
    context_index.build_index(workspace=workspace, db_path=db_path, force=True)

    results = context_index.search_index(db_path=db_path, query="run_tool command_result", limit=10)

    assert results
    assert any(item["kind"] == "symbol" and item["name"] == "ToolExecutionService.run_tool" for item in results)
    assert any(item["kind"] == "route" and item["name"] == "POST /api/tools/run" for item in results)
    assert any(item["kind"] == "doc" and "CODEMAP.md" in item["path"] for item in results)


def test_routes_include_handler_metadata_and_rendering(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    db_path = tmp_path / "index.sqlite"
    context_index.build_index(workspace=workspace, db_path=db_path, force=True)

    results = context_index.search_index(db_path=db_path, query="run_tool", kind="route", limit=5)
    run_tool_route = next(item for item in results if item["name"] == "POST /api/tools/run")
    rendered = context_index.render_search_results([run_tool_route])

    assert run_tool_route["extra"]["handler"] == "handle_run_tool"
    assert "-> handle_run_tool" in rendered


def test_search_can_filter_by_kind_and_render_json(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    db_path = tmp_path / "index.sqlite"
    context_index.build_index(workspace=workspace, db_path=db_path, force=True)

    results = context_index.search_index(db_path=db_path, query="run_tool", kind="symbol", limit=5)
    rendered = context_index.render_search_results(results, json_output=True)

    payload = json.loads(rendered)
    assert payload["results"]
    assert {item["kind"] for item in payload["results"]} == {"symbol"}
    assert any(item["name"] == "ToolExecutionService.run_tool" for item in payload["results"])


def test_search_profiles_can_prioritize_routes_and_tests(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    db_path = tmp_path / "index.sqlite"
    context_index.build_index(workspace=workspace, db_path=db_path, force=True)

    route_results = context_index.search_index(db_path=db_path, query="run_tool", profile="route", limit=3)
    test_results = context_index.search_index(db_path=db_path, query="command_result run_tool", profile="test", limit=3)
    contract_results = context_index.search_index(db_path=db_path, query="Protocol V3 Tool contract", profile="contract", limit=3)

    assert route_results[0]["kind"] == "route"
    assert route_results[0]["name"] == "POST /api/tools/run"
    assert any(item["kind"] == "test" and item["name"] == "test_run_tool_records_command_result" for item in test_results)
    assert contract_results[0]["kind"] == "doc"
    assert contract_results[0]["path"] == "docs/ARCHITECTURE_BOUNDARIES.md"


def test_domain_search_reranks_context_index_docs_below_domain_results(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    db_path = tmp_path / "index.sqlite"
    context_index.build_index(workspace=workspace, db_path=db_path, force=True)

    results = context_index.search_index(db_path=db_path, query="run_tool command_result observer", limit=5)

    assert results[0]["path"] != "docs/CONTEXT_INDEX.md"
    assert any("CODEMAP.md" in item["path"] or item["kind"] in {"route", "symbol"} for item in results[:3])


def test_freshness_status_reports_changed_index_sources(tmp_path: Path) -> None:
    workspace = _sample_workspace(tmp_path)
    db_path = tmp_path / "index.sqlite"
    context_index.build_index(workspace=workspace, db_path=db_path, force=True)

    _write(
        workspace / "server" / "tools" / "service.py",
        "class ToolExecutionService:\n"
        "    async def run_tool(self, tool_name: str):\n"
        "        return {'status': 'changed'}\n",
    )
    status = context_index.freshness_status(workspace=workspace, db_path=db_path)
    warning = context_index.format_freshness_warning(status)

    assert status["exists"] is True
    assert status["stale"] is True
    assert "server/tools/service.py" in status["changed_paths"]
    assert "stale" in warning.lower()
