from __future__ import annotations

from aiohttp import web
from loguru import logger

from app.db import get_session
from app.repos.ticket_admin_audit_repo import TicketAdminAuditRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from auth.middleware import require_auth
from config import TICKET_ADMIN_CONFIG_API_ENABLED
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.settings import (
    WebSettingsAuditItem,
    WebSettingsCalendarItem,
    WebSettingsCapabilities,
    WebSettingsOlaTargetItem,
    WebSettingsOverview,
    WebSettingsPayload,
    WebSettingsPriorityMatrixItem,
    WebSettingsQueueItem,
    WebSettingsQueueMemberItem,
    WebSettingsResolutionCodeItem,
    WebSettingsRoutingRuleItem,
    WebSettingsSlaPolicyItem,
    WebSettingsSlaTargetItem,
)


def _empty_settings_payload(*, actor_role: str) -> WebSettingsPayload:
    return WebSettingsPayload(
        capabilities=WebSettingsCapabilities(
            can_write=actor_role == "admin",
            actor_role=actor_role,
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
            repo = TicketAdminConfigRepo(session)
            audit_repo = TicketAdminAuditRepo(session)

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
                    can_write=actor_role == "admin",
                    actor_role=actor_role,
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
