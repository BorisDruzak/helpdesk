"""Health checks for request templates and helpdesk policies."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import uuid

from app.db.models import Ticket
from app.repos import TicketEventsRepo
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from tickets.approval_policy import _approval_mode, _resolve_approval_source
from tickets.diagnostic_policy import collect_diagnostic_policy_auto_run_triggers
from tickets.helpdesk_policy_runtime import apply_effective_registry_policies, resolve_effective_ticket_policy
from tickets.ola_service import _targets_from_ola_policy, get_ola_targets_for_queue
from tickets.priority_policy import compute_priority_from_policy
from tickets.routing_service import TicketRoutingService
from tickets.sla_service import TicketSlaService
from tickets.statuses import WAITING_STATUSES
from tickets.visibility_policy import apply_ticket_visibility_payload_async


POLICY_KINDS = (
    "routing",
    "sla",
    "ola",
    "approval",
    "closure",
    "visibility",
    "notification",
    "diagnostic",
    "reporting",
)

FORBIDDEN_PUBLIC_FIELDS = {
    "ticket_id",
    "requester_id",
    "requester_display_name",
    "full_name",
    "phone",
    "room",
    "building",
    "urgency",
    "importance",
    "urgency_reason",
    "importance_reason",
    "priority",
    "assignee_id",
    "queue_id",
    "custom_fields",
    "device_id",
    "asset_id",
    "external_ref",
    "trace_id",
    "operation_id",
}

SEVERITY_WEIGHT = {"critical": 40, "error": 25, "warning": 10, "info": 2}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issue(
    severity: str,
    kind: str,
    policy_kind: str,
    message: str,
    *,
    path: str | None = None,
    reference: str | None = None,
    suggested_fix: str | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "kind": kind,
        "policy_kind": policy_kind,
        "message": message,
        "path": path,
        "reference": reference,
        "suggested_fix": suggested_fix,
    }


def _latest_active_by_code(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not item.get("is_active", True):
            continue
        code = str(item.get("code") or "").strip()
        if code and code not in result:
            result[code] = item
    return result


def _policy_config(policy: dict[str, Any] | None) -> dict[str, Any]:
    config = (policy or {}).get("config")
    return deepcopy(config) if isinstance(config, dict) else {}


def _rules(config: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rules = config.get("rules") or config.get("routing_rules") or []
    return [rule for rule in raw_rules if isinstance(rule, dict)] if isinstance(raw_rules, list) else []


def _condition_fingerprint(rule: dict[str, Any]) -> str:
    condition = rule.get("when") or rule.get("conditions") or rule.get("condition") or {}
    return repr(condition)


def _is_catch_all(rule: dict[str, Any]) -> bool:
    condition = rule.get("when") or rule.get("conditions") or rule.get("condition")
    return condition in (None, {}, [], True, "always", "catch_all")


def _queue_ref_from_action(rule: dict[str, Any]) -> Any:
    action = rule.get("then") if isinstance(rule.get("then"), dict) else rule
    return action.get("queue_code") or action.get("queue_id") or action.get("queue")


def _template_policy_code(template: dict[str, Any], kind: str) -> str | None:
    direct = template.get(f"{kind}_policy_code")
    if direct:
        return str(direct).strip()
    config = template.get("config") if isinstance(template.get("config"), dict) else {}
    refs = config.get("policy_refs") if isinstance(config.get("policy_refs"), dict) else {}
    value = refs.get(kind)
    return str(value).strip() if value else None


def _policy_ref_code(template_context: dict[str, Any], kind: str) -> str | None:
    direct = template_context.get(f"{kind}_policy_code")
    if direct not in (None, ""):
        return str(direct).strip()
    refs = template_context.get("policy_refs") if isinstance(template_context.get("policy_refs"), dict) else {}
    ref = refs.get(kind)
    if isinstance(ref, dict):
        return str(ref.get("code") or ref.get("policy_code") or "").strip() or None
    return str(ref or "").strip() or None


def _policy_code(policy: dict[str, Any], template_context: dict[str, Any], kind: str) -> str | None:
    for key in ("code", "policy_code", f"{kind}_policy_code"):
        value = policy.get(key) if isinstance(policy, dict) else None
        if value not in (None, ""):
            return str(value).strip()
    return _policy_ref_code(template_context, kind)


def _suggested_playbooks_from_policy(policy: dict[str, Any]) -> list[str]:
    raw_items: list[Any] = []
    value = policy.get("suggested_playbooks") if isinstance(policy, dict) else None
    if isinstance(value, list):
        raw_items.extend(value)
    for key in ("suggested_playbook_id", "suggested_playbook"):
        if isinstance(policy, dict) and policy.get(key):
            raw_items.append(policy.get(key))
    result: list[str] = []
    for item in raw_items:
        playbook = item.get("playbook_key") or item.get("key") or item.get("id") if isinstance(item, dict) else item
        playbook_key = str(playbook or "").strip()
        if playbook_key and playbook_key not in result:
            result.append(playbook_key)
    return result


class PolicyHealthService:
    def __init__(self, session: Any | None = None):
        self.session = session

    async def list_health(self) -> dict[str, Any]:
        if self.session is None:
            raise RuntimeError("session is required")
        repo = HelpdeskPolicyRepo(self.session)
        admin_repo = TicketAdminConfigRepo(self.session)
        templates = await repo.list_request_templates(include_inactive=False)
        policies = await repo.list_policies(include_inactive=False)
        queues = await admin_repo.list_queues(include_inactive=False)
        return self.evaluate(templates=templates, policies=policies, queues=queues)

    async def get_health(self, template_code: str) -> dict[str, Any] | None:
        dashboard = await self.list_health()
        for item in dashboard["templates"]:
            if item["template_code"] == template_code:
                return item
        return None

    async def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.session is None:
            raise RuntimeError("session is required")
        template_code = str(payload.get("template_code") or "").strip()
        repo = HelpdeskPolicyRepo(self.session)
        effective = await repo.resolve_effective_request_template(
            template_code=template_code,
            raise_if_missing=False,
        )
        if not effective:
            raise ValueError("unknown template_code")

        template = effective.get("request_template") or {}
        request_form_data = payload.get("request_form_data")
        if not isinstance(request_form_data, dict):
            request_form_data = payload.get("custom_fields") if isinstance(payload.get("custom_fields"), dict) else {}
        request_form_data = deepcopy(request_form_data)
        device_metadata = payload.get("device_metadata") if isinstance(payload.get("device_metadata"), dict) else {}
        requester_context = payload.get("requester_context") if isinstance(payload.get("requester_context"), dict) else {}

        template_context: dict[str, Any] = {
            "key": template_code,
            "template_code": template_code,
            "request_template_version": template.get("version"),
            "ticket_type": template.get("ticket_type"),
            "category_id": template.get("category_id"),
            "service_id": template.get("service_id"),
            "subcategory_id": template.get("subcategory_id"),
        }
        for kind in POLICY_KINDS:
            code = template.get(f"{kind}_policy_code")
            if code:
                template_context[f"{kind}_policy_code"] = code
        if template.get("priority_policy_code"):
            template_context["priority_policy_code"] = template.get("priority_policy_code")
        if template.get("sla_policy_id") is not None:
            template_context["sla_policy_id"] = template.get("sla_policy_id")

        validated_submission = await apply_effective_registry_policies(
            self.session,
            {
                "form_key": template_code,
                "ticket_type": template.get("ticket_type"),
                "template_context": template_context,
            },
        )
        template_context = validated_submission.get("template_context") or template_context
        if not isinstance(template_context, dict):
            template_context = {}

        priority_policy = template_context.get("priority_policy")
        priority_decision = compute_priority_from_policy(
            priority_policy=priority_policy if isinstance(priority_policy, dict) else {},
            submitted_values=request_form_data,
            fallback={
                "impact": payload.get("impact"),
                "urgency": payload.get("urgency"),
                "importance": payload.get("importance"),
                "actor_role": "admin",
            },
        )
        priority_class = str(priority_decision.get("priority_class") or "P3")
        legacy_priority = str(priority_decision.get("legacy_priority") or "P4")

        custom_fields = {
            "request_form_data": request_form_data,
            "requester_profile": deepcopy(requester_context.get("requester_profile") or {}),
            "request_template": deepcopy(template_context),
            "priority_class": priority_class,
        }
        diagnostic_consent = payload.get("diagnostic_consent")
        if isinstance(diagnostic_consent, dict):
            custom_fields["diagnostic_consent"] = deepcopy(diagnostic_consent)

        now = datetime.now(timezone.utc)
        ticket = Ticket(
            ticket_id=f"dry-run-{uuid.uuid4()}",
            ticket_code="DRY-RUN",
            device_id=str(device_metadata.get("device_id") or requester_context.get("device_id") or "dry-run-device"),
            title=str(payload.get("title") or template.get("public_title") or template_code),
            description=str(payload.get("description") or ""),
            status="new",
            priority=legacy_priority,
            requester_id=str(requester_context.get("requester_id") or "dry-run:requester"),
            ticket_type=str(template.get("ticket_type") or "service_request"),
            category_id=template.get("category_id"),
            service_id=template.get("service_id"),
            subcategory_id=template.get("subcategory_id"),
            custom_fields=custom_fields,
            created_at=now,
            updated_at=now,
        )
        ticket.sla_policy_id = template_context.get("sla_policy_id")

        ticket_repo = TicketEventsRepo(self.session)
        admin_repo = TicketAdminConfigRepo(self.session)
        routing_service = TicketRoutingService(self.session, ticket_repo)
        routing_decision = await routing_service.resolve_routing_decision(ticket, device_metadata=device_metadata)
        routing_payload: dict[str, Any] = {"queue_id": None, "queue_code": None, "source": None, "matched_rule": None}
        if isinstance(routing_decision, dict):
            queue_id = routing_decision.get("queue_id")
            ticket.queue_id = queue_id
            ticket.status = "queued" if queue_id is not None else "new"
            queue = await admin_repo.get_queue(queue_id) if queue_id is not None else None
            actions = routing_decision.get("actions") if isinstance(routing_decision.get("actions"), dict) else {}
            routing_payload = {
                "queue_id": queue_id,
                "queue_code": getattr(queue, "code", None),
                "source": routing_decision.get("source"),
                "matched_rule": routing_decision.get("matched_rule"),
                "assignee_strategy": actions.get("assignee_strategy"),
            }

        sla_payload: dict[str, Any] = {"policy_code": _policy_ref_code(template_context, "sla")}
        sla_service = TicketSlaService(self.session, ticket_repo)
        sla_policy, sla_targets = await sla_service._get_policy_and_targets(ticket)
        sla_target = sla_service._target_for_priority(sla_targets, priority_class)
        if sla_policy and sla_target:
            calendar = await sla_service._calendar_for_policy(sla_policy)
            sla_payload = {
                "policy_code": _policy_code(sla_policy if isinstance(sla_policy, dict) else {}, template_context, "sla"),
                "first_response_min": sla_target.first_response_min,
                "resolution_min": sla_target.resolution_min,
                "first_response_due_preview": sla_service._due_at(now, sla_target.first_response_min, calendar).isoformat(),
                "resolution_due_preview": sla_service._due_at(now, sla_target.resolution_min, calendar).isoformat(),
            }

        ola_policy = await resolve_effective_ticket_policy(self.session, ticket, "ola")
        ola_targets = _targets_from_ola_policy(ola_policy, priority_class)
        if ola_targets is None and ticket.queue_id is not None:
            ola_targets = await get_ola_targets_for_queue(self.session, ticket.queue_id, priority_class)
        ola_payload: dict[str, Any] = {"policy_code": _policy_code(ola_policy, template_context, "ola")}
        if ola_targets:
            ack_min, processing_min = ola_targets
            ola_payload.update(
                {
                    "ack_min": ack_min,
                    "processing_min": processing_min,
                    "ack_due_preview": sla_service._due_at(now, ack_min, None).isoformat(),
                    "processing_due_preview": sla_service._due_at(now, processing_min, None).isoformat(),
                }
            )

        approval_policy = await resolve_effective_ticket_policy(self.session, ticket, "approval")
        approval_source = approval_policy.get("approver_source") or approval_policy.get("approvers") or {}
        source_type, approvers = await _resolve_approval_source(self.session, ticket, approval_source)
        approval_payload = {
            "policy_code": _policy_code(approval_policy, template_context, "approval"),
            "required": bool(approval_policy.get("required")),
            "mode": _approval_mode(approval_policy) if approval_policy else "any_one",
            "approver_source": source_type or None,
            "approvers": approvers,
        }

        closure_policy = await resolve_effective_ticket_policy(self.session, ticket, "closure")
        before_resolved = closure_policy.get("before_resolved") if isinstance(closure_policy.get("before_resolved"), dict) else {}
        closure_payload = {
            "policy_code": _policy_code(closure_policy, template_context, "closure"),
            "requires_public_summary": bool(
                before_resolved.get("require_public_summary") or closure_policy.get("require_public_summary")
            ),
            "requires_resolution_code": bool(
                before_resolved.get("require_resolution_code") or closure_policy.get("require_resolution_code")
            ),
        }

        visibility_payload = await apply_ticket_visibility_payload_async(
            self.session,
            ticket,
            {"status": ticket.status, "root_cause": "dry-run"},
            visibility="public",
        )

        diagnostic_policy = await resolve_effective_ticket_policy(self.session, ticket, "diagnostic")
        triggers, diagnostic_skips = collect_diagnostic_policy_auto_run_triggers(
            ticket=ticket,
            custom_fields=custom_fields,
            state=None,
        )

        return {
            "template_code": template_code,
            "routing": routing_payload,
            "priority": {
                "policy_code": _policy_ref_code(template_context, "priority"),
                "priority_class": priority_class,
                "legacy_priority": legacy_priority,
                "priority_source": priority_decision.get("priority_source"),
            },
            "sla": sla_payload,
            "ola": ola_payload,
            "approval": approval_payload,
            "closure": closure_payload,
            "visibility": {
                "policy_code": _policy_ref_code(template_context, "visibility"),
                "public_status": visibility_payload.get("public_status"),
                "public_status_label": visibility_payload.get("public_status_label"),
                "source": (visibility_payload.get("visibility") or {}).get("source"),
            },
            "diagnostic": {
                "policy_code": _policy_code(diagnostic_policy, template_context, "diagnostic"),
                "suggested_playbooks": _suggested_playbooks_from_policy(diagnostic_policy),
                "auto_run_triggers": triggers,
                "skipped_auto_run": diagnostic_skips,
            },
            "warnings": [skip.get("reason") for skip in diagnostic_skips if skip.get("reason")],
            "would_create_ticket": False,
        }

    def evaluate(
        self,
        *,
        templates: list[dict[str, Any]],
        policies: dict[str, list[dict[str, Any]]],
        queues: list[Any],
    ) -> dict[str, Any]:
        policy_index = {kind: _latest_active_by_code(policies.get(kind, [])) for kind in POLICY_KINDS}
        queue_codes = {str(getattr(queue, "code", None) or queue.get("code")) for queue in queues}
        queue_ids = {getattr(queue, "id", None) if not isinstance(queue, dict) else queue.get("id") for queue in queues}
        items = [self._evaluate_template(template, policy_index, queue_codes, queue_ids) for template in templates]
        return {
            "status": "ok",
            "templates": items,
            "summary": {
                "total": len(items),
                "ok": sum(1 for item in items if item["health_status"] == "ok"),
                "warning": sum(1 for item in items if item["health_status"] == "warning"),
                "error": sum(1 for item in items if item["health_status"] == "error"),
            },
        }

    def _evaluate_template(
        self,
        template: dict[str, Any],
        policy_index: dict[str, dict[str, dict[str, Any]]],
        queue_codes: set[str],
        queue_ids: set[Any],
    ) -> dict[str, Any]:
        checks: dict[str, dict[str, Any]] = {}
        issues: list[dict[str, Any]] = []
        for kind in POLICY_KINDS:
            checks[kind] = self._check_policy_reference(template, kind, policy_index, issues)

        self._check_routing(template, checks, issues, policy_index["routing"], queue_codes, queue_ids)
        self._check_sla(template, checks, issues, policy_index["sla"])
        self._check_approval(checks, issues, policy_index["approval"])
        self._check_visibility(checks, issues, policy_index["visibility"])
        self._check_ola(checks, issues, policy_index["ola"])

        severity_counts = {severity: 0 for severity in ("critical", "error", "warning", "info")}
        for issue in issues:
            severity_counts[issue["severity"]] += 1
        conflict_count = sum(1 for issue in issues if issue["kind"] == "conflict")
        if severity_counts["critical"] or severity_counts["error"]:
            health_status = "error"
        elif severity_counts["warning"]:
            health_status = "warning"
        else:
            health_status = "ok"
        score = max(0, 100 - sum(SEVERITY_WEIGHT[issue["severity"]] for issue in issues))
        return {
            "template_id": template.get("template_code"),
            "template_code": template.get("template_code"),
            "template_name": template.get("internal_name") or template.get("public_title"),
            "version": template.get("version"),
            "status": "published" if template.get("published_at") else "draft",
            "owner": template.get("updated_by") or template.get("created_by"),
            "health_status": health_status,
            "health_score": score,
            "conflict_count": conflict_count,
            "issue_count": len(issues),
            "issues_by_severity": severity_counts,
            "checks": checks,
            "issues": issues,
            "last_checked_at": _now_iso(),
        }

    def _check_policy_reference(
        self,
        template: dict[str, Any],
        kind: str,
        policy_index: dict[str, dict[str, dict[str, Any]]],
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        code = _template_policy_code(template, kind)
        if not code:
            return {"status": "missing", "reference": None}
        policy = policy_index[kind].get(code)
        if policy is None:
            issues.append(_issue("error", "invalid_reference", kind, f"{kind} policy does not exist", reference=code))
            return {"status": "error", "reference": code}
        return {"status": "ok", "reference": code, "policy_title": policy.get("title")}

    def _check_routing(
        self,
        template: dict[str, Any],
        checks: dict[str, dict[str, Any]],
        issues: list[dict[str, Any]],
        routing_policies: dict[str, dict[str, Any]],
        queue_codes: set[str],
        queue_ids: set[Any],
    ) -> None:
        config = template.get("config") if isinstance(template.get("config"), dict) else {}
        code = checks["routing"].get("reference")
        policy_config = _policy_config(routing_policies.get(code)) if code else {}
        routing_config = policy_config or config.get("routing_policy") or config.get("routing") or {}
        rules = _rules(routing_config) if isinstance(routing_config, dict) else []
        default_queue = config.get("default_queue_code") or config.get("default_queue_id") or routing_config.get("default_queue")
        checks["routing"].update({"rule_count": len(rules), "resolved_queue": default_queue, "assignee_strategy": routing_config.get("assignee_strategy") if isinstance(routing_config, dict) else None})
        if not code and not rules and not default_queue:
            issues.append(_issue("warning", "missing_policy", "routing", "routing policy or fallback queue is missing", suggested_fix="Attach routing policy or set explicit fallback queue."))
        if default_queue and default_queue not in queue_codes and default_queue not in queue_ids:
            issues.append(_issue("error", "invalid_reference", "routing", "fallback queue does not exist", path="routing.default_queue", reference=str(default_queue)))
        seen: dict[str, Any] = {}
        catch_all_seen = False
        for index, rule in enumerate(rules):
            queue_ref = _queue_ref_from_action(rule)
            if queue_ref and queue_ref not in queue_codes and queue_ref not in queue_ids:
                issues.append(_issue("error", "invalid_reference", "routing", "routing rule points to inactive or missing queue", path=f"routing.rules[{index}]", reference=str(queue_ref)))
            fingerprint = _condition_fingerprint(rule)
            action = repr(rule.get("then") or rule.get("action") or {})
            if fingerprint in seen and seen[fingerprint] != action:
                issues.append(_issue("error", "conflict", "routing", "duplicate routing condition has different actions", path=f"routing.rules[{index}]"))
            seen[fingerprint] = action
            if catch_all_seen and not _is_catch_all(rule):
                issues.append(_issue("warning", "conflict", "routing", "catch-all routing rule shadows a later specific rule", path=f"routing.rules[{index}]"))
            if _is_catch_all(rule):
                catch_all_seen = True
        if rules:
            checks["routing"]["matched_rule"] = "rules[0]"

    def _check_sla(
        self,
        template: dict[str, Any],
        checks: dict[str, dict[str, Any]],
        issues: list[dict[str, Any]],
        sla_policies: dict[str, dict[str, Any]],
    ) -> None:
        config = template.get("config") if isinstance(template.get("config"), dict) else {}
        explicit_no_sla = bool(config.get("no_sla") or config.get("sla_not_required"))
        if checks["sla"]["status"] == "missing" and not explicit_no_sla:
            issues.append(_issue("warning", "missing_policy", "sla", "SLA policy is missing and no explicit no_sla marker is set"))
        policy = sla_policies.get(checks["sla"].get("reference"))
        policy_config = _policy_config(policy)
        pause_statuses = set(policy_config.get("pause_statuses") or [])
        invalid_pause = sorted(pause_statuses - set(WAITING_STATUSES))
        if invalid_pause:
            issues.append(_issue("error", "schema_error", "sla", "SLA pause statuses are not canonical waiting statuses", path="sla.pause_statuses", reference=", ".join(invalid_pause)))

    def _check_ola(self, checks: dict[str, dict[str, Any]], issues: list[dict[str, Any]], ola_policies: dict[str, dict[str, Any]]) -> None:
        policy = ola_policies.get(checks["ola"].get("reference"))
        pause_statuses = set(_policy_config(policy).get("pause_statuses") or [])
        invalid_pause = sorted(pause_statuses - set(WAITING_STATUSES))
        if invalid_pause:
            issues.append(_issue("error", "schema_error", "ola", "OLA pause statuses are not canonical waiting statuses", path="ola.pause_statuses", reference=", ".join(invalid_pause)))

    def _check_approval(self, checks: dict[str, dict[str, Any]], issues: list[dict[str, Any]], approval_policies: dict[str, dict[str, Any]]) -> None:
        policy = approval_policies.get(checks["approval"].get("reference"))
        config = _policy_config(policy)
        if config.get("required") and not (config.get("approvers") or config.get("roles") or config.get("groups")):
            issues.append(_issue("error", "invalid_reference", "approval", "approval is required but approvers are not resolvable", path="approval.approvers"))

    def _check_visibility(self, checks: dict[str, dict[str, Any]], issues: list[dict[str, Any]], visibility_policies: dict[str, dict[str, Any]]) -> None:
        policy = visibility_policies.get(checks["visibility"].get("reference"))
        config = _policy_config(policy)
        public_fields = set(config.get("public_fields") or config.get("show_to_requester") or config.get("public_queue_fields") or [])
        leaked = sorted(public_fields & FORBIDDEN_PUBLIC_FIELDS)
        if leaked:
            issues.append(_issue("critical", "privacy_risk", "visibility", "visibility policy exposes forbidden public fields", path="visibility.public_fields", reference=", ".join(leaked), suggested_fix="Remove forbidden fields from requester/public projections."))
