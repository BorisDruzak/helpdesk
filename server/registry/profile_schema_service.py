from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RegistryAdminPolicy
from registry.admin_operations_service import RegistryAdminOperationsService


PROFILE_SCHEMA_POLICY_KEY = "requester_profile_schema"
PROFILE_SCHEMA_KEY = "requester_profile"
CUSTOM_STORAGE_PREFIX = "registry_people.metadata_json.profile_custom_fields."
CUSTOM_STORAGE_PREFIX_LEGACY = "registry_person.metadata_json.profile_custom_fields."

_FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_CUSTOM_FIELD_TYPES = {"text", "textarea", "select", "phone", "email", "url", "number", "date", "checkbox"}


class ProfileSchemaValidationError(ValueError):
    def __init__(self, message: str, details: dict[str, str] | None = None):
        super().__init__(message)
        self.details = details or {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: object, *, max_length: int = 500) -> str:
    return str(value or "").strip()[:max_length]


def _bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _system_field(
    key: str,
    label: str,
    field_type: str,
    storage_target: str,
    *,
    required: bool,
    editable: bool = True,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": field_type,
        "required": required,
        "visible": True,
        "system": True,
        "custom": False,
        "editable": editable,
        "can_delete": False,
        "can_hide": False,
        "target_kind": "registry_person_field" if storage_target.startswith("registry_people.") else "registry_relationship",
        "storage_target": storage_target,
        "help_text": None,
        "validation": {},
    }


def _optional_field(key: str, label: str, field_type: str, storage_target: str) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": field_type,
        "required": False,
        "visible": True,
        "system": False,
        "custom": False,
        "editable": True,
        "can_delete": False,
        "can_hide": True,
        "target_kind": "registry_person_metadata",
        "storage_target": storage_target,
        "help_text": None,
        "validation": {},
    }


DEFAULT_PROFILE_FIELDS: tuple[dict[str, Any], ...] = (
    _system_field("full_name", "ФИО", "text", "registry_people.full_name", required=True),
    _system_field("login_identity", "Логин учетной записи", "identity", "registry_person_identities.ui_login", required=False, editable=False),
    _system_field("department_id", "Подразделение", "department_picker", "registry_people.department_id", required=True),
    _system_field("location_id", "Локация", "location_picker", "registry_people.location_id", required=True),
    _system_field("phone", "Телефон или внутренний номер", "phone", "registry_people.phone", required=True),
    _optional_field("internal_extension", "Внутренний номер", "phone", "registry_people.metadata_json.internal_extension"),
    _system_field("active_device_links", "Активные привязки устройств", "device_links", "device_user_bindings", required=False, editable=False),
    _optional_field("position", "Должность", "text", "registry_people.metadata_json.position"),
    _optional_field("workplace_label", "Рабочее место", "text", "registry_people.metadata_json.workplace_label"),
    _optional_field("preferred_contact_method", "Предпочтительный способ связи", "select", "registry_people.metadata_json.preferred_contact_method"),
)


def default_profile_schema() -> dict[str, Any]:
    fields = [deepcopy(field) for field in DEFAULT_PROFILE_FIELDS]
    return {
        "schema_key": PROFILE_SCHEMA_KEY,
        "version": "default",
        "storage": {
            "system_fields": "registry_people",
            "identities": "registry_person_identities",
            "custom_fields": "registry_people.metadata_json.profile_custom_fields",
        },
        "fields": fields,
        "custom_fields": [],
        "system_fields": [field["key"] for field in fields if field.get("system")],
        "editable_optional_fields": [field["key"] for field in fields if field.get("can_hide")],
        "warnings": [],
    }


class RequesterProfileSchemaService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_schema(self) -> dict[str, Any]:
        row = await self.session.get(RegistryAdminPolicy, PROFILE_SCHEMA_POLICY_KEY)
        config = row.config_json if row is not None and isinstance(row.config_json, dict) else {}
        schema = self.normalize_config(config, strict=False)
        if row is not None and row.updated_at:
            schema["version"] = row.updated_at.isoformat()
            schema["updated_at"] = row.updated_at.isoformat()
            schema["updated_by"] = row.updated_by
        return schema

    async def preview_schema(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"schema": self.normalize_config(payload, strict=True), "dry_run": True}

    async def save_schema(self, payload: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _text(payload.get("reason"), max_length=1000) or None
        before = await self.get_schema()
        normalized = self.normalize_config(payload, strict=True)
        config = {
            "field_overrides": self._stored_field_overrides(payload.get("field_overrides")),
            "custom_fields": normalized["custom_fields"],
            "updated_at": _now_iso(),
            "updated_by": actor_id,
        }
        row = await self.session.get(RegistryAdminPolicy, PROFILE_SCHEMA_POLICY_KEY)
        if row is None:
            row = RegistryAdminPolicy(
                policy_key=PROFILE_SCHEMA_POLICY_KEY,
                config_json=config,
                updated_by=actor_id,
            )
            self.session.add(row)
        else:
            row.config_json = config
            row.updated_by = actor_id
        await RegistryAdminOperationsService(self.session).append_event(
            object_type="profile_schema",
            object_id=PROFILE_SCHEMA_KEY,
            event_type="profile_schema_updated",
            actor_id=actor_id,
            reason=reason,
            payload={
                "schema_key": PROFILE_SCHEMA_KEY,
                "before": self._audit_schema(before),
                "after": self._audit_schema(normalized),
                "custom_field_keys": [field["key"] for field in normalized["custom_fields"]],
            },
        )
        await self.session.flush()
        saved = await self.get_schema()
        return {"schema": saved, "updated": True}

    def normalize_config(self, config: dict[str, Any] | None, *, strict: bool) -> dict[str, Any]:
        config = config if isinstance(config, dict) else {}
        schema = default_profile_schema()
        details: dict[str, str] = {}
        fields = {field["key"]: deepcopy(field) for field in schema["fields"]}

        overrides = config.get("field_overrides")
        if overrides is None and "fields" in config:
            overrides = {
                str(item.get("key") or ""): item
                for item in config.get("fields") or []
                if isinstance(item, dict) and item.get("key")
            }
        overrides = overrides if isinstance(overrides, dict) else {}
        for key, raw_override in overrides.items():
            field_key = _text(key, max_length=80)
            if field_key not in fields:
                if strict:
                    details[field_key or "field"] = "Неизвестное поле профиля."
                continue
            if not isinstance(raw_override, dict):
                if strict:
                    details[field_key] = "Настройка поля должна быть объектом."
                continue
            field = fields[field_key]
            visible = _bool(raw_override.get("visible"), default=bool(field["visible"]))
            required = _bool(raw_override.get("required"), default=bool(field["required"]))
            if field.get("system"):
                if not visible:
                    details[field_key] = "Системное поле нельзя скрыть или удалить."
                if bool(field["required"]) and not required:
                    details[field_key] = "Обязательное системное поле нельзя сделать необязательным."
            else:
                field["visible"] = visible
                field["required"] = required
            if "help_text" in raw_override:
                field["help_text"] = _text(raw_override.get("help_text"), max_length=500) or None
            if "validation" in raw_override:
                field["validation"] = self._normalize_validation(raw_override.get("validation"), details, field_key)
            section = _text(raw_override.get("section"), max_length=120)
            if section:
                field["section"] = section
            if raw_override.get("order") is not None:
                try:
                    field["order"] = int(raw_override.get("order"))
                except (TypeError, ValueError):
                    if strict:
                        details[f"{field_key}.order"] = "РџРѕСЂСЏРґРѕРє РїРѕР»СЏ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ С‡РёСЃР»РѕРј."
            fields[field_key] = field

        custom_fields = self._normalize_custom_fields(config.get("custom_fields") or [], details)
        if details and strict:
            raise ProfileSchemaValidationError("Некорректная схема профиля.", details)
        schema["fields"] = list(fields.values()) + custom_fields
        schema["custom_fields"] = custom_fields
        schema["required_fields"] = [
            {"key": field["key"], "label": field["label"]}
            for field in schema["fields"]
            if field.get("visible", True) and field.get("required")
        ]
        return schema

    def validate_profile_payload(self, schema: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
        details: dict[str, str] = {}
        custom_payload = payload.get("custom_fields") if isinstance(payload.get("custom_fields"), dict) else {}
        normalized_custom: dict[str, Any] = {}
        for field in schema.get("fields") or []:
            if not isinstance(field, dict) or not field.get("visible", True):
                continue
            key = str(field.get("key") or "")
            label = str(field.get("label") or key)
            if field.get("custom"):
                value = custom_payload.get(key)
                cleaned = self._clean_field_value(field, value)
                if field.get("required") and cleaned in {"", None}:
                    details[f"custom_fields.{key}"] = f"Заполните поле: {label}."
                    continue
                if cleaned not in {"", None}:
                    normalized_custom[key] = cleaned
                continue
            if field.get("required") and key not in {"full_name", "department_id", "location_id", "phone"}:
                value = payload.get(key)
                cleaned = self._clean_field_value(field, value)
                if cleaned in {"", None}:
                    details[key] = f"Заполните поле: {label}."
        return details, normalized_custom

    def profile_custom_fields(self, person_metadata: dict[str, Any] | None, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = person_metadata if isinstance(person_metadata, dict) else {}
        raw = metadata.get("profile_custom_fields")
        values = dict(raw) if isinstance(raw, dict) else {}
        if not schema:
            return values
        allowed = {field["key"] for field in schema.get("custom_fields") or [] if isinstance(field, dict)}
        return {key: value for key, value in values.items() if key in allowed}

    def completion_missing_fields(self, person: Any | None, schema: dict[str, Any]) -> list[dict[str, str]]:
        metadata = getattr(person, "metadata_json", None) if person is not None else {}
        metadata = metadata if isinstance(metadata, dict) else {}
        custom_values = metadata.get("profile_custom_fields") if isinstance(metadata.get("profile_custom_fields"), dict) else {}
        missing: list[dict[str, str]] = []
        for field in schema.get("fields") or []:
            if not isinstance(field, dict) or not field.get("visible", True) or not field.get("required"):
                continue
            key = str(field.get("key") or "")
            label = str(field.get("label") or key)
            if field.get("custom"):
                value = custom_values.get(key)
            elif key in {"internal_extension", "position", "workplace_label", "preferred_contact_method"}:
                value = metadata.get(key)
            elif key in {"login_identity", "active_device_links"}:
                continue
            elif key == "phone":
                value = getattr(person, "phone", None) if person is not None else None
                value = value or metadata.get("internal_extension") or metadata.get("extension")
            else:
                value = getattr(person, key, None) if person is not None else None
            if not _text(value):
                missing.append({"key": key, "label": label})
        return missing

    def _normalize_custom_fields(self, raw_fields: Any, details: dict[str, str]) -> list[dict[str, Any]]:
        if not isinstance(raw_fields, list):
            details["custom_fields"] = "Пользовательские поля должны быть списком."
            return []
        reserved = {field["key"] for field in DEFAULT_PROFILE_FIELDS}
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_fields):
            prefix = f"custom_fields.{index}"
            if not isinstance(raw, dict):
                details[prefix] = "Пользовательское поле должно быть объектом."
                continue
            key = _text(raw.get("key"), max_length=80).lower()
            if not key or not _FIELD_KEY_RE.match(key):
                details[f"{prefix}.key"] = "Ключ поля должен быть латинским идентификатором."
                continue
            if key in reserved or key in seen:
                details[f"{prefix}.key"] = "Ключ пользовательского поля не должен совпадать с системным или повторяться."
            seen.add(key)
            label = _text(raw.get("label"), max_length=160)
            if not label:
                details[f"{prefix}.label"] = "Укажите название поля."
            field_type = _text(raw.get("type"), max_length=40).lower() or "text"
            if field_type not in _CUSTOM_FIELD_TYPES:
                details[f"{prefix}.type"] = "Недопустимый тип пользовательского поля."
            storage_target = _text(raw.get("storage_target"), max_length=240)
            if storage_target.startswith(CUSTOM_STORAGE_PREFIX_LEGACY):
                storage_target = f"{CUSTOM_STORAGE_PREFIX}{storage_target.removeprefix(CUSTOM_STORAGE_PREFIX_LEGACY)}"
            expected_target = f"{CUSTOM_STORAGE_PREFIX}{key}"
            if storage_target != expected_target:
                details[f"{prefix}.storage_target"] = f"Разрешенная цель хранения: {expected_target}."
            field = {
                "key": key,
                "label": label,
                "type": field_type,
                "required": _bool(raw.get("required"), default=False),
                "visible": _bool(raw.get("visible"), default=True),
                "system": False,
                "custom": True,
                "editable": True,
                "can_delete": True,
                "can_hide": True,
                "target_kind": "registry_person_metadata",
                "storage_target": expected_target,
                "help_text": _text(raw.get("help_text"), max_length=500) or None,
                "validation": self._normalize_validation(raw.get("validation"), details, prefix),
                "options": raw.get("options") if isinstance(raw.get("options"), list) else [],
                "audit_behavior": "profile_custom_field_change",
            }
            section = _text(raw.get("section"), max_length=120)
            if section:
                field["section"] = section
            if raw.get("order") is not None:
                try:
                    field["order"] = int(raw.get("order"))
                except (TypeError, ValueError):
                    details[f"{prefix}.order"] = "РџРѕСЂСЏРґРѕРє РїРѕР»СЏ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ С‡РёСЃР»РѕРј."
            normalized.append(field)
        return normalized

    def _normalize_validation(self, raw: Any, details: dict[str, str], prefix: str) -> dict[str, Any]:
        if raw is None or raw == "":
            return {}
        if not isinstance(raw, dict):
            details[f"{prefix}.validation"] = "Правила проверки должны быть объектом."
            return {}
        validation: dict[str, Any] = {}
        if raw.get("max_length") is not None:
            try:
                max_length = int(raw.get("max_length"))
            except (TypeError, ValueError):
                details[f"{prefix}.validation.max_length"] = "Максимальная длина должна быть числом."
            else:
                if not 1 <= max_length <= 1000:
                    details[f"{prefix}.validation.max_length"] = "Максимальная длина должна быть от 1 до 1000."
                else:
                    validation["max_length"] = max_length
        if raw.get("pattern") is not None:
            pattern = _text(raw.get("pattern"), max_length=300)
            if pattern:
                validation["pattern"] = pattern
        return validation

    def _clean_field_value(self, field: dict[str, Any], value: Any) -> Any:
        if field.get("type") == "checkbox":
            return bool(value)
        text = _text(value, max_length=int((field.get("validation") or {}).get("max_length") or 500))
        return text or None

    def _stored_field_overrides(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        allowed_keys = {field["key"] for field in DEFAULT_PROFILE_FIELDS}
        result: dict[str, Any] = {}
        for key, value in raw.items():
            if key in allowed_keys and isinstance(value, dict):
                result[key] = {
                    item_key: item_value
                    for item_key, item_value in value.items()
                    if item_key in {"visible", "required", "help_text", "validation", "section", "order"}
                }
        return result

    def _audit_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_key": schema.get("schema_key"),
            "fields": [
                {
                    "key": field.get("key"),
                    "required": field.get("required"),
                    "visible": field.get("visible"),
                    "custom": field.get("custom"),
                    "storage_target": field.get("storage_target"),
                }
                for field in schema.get("fields", [])
                if isinstance(field, dict)
            ],
        }
