from __future__ import annotations

from typing import Any


CONTENT_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "type": "article",
        "title": "Article / How-to",
        "default_visibility": "requester",
        "sections": ["Назначение", "Когда использовать", "Шаги", "Проверка результата", "Если не помогло", "Связанные услуги / типы обращения"],
    },
    {
        "type": "faq",
        "title": "FAQ",
        "default_visibility": "requester",
        "sections": ["Вопрос", "Короткий ответ", "Подробности", "Связанные статьи"],
    },
    {
        "type": "troubleshooting_tree",
        "title": "Troubleshooting",
        "default_visibility": "support_internal",
        "sections": ["Симптомы", "Возможные причины", "Проверки", "Решение", "Когда эскалировать", "Что указать в заявке"],
    },
    {
        "type": "runbook",
        "title": "Support runbook",
        "default_visibility": "support_internal",
        "sections": ["Scope", "Preconditions", "Required access", "Steps", "Validation", "Rollback", "Evidence to collect", "Escalation"],
    },
    {
        "type": "known_error",
        "title": "Known error",
        "default_visibility": "support_internal",
        "sections": ["Symptoms", "Affected services/offerings", "Root cause, if known", "Workaround", "Permanent fix", "Status", "Linked tickets/problems"],
    },
    {
        "type": "workaround",
        "title": "Workaround",
        "default_visibility": "support_internal",
        "sections": ["Applies to", "Temporary steps", "Risk/side effects", "Reversal", "Expiry/review date"],
    },
    {
        "type": "policy",
        "title": "Policy/process",
        "default_visibility": "support_internal",
        "sections": ["Policy statement", "Applies to", "Process", "Exceptions", "Owner", "Review cycle"],
    },
    {
        "type": "glossary_term",
        "title": "Glossary term",
        "default_visibility": "requester",
        "sections": ["Definition", "Synonyms", "Related terms", "Related services/offerings"],
    },
    {
        "type": "service_description",
        "title": "Service description",
        "default_visibility": "requester",
        "sections": ["Что входит", "Сроки", "Ограничения"],
    },
)


def get_content_template(item_type: str) -> dict[str, Any]:
    normalized = str(item_type or "article")
    for template in CONTENT_TEMPLATES:
        if template["type"] == normalized:
            return dict(template)
    return dict(CONTENT_TEMPLATES[0])


def default_visibility_for_item_type(item_type: str) -> str:
    return str(get_content_template(item_type).get("default_visibility") or "support_internal")


def _has_markdown_heading(body: str, section: str) -> bool:
    needle = section.strip().casefold()
    for line in str(body or "").splitlines():
        text = line.strip().lstrip("#").strip().casefold()
        if text == needle:
            return True
    return False


def validate_template_body(item_type: str, body: str) -> dict[str, Any]:
    template = get_content_template(item_type)
    missing = [section for section in template["sections"] if not _has_markdown_heading(body, section)]
    return {"valid": not missing, "item_type": template["type"], "missing_sections": missing}
