import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLineEdit  # noqa: E402

from pc_agent.ui_gui.dynamic_form_widget import DynamicFormWidget, dynamic_form_field_visible  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_dynamic_form_field_visible_supports_equals_and_in_rules():
    assert dynamic_form_field_visible({"key": "room"}, {"room": "501"}) is True
    assert dynamic_form_field_visible(
        {"key": "shared", "visible_when": {"field": "relationship_type", "equals": "shared_user"}},
        {"relationship_type": "shared_user"},
    ) is True
    assert dynamic_form_field_visible(
        {"key": "shared", "visible_when": {"field": "relationship_type", "equals": "shared_user"}},
        {"relationship_type": "primary_user"},
    ) is False
    assert dynamic_form_field_visible(
        {"key": "location", "visible_when": {"field": "relationship_type", "in": ["primary_user", "temporary_user"]}},
        {"relationship_type": "temporary_user"},
    ) is True


def test_dynamic_form_widget_collects_text_select_and_checkbox_values():
    _app()
    widget = DynamicFormWidget()
    widget.set_form(
        {
            "fields": [
                {"key": "full_name", "label": "ФИО", "type": "text", "required": True},
                {
                    "key": "relationship_type",
                    "label": "Тип ПК",
                    "type": "select",
                    "required": True,
                    "options": [
                        {"value": "primary_user", "label": "Мой основной ПК"},
                        {"value": "shared_user", "label": "Общий ПК"},
                    ],
                },
                {
                    "key": "is_shared_device",
                    "label": "Это общий ПК",
                    "type": "checkbox",
                    "visible_when": {"field": "relationship_type", "equals": "shared_user"},
                },
            ]
        },
        values={"full_name": "Иван Иванов", "relationship_type": "shared_user", "is_shared_device": True},
    )

    assert isinstance(widget._widgets["full_name"], QLineEdit)
    assert isinstance(widget._widgets["relationship_type"], QComboBox)
    assert isinstance(widget._widgets["is_shared_device"], QCheckBox)
    assert widget.values() == {
        "full_name": "Иван Иванов",
        "relationship_type": "shared_user",
        "is_shared_device": True,
    }
    assert widget.missing_required_labels() == []


def test_dynamic_form_widget_returns_only_visible_fields_and_validates_required():
    _app()
    widget = DynamicFormWidget()
    widget.set_form(
        {
            "fields": [
                {"key": "login", "label": "Логин", "type": "text", "required": True},
                {
                    "key": "room",
                    "label": "Кабинет",
                    "type": "text",
                    "required": True,
                    "visible_when": {"field": "relationship_type", "equals": "primary_user"},
                },
                {
                    "key": "relationship_type",
                    "label": "Тип ПК",
                    "type": "select",
                    "required": True,
                    "options": [
                        {"value": "primary_user", "label": "Мой основной ПК"},
                        {"value": "shared_user", "label": "Общий ПК"},
                    ],
                },
            ]
        },
        values={"relationship_type": "shared_user"},
    )

    assert widget.values() == {"login": "", "relationship_type": "shared_user"}
    assert widget.missing_required_labels() == ["Логин"]

    widget._widgets["login"].setText("DOMAIN\\User")
    assert widget.validate_required_fields(show_feedback=True) == []
