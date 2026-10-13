"""Lossless supported form-to-map conversion; unsupported semantics block it."""
from copy import deepcopy
import hashlib
from web_api.dto.request_scenario import ScenarioDefinition, FieldType
from typing import get_args


class ConversionBlocked(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("Form cannot be converted without losing semantics")


def _condition(rule):
    if not rule:
        return None
    if "op" in rule:
        return deepcopy(rule)
    if set(rule) <= {"field", "equals"} and "equals" in rule:
        return {"source": "answer", "field": rule["field"], "op": "eq", "value": rule["equals"]}
    if set(rule) <= {"field", "in"} and "in" in rule:
        return {"source": "answer", "field": rule["field"], "op": "in", "value": rule["in"]}
    raise ConversionBlocked([{"code": "unsupported_condition", "path": "fields", "message": "Условие формы нельзя перенести без изменения поведения."}])


def convert_form(offering, form):
    issues = []
    def block(path, message):
        issues.append({"code": "unsupported_form_feature", "path": path, "message": message})
    if form.get("playbook_triggers"):
        block("playbook_triggers", "Форма запускает операции. Автоматический перенос таких действий пока не поддерживается.")
    for flag in ("on_behalf_policy", "device_required", "custom_renderer", "layout"):
        if form.get(flag):
            block(flag, "Форма содержит специальное поведение: " + flag)
    fields = []
    allowed = {"key", "label", "type", "required", "options", "validation", "process_mapping", "visible_when",
               "required_when", "placeholder", "help_text", "allow_unknown", "group", "group_title", "aliases", "visibility"}
    for old in form.get("fields", []):
        path = "fields." + str(old.get("key", ""))
        if old.get("type") not in get_args(FieldType):
            block(path, "Неподдерживаемый тип поля: " + str(old.get("type")))
        unknown = {key for key, value in old.items() if key not in allowed and value not in (None, "", [], {})}
        if unknown:
            block(path, "Специальные настройки поля: " + ", ".join(sorted(unknown)))
        if set(old.get("validation") or {}) - {"min_length", "max_length", "min_value", "max_value", "optional_when_legacy_missing"}:
            block(path, "Специальные проверки ответа требуют ручного переноса.")
        raw = {key: deepcopy(value) for key, value in old.items() if key in allowed - {"visibility"}}
        raw["visible_when"] = _condition(old.get("visible_when") or old.get("visibility"))
        raw["required_when"] = _condition(old.get("required_when"))
        if old["key"] in (form.get("field_roles") or {}):
            raw.setdefault("process_mapping", {})["roles"] = deepcopy(form["field_roles"][old["key"]])
        fields.append(raw)
    if len(fields) > 100:
        block("fields", "В одной форме больше 100 полей; требуется разбиение с проверкой условий.")
    if issues:
        raise ConversionBlocked(issues)
    digest = hashlib.sha256(offering["full_code"].encode()).hexdigest()[:32]
    first = "questions" if fields else "submit"
    category = (offering.get("metadata") or {}).get("studio_catalog", {}).get("category_id")
    blocks = ([{"id": "questions", "kind": "form_page", "title": offering["public_title"], "layout": "group",
                "fields": fields, "transitions": [{"to": "submit"}]}] if fields else [])
    blocks.append({"id": "submit", "kind": "submit_ticket", "title": "Создать обращение"})
    try:
        definition = ScenarioDefinition.model_validate({"schema_version": 2, "scenario_key": "converted_" + digest,
            "service_code": offering["service_code"], "offering_full_code": offering["full_code"],
            "title": offering["public_title"], "description": offering.get("short_description") or "", "category_id": category,
            "entry_block_id": first, "entry_points": [{"key": "entry_" + digest, "title": offering["public_title"],
                "target_block_id": first, "category_id": category, "visibility": offering.get("visibility", "public")}],
            "blocks": blocks, "process_binding": {"request_template_key": offering["request_template_key"]},
            "publish_offering": offering.get("lifecycle_status") == "draft",
            "editor_layout": {"positions": {"system_start": {"x": -320, "y": 0}, first: {"x": 0, "y": 0}, "submit": {"x": 360, "y": 0}}}})
        from tickets.request_scenario_validation import validate_scenario
        from dataclasses import asdict
        validation = validate_scenario(definition)
        if validation:
            raise ConversionBlocked([asdict(issue) for issue in validation])
        return definition
    except ConversionBlocked:
        raise
    except ValueError as exc:
        raise ConversionBlocked([{"code": "unsupported_schema", "path": "fields", "message": "Форма содержит неподдерживаемые поля, роли или условия. Исходная форма сохранена."}]) from exc
