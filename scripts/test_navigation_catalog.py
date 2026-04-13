from scripts import navigation_catalog as nav


def test_find_topics_for_query_includes_planning_topic() -> None:
    topics = nav.find_topics_for_query("plans.md")

    assert any(topic.key == "planning" for topic in topics)


def test_release_topic_related_docs_include_handoff_artifacts() -> None:
    release_topic = next(topic for topic in nav.TOPICS if topic.key == "release")

    assert "PLANS.md" in release_topic.related_docs
    assert ".cursor/skills/pc-client-release/SKILL.md" in release_topic.related_docs


def test_harness_drift_rules_require_non_markdown_artifacts() -> None:
    navigation_rule = next(rule for rule in nav.DRIFT_RULES if rule.key == "navigation_harness")
    workflow_rule = next(rule for rule in nav.DRIFT_RULES if rule.key == "workflow_harness")

    assert ".cursor/rules/navigation-tools.mdc" in navigation_rule.required_docs
    assert ".cursor/skills/pc-client-release/SKILL.md" in workflow_rule.required_docs
