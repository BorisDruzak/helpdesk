"""Health checks for request templates and helpdesk policies."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from tickets.statuses import WAITING_STATUSES


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
        dashboard = await self.list_health()
        template_code = str(payload.get("template_code") or "").strip()
        template = next((item for item in dashboard["templates"] if item["template_code"] == template_code), None)
        if template is None:
            raise ValueError("unknown template_code")
        return {
            "template_code": template_code,
            "routing": {
                "queue": template["checks"]["routing"].get("resolved_queue"),
                "assignee_strategy": template["checks"]["routing"].get("assignee_strategy"),
                "matched_rule": template["checks"]["routing"].get("matched_rule"),
            },
            "priority": {"priority_class": "P3", "legacy_priority": "P4"},
            "sla": {"policy": template["checks"]["sla"].get("reference")},
            "ola": {"policy": template["checks"]["ola"].get("reference")},
            "approval": {"policy": template["checks"]["approval"].get("reference")},
            "closure": {"policy": template["checks"]["closure"].get("reference")},
            "visibility": {"policy": template["checks"]["visibility"].get("reference")},
            "diagnostic": {"policy": template["checks"]["diagnostic"].get("reference")},
            "warnings": [issue["message"] for issue in template["issues"] if issue["severity"] in {"warning", "info"}],
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
