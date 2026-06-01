from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from auth.context import AuthContext
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo, normalize_template_code
from app.repos.service_catalog_repo import ServiceCatalogRepo
from tickets.form_catalog import validate_form_pack_schema
from tickets.service_catalog_publication import ServiceCatalogPublicationService
from web_api.dto.admin import AdminHelpdeskFormSchemaItem, AdminHelpdeskRequestTemplateItem
from web_api.dto.request_studio import (
    RequestStudioDraftRequest,
    RequestStudioIssue,
    RequestStudioPublishPreview,
    RequestStudioPublishResult,
    RequestStudioPublishStep,
    RequestStudioValidationResult,
)

BLOCKING_POLICY_KINDS = ("routing", "sla", "closure", "visibility")
OPTIONAL_POLICY_KINDS = ("approval", "notification")


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


def _request_token(payload: RequestStudioDraftRequest) -> str:
    canonical = payload.model_dump(mode="json", exclude={"confirmation_token"})
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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


class RequestStudioPublicationService:
    def __init__(self, session: Any):
        self.session = session
        self.policy_repo = HelpdeskPolicyRepo(session)
        self.catalog_repo = ServiceCatalogRepo(session)

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
            confirmation_token=_request_token(payload),
        )

    async def preview_publish(self, payload: RequestStudioDraftRequest) -> RequestStudioPublishPreview:
        validation = await self.validate_draft(payload)
        blocked = not validation.can_publish
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
            confirmation_token=validation.confirmation_token or _request_token(payload),
            message=(
                "Публикация заблокирована. Исправьте ошибки в Studio."
                if blocked
                else "Проверка пройдена. Подтвердите публикацию текущего draft."
            ),
        )

    async def publish(self, payload: RequestStudioDraftRequest, *, auth_context: AuthContext) -> RequestStudioPublishResult:
        expected_token = _request_token(payload)
        if payload.confirmation_token != expected_token:
            raise ValueError("confirmation_token is required and must match the previewed draft")
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
                        confirmation_token=expected_token,
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
                    confirmation_token=expected_token,
                )
            )
        if payload.publish_offering:
            offering = await self.catalog_repo.publish_offering(offering["full_code"], actor_id=actor_id, actor_role=actor_role)

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
