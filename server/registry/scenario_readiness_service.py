"""On-demand read-only projection over Registry quality and canonical policy checks."""
from __future__ import annotations

from typing import Any
from types import SimpleNamespace
from sqlalchemy import select

from app.db.models import RegistryPerson, RequestStudioScenario, RequestStudioScenarioVersion
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from registry.manager_resolution import REASONS, resolve_person_manager
from registry.organization_service import organization_trust_impact
from registry.organization_trust import field_trust
from registry.profile_schema_service import RequesterProfileSchemaService
from registry.service import RegistrySnapshotService, _quality_issue_key
from tickets.policy_health_service import PolicyHealthService
from tickets.approval_policy import _resolve_approval_source
from tickets.request_scenario_processing import validate_map_processing_references
from tickets.request_scenario_validation import validate_scenario
from web_api.dto.request_scenario import ScenarioDefinition

DIMENSIONS = {"identities": "Идентичности", "profiles": "Профили", "departments": "Подразделения", "managers": "Руководители", "locations": "Локации", "devices": "Устройства", "profile_schema": "Схема профиля", "queues": "Очереди", "v3_cards": "Карты v3"}
IMPACTS = ("blocks_function", "attention", "information")


def _issue(kind, dimension, impact, object_type, object_id, title, description, *, function=None, action=None, **extra):
    return {"kind": kind, "dimension": dimension, "impact": impact, "object_type": object_type, "object_id": str(object_id),
            "title": title, "description": description, "scenario_readiness": True,
            "severity": {"blocks_function": "danger", "attention": "warning", "information": "info"}[impact],
            "affected_function": function or DIMENSIONS[dimension], "remediation": action or "Проверьте связанный объект Registry.", **extra}


def registry_issue_projection(issue):
    kind = issue["kind"]
    if "department" in kind:
        dimension, function = "departments", "Организационный контекст"
    elif "location" in kind:
        dimension, function = "locations", "Контекст места работы"
    elif kind in {"missing_identity", "duplicate_person", "ui_user_unlinked_registry_person"}:
        dimension, function = "identities", "Подтверждённый контекст сотрудника"
    else:
        dimension, function = "devices", "Выбор подтверждённого устройства"
    impact = "information" if dimension == "devices" and kind not in {"binding_inactive_person", "registration_conflict"} else "attention"
    if kind in {"binding_inactive_person", "registration_conflict"}:
        impact = "blocks_function"
    result = _issue(kind, dimension, impact, issue["object_type"], issue["object_id"], DIMENSIONS[dimension] + ": требуется проверка",
                    "Отсутствует или неоднозначна связь справочника. Проверка относится к указанной функции; обычные обращения без устройства остаются доступны.", function=function)
    for key in ("issue_key", "issue_state", "issue_state_reason", "person_id", "device_id", "binding_id", "claim_id"):
        if key in issue:
            result[key] = issue[key]
    return result


def summarize_readiness(issues):
    active = [issue for issue in issues if issue.get("issue_state", "active") not in {"ignored", "snoozed", "resolved"}]
    counts = {impact: sum(issue["impact"] == impact for issue in active) for impact in IMPACTS}
    dimensions = [{"key": key, "label": label, "counts": {impact: sum(issue["dimension"] == key and issue["impact"] == impact for issue in active) for impact in IMPACTS}} for key, label in DIMENSIONS.items()]
    # Export contains aggregates only: no identifiers, metadata, personal fields or ticket contents.
    return {"counts": counts, "dimensions": dimensions, "export": {"schema": "registry_scenario_readiness_aggregate_v1", "read_only": True, "counts": counts, "dimensions": dimensions}}


def _manager_source(policy):
    source = policy.get("approver_source") or policy.get("approvers") or {}
    while source:
        if isinstance(source, str):
            return {"type": source} if source == "requester_manager" else None
        if not isinstance(source, dict):
            return None
        if source.get("type") == "requester_manager":
            return source
        source = source.get("fallback")
    return None


class RegistryScenarioReadinessService:
    def __init__(self, session):
        self.session = session

    async def preview(self):
        snapshot_service = RegistrySnapshotService(self.session)
        snapshot = await snapshot_service.build_snapshot(full_scan=True)
        issues = [registry_issue_projection(issue) for issue in snapshot["data_quality"]]
        schema_service = RequesterProfileSchemaService(self.session)
        schema = await schema_service.get_schema()
        people = (await self.session.scalars(select(RegistryPerson).where(RegistryPerson.status.in_(["active", "self_reported"])))).all()
        profiles = {person["person_id"]: person for person in snapshot["people"]}
        for person in people:
            profile = profiles.get(person.person_id, {})
            if not profile.get("profile_completion", {}).get("complete", False):
                issues.append(_issue("scenario_profile_incomplete", "profiles", "attention", "person", person.person_id, "Профиль заполнен не полностью", "Проверьте обязательные поля действующей схемы профиля.", function="Создание обычного обращения по действующей политике профиля", person_id=person.person_id))
            if not profile.get("primary_device_count") and not profile.get("shared_device_count"):
                issues.append(_issue("scenario_person_no_device", "devices", "information", "person", person.person_id, "Нет активной привязки компьютера", "Сценарии без обязательного устройства и обычные обращения доступны.", function="Выбор устройства в сценарии", person_id=person.person_id))
            for key, dimension in (("department_id", "departments"), ("location_id", "locations")):
                if getattr(person, key) and field_trust(person, key).get("state") != "confirmed":
                    issues.append(_issue("scenario_unconfirmed_" + dimension, dimension, "attention", "person", person.person_id, "Организационные сведения не подтверждены", "Подтверждение учётной записи не подтверждает выбранное подразделение или локацию.", function="Доступность ограниченных материалов и услуг", action="Проверьте сведения и подтвердите их в карточке сотрудника.", person_id=person.person_id))
            invalid = schema_service.profile_value_issues(person.metadata_json, schema)
            if invalid:
                issues.append(_issue("scenario_profile_values_invalid", "profile_schema", "attention", "person", person.person_id, "Сохранённые значения требуют исправления", f"Количество полей: {len(invalid)}. Значения сохранены; массовое преобразование не выполняется.", function="Проверка дополнительных полей профиля", person_id=person.person_id))
        if schema.get("warnings"):
            issues.append(_issue("scenario_profile_schema_invalid", "profile_schema", "blocks_function", "profile_schema", "requester_profile", "Схема профиля требует исправления", "Некорректные типы, ограничения или варианты списка. Проверьте схему до сохранения новых профилей.", function="Редактирование профиля", fix_href="/app/admin/registry?tab=profile_schema", action="Откройте вкладку «Схема профиля»."))
        health = await PolicyHealthService(self.session).list_health()
        for obj in [*health.get("templates", []), *health.get("services", []), *health.get("offerings", [])]:
            for finding in obj.get("issues", []):
                dimension = "queues" if finding.get("policy_kind") == "routing" else "v3_cards"
                reference = str(obj.get("object_code") or obj.get("template_code") or "catalog")
                issues.append(_issue("scenario_policy_" + str(finding.get("kind") or "invalid") + "_" + str(finding.get("policy_kind") or "binding"), dimension,
                    "blocks_function" if finding.get("severity") in {"critical", "error"} else "attention", "request_template", reference,
                    f"Обработка услуги «{obj.get('title') or obj.get('template_name') or reference}» требует проверки",
                    "Действующий Policy Health обнаружил отсутствующую ссылку или конфликт настройки.", function="Маршрутизация, SLA или зависимая политика услуги",
                    action="Откройте Policy Health для конкретной услуги.", fix_href="/app/admin/policy-health"))
        await self._published_scenarios(issues)
        await self._managers(issues, people)
        # Apply the existing exceptions and stable issue-key mechanism; never save findings.
        unique = {issue.get("issue_key") or _quality_issue_key(issue): issue for issue in issues}
        issues = await snapshot_service._apply_quality_issue_overrides(list(unique.values()))
        impact = await organization_trust_impact(self.session)
        return {"read_only": True, "issues": issues, **summarize_readiness(issues), "organization_trust_impact": impact,
                "checked": {"people": len(people), "ui_users": len(snapshot.get("ui_users", [])), "devices": len(snapshot["assets"])}}

    async def _published_scenarios(self, issues):
        repo = TicketAdminConfigRepo(self.session)
        queues = [{"code": row.code, "is_active": row.is_active} for row in await repo.list_queues(include_inactive=True)]
        calendars = [{"id": row.id, "is_active": row.is_active, "timezone": row.timezone, "weekly_hours_json": row.weekly_hours_json, "holidays_json": row.holidays_json} for row in await repo.list_calendars(include_inactive=True)]
        rows = (await self.session.execute(select(RequestStudioScenario, RequestStudioScenarioVersion).outerjoin(RequestStudioScenarioVersion, RequestStudioScenarioVersion.id == RequestStudioScenario.published_version_id).where(RequestStudioScenario.enabled.is_(True), RequestStudioScenario.archived.is_(False)))).all()
        for scenario, version in rows:
            try:
                if version is None or version.state != "published":
                    raise ValueError("missing published version")
                definition = ScenarioDefinition.model_validate(version.definition)
                failures = [*validate_scenario(definition), *validate_map_processing_references(definition, queues, calendars)]
            except ValueError:
                failures = [True]
            if failures:
                issues.append(_issue("scenario_map_unavailable", "v3_cards", "blocks_function", "request_scenario", scenario.id,
                    f"Карта услуги «{scenario.title}» требует исправления", "Недоступны опубликованная версия, маршрут, срок обработки или зависимые настройки.", function="Выполнение конкретной карты обращения",
                    action="Откройте карту услуги и проверьте направления, сроки и зависимости.", fix_href="/app/admin/request-template-studio"))

    async def _managers(self, issues, people):
        repo = HelpdeskPolicyRepo(self.session)
        templates = await repo.list_request_templates(include_inactive=False)
        policies = await repo.list_policies(include_inactive=False)
        approval_by_code = {item["code"]: item.get("config") or {} for item in reversed(policies.get("approval", []))}
        cache: dict[tuple[str, bool], dict[str, Any]] = {}
        for template in templates:
            if not template.get("published_at"):
                continue
            policy = approval_by_code.get(template.get("approval_policy_code")) or (template.get("config") or {}).get("approval_policy") or {}
            source = _manager_source(policy)
            if not source or policy.get("required") is False:
                continue
            allow_department = source.get("allow_department_fallback") is True
            failures = []
            related_people = []
            for person in people:
                key = (person.person_id, allow_department)
                if key not in cache:
                    cache[key] = await resolve_person_manager(self.session, person, allow_department_fallback=allow_department)
                if cache[key]["status"] != "available":
                    failures.append(cache[key]["status"])
                    related_people.append({"person_id": person.person_id, "label": person.display_name, "reason": cache[key]["message"]})
            if failures:
                fallback = source.get("fallback")
                fallback_ids = (await _resolve_approval_source(self.session, SimpleNamespace(custom_fields={}, queue_id=None), fallback))[1] if fallback else []
                issues.append(_issue("scenario_manager_unavailable", "managers", "attention" if fallback_ids else "blocks_function", "request_template", template["template_code"],
                    f"Для услуги «{template.get('public_title') or template['template_code']}» не определён руководитель" + ("; настроен резервный процесс" if fallback_ids else " requester_manager"),
                    f"Сотрудников с недостающей связью: {len(failures)}. {' '.join(REASONS.get(reason, 'Проверьте организационную связь.') for reason in sorted(set(failures)))}", function="Согласование руководителем по конкретной услуге",
                    action="Подтвердите руководителя сотрудника или подразделения, проверьте активность и предметное право; настройте резервного согласующего.", fix_href="/app/admin/registry?tab=people", related_people=related_people))
