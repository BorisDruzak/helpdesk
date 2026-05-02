from scripts import build_context_pack


def test_build_context_pack_includes_context_index_results(monkeypatch) -> None:
    def fake_search(*, query: str, limit: int):
        assert query == "run_tool command_result"
        assert limit == 4
        return [
            {
                "kind": "route",
                "name": "POST /api/admin/run_tool",
                "title": "POST /api/admin/run_tool",
                "path": "server/routes.py",
                "line_start": 42,
                "summary": "web.post('/api/admin/run_tool', handle_run_tool)",
                "extra": {"handler": "handle_run_tool"},
            }
        ]

    monkeypatch.setattr(build_context_pack, "_search_context_index", fake_search)

    pack = build_context_pack.build_context_pack("run_tool command_result", max_items=4)
    rendered = build_context_pack.render_context_pack(pack)

    assert pack["context_index_results"][0].startswith("[route] POST /api/admin/run_tool")
    assert "## Context Index Results" in rendered
    assert "server/routes.py:42" in rendered


def test_build_context_pack_uses_russian_topic_aliases() -> None:
    pack = build_context_pack.build_context_pack("обновление агента")

    assert pack["recommended_mode"] == "Agent updates / rollout"
    assert "agent_updates" in pack["matched_topics"]
    assert "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md" in pack["open_first"]
    assert "pc-client-agent-updates" in pack["skills"]


def test_render_context_pack_is_compact_and_actionable() -> None:
    pack = build_context_pack.build_context_pack("observer traces")
    rendered = build_context_pack.render_context_pack(pack)

    assert "# Context Pack: observer traces" in rendered
    assert "## Open First" in rendered
    assert "server/docs/OBSERVER_LAYER.md" in rendered
    assert "python scripts/verify_workspace.py" in rendered
