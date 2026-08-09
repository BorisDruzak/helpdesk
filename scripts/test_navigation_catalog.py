from scripts import navigation_catalog as nav
from pathlib import Path


def test_find_topics_for_query_includes_planning_topic() -> None:
    topics = nav.find_topics_for_query("plans.md")

    assert any(topic.key == "planning" for topic in topics)


def test_knowledge_queries_route_to_external_platform_topic() -> None:
    topics = nav.find_topics_for_query("KnowledgePort external integration")

    assert any(topic.key == "external_knowledge_platform" for topic in topics)
    assert all(topic.key != "knowledge_platform" for topic in topics)


def test_external_knowledge_topic_contains_no_removed_local_artifacts() -> None:
    topics = [topic for topic in nav.TOPICS if topic.key == "external_knowledge_platform"]
    assert len(topics) == 1
    topic = topics[0]
    artifacts = "\n".join(nav.iter_topic_artifacts(topic))
    metadata = "\n".join((*topic.aliases, topic.summary, *topic.checks))

    assert "KnowledgePort" in metadata
    for removed_surface in (
        "server/knowledge/",
        "server/ai/",
        "knowledge_repo.py",
        "/api/knowledge/",
        "/api/web/knowledge/",
        "/app/knowledge",
        "KNOWLEDGE_PLATFORM.md",
    ):
        assert removed_surface not in artifacts
        assert removed_surface not in metadata


def test_release_topic_related_docs_include_handoff_artifacts() -> None:
    release_topic = next(topic for topic in nav.TOPICS if topic.key == "release")

    assert "PLANS.md" in release_topic.related_docs
    assert "docs/LOCAL_WORKFLOW.md" in release_topic.related_docs
    assert nav.RELEASE_SKILL in release_topic.skills


def test_harness_drift_rules_require_non_markdown_artifacts() -> None:
    navigation_rule = next(rule for rule in nav.DRIFT_RULES if rule.key == "navigation_harness")
    workflow_rule = next(rule for rule in nav.DRIFT_RULES if rule.key == "workflow_harness")

    assert "docs/CONTEXT_EFFICIENCY.md" in navigation_rule.required_docs
    assert "docs/AGENT_CAPABILITIES_AND_REQUIREMENTS.md" in workflow_rule.required_docs


def test_agent_updates_query_prefers_agent_updates_topic() -> None:
    topics = nav.find_topics_for_query("launcher rollout")

    assert topics[0].key == "agent_updates"
    assert topics[0].playbook == "pc_agent/docs/AGENT_UPDATE_WORKFLOW.md"
    assert topics[0].plan_required is True


def test_collect_docs_to_update_uses_drift_rules_for_task_intake() -> None:
    docs = nav.collect_docs_to_update((), paths=("scripts/task_intake.py",))

    assert "AGENTS.md" in docs
    assert "docs/CODEX_WORKFLOW.md" in docs
    assert "docs/QUICK_LOOKUP.md" in docs
    assert "docs/ARCHITECTURE_BOUNDARIES.md" in docs
    assert "docs/CONTEXT_EFFICIENCY.md" in docs


def test_docs_sync_topic_includes_architecture_boundaries() -> None:
    topic = next(topic for topic in nav.TOPICS if topic.key == "docs_sync")

    assert "docs/CODEX_WORKFLOW.md" in topic.first_files
    assert "docs/CODEX_WORKFLOW.md" in topic.related_docs
    assert "docs/CODEX_WORKFLOW.md" in topic.docs_to_update
    assert "docs/ARCHITECTURE_BOUNDARIES.md" in topic.first_files
    assert "docs/ARCHITECTURE_BOUNDARIES.md" in topic.related_docs
    assert "docs/ARCHITECTURE_BOUNDARIES.md" in topic.docs_to_update
    assert "docs/CONTEXT_INDEX.md" in topic.first_files
    assert "docs/CONTEXT_INDEX.md" in topic.related_docs
    assert "docs/CONTEXT_INDEX.md" in topic.docs_to_update
    assert "scripts/search_context_index.py" in topic.first_files


def test_context_index_topic_routes_retrieval_queries() -> None:
    topics = nav.find_topics_for_query("rag context index symbols routes")

    assert topics[0].key == "context_index"
    assert "scripts/build_context_index.py" in topics[0].first_files
    assert "scripts/search_context_index.py" in topics[0].first_files
    assert "docs/CONTEXT_INDEX.md" in topics[0].docs_to_update


def test_context_index_drift_requires_context_docs() -> None:
    docs = nav.collect_docs_to_update((), paths=("scripts/context_index.py",))

    assert "docs/CONTEXT_INDEX.md" in docs
    assert "docs/CODEX_WORKFLOW.md" in docs
    assert "docs/QUICK_LOOKUP.md" in docs


def test_all_topic_artifacts_exist() -> None:
    missing: list[str] = []
    for topic in nav.TOPICS:
        for artifact in nav.iter_topic_artifacts(topic):
            if not (nav.REPO_ROOT / Path(artifact)).exists():
                missing.append(artifact)

    assert missing == []


def test_domain_drift_rules_require_navigation_catalog_and_quick_lookup() -> None:
    rule_keys = {
        "server_entrypoints",
        "server_protocol",
        "agent_protocol",
        "server_auth",
        "agent_auth",
        "modules",
        "tickets",
        "server_ui_structure",
        "agent_gui_structure",
        "agent_updates_flow",
        "agent_runtime",
    }

    for rule in nav.DRIFT_RULES:
        if rule.key not in rule_keys:
            continue
        assert "docs/QUICK_LOOKUP.md" in rule.required_artifacts_all
        assert "scripts/navigation_catalog.py" in rule.required_artifacts_all
