from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import RegistryAdminPolicy, RegistryPerson
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.profile_values import CONTACT_OPTIONS, clean_profile_value, safe_pattern


PROFILE_SCHEMA_POLICY_KEY = "requester_profile_schema"
PROFILE_SCHEMA_KEY = "requester_profile"
CUSTOM_STORAGE_PREFIX = "registry_people.metadata_json.profile_custom_fields."
CUSTOM_STORAGE_PREFIX_LEGACY = "registry_person.metadata_json.profile_custom_fields."

_FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_CUSTOM_FIELD_TYPES = {"text", "textarea", "select", "phone", "email", "url", "number", "date", "checkbox"}
_PROFILE_WRITE_LIMITS = {"full_name": 240, "phone": 80, "internal_extension": 80, "position": 160, "workplace_label": 160, "preferred_contact_method": 80}


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
    for field in fields:
        if field["key"] in _PROFILE_WRITE_LIMITS:
            field["validation"] = {"max_length": _PROFILE_WRITE_LIMITS[field["key"]]}
    next(field for field in fields if field["key"] == "preferred_contact_method")["options"] = deepcopy(CONTACT_OPTIONS)
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

    async def get_schema(self, *, for_update: bool = False) -> dict[str, Any]:
        row = await self.session.get(RegistryAdminPolicy, PROFILE_SCHEMA_POLICY_KEY, **({"with_for_update": True, "populate_existing": True} if for_update else {}))
        config = row.config_json if row is not None and isinstance(row.config_json, dict) else {}
        schema = self.normalize_config(config, strict=False)
        if row is not None and row.updated_at:
            schema["version"] = row.updated_at.isoformat()
            schema["updated_at"] = row.updated_at.isoformat()
            schema["updated_by"] = row.updated_by
        return schema

    async def preview_schema(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self.normalize_config(payload, strict=True)
        await self._check_schema_changes(await self.get_schema(), normalized)
        return {"schema": normalized, "dry_run": True}

    async def save_schema(self, payload: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        reason = _text(payload.get("reason"), max_length=1000) or None
        before = await self.get_schema(for_update=True)
        normalized = self.normalize_config(payload, strict=True)
        await self._check_schema_changes(before, normalized)
        config = {
            "field_overrides": self._stored_field_overrides({field["key"]: field for field in normalized["fields"] if not field.get("custom")}),
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

    async def _check_schema_changes(self, before: dict[str, Any], after: dict[str, Any]) -> None:
        previous = before.get("custom_fields") or []
        if not previous or previous == after.get("custom_fields"):
            return
        metadata = (await self.session.execute(select(RegistryPerson.metadata_json))).scalars().all()
        issues = self.schema_change_issues(before, after, metadata)
        if issues:
            raise ProfileSchemaValidationError("Изменение затрагивает сохранённые значения профилей. Сначала исправьте значения или скройте необязательное поле.", issues)

    def schema_change_issues(self, before: dict[str, Any], after: dict[str, Any], metadata_rows: list[Any]) -> dict[str, str]:
        old_fields = {field["key"]: field for field in before.get("custom_fields") or []}
        new_fields = {field["key"]: field for field in after.get("custom_fields") or []}
        counts: dict[str, int] = {}
        for metadata in metadata_rows:
            values = metadata.get("profile_custom_fields") if isinstance(metadata, dict) else None
            if not isinstance(values, dict):
                continue
            for key, old in old_fields.items():
                value = values.get(key)
                if value is None or value == "":
                    continue
                new = new_fields.get(key)
                incompatible = new is None or old["type"] != new["type"]
                if not incompatible and old != new:
                    try:
                        self._clean_field_value(new, value)
                    except ValueError:
                        incompatible = True
                if incompatible:
                    counts[key] = counts.get(key, 0) + 1
        return {key: f"Изменение затрагивает профили: {count}. Сохраните тип и используемые значения." for key, count in counts.items()}

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
                validation = self._normalize_validation(raw_override.get("validation"), details, field_key)
                cap = _PROFILE_WRITE_LIMITS.get(field_key)
                if cap and validation.get("max_length", cap) > cap:
                    details[f"{field_key}.validation.max_length"] = f"Для этого поля допустимо не более {cap} символов."
                    validation["max_length"] = cap
                field["validation"] = {**field["validation"], **validation}
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
        if details:
            schema["warnings"] = [f"{key}: {message}" for key, message in details.items()]
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
        if "custom_fields" in payload and not isinstance(payload["custom_fields"], dict):
            details["custom_fields"] = "Пользовательские значения должны быть объектом."
        custom_payload = payload.get("custom_fields") if isinstance(payload.get("custom_fields"), dict) else {}
        normalized_custom: dict[str, Any] = {}
        for field in schema.get("fields") or []:
            if not isinstance(field, dict) or not field.get("visible", True):
                continue
            key = str(field.get("key") or "")
            label = str(field.get("label") or key)
            if field.get("custom"):
                value = custom_payload.get(key)
                try:
                    cleaned = self._clean_field_value(field, value)
                except ValueError as exc:
                    details[f"custom_fields.{key}"] = str(exc)
                    continue
                if field.get("required") and cleaned is None:
                    details[f"custom_fields.{key}"] = f"Заполните поле: {label}."
                    continue
                if key in custom_payload:
                    normalized_custom[key] = cleaned
                continue
            if field.get("editable", True) and (key in payload or field.get("required")):
                value = payload.get(key)
                try:
                    cleaned = self._clean_field_value(field, value)
                except ValueError as exc:
                    details[key] = str(exc)
                    continue
                if field.get("required") and key not in {"full_name", "department_id", "location_id", "phone"} and cleaned is None:
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

    def profile_value_issues(self, person_metadata: dict[str, Any] | None, schema: dict[str, Any]) -> list[dict[str, str]]:
        values = self.profile_custom_fields(person_metadata, schema)
        issues = []
        for field in schema.get("custom_fields") or []:
            key = field["key"]
            if key not in values or values[key] is None:
                continue
            try:
                self._clean_field_value(field, values[key])
            except ValueError as exc:
                issues.append({"key": key, "label": field["label"], "message": str(exc), "code": "legacy_value_needs_correction"})
        return issues

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
            if value is None or value == "":
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
                "options": self._normalize_options(raw.get("options"), details, prefix) if field_type == "select" else [],
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
        for length_key in ("min_length", "max_length"):
            if raw.get(length_key) is None:
                continue
            try:
                max_length = int(raw[length_key])
                if isinstance(raw[length_key], bool) or str(max_length) != str(raw[length_key]):
                    raise ValueError
            except (TypeError, ValueError):
                details[f"{prefix}.validation.{length_key}"] = "Длина должна быть целым числом."
            else:
                if not 1 <= max_length <= 1000:
                    details[f"{prefix}.validation.{length_key}"] = "Длина должна быть от 1 до 1000."
                else:
                    validation[length_key] = max_length
        if validation.get("min_length", 0) > validation.get("max_length", 1000):
            details[f"{prefix}.validation"] = "Минимальная длина превышает максимальную."
        if set(raw) - {"min_length", "max_length", "pattern"}:
            details[f"{prefix}.validation"] = "Неподдерживаемое правило проверки."
        if raw.get("pattern") is not None:
            pattern = raw["pattern"]
            if pattern:
                try:
                    safe_pattern(pattern)
                except ValueError as exc:
                    details[f"{prefix}.validation.pattern"] = str(exc)
                else:
                    validation["pattern"] = pattern
        return validation

    def _clean_field_value(self, field: dict[str, Any], value: Any) -> Any:
        return clean_profile_value(field, value)

    def _normalize_options(self, raw: Any, details: dict[str, str], prefix: str) -> list[dict[str, str]]:
        if not isinstance(raw, list) or not 1 <= len(raw) <= 100:
            details[f"{prefix}.options"] = "Добавьте от 1 до 100 вариантов списка."
            return []
        options = []
        seen = set()
        for index, option in enumerate(raw):
            value = option.get("value") if isinstance(option, dict) else option
            label = option.get("label") if isinstance(option, dict) else option
            if (not isinstance(value, str) or not value.strip() or len(value) > 120
                    or not isinstance(label, str) or not label.strip() or len(label) > 160
                    or value.strip() in seen):
                details[f"{prefix}.options.{index}"] = "Укажите уникальное значение и название варианта."
                continue
            seen.add(value.strip())
            options.append({"value": value.strip(), "label": label.strip()})
        return options

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
