from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any

from auth.context import AuthContext
from config import (
    ALLOW_INSECURE_DEV_DEFAULTS,
    APP_ENV,
    DATABASE_URL,
    REQUEST_STUDIO_CONFIRMATION_SECRET,
    REQUEST_STUDIO_CONFIRMATION_TTL_SECONDS,
)
from sqlalchemy import select
from app.db.models import FormField, FormSchema, HelpdeskServiceOffering, RequestStudioPublishToken, RequestTemplate
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo, normalize_template_code
from app.repos.helpdesk_policy_repo import serialize_form_schema, serialize_request_template
from app.repos.service_catalog_repo import ServiceCatalogRepo
from tickets.form_catalog import validate_form_pack_schema
from tickets.service_catalog_contract import full_offering_code
from tickets.service_catalog_publication import ServiceCatalogPublicationService
from web_api.dto.admin import AdminHelpdeskFormSchemaItem, AdminHelpdeskRequestTemplateItem
from web_api.dto.request_studio import (
    RequestStudioDiffChange,
    RequestStudioDraftRequest,
    RequestStudioIssue,
    RequestStudioObjectDiff,
    RequestStudioPublishPreview,
    RequestStudioPublishResult,
    RequestStudioPublishStep,
    RequestStudioValidationResult,
)

BLOCKING_POLICY_KINDS = ("routing", "sla", "closure", "visibility")
OPTIONAL_POLICY_KINDS = ("approval", "notification")
CONFIRMATION_SCOPE = "request_studio.publish"
CONFIRMATION_VERSION = "rs1"


def _actor(auth_context: AuthContext) -> tuple[str, str]:
    actor_id = str(auth_context.actor_id or auth_context.actor_role or "admin").strip() or "admin"
    actor_role = str(auth_context.actor_role or "admin").strip() or "admin"
    return actor_id, actor_role


def _policy_ref(form: dict[str, Any], kind: str) -> str | None:
    direct = str(form.get(f"{kind}_policy_ref") or "").strip()
    if direct:
        return normalize_template_code(direct)
    code = str(form.get(f"{kind}_policy_code") or "").strip()
    if code:
        return normalize_template_code(code)
    refs = form.get("policy_refs") if isinstance(form.get("policy_refs"), dict) else {}
    ref = refs.get(kind) if isinstance(refs, dict) else None
    if isinstance(ref, dict):
        return normalize_template_code(ref.get("code")) or None
    return normalize_template_code(ref) or None


def _status(issues: list[RequestStudioIssue]) -> str:
    if any(issue.severity == "error" for issue in issues):
        return "error"
    if any(issue.severity == "warning" for issue in issues):
        return "warning"
    return "ok"


def _issue(
    severity: str,
    code: str,
    message: str,
    *,
    path: str | None = None,
    suggested_fix: str | None = None,
) -> RequestStudioIssue:
    return RequestStudioIssue(
        severity=severity,
        code=code,
        message=message,
        path=path,
        suggested_fix=suggested_fix,
    )


def _canonical_payload(payload: RequestStudioDraftRequest) -> dict[str, Any]:
    return payload.model_dump(mode="json", exclude={"confirmation_token"})


def _draft_hash(payload: RequestStudioDraftRequest) -> str:
    canonical = _canonical_payload(payload)
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _confirmation_secret() -> bytes:
    secret = REQUEST_STUDIO_CONFIRMATION_SECRET
    if secret:
        return secret.encode("utf-8")
    if APP_ENV in {"pilot", "prod", "production"} and not ALLOW_INSECURE_DEV_DEFAULTS:
        raise RuntimeError("REQUEST_STUDIO_CONFIRMATION_SECRET is required for Request Studio publish in strict runtime")
    fallback = f"request-studio-dev:{DATABASE_URL}"
    return hashlib.sha256(fallback.encode("utf-8")).digest()


def _sign_token_payload(payload_segment: str) -> str:
    signature = hmac.new(_confirmation_secret(), payload_segment.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(signature)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _decode_confirmation_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != CONFIRMATION_VERSION:
        raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_MALFORMED", "Некорректный confirmation token.")
    payload_segment = parts[1]
    expected_signature = _sign_token_payload(payload_segment)
    if not hmac.compare_digest(parts[2], expected_signature):
        raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_INVALID", "Confirmation token не прошёл проверку подписи.")
    try:
        decoded = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_MALFORMED", "Некорректный confirmation token.")
    if not isinstance(decoded, dict):
        raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_MALFORMED", "Некорректный confirmation token.")
    return decoded


def _normalized_form(payload: RequestStudioDraftRequest) -> dict[str, Any]:
    raw_form = payload.form.model_dump(mode="json", exclude_none=True)
    normalized_pack = validate_form_pack_schema(
        {
            "pack_key": "request_studio_publish_preview",
            "version": "preview",
            "title": "Request Studio preview",
            "forms": [raw_form],
        }
    )
    return normalized_pack["forms"][0]


def _normalize_value(value: Any) -> Any:
    if value == "":
        return None
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in sorted(value.items()) if item not in (None, "", [], {})}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def _change(path: str, label: str, before: Any, after: Any, *, severity: str = "info") -> RequestStudioDiffChange | None:
    normalized_before = _normalize_value(before)
    normalized_after = _normalize_value(after)
    if normalized_before == normalized_after:
        return None
    if normalized_before is None and normalized_after is not None:
        change_type = "added"
    elif normalized_before is not None and normalized_after is None:
        change_type = "removed"
    else:
        change_type = "changed"
    return RequestStudioDiffChange(
        path=path,
        label=label,
        from_value=normalized_before,
        to_value=normalized_after,
        change_type=change_type,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
    )


def _field_projection(field: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "key": str(field.get("key") or ""),
        "label": field.get("label"),
        "type": field.get("type") or field.get("field_type"),
        "required": bool(field.get("required")),
        "options": deepcopy(field.get("options") or []),
        "visibility": deepcopy(field.get("visibility") or field.get("visible_when") or {}),
        "process_mapping": deepcopy(field.get("process_mapping") or {}),
        "sort_order": int(field.get("sort_order") if field.get("sort_order") is not None else index),
    }


def _field_changes(before_fields: list[dict[str, Any]], after_fields: list[dict[str, Any]]) -> list[RequestStudioDiffChange]:
    before_by_key = {_field_projection(field, index)["key"]: _field_projection(field, index) for index, field in enumerate(before_fields)}
    after_by_key = {_field_projection(field, index)["key"]: _field_projection(field, index) for index, field in enumerate(after_fields)}
    changes: list[RequestStudioDiffChange] = []
    for key in sorted(set(before_by_key) | set(after_by_key)):
        before = before_by_key.get(key)
        after = after_by_key.get(key)
        label = str((after or before or {}).get("label") or key)
        if before is None:
            changes.append(
                RequestStudioDiffChange(
                    path=f"fields.{key}",
                    label=f"Поле \"{label}\"",
                    from_value=None,
                    to_value=after,
                    change_type="added",
                    severity="info",
                )
            )
            continue
        if after is None:
            changes.append(
                RequestStudioDiffChange(
                    path=f"fields.{key}",
                    label=f"Поле \"{label}\"",
                    from_value=before,
                    to_value=None,
                    change_type="removed",
                    severity="warning",
                )
            )
            continue
        for field_name, field_label in (
            ("label", f"Название поля \"{label}\""),
            ("type", f"Тип поля \"{label}\""),
            ("required", f"Обязательность поля \"{label}\""),
            ("options", f"Варианты поля \"{label}\""),
            ("visibility", f"Условия показа поля \"{label}\""),
            ("process_mapping", f"Назначение поля \"{label}\""),
            ("sort_order", f"Порядок поля \"{label}\""),
        ):
            item = _change(f"fields.{key}.{field_name}", field_label, before.get(field_name), after.get(field_name))
            if item:
                changes.append(item)
    return changes


def _request_template_candidate(form: dict[str, Any], payload: RequestStudioDraftRequest, template_code: str, form_schema_id: str) -> dict[str, Any]:
    return {
        "template_code": template_code,
        "public_title": str(form.get("title") or payload.offering.public_title or template_code),
        "description": str(form.get("description") or payload.offering.short_description or "").strip() or None,
        "ticket_type": str(form.get("ticket_type") or payload.offering.request_type or "incident"),
        "form_schema_id": form_schema_id,
        "workflow_profile_id": str(form.get("ticket_type") or payload.offering.request_type or "incident"),
        "priority_policy_code": _policy_ref(form, "priority"),
        "routing_policy_code": _policy_ref(form, "routing") or payload.offering.routing_policy_code,
        "sla_policy_code": _policy_ref(form, "sla") or payload.offering.sla_policy_code,
        "approval_policy_code": _policy_ref(form, "approval") or payload.offering.approval_policy_code,
        "closure_policy_code": _policy_ref(form, "closure") or payload.offering.closure_policy_code,
        "visibility_policy_code": _policy_ref(form, "visibility") or payload.offering.visibility_policy_code,
        "notification_policy_code": _policy_ref(form, "notification") or payload.offering.notification_policy_code,
        "reporting_policy_code": _policy_ref(form, "reporting"),
    }


def _offering_candidate(payload: RequestStudioDraftRequest, template_code: str, form_schema_id: str, ticket_type: str) -> dict[str, Any]:
    result = payload.offering.model_dump(mode="json", exclude_none=True)
    result["request_template_key"] = template_code
    result["form_schema_id"] = form_schema_id
    result["request_type"] = result.get("request_type") or ticket_type
    if payload.publish_offering:
        result["lifecycle_status"] = "published"
    return result


def _service_candidate(service: dict[str, Any] | None, payload: RequestStudioDraftRequest) -> dict[str, Any] | None:
    if not service:
        return None
    result = deepcopy(service)
    if payload.publish_service and result.get("lifecycle_status") != "published":
        result["lifecycle_status"] = "published"
    return result


class RequestStudioPublicationService:
    def __init__(self, session: Any):
        self.session = session
        self.policy_repo = HelpdeskPolicyRepo(session)
        self.catalog_repo = ServiceCatalogRepo(session)

    async def _issue_confirmation_token(
        self,
        payload: RequestStudioDraftRequest,
        *,
        auth_context: AuthContext,
        summary: dict[str, int],
    ) -> tuple[str, datetime]:
        actor_id, actor_role = _actor(auth_context)
        issued_at = _utc_now()
        ttl = max(1, int(REQUEST_STUDIO_CONFIRMATION_TTL_SECONDS or 600))
        expires_at = issued_at + timedelta(seconds=ttl)
        nonce = secrets.token_urlsafe(32)
        token_payload = {
            "scope": CONFIRMATION_SCOPE,
            "draft_hash": _draft_hash(payload),
            "actor_id": actor_id,
            "actor_role": actor_role,
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "nonce": nonce,
            "preview_version": 1,
        }
        payload_segment = _b64url_encode(
            json.dumps(token_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        token = f"{CONFIRMATION_VERSION}.{payload_segment}.{_sign_token_payload(payload_segment)}"
        self.session.add(
            RequestStudioPublishToken(
                token_hash=_sha256_text(token),
                nonce_hash=_sha256_text(nonce),
                draft_hash=token_payload["draft_hash"],
                scope=CONFIRMATION_SCOPE,
                actor_id=actor_id,
                actor_role=actor_role,
                issued_at=issued_at,
                expires_at=expires_at,
                preview_summary_json=deepcopy(summary),
                created_at=issued_at,
                updated_at=issued_at,
            )
        )
        await self.session.flush()
        return token, expires_at

    async def _validate_confirmation_token(
        self,
        payload: RequestStudioDraftRequest,
        *,
        auth_context: AuthContext,
    ) -> RequestStudioPublishToken:
        token = str(payload.confirmation_token or "").strip()
        if not token:
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_REQUIRED", "Confirmation token is required.")
        decoded = _decode_confirmation_token(token)
        actor_id, actor_role = _actor(auth_context)
        if decoded.get("scope") != CONFIRMATION_SCOPE:
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_SCOPE", "Confirmation token относится к другому действию.")
        if decoded.get("actor_id") != actor_id or decoded.get("actor_role") != actor_role:
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_ACTOR_MISMATCH", "Confirmation token выпущен для другого администратора.")
        draft_hash = _draft_hash(payload)
        if not hmac.compare_digest(str(decoded.get("draft_hash") or ""), draft_hash):
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_DRAFT_MISMATCH", "Draft изменился после preview. Подготовьте публикацию заново.", status=409)
        expires_at = _parse_iso_datetime(decoded.get("expires_at"))
        if expires_at is None or expires_at <= _utc_now():
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_EXPIRED", "Preview устарел. Подготовьте публикацию заново.", status=409)
        nonce = str(decoded.get("nonce") or "")
        stmt = (
            select(RequestStudioPublishToken)
            .where(RequestStudioPublishToken.token_hash == _sha256_text(token))
            .with_for_update()
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_UNKNOWN", "Confirmation token не найден или уже очищен.", status=409)
        if row.used_at is not None:
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_USED", "Confirmation token уже использован.", status=409)
        stored_expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
        if stored_expires_at <= _utc_now():
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_EXPIRED", "Preview устарел. Подготовьте публикацию заново.", status=409)
        if row.scope != CONFIRMATION_SCOPE or row.actor_id != actor_id or row.actor_role != actor_role:
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_ACTOR_MISMATCH", "Confirmation token выпущен для другого администратора.")
        if row.draft_hash != draft_hash or row.nonce_hash != _sha256_text(nonce):
            raise RequestStudioConfirmationError("CONFIRMATION_TOKEN_DRAFT_MISMATCH", "Draft изменился после preview. Подготовьте публикацию заново.", status=409)
        return row

    async def _mark_confirmation_used(self, token_row: RequestStudioPublishToken, *, auth_context: AuthContext) -> None:
        actor_id, _actor_role = _actor(auth_context)
        now = _utc_now()
        token_row.used_at = now
        token_row.used_by = actor_id
        token_row.updated_at = now
        await self.session.flush()

    async def _active_form_schema(self, schema_id: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                select(FormSchema)
                .where(FormSchema.schema_id == schema_id, FormSchema.is_active.is_(True))
                .order_by(FormSchema.created_at.desc())
            )
        ).scalar_one_or_none()
        if not row:
            return None
        fields = list(
            (
                await self.session.execute(
                    select(FormField)
                    .where(FormField.schema_id == row.schema_id, FormField.schema_version == row.version)
                    .order_by(FormField.sort_order.asc(), FormField.id.asc())
                )
            ).scalars().all()
        )
        return serialize_form_schema(row, fields=fields)

    async def _active_request_template(self, template_code: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                select(RequestTemplate)
                .where(RequestTemplate.template_code == template_code, RequestTemplate.is_active.is_(True))
                .order_by(RequestTemplate.created_at.desc())
            )
        ).scalar_one_or_none()
        return serialize_request_template(row) if row else None

    async def _build_diffs(
        self,
        payload: RequestStudioDraftRequest,
        *,
        validation: RequestStudioValidationResult,
    ) -> tuple[list[RequestStudioObjectDiff], dict[str, int]]:
        blocked = not validation.can_publish
        try:
            form = _normalized_form(payload)
        except ValueError:
            form = None
        template_code = normalize_template_code((form or {}).get("key") or payload.offering.request_template_key)
        form_schema_id = f"{template_code}_form" if template_code else ""
        service_code = normalize_template_code(payload.offering.service_code)
        offering_code = normalize_template_code(payload.offering.code)
        offering_full_code = full_offering_code(service_code, offering_code) if service_code and offering_code else ""

        diffs: list[RequestStudioObjectDiff] = []
        if form and template_code:
            existing_form = await self._active_form_schema(form_schema_id)
            form_changes = [
                item
                for item in (
                    _change("title", "Название формы", (existing_form or {}).get("title"), form.get("title")),
                    _change("description", "Описание формы", (existing_form or {}).get("description"), form.get("description")),
                    _change("ticket_type", "Тип процесса", (existing_form or {}).get("ticket_type"), form.get("ticket_type")),
                    _change("form_key", "Ключ формы", (existing_form or {}).get("form_key"), template_code),
                    _change("request_template_code", "Связанный тип обращения", (existing_form or {}).get("request_template_code"), template_code),
                )
                if item is not None
            ]
            form_changes.extend(_field_changes((existing_form or {}).get("fields") or [], form.get("fields") or []))
            diffs.append(
                RequestStudioObjectDiff(
                    object_type="form_schema",
                    object_code=form_schema_id,
                    action="blocked" if blocked else ("create" if existing_form is None else ("update" if form_changes else "noop")),
                    title="Форма пользователя",
                    changes=form_changes,
                )
            )

            existing_template = await self._active_request_template(template_code)
            template_candidate = _request_template_candidate(form, payload, template_code, form_schema_id)
            template_fields = (
                ("public_title", "Название типа обращения"),
                ("description", "Описание типа обращения"),
                ("ticket_type", "Тип процесса"),
                ("form_schema_id", "Форма пользователя"),
                ("workflow_profile_id", "Профиль обработки"),
                ("routing_policy_code", "Маршрут"),
                ("sla_policy_code", "Сроки"),
                ("approval_policy_code", "Согласование"),
                ("closure_policy_code", "Закрытие"),
                ("visibility_policy_code", "Видимость"),
                ("notification_policy_code", "Уведомления"),
                ("reporting_policy_code", "Отчётность"),
            )
            template_changes = [
                item
                for field, label in template_fields
                if (item := _change(field, label, (existing_template or {}).get(field), template_candidate.get(field))) is not None
            ]
            template_warnings: list[str] = []
            conflicting_offerings = list(
                (
                    await self.session.execute(
                        select(HelpdeskServiceOffering).where(
                            HelpdeskServiceOffering.request_template_key == template_code,
                            HelpdeskServiceOffering.full_code != offering_full_code,
                        )
                    )
                ).scalars().all()
            )
            if conflicting_offerings:
                template_warnings.append("Такой template_code уже связан с другим типом обращения. Проверьте, что не перезаписываете чужой шаблон.")
            diffs.append(
                RequestStudioObjectDiff(
                    object_type="request_template",
                    object_code=template_code,
                    action="blocked" if blocked else ("create" if existing_template is None else ("update" if template_changes else "noop")),
                    title="Тип обращения",
                    changes=template_changes,
                    warnings=template_warnings,
                )
            )

            existing_offering = await self.catalog_repo.get_offering_by_full_code(offering_full_code)
            offering_candidate = _offering_candidate(payload, template_code, form_schema_id, template_candidate["ticket_type"])
            offering_fields = (
                ("public_title", "Название в каталоге"),
                ("short_description", "Краткое описание"),
                ("lifecycle_status", "Статус публикации"),
                ("visibility", "Видимость"),
                ("request_type", "Тип заявки"),
                ("request_template_key", "Тип обращения"),
                ("form_schema_id", "Форма"),
                ("routing_policy_code", "Маршрут"),
                ("sla_policy_code", "Сроки"),
                ("approval_policy_code", "Согласование"),
                ("closure_policy_code", "Закрытие"),
                ("visibility_policy_code", "Видимость обращения"),
                ("notification_policy_code", "Уведомления"),
            )
            offering_changes = [
                item
                for field, label in offering_fields
                if (item := _change(field, label, (existing_offering or {}).get(field), offering_candidate.get(field))) is not None
            ]
            diffs.append(
                RequestStudioObjectDiff(
                    object_type="offering",
                    object_code=offering_full_code,
                    action="blocked" if blocked else ("create" if existing_offering is None else ("update" if offering_changes else "noop")),
                    title="Каталог услуг",
                    changes=offering_changes,
                )
            )

        service = await self.catalog_repo.get_service_by_code(service_code) if service_code else None
        service_candidate = _service_candidate(service, payload)
        service_changes = [
            item
            for item in (
                _change("lifecycle_status", "Статус раздела", (service or {}).get("lifecycle_status"), (service_candidate or {}).get("lifecycle_status")),
                _change("visibility", "Видимость раздела", (service or {}).get("visibility"), (service_candidate or {}).get("visibility")),
                _change("default_queue_id", "Очередь по умолчанию", (service or {}).get("default_queue_id"), (service_candidate or {}).get("default_queue_id")),
            )
            if item is not None
        ]
        service_action = "blocked" if blocked else ("create" if service is None else ("update" if service_changes else "noop"))
        service_warnings = [] if service else ["Раздел каталога не найден. Publication validation должна блокировать публикацию до выбора существующего раздела."]
        if service_code:
            diffs.append(
                RequestStudioObjectDiff(
                    object_type="service",
                    object_code=service_code,
                    action=service_action,
                    title="Раздел каталога",
                    changes=service_changes,
                    warnings=service_warnings,
                )
            )

        summary = {"creates": 0, "updates": 0, "noops": 0, "blocked": 0, "warnings": 0}
        for diff in diffs:
            if diff.action == "create":
                summary["creates"] += 1
            elif diff.action == "update":
                summary["updates"] += 1
            elif diff.action == "noop":
                summary["noops"] += 1
            elif diff.action == "blocked":
                summary["blocked"] += 1
            summary["warnings"] += len(diff.warnings)
        return diffs, summary

    async def validate_draft(self, payload: RequestStudioDraftRequest) -> RequestStudioValidationResult:
        issues: list[RequestStudioIssue] = []
        form: dict[str, Any] | None = None
        try:
            form = _normalized_form(payload)
        except ValueError as exc:
            issues.append(
                _issue(
                    "error",
                    "form_invalid",
                    str(exc) or "Форма пользователя заполнена некорректно.",
                    path="form",
                    suggested_fix="Исправьте поля формы в Studio и сохраните черновик.",
                )
            )

        template_code = normalize_template_code(payload.form.key or payload.offering.request_template_key)
        service_code = normalize_template_code(payload.offering.service_code)
        offering_code = normalize_template_code(payload.offering.code)
        if not template_code:
            issues.append(_issue("error", "template_missing", "Не задан тип обращения.", path="form.key"))
        if not service_code:
            issues.append(_issue("error", "service_missing", "Не выбран раздел каталога.", path="offering.service_code"))
        if not offering_code:
            issues.append(_issue("error", "offering_missing", "Не задан код типа обращения.", path="offering.code"))
        if not str(payload.offering.public_title or payload.form.title or "").strip():
            issues.append(_issue("error", "title_missing", "Не задано название типа обращения.", path="offering.public_title"))

        service = None
        if service_code:
            try:
                service = await self.catalog_repo.get_service_by_code(service_code)
            except ValueError:
                service = None
            if not service:
                issues.append(
                    _issue(
                        "error",
                        "service_not_found",
                        "Выбранный раздел каталога не найден.",
                        path="offering.service_code",
                        suggested_fix="Выберите существующий раздел или создайте его в экспертном каталоге.",
                    )
                )

        if form:
            fields = form.get("fields") if isinstance(form.get("fields"), list) else []
            if not fields:
                issues.append(
                    _issue(
                        "error",
                        "form_empty",
                        "Форма пользователя пустая. Нельзя публиковать обращение без полей.",
                        path="form.fields",
                    )
                )
            for kind in BLOCKING_POLICY_KINDS:
                code = _policy_ref(form, kind) or getattr(payload.offering, f"{kind}_policy_code", None)
                if not code:
                    labels = {
                        "routing": "Не выбран маршрут. Заявка не попадёт в рабочую очередь.",
                        "sla": "Не выбран срок выполнения. Публикация заблокирована.",
                        "closure": "Не настроено закрытие. Исполнитель не получит обязательные действия перед закрытием.",
                        "visibility": "Правила видимости не выбраны. Пользователь может увидеть неправильный статус.",
                    }
                    issues.append(_issue("error", f"{kind}_missing", labels[kind], path=f"form.{kind}_policy_ref"))
                    continue
                effective = await self.policy_repo.resolve_policy_ref(kind=kind, code=code, source="request_studio.safe_publish")
                if not effective.get("sources"):
                    issues.append(
                        _issue(
                            "error",
                            f"{kind}_invalid",
                            f"Политика {code} для блока {kind} не активна или не найдена.",
                            path=f"form.{kind}_policy_ref",
                            suggested_fix="Выберите активную политику в Studio или откройте экспертную настройку.",
                        )
                    )

            approval_code = _policy_ref(form, "approval") or payload.offering.approval_policy_code
            if not approval_code and str(payload.form.ticket_type or "").strip().lower() in {"access", "access_request"}:
                issues.append(
                    _issue(
                        "warning",
                        "approval_recommended",
                        "Согласование не включено. Для доступа обычно требуется согласование.",
                        path="form.approval_policy_ref",
                    )
                )
            notification_code = _policy_ref(form, "notification") or payload.offering.notification_policy_code
            if notification_code:
                effective = await self.policy_repo.resolve_policy_ref(kind="notification", code=notification_code, source="request_studio.safe_publish")
                if not effective.get("sources"):
                    issues.append(
                        _issue(
                            "warning",
                            "notification_invalid",
                            f"Политика уведомлений {notification_code} не активна или не найдена.",
                            path="form.notification_policy_ref",
                            suggested_fix="Выберите активную политику или отметьте уведомления как неиспользуемые.",
                        )
                    )
            else:
                issues.append(
                    _issue(
                        "warning",
                        "notification_unused",
                        "Уведомления не выбраны. Это рекомендация, не блокер публикации.",
                        path="form.notification_policy_ref",
                    )
                )

        if service and service.get("lifecycle_status") != "published" and payload.publish_service:
            service_validation = await ServiceCatalogPublicationService(self.session).validate_service(service_code)
            for catalog_issue in service_validation.get("issues") or []:
                severity = "error" if catalog_issue.get("severity") in {"critical", "error"} else "warning"
                issues.append(
                    _issue(
                        severity,
                        f"service_{catalog_issue.get('kind') or 'validation'}",
                        str(catalog_issue.get("message") or "Раздел каталога не готов к публикации."),
                        path=f"service.{catalog_issue.get('path') or ''}".rstrip("."),
                        suggested_fix=catalog_issue.get("suggested_fix"),
                    )
                )

        status = _status(issues)
        return RequestStudioValidationResult(
            status=status,  # type: ignore[arg-type]
            can_publish=status != "error",
            issues=issues,
            confirmation_token=None,
        )

    async def preview_publish(self, payload: RequestStudioDraftRequest, *, auth_context: AuthContext) -> RequestStudioPublishPreview:
        validation = await self.validate_draft(payload)
        blocked = not validation.can_publish
        diffs, summary = await self._build_diffs(payload, validation=validation)
        confirmation_token: str | None = None
        expires_at: datetime | None = None
        if not blocked:
            confirmation_token, expires_at = await self._issue_confirmation_token(
                payload,
                auth_context=auth_context,
                summary=summary,
            )
        steps = [
            RequestStudioPublishStep(
                key="form_schema",
                label="Форма пользователя",
                status="blocked" if blocked else "will_publish",
                details="Будет опубликована версия form schema из текущего draft.",
            ),
            RequestStudioPublishStep(
                key="request_template",
                label="Тип обращения",
                status="blocked" if blocked else "will_publish",
                details="Будет опубликован request template с выбранными политиками.",
            ),
            RequestStudioPublishStep(
                key="service_catalog",
                label="Каталог услуг",
                status="blocked" if blocked else "will_publish",
                details="Раздел и тип обращения будут опубликованы, если validation не найдёт блокеров.",
            ),
        ]
        return RequestStudioPublishPreview(
            validation=validation,
            steps=steps,
            confirmation_token=confirmation_token,
            expires_at=expires_at.isoformat() if expires_at else None,
            diffs=diffs,
            summary=summary,
            message=(
                "Публикация заблокирована. Исправьте ошибки в Studio."
                if blocked
                else "Проверка пройдена. Подтвердите публикацию текущего draft."
            ),
        )

    async def publish(self, payload: RequestStudioDraftRequest, *, auth_context: AuthContext) -> RequestStudioPublishResult:
        token_row = await self._validate_confirmation_token(payload, auth_context=auth_context)
        validation = await self.validate_draft(payload)
        if not validation.can_publish:
            raise RequestStudioPublishBlocked(validation)

        actor_id, actor_role = _actor(auth_context)
        form = _normalized_form(payload)
        template_code = normalize_template_code(form.get("key") or payload.offering.request_template_key)
        form_schema = await self.policy_repo.publish_form_schema(
            schema_id=f"{template_code}_form",
            title=str(form.get("title") or template_code),
            description=str(form.get("description") or "").strip() or None,
            form_key=template_code,
            request_template_code=template_code,
            ticket_type=str(form.get("ticket_type") or "incident"),
            fields=form.get("fields") if isinstance(form.get("fields"), list) else [],
            field_roles=form.get("field_roles") if isinstance(form.get("field_roles"), dict) else {},
            config={
                "source": "request_studio_safe_publish",
                "request_kind": form.get("request_kind") or template_code,
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        request_template = await self.policy_repo.publish_request_template(
            template_code=template_code,
            public_title=str(form.get("title") or payload.offering.public_title or template_code),
            internal_name=f"{form.get('ticket_type') or 'process'} / {template_code}",
            description=str(form.get("description") or payload.offering.short_description or "").strip() or None,
            ticket_type=str(form.get("ticket_type") or payload.offering.request_type or "incident"),
            category_id=form.get("category_id") if form.get("category_id") is not None else None,
            service_id=form.get("service_id") if form.get("service_id") is not None else None,
            subcategory_id=form.get("subcategory_id") if form.get("subcategory_id") is not None else None,
            form_schema_id=f"{template_code}_form",
            workflow_profile_id=str(form.get("ticket_type") or payload.offering.request_type or "incident"),
            priority_policy_code=_policy_ref(form, "priority"),
            routing_policy_code=_policy_ref(form, "routing") or payload.offering.routing_policy_code,
            sla_policy_id=form.get("sla_policy_id") if form.get("sla_policy_id") is not None else None,
            sla_policy_code=_policy_ref(form, "sla") or payload.offering.sla_policy_code,
            ola_policy_code=_policy_ref(form, "ola"),
            approval_policy_code=_policy_ref(form, "approval") or payload.offering.approval_policy_code,
            diagnostic_policy_code=_policy_ref(form, "diagnostic"),
            closure_policy_code=_policy_ref(form, "closure") or payload.offering.closure_policy_code,
            visibility_policy_code=_policy_ref(form, "visibility") or payload.offering.visibility_policy_code,
            notification_policy_code=_policy_ref(form, "notification") or payload.offering.notification_policy_code,
            reporting_policy_code=_policy_ref(form, "reporting"),
            config={
                "form": deepcopy(form),
                "form_schema": {
                    "schema_id": form_schema["schema_id"],
                    "version": form_schema["version"],
                    "field_count": len(form_schema.get("fields") or []),
                },
                "field_roles": form.get("field_roles") if isinstance(form.get("field_roles"), dict) else {},
                "request_studio": {
                    "published_at": datetime.now(timezone.utc).isoformat(),
                },
            },
            overrides={
                "source": "request_studio_safe_publish",
                "publish_policies": False,
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )

        offering_payload = payload.offering.model_dump(mode="json", exclude_none=True)
        offering_payload["request_template_key"] = template_code
        offering_payload["form_schema_id"] = form_schema["schema_id"]
        offering_payload["request_type"] = offering_payload.get("request_type") or request_template["ticket_type"]
        offering = await self.catalog_repo.upsert_offering_draft(offering_payload, actor_id=actor_id, actor_role=actor_role)
        publication = ServiceCatalogPublicationService(self.session)
        service = await self.catalog_repo.get_service_by_code(payload.offering.service_code)
        if service and service.get("lifecycle_status") != "published" and payload.publish_service:
            service_validation = await publication.validate_service(payload.offering.service_code)
            if service_validation["blocking"]:
                raise RequestStudioPublishBlocked(
                    RequestStudioValidationResult(
                        status="error",
                        can_publish=False,
                        issues=[
                            _issue("error", "service_publication_blocked", str(issue.get("message") or "Раздел каталога не готов."), path=f"service.{issue.get('path') or ''}".rstrip("."))
                            for issue in service_validation.get("issues") or []
                            if issue.get("severity") in {"critical", "error"}
                        ],
                        confirmation_token=None,
                    )
                )
            service = await self.catalog_repo.publish_service(payload.offering.service_code, actor_id=actor_id, actor_role=actor_role)
        offering_validation = await publication.validate_offering(offering["full_code"])
        if offering_validation["blocking"]:
            raise RequestStudioPublishBlocked(
                RequestStudioValidationResult(
                    status="error",
                    can_publish=False,
                    issues=[
                        _issue("error", "offering_publication_blocked", str(issue.get("message") or "Тип обращения в каталоге не готов."), path=f"offering.{issue.get('path') or ''}".rstrip("."))
                        for issue in offering_validation.get("issues") or []
                        if issue.get("severity") in {"critical", "error"}
                    ],
                    confirmation_token=None,
                )
            )
        if payload.publish_offering:
            offering = await self.catalog_repo.publish_offering(offering["full_code"], actor_id=actor_id, actor_role=actor_role)
        await self._mark_confirmation_used(token_row, auth_context=auth_context)

        return RequestStudioPublishResult(
            validation=validation,
            request_template=AdminHelpdeskRequestTemplateItem.model_validate(request_template),
            form_schema=AdminHelpdeskFormSchemaItem.model_validate(form_schema),
            service=service,
            offering=offering,
            message="Тип обращения опубликован из Studio.",
        )


class RequestStudioPublishBlocked(ValueError):
    def __init__(self, validation: RequestStudioValidationResult):
        super().__init__("request studio publication is blocked")
        self.validation = validation


class RequestStudioConfirmationError(ValueError):
    def __init__(self, error_code: str, message: str, *, status: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.status = status
