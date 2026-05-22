"""Reusable dynamic form widgets for agent GUI surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QDate, QDateTime, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme

OPTION_FIELD_TYPES = {"select", "radio"}
MULTI_SELECT_FIELD_TYPES = {"multi_select"}
PICKER_FIELD_TYPES = {"user_picker", "department_picker", "location_picker", "device_picker", "service_picker"}
PICKER_OPTION_KEYS = {
    "user_picker": "users",
    "department_picker": "departments",
    "location_picker": "locations",
    "device_picker": "devices",
    "service_picker": "services",
}

REQUESTER_VISIBLE_AUDIENCES = {"requester", "user", "portal", "public", "customer", "employee"}
INTERNAL_PROCESS_FIELD_KEYS = {
    "ticket_type",
    "ticket_type_code",
    "priority",
    "priority_class",
    "priority_policy",
    "priority_policy_id",
    "priority_policy_code",
    "sla_policy",
    "sla_policy_id",
    "sla_policy_code",
    "ola_policy",
    "ola_policy_id",
    "ola_policy_code",
    "routing_policy",
    "routing_policy_id",
    "routing_policy_code",
    "workflow_profile",
    "workflow_profile_id",
    "approval_policy",
    "approval_policy_id",
    "approval_policy_code",
    "closure_policy",
    "closure_policy_id",
    "closure_policy_code",
    "diagnostic_policy",
    "diagnostic_policy_id",
    "diagnostic_policy_code",
    "visibility_policy",
    "visibility_policy_id",
    "visibility_policy_code",
    "notification_policy",
    "notification_policy_id",
    "notification_policy_code",
    "reporting_policy",
    "reporting_policy_id",
    "reporting_policy_code",
}


def _field_audience_values(raw_value: Any) -> set[str]:
    if isinstance(raw_value, str):
        values = [raw_value]
    elif isinstance(raw_value, list):
        values = raw_value
    elif isinstance(raw_value, tuple):
        values = list(raw_value)
    else:
        values = []
    return {str(item or "").strip().lower() for item in values if str(item or "").strip()}


def dynamic_form_field_requester_visible(field_def: dict[str, Any]) -> bool:
    """Return whether a server-driven field is safe to render in requester GUI."""
    if not isinstance(field_def, dict):
        return False
    field_key = str(field_def.get("key") or "").strip().lower()
    visibility = field_def.get("visibility") if isinstance(field_def.get("visibility"), dict) else {}
    if field_def.get("internal") is True or visibility.get("internal") is True:
        return False
    requester_visible = field_def.get("requester_visible", visibility.get("requester_visible"))
    if requester_visible is False:
        return False
    if requester_visible is True:
        return True

    hidden_from = set()
    hidden_from.update(_field_audience_values(field_def.get("hidden_from")))
    hidden_from.update(_field_audience_values(visibility.get("hidden_from")))
    if hidden_from & REQUESTER_VISIBLE_AUDIENCES:
        return False

    visible_to = set()
    for key in ("visible_to", "visible_for", "audience", "audiences"):
        visible_to.update(_field_audience_values(field_def.get(key)))
        visible_to.update(_field_audience_values(visibility.get(key)))
    if visible_to:
        return bool(visible_to & REQUESTER_VISIBLE_AUDIENCES)

    if field_key in INTERNAL_PROCESS_FIELD_KEYS:
        return False
    return True


def dynamic_form_field_visible(field_def: dict[str, Any], values: dict[str, Any]) -> bool:
    rule = field_def.get("visible_when")
    if not isinstance(rule, dict):
        return True
    current_value = values.get(str(rule.get("field") or ""))
    if "equals" in rule:
        return str(current_value or "").strip() == str(rule.get("equals") or "").strip()
    allowed = {str(item or "").strip() for item in rule.get("in") or []}
    return str(current_value or "").strip() in allowed


class DynamicFileFieldWidget(QWidget):
    """Single file selector used by dynamic forms."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._path = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setPlaceholderText("Файл не выбран")
        self.choose_button = QPushButton("Выбрать файл")
        self.choose_button.setObjectName("SecondaryButton")
        self.choose_button.clicked.connect(self._choose_file)
        self.clear_button = QPushButton("Убрать")
        self.clear_button.setObjectName("SecondaryButton")
        self.clear_button.clicked.connect(self.clear_file_path)
        layout.addWidget(self.path_input, 1)
        layout.addWidget(self.choose_button)
        layout.addWidget(self.clear_button)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл")
        if path:
            self.set_file_path(path)

    def set_file_path(self, path: str) -> None:
        normalized = str(path or "").strip()
        if normalized == self._path:
            return
        self._path = normalized
        self.path_input.setText(normalized)
        self.changed.emit()

    def clear_file_path(self) -> None:
        self.set_file_path("")

    def value(self) -> dict[str, str]:
        if not self._path:
            return {}
        return {"path": self._path, "filename": Path(self._path).name}

    def file_path(self) -> str:
        return self._path


class DynamicFormWidget(QWidget):
    """Dynamic form fields driven by a schema/field contract."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._field_defs: list[dict[str, Any]] = []
        self._containers: dict[str, QWidget] = {}
        self._widgets: dict[str, QWidget] = {}
        self._labels: dict[str, QLabel] = {}
        self._help_labels: dict[str, QLabel] = {}
        self._error_labels: dict[str, QLabel] = {}
        self._registry_options: dict[str, list[dict[str, Any]]] = {}
        self._show_validation_feedback = False
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

    def clear_form(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._field_defs = []
        self._containers = {}
        self._widgets = {}
        self._labels = {}
        self._help_labels = {}
        self._error_labels = {}
        self._registry_options = {}
        self._show_validation_feedback = False

    def set_form(
        self,
        form_def: Optional[dict[str, Any]],
        values: Optional[dict[str, Any]] = None,
        *,
        include_keys: Optional[set[str]] = None,
        exclude_keys: Optional[set[str]] = None,
        registry_options: Optional[dict[str, Any]] = None,
    ) -> None:
        self.clear_form()
        values = values or {}
        self._registry_options = {
            str(key): [item for item in value if isinstance(item, dict)]
            for key, value in (registry_options or {}).items()
            if isinstance(value, list)
        }
        if not isinstance(form_def, dict):
            return
        include_keys = {str(key) for key in include_keys or set()}
        exclude_keys = {str(key) for key in exclude_keys or set()}
        self._field_defs = [
            field
            for field in list(form_def.get("fields") or [])
            if isinstance(field, dict)
            and dynamic_form_field_requester_visible(field)
            and (not include_keys or str(field.get("key") or "").strip() in include_keys)
            and str(field.get("key") or "").strip() not in exclude_keys
        ]
        for field_def in self._field_defs:
            self._add_field(field_def, values)

        self._layout.addStretch(1)
        self._apply_visibility()
        self._apply_validation_state(set())

    def _add_field(self, field_def: dict[str, Any], values: dict[str, Any]) -> None:
        field_key = str(field_def.get("key") or "").strip()
        if not field_key:
            return
        container = QWidget(self)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        field_label_text = str(field_def.get("label") or field_key)
        if field_def.get("required"):
            field_label_text = f"{field_label_text} *"
        field_label = QLabel(field_label_text)
        field_label.setStyleSheet(f"font-size: {theme.UI_FONT_PT + 1}pt; font-weight: 700; color: {theme.TEXT_PRIMARY};")
        container_layout.addWidget(field_label)

        widget = self._build_input_widget(field_def, values)
        container_layout.addWidget(widget)
        help_text = str(field_def.get("help_text") or "").strip()
        if help_text:
            help_label = QLabel(help_text)
            help_label.setWordWrap(True)
            help_label.setStyleSheet(f"font-size: {theme.UI_FONT_PT}pt; color: {theme.TEXT_MUTED};")
            container_layout.addWidget(help_label)
            self._help_labels[field_key] = help_label

        error_label = QLabel("")
        error_label.setWordWrap(True)
        error_label.setStyleSheet(f"font-size: {theme.UI_FONT_PT}pt; color: {theme.DANGER_FG};")
        error_label.setVisible(False)
        container_layout.addWidget(error_label)

        self._containers[field_key] = container
        self._widgets[field_key] = widget
        self._labels[field_key] = field_label
        self._error_labels[field_key] = error_label
        self._layout.addWidget(container)

    def _build_input_widget(self, field_def: dict[str, Any], values: dict[str, Any]) -> QWidget:
        field_key = str(field_def.get("key") or "").strip()
        field_type = str(field_def.get("type") or "text").strip().lower()
        if field_type == "textarea":
            input_widget = QTextEdit()
            input_widget.setMinimumHeight(88)
            input_widget.setPlaceholderText(field_def.get("placeholder") or "")
            input_widget.setPlainText(str(values.get(field_key) or ""))
            input_widget.textChanged.connect(self._on_any_changed)
            return input_widget
        if field_type == "date":
            input_widget = QDateEdit()
            input_widget.setCalendarPopup(True)
            input_widget.setDisplayFormat("yyyy-MM-dd")
            current_date = QDate.fromString(str(values.get(field_key) or "")[:10], "yyyy-MM-dd")
            input_widget.setDate(current_date if current_date.isValid() else QDate.currentDate())
            input_widget.dateChanged.connect(self._on_any_changed)
            return input_widget
        if field_type == "datetime":
            input_widget = QDateTimeEdit()
            input_widget.setCalendarPopup(True)
            input_widget.setDisplayFormat("yyyy-MM-dd HH:mm")
            raw_datetime = str(values.get(field_key) or "").strip().replace("T", " ")[:16]
            current_datetime = QDateTime.fromString(raw_datetime, "yyyy-MM-dd HH:mm")
            input_widget.setDateTime(current_datetime if current_datetime.isValid() else QDateTime.currentDateTime())
            input_widget.dateTimeChanged.connect(self._on_any_changed)
            return input_widget
        if field_type in OPTION_FIELD_TYPES:
            input_widget = QComboBox()
            input_widget.addItem("Выберите...", "")
            for option in field_def.get("options") or []:
                input_widget.addItem(option.get("label") or option.get("value") or "", option.get("value") or "")
            current_index = input_widget.findData(str(values.get(field_key) or ""))
            if current_index >= 0:
                input_widget.setCurrentIndex(current_index)
            input_widget.currentIndexChanged.connect(self._on_any_changed)
            return input_widget
        if field_type in PICKER_FIELD_TYPES:
            input_widget = QComboBox()
            input_widget.addItem("Выберите...", "")
            option_key = PICKER_OPTION_KEYS.get(field_type, "")
            options = self._registry_options.get(option_key) or field_def.get("options") or []
            for option in options:
                option_value = str(
                    option.get("value")
                    or option.get("id")
                    or option.get("person_id")
                    or option.get("department_id")
                    or option.get("location_id")
                    or option.get("device_id")
                    or option.get("service_id")
                    or ""
                ).strip()
                option_label = str(
                    option.get("label")
                    or option.get("display_name")
                    or option.get("name")
                    or option.get("hostname")
                    or option_value
                ).strip()
                if option_value:
                    input_widget.addItem(option_label, option_value)
            current_value = str(values.get(field_key) or "").strip()
            if current_value and input_widget.findData(current_value) < 0:
                input_widget.addItem(current_value, current_value)
            current_index = input_widget.findData(current_value)
            if current_index >= 0:
                input_widget.setCurrentIndex(current_index)
            elif input_widget.count() == 2:
                input_widget.setCurrentIndex(1)
            input_widget.currentIndexChanged.connect(self._on_any_changed)
            return input_widget
        if field_type in MULTI_SELECT_FIELD_TYPES:
            input_widget = QListWidget()
            input_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
            current_values = values.get(field_key)
            if isinstance(current_values, list):
                selected_values = {str(item) for item in current_values}
            else:
                selected_values = {item.strip() for item in str(current_values or "").split(",") if item.strip()}
            for option in field_def.get("options") or []:
                option_value = str(option.get("value") or "").strip()
                item = QListWidgetItem(option.get("label") or option_value)
                item.setData(Qt.ItemDataRole.UserRole, option_value)
                input_widget.addItem(item)
                item.setSelected(option_value in selected_values)
            input_widget.itemSelectionChanged.connect(self._on_any_changed)
            return input_widget
        if field_type == "checkbox":
            input_widget = QCheckBox(field_def.get("placeholder") or "Подтверждаю")
            input_widget.setChecked(bool(values.get(field_key)))
            input_widget.stateChanged.connect(self._on_any_changed)
            return input_widget
        if field_type == "file":
            input_widget = DynamicFileFieldWidget()
            raw_value = values.get(field_key)
            if isinstance(raw_value, dict):
                input_widget.set_file_path(str(raw_value.get("path") or ""))
            else:
                input_widget.set_file_path(str(raw_value or ""))
            input_widget.changed.connect(self._on_any_changed)
            return input_widget
        input_widget = QLineEdit()
        input_widget.setPlaceholderText(field_def.get("placeholder") or "")
        input_widget.setText(str(values.get(field_key) or ""))
        input_widget.textChanged.connect(self._on_any_changed)
        return input_widget

    def _on_any_changed(self, *_args) -> None:
        self._apply_visibility()
        if self._show_validation_feedback:
            self.validate_required_fields(show_feedback=True)
        self.changed.emit()

    def _field_value(self, field_key: str) -> Any:
        widget = self._widgets.get(field_key)
        if widget is None:
            return ""
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        if isinstance(widget, QDateEdit):
            return widget.date().toString("yyyy-MM-dd")
        if isinstance(widget, QDateTimeEdit):
            return widget.dateTime().toString("yyyy-MM-ddTHH:mm")
        if isinstance(widget, QComboBox):
            return str(widget.currentData() or "").strip()
        if isinstance(widget, QListWidget):
            result: list[str] = []
            for item in widget.selectedItems():
                value = item.data(Qt.ItemDataRole.UserRole)
                result.append(str(value if value is not None else item.text()).strip())
            return [item for item in result if item]
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, DynamicFileFieldWidget):
            return widget.value()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        return ""

    def values(self, *, visible_only: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {}
        current_values = {field_def.get("key"): self._field_value(str(field_def.get("key") or "")) for field_def in self._field_defs}
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            if not field_key:
                continue
            if visible_only and not dynamic_form_field_visible(field_def, current_values):
                continue
            result[field_key] = current_values.get(field_key)
        return result

    def set_file_field_path(self, field_key: str, path: str) -> None:
        widget = self._widgets.get(str(field_key or "").strip())
        if isinstance(widget, DynamicFileFieldWidget):
            widget.set_file_path(path)

    def clear_file_field_path(self, field_key: str) -> None:
        widget = self._widgets.get(str(field_key or "").strip())
        if isinstance(widget, DynamicFileFieldWidget):
            widget.clear_file_path()

    def file_attachment_paths(self, *, visible_only: bool = True) -> list[str]:
        paths: list[str] = []
        current_values = {field_def.get("key"): self._field_value(str(field_def.get("key") or "")) for field_def in self._field_defs}
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            if not field_key or str(field_def.get("type") or "").strip().lower() != "file":
                continue
            if visible_only and not dynamic_form_field_visible(field_def, current_values):
                continue
            widget = self._widgets.get(field_key)
            if isinstance(widget, DynamicFileFieldWidget):
                path = widget.file_path()
                if path:
                    paths.append(path)
        return paths

    def missing_required_labels(self) -> list[str]:
        values = self.values(visible_only=False)
        missing: list[str] = []
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            if not field_key or not field_def.get("required"):
                continue
            if not dynamic_form_field_visible(field_def, values):
                continue
            value = values.get(field_key)
            if field_def.get("type") == "checkbox":
                if value is not True:
                    missing.append(str(field_def.get("label") or field_key))
            elif isinstance(value, list):
                if not value:
                    missing.append(str(field_def.get("label") or field_key))
            elif isinstance(value, dict):
                if not str(value.get("path") or value.get("filename") or "").strip():
                    missing.append(str(field_def.get("label") or field_key))
            elif not str(value or "").strip():
                missing.append(str(field_def.get("label") or field_key))
        return missing

    def _missing_required_keys(self) -> set[str]:
        values = self.values(visible_only=False)
        missing: set[str] = set()
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            if not field_key or not field_def.get("required"):
                continue
            if not dynamic_form_field_visible(field_def, values):
                continue
            value = values.get(field_key)
            if field_def.get("type") == "checkbox":
                if value is not True:
                    missing.add(field_key)
            elif isinstance(value, list):
                if not value:
                    missing.add(field_key)
            elif isinstance(value, dict):
                if not str(value.get("path") or value.get("filename") or "").strip():
                    missing.add(field_key)
            elif not str(value or "").strip():
                missing.add(field_key)
        return missing

    def clear_validation_feedback(self) -> None:
        self._show_validation_feedback = False
        self._apply_validation_state(set())

    def validate_required_fields(self, *, show_feedback: bool = False) -> list[str]:
        if show_feedback:
            self._show_validation_feedback = True
        missing_keys = self._missing_required_keys()
        self._apply_validation_state(missing_keys if self._show_validation_feedback else set())
        return [
            str(field_def.get("label") or field_def.get("key") or "")
            for field_def in self._field_defs
            if str(field_def.get("key") or "").strip() in missing_keys
        ]

    def _apply_validation_state(self, missing_keys: set[str]) -> None:
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            label = self._labels.get(field_key)
            help_label = self._help_labels.get(field_key)
            error_label = self._error_labels.get(field_key)
            widget = self._widgets.get(field_key)
            is_missing = field_key in missing_keys
            if label is not None:
                label.setStyleSheet(
                    f"font-size: {theme.UI_FONT_PT + 1}pt; font-weight: 700; "
                    f"color: {theme.DANGER_FG if is_missing else theme.TEXT_PRIMARY};"
                )
            if help_label is not None:
                help_label.setStyleSheet(
                    f"font-size: {theme.UI_FONT_PT}pt; color: {theme.DANGER_FG if is_missing else theme.TEXT_MUTED};"
                )
            if error_label is not None:
                if is_missing:
                    error_text = str(
                        field_def.get("required_message")
                        or f"Заполните поле «{field_def.get('label') or field_key}»."
                    ).strip()
                    error_label.setText(error_text)
                    error_label.setVisible(True)
                else:
                    error_label.setText("")
                    error_label.setVisible(False)
            if widget is not None:
                if is_missing:
                    widget.setStyleSheet(
                        f"border: 1px solid {theme.DANGER_BORDER}; border-radius: 14px; "
                        f"background: {theme.DANGER_BG}; color: {theme.TEXT_PRIMARY};"
                    )
                else:
                    widget.setStyleSheet("")

    def _apply_visibility(self) -> None:
        values = self.values(visible_only=False)
        for field_def in self._field_defs:
            field_key = str(field_def.get("key") or "").strip()
            container = self._containers.get(field_key)
            if container is not None:
                container.setVisible(dynamic_form_field_visible(field_def, values))
