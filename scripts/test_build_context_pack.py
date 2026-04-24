from scripts import build_context_pack


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
