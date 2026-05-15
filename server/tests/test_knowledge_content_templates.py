from __future__ import annotations

from knowledge.content_templates import default_visibility_for_item_type, get_content_template, validate_template_body


def test_article_template_requires_operational_sections() -> None:
    template = get_content_template("article")

    assert template["sections"] == [
        "Назначение",
        "Когда использовать",
        "Шаги",
        "Проверка результата",
        "Если не помогло",
        "Связанные услуги / типы обращения",
    ]

    result = validate_template_body(
        "article",
        """
## Назначение
Помочь пользователю выполнить безопасные проверки.
## Когда использовать
Перед созданием заявки.
## Шаги
1. Проверьте подключение.
## Проверка результата
Проверьте, исчезла ли проблема.
## Если не помогло
Создайте заявку.
## Связанные услуги / типы обращения
Сеть / VPN.
""",
    )

    assert result["valid"] is True
    assert result["missing_sections"] == []


def test_runbook_and_known_error_default_internal_visibility() -> None:
    assert default_visibility_for_item_type("runbook") == "support_internal"
    assert default_visibility_for_item_type("known_error") == "support_internal"
    assert default_visibility_for_item_type("workaround") == "support_internal"
    assert default_visibility_for_item_type("article") == "requester"


def test_template_validator_reports_missing_sections() -> None:
    result = validate_template_body("troubleshooting_tree", "## Симптомы\nVPN не подключается.")

    assert result["valid"] is False
    assert "Возможные причины" in result["missing_sections"]
    assert "Что указать в заявке" in result["missing_sections"]
