from __future__ import annotations

from aiohttp import web
from loguru import logger

from access_control.service import can, can_role
from app.db import get_session
from app.repos.ticket_admin_audit_repo import TicketAdminAuditRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from auth.middleware import require_auth
from config import (
    TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS,
    TICKET_ADMIN_CONFIG_API_ENABLED,
    TICKET_ADMIN_CONFIG_WRITE_ENABLED,
    TICKET_AUDITOR_ROLE_ENABLED,
    TICKET_AUTO_CLOSE_HOURS,
    TICKET_EVENTS_HOT_RETENTION_DAYS,
    TICKET_FSM_MODE,
    TICKET_LEGACY_ROLE_FIELDS,
    TICKET_OLA_ENABLED,
    TICKET_REQUIRE_ROOT_CAUSE_PRIORITIES,
    TICKET_RESOLUTION_VALIDATION_MODE,
    TICKET_RETENTION_DRY_RUN,
    TICKET_RETENTION_ENABLED,
    TICKET_SLA_CALENDAR_ENABLED,
    TICKET_TAKE_QUEUE_COMMON_CODE,
    TICKET_TAKE_QUEUE_MODE,
    TICKET_TAKE_QUEUE_TEST_CODE,
)
from tickets.form_catalog import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    build_default_ticket_form_pack,
    build_routing_builder_catalog,
    resolve_ticket_form_pack,
    validate_form_pack_schema,
)
from tickets.statuses import (
    CANONICAL_STATUSES,
    REQUESTER_STATUS_LABELS_RU,
    STATUS_LABELS_RU,
    next_action_owner_for_status,
    requester_status_for_internal,
)
from tickets.workflow_profiles import list_workflow_profiles
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.settings import (
    WebSettingsAuditItem,
    WebSettingsCalendarItem,
    WebSettingsCapabilities,
    WebSettingsOlaTargetItem,
    WebSettingsOverview,
    WebSettingsPayload,
    WebSettingsPriorityModelPayload,
    WebSettingsProcessSchemaItem,
    WebSettingsPriorityMatrixItem,
    WebSettingsQueueItem,
    WebSettingsQueueMemberItem,
    WebSettingsResolutionCodeItem,
    WebSettingsRoutingBuilderFieldItem,
    WebSettingsRoutingBuilderFormFieldItem,
    WebSettingsRoutingBuilderFormItem,
    WebSettingsRoutingBuilderOperatorItem,
    WebSettingsRoutingBuilderPayload,
    WebSettingsRoutingRuleItem,
    WebSettingsSlaPolicyItem,
    WebSettingsSlaTargetItem,
    WebSettingsNextActionOwnerItem,
    WebSettingsRequesterStatusItem,
    WebSettingsTicketGovernancePayload,
    WebSettingsTicketOperationalFlags,
    WebSettingsTicketSettingsPayload,
    WebSettingsTicketStatusItem,
    WebSettingsSupportLineItem,
    WebSettingsWorkflowProfileItem,
)


NEXT_ACTION_OWNER_LABELS = {
    "support": "Поддержка",
    "requester": "Пользователь",
    "internal_team": "Внутренняя группа",
    "vendor": "Внешняя сторона",
    "approver": "Согласующий",
    "system": "Система",
}


def _build_process_schema_items() -> list[WebSettingsProcessSchemaItem]:
    return [
        WebSettingsProcessSchemaItem(
            key="request_template",
            label="request_template",
            meaning="Каталог обращений собирает факты и порождает процессный контекст",
            source="request_forms",
            ui_surface="/app/admin/forms",
            status="active",
        ),
        WebSettingsProcessSchemaItem(
            key="ticket_type_workflow_profile",
            label="ticket_type / workflow_profile",
            meaning="Тип заявки выбирает профиль workflow",
            source="workflow_profiles",
            ui_surface="/app/settings",
            status="active",
        ),
        WebSettingsProcessSchemaItem(
            key="category",
            label="category / service / subcategory",
            meaning="Категория определяет профильную область",
            source="request_template.category_id",
            ui_surface="/app/admin/forms",
            status="active",
        ),
        WebSettingsProcessSchemaItem(
            key="priority",
            label="priority",
            meaning="Приоритет рассчитывается из impact, urgency и importance",
            source="priority_policy",
            ui_surface="/app/settings",
            status="active",
        ),
        WebSettingsProcessSchemaItem(
            key="routing",
            label="routing",
            meaning="Роутинг выбирает очередь",
            source="routing_rules",
            ui_surface="/app/settings",
            status="active",
        ),
        WebSettingsProcessSchemaItem(
            key="queue",
            label="queue",
            meaning="Очередь определяет группу ответственных",
            source="ticket_queues.members",
            ui_surface="/app/settings",
            status="active",
        ),
        WebSettingsProcessSchemaItem(
            key="sla",
            label="SLA",
            meaning="SLA задаёт срок перед пользователем",
            source="sla_policies.targets",
            ui_surface="/app/settings",
            status="active",
        ),
        WebSettingsProcessSchemaItem(
            key="ola",
            label="OLA",
            meaning="OLA задаёт внутренние сроки между группами",
            source="queue.ola_targets",
            ui_surface="/app/settings",
            status="active",
        ),
        WebSettingsProcessSchemaItem(
            key="support_line",
            label="support_line",
            meaning="Линия поддержки отражает глубину компетенции",
            source="queue role / future support line catalog",
            ui_surface="/app/settings",
            status="planned",
        ),
        WebSettingsProcessSchemaItem(
            key="status_next_action_owner",
            label="status / next_action_owner",
            meaning="Статус показывает этап, next_action_owner показывает чей ход",
            source="ticket status registry",
            ui_surface="/app/settings",
            status="active",
        ),
        WebSettingsProcessSchemaItem(
            key="observer",
            label="ticket observer summary / trace detail",
            meaning="Observer показывает трассу обработки тикета и детали событий",
            source="observer traces",
            ui_surface="/app/admin/observer",
            status="active",
        ),
    ]


def _build_support_line_items() -> list[WebSettingsSupportLineItem]:
    return [
        WebSettingsSupportLineItem(
            code="L1",
            label="L1",
            competence_depth="Первичная диагностика, уточнение фактов, базовое восстановление",
            routing_role="triage",
            status="planned",
        ),
        WebSettingsSupportLineItem(
            code="L2",
            label="L2",
            competence_depth="Профильная диагностика и выполнение работ в очереди",
            routing_role="specialist",
            status="planned",
        ),
        WebSettingsSupportLineItem(
            code="L3",
            label="L3",
            competence_depth="Глубокая экспертиза, изменения, нестандартные аварии",
            routing_role="engineering",
            status="planned",
        ),
    ]


def _build_priority_model_payload() -> WebSettingsPriorityModelPayload:
    return WebSettingsPriorityModelPayload(
        direct_user_priority_choice=False,
        impact_levels=["minimal", "low", "medium", "high"],
        urgency_levels=["minimal", "low", "medium", "high"],
        importance_sources=[
            "service_criticality",
            "deadline",
            "security",
            "public_service",
            "reporting_period",
        ],
        modifiers=[
            "critical_service",
            "deadline_today",
            "deadline_tomorrow",
            "reporting_period",
            "public_service",
            "citizen_reception",
            "confirmed_outage",
            "similar_tickets",
            "security",
        ],
    )


def _status_stage(status: str) -> str:
    if status in {"new", "queued", "assigned"}:
        return "intake"
    if status in {"in_progress", "scheduled"}:
        return "work"
    if status.startswith("waiting_on_"):
        return "waiting"
    if status == "resolved":
        return "review"
    if status in {"closed", "canceled"}:
        return "terminal"
    return "work"


def _build_ticket_settings_payload() -> WebSettingsTicketSettingsPayload:
    requester_map: dict[str, list[str]] = {}
    owner_map: dict[str, list[str]] = {}
    status_items: list[WebSettingsTicketStatusItem] = []

    for status in CANONICAL_STATUSES:
        requester_status = requester_status_for_internal(status)
        owner = next_action_owner_for_status(status)
        requester_map.setdefault(requester_status, []).append(status)
        owner_map.setdefault(owner, []).append(status)
        status_items.append(
            WebSettingsTicketStatusItem(
                value=status,
                label=STATUS_LABELS_RU.get(status, status),
                requester_status=requester_status,
                requester_label=REQUESTER_STATUS_LABELS_RU.get(requester_status, requester_status),
                next_action_owner=owner,
                stage=_status_stage(status),
                waits=status.startswith("waiting_on_"),
                terminal=status in {"resolved", "closed", "canceled"},
            )
        )

    root_cause_priorities = [
        item.strip()
        for item in TICKET_REQUIRE_ROOT_CAUSE_PRIORITIES.split(",")
        if item.strip()
    ]

    return WebSettingsTicketSettingsPayload(
        internal_statuses=status_items,
        requester_statuses=[
            WebSettingsRequesterStatusItem(
                value=value,
                label=label,
                internal_statuses=requester_map.get(value, []),
            )
            for value, label in REQUESTER_STATUS_LABELS_RU.items()
        ],
        next_action_owners=[
            WebSettingsNextActionOwnerItem(
                value=value,
                label=label,
                internal_statuses=owner_map.get(value, []),
            )
            for value, label in NEXT_ACTION_OWNER_LABELS.items()
        ],
        workflow_profiles=[
            WebSettingsWorkflowProfileItem(**profile.to_dict())
            for profile in list_workflow_profiles()
        ],
        process_schema=_build_process_schema_items(),
        support_lines=_build_support_line_items(),
        priority_model=_build_priority_model_payload(),
        governance=WebSettingsTicketGovernancePayload(
            fsm_mode=TICKET_FSM_MODE,
            legacy_role_fields=TICKET_LEGACY_ROLE_FIELDS,
            auto_close_hours=TICKET_AUTO_CLOSE_HOURS,
            resolution_validation_mode=TICKET_RESOLUTION_VALIDATION_MODE,
            require_root_cause_priorities=root_cause_priorities,
            evidence_gate_enabled=True,
            passport_enabled=True,
            requester_confirmation_required=True,
        ),
        operational_flags=WebSettingsTicketOperationalFlags(
            admin_config_api_enabled=TICKET_ADMIN_CONFIG_API_ENABLED,
            admin_config_write_enabled=TICKET_ADMIN_CONFIG_WRITE_ENABLED,
            auditor_role_enabled=TICKET_AUDITOR_ROLE_ENABLED,
            sla_calendar_enabled=TICKET_SLA_CALENDAR_ENABLED,
            ola_enabled=TICKET_OLA_ENABLED,
            retention_enabled=TICKET_RETENTION_ENABLED,
            retention_dry_run=TICKET_RETENTION_DRY_RUN,
            events_hot_retention_days=TICKET_EVENTS_HOT_RETENTION_DAYS,
            admin_audit_hot_retention_days=TICKET_ADMIN_AUDIT_HOT_RETENTION_DAYS,
            take_queue_mode=TICKET_TAKE_QUEUE_MODE,
            take_queue_common_code=TICKET_TAKE_QUEUE_COMMON_CODE,
            take_queue_test_code=TICKET_TAKE_QUEUE_TEST_CODE,
        ),
    )


def _build_routing_builder_payload(pack: dict | None = None) -> WebSettingsRoutingBuilderPayload:
    catalog = build_routing_builder_catalog(pack or validate_form_pack_schema(build_default_ticket_form_pack()))
    return WebSettingsRoutingBuilderPayload(
        operators=[
            WebSettingsRoutingBuilderOperatorItem(
                value=str(item.get("value") or ""),
                label=str(item.get("label") or ""),
            )
            for item in catalog.get("operators", [])
            if isinstance(item, dict)
        ],
        fields=[
            WebSettingsRoutingBuilderFieldItem(
                field=str(item.get("field") or ""),
                label=str(item.get("label") or item.get("field") or ""),
                source=str(item.get("source") or "ticket"),
                form_key=str(item.get("form_key") or "").strip() or None,
                form_title=str(item.get("form_title") or "").strip() or None,
                field_type=str(item.get("field_type") or "").strip() or None,
            )
            for item in catalog.get("fields", [])
            if isinstance(item, dict) and str(item.get("field") or "").strip()
        ],
        forms=[
            WebSettingsRoutingBuilderFormItem(
                key=str(item.get("key") or ""),
                request_kind=str(item.get("request_kind") or item.get("key") or ""),
                title=str(item.get("title") or item.get("key") or ""),
                fields=[
                    WebSettingsRoutingBuilderFormFieldItem(
                        key=str(field.get("key") or ""),
                        label=str(field.get("label") or field.get("key") or ""),
                        field=str(field.get("field") or ""),
                        type=str(field.get("type") or "text"),
                    )
                    for field in item.get("fields", [])
                    if isinstance(field, dict) and str(field.get("field") or "").strip()
                ],
            )
            for item in catalog.get("forms", [])
            if isinstance(item, dict) and str(item.get("key") or "").strip()
        ],
    )


def _empty_settings_payload(*, actor_role: str) -> WebSettingsPayload:
    can_manage_queues = can_role(actor_role, "settings.manage_queues")
    can_manage_routing = can_role(actor_role, "settings.manage_routing")
    return WebSettingsPayload(
        capabilities=WebSettingsCapabilities(
            can_write=can_manage_queues or can_manage_routing,
            actor_role=actor_role,
            can_manage_queues=can_manage_queues,
            can_manage_routing=can_manage_routing,
            manage_queues_denial_reason=None if can_manage_queues else "Недостаточно прав: settings.manage_queues",
            manage_routing_denial_reason=None if can_manage_routing else "Недостаточно прав: settings.manage_routing",
        ),
        overview=WebSettingsOverview(
            queues_count=0,
            active_queues_count=0,
            routing_rules_count=0,
            active_routing_rules_count=0,
            sla_policies_count=0,
            calendars_count=0,
            resolution_codes_count=0,
            audit_records_count=0,
        ),
        routing_builder=_build_routing_builder_payload(),
        ticket_settings=_build_ticket_settings_payload(),
        queues=[],
        routing_rules=[],
        sla_policies=[],
        calendars=[],
        resolution_codes=[],
        audit=[],
    )


@require_auth("admin", "support", "auditor")
async def handle_web_settings_payload(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    actor_role = str(auth_context.actor_role or "")
    if not TICKET_ADMIN_CONFIG_API_ENABLED:
        payload = _empty_settings_payload(actor_role=actor_role)
        return json_model_response(SuccessResponse[WebSettingsPayload](data=payload))

    try:
        async with get_session() as session:
            can_manage_queues = await can(session, auth_context, "settings.manage_queues")
            can_manage_routing = await can(session, auth_context, "settings.manage_routing")
            repo = TicketAdminConfigRepo(session)
            audit_repo = TicketAdminAuditRepo(session)
            form_pack = await resolve_ticket_form_pack(
                TicketFormPacksRepo(session),
                pack_key=DEFAULT_TICKET_FORM_PACK_KEY,
            )

            queues = await repo.list_queues(include_inactive=True)
            queue_name_map = {queue.id: queue.name for queue in queues}
            routing_rules = await repo.list_routing_rules(include_disabled=True)
            sla_policies = await repo.list_sla_policies(include_inactive=True)
            calendars = await repo.list_calendars(include_inactive=True)
            calendars_map = {calendar.id: calendar.name for calendar in calendars}
            resolution_codes = await repo.list_resolution_codes(include_inactive=True)
            audit_records = await audit_repo.list_audit(limit=80, offset=0)

            queue_items: list[WebSettingsQueueItem] = []
            for queue in queues:
                members = await repo.list_queue_members(queue.id)
                ola_targets = await repo.list_ola_targets(queue.id)
                open_tickets_count = await repo.count_open_tickets_in_queue(queue.id)
                enabled_routing_rules_count = await repo.count_enabled_rules_targeting_queue(queue.id)
                queue_items.append(
                    WebSettingsQueueItem(
                        id=queue.id,
                        code=queue.code,
                        name=queue.name,
                        is_triage=queue.is_triage,
                        is_active=queue.is_active,
                        auto_assign_enabled=getattr(queue, "auto_assign_enabled", True),
                        open_tickets_count=open_tickets_count,
                        enabled_routing_rules_count=enabled_routing_rules_count,
                        members=[
                            WebSettingsQueueMemberItem(
                                actor_id=member.actor_id,
                                role_in_queue=member.role_in_queue,
                            )
                            for member in members
                        ],
                        ola_targets=[
                            WebSettingsOlaTargetItem(
                                priority=target.priority,
                                ack_min=target.ack_min,
                                processing_min=target.processing_min,
                            )
                            for target in sorted(ola_targets, key=lambda item: item.priority)
                        ],
                    )
                )

            policy_items: list[WebSettingsSlaPolicyItem] = []
            for policy in sla_policies:
                targets = await repo.get_sla_targets(policy.id)
                priority_matrix = await repo.get_priority_matrix(policy.id)
                open_tickets_count = await repo.count_open_tickets_with_policy(policy.id)
                policy_items.append(
                    WebSettingsSlaPolicyItem(
                        id=policy.id,
                        name=policy.name,
                        timezone=policy.timezone,
                        business_hours_json=policy.business_hours_json,
                        calendar_id=getattr(policy, "calendar_id", None),
                        calendar_name=calendars_map.get(getattr(policy, "calendar_id", None)),
                        is_default=policy.is_default,
                        is_active=getattr(policy, "is_active", True),
                        open_tickets_count=open_tickets_count,
                        targets=[
                            WebSettingsSlaTargetItem(
                                priority=target.priority,
                                first_response_min=target.first_response_min,
                                resolution_min=target.resolution_min,
                            )
                            for target in sorted(targets, key=lambda item: item.priority)
                        ],
                        priority_matrix=[
                            WebSettingsPriorityMatrixItem(
                                impact=row.impact,
                                urgency=row.urgency,
                                priority=row.priority,
                            )
                            for row in sorted(priority_matrix, key=lambda item: (item.impact, item.urgency))
                        ],
                    )
                )

            payload = WebSettingsPayload(
                capabilities=WebSettingsCapabilities(
                    can_write=can_manage_queues or can_manage_routing,
                    actor_role=actor_role,
                    can_manage_queues=can_manage_queues,
                    can_manage_routing=can_manage_routing,
                    manage_queues_denial_reason=(
                        None if can_manage_queues else "Недостаточно прав: settings.manage_queues"
                    ),
                    manage_routing_denial_reason=(
                        None if can_manage_routing else "Недостаточно прав: settings.manage_routing"
                    ),
                ),
                overview=WebSettingsOverview(
                    queues_count=len(queues),
                    active_queues_count=sum(1 for queue in queues if queue.is_active),
                    routing_rules_count=len(routing_rules),
                    active_routing_rules_count=sum(1 for rule in routing_rules if rule.enabled),
                    sla_policies_count=len(sla_policies),
                    calendars_count=len(calendars),
                    resolution_codes_count=len(resolution_codes),
                    audit_records_count=len(audit_records),
                ),
                routing_builder=_build_routing_builder_payload(form_pack),
                ticket_settings=_build_ticket_settings_payload(),
                queues=queue_items,
                routing_rules=[
                    WebSettingsRoutingRuleItem(
                        id=rule.id,
                        enabled=rule.enabled,
                        priority_order=rule.priority_order,
                        condition_json=rule.condition_json,
                        target_queue_id=rule.target_queue_id,
                        target_queue_name=queue_name_map.get(rule.target_queue_id),
                    )
                    for rule in routing_rules
                ],
                sla_policies=policy_items,
                calendars=[
                    WebSettingsCalendarItem(
                        id=calendar.id,
                        code=calendar.code,
                        name=calendar.name,
                        timezone=calendar.timezone,
                        weekly_hours_json=calendar.weekly_hours_json,
                        holidays_json=calendar.holidays_json,
                        is_active=calendar.is_active,
                        created_at=calendar.created_at.isoformat() if calendar.created_at else None,
                        updated_at=calendar.updated_at.isoformat() if calendar.updated_at else None,
                    )
                    for calendar in calendars
                ],
                resolution_codes=[
                    WebSettingsResolutionCodeItem(
                        code=item.code,
                        name=item.name,
                        is_active=item.is_active,
                        sort_order=item.sort_order,
                        usage_count=await repo.count_tickets_with_resolution_code(item.code),
                    )
                    for item in resolution_codes
                ],
                audit=[
                    WebSettingsAuditItem(
                        id=record.id,
                        entity_type=record.entity_type,
                        entity_id=record.entity_id,
                        action=record.action,
                        actor_id=record.actor_id,
                        actor_role=record.actor_role,
                        trace_id=record.trace_id,
                        created_at=record.created_at.isoformat() if record.created_at else None,
                    )
                    for record in audit_records
                ],
            )
            await session.commit()
    except Exception as exc:
        logger.warning(f"[web_settings] failed to build settings payload: {exc}")
        payload = _empty_settings_payload(actor_role=actor_role)

    return json_model_response(SuccessResponse[WebSettingsPayload](data=payload))
