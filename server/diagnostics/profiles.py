from __future__ import annotations

from typing import Any


DIAGNOSTIC_PROFILES: list[dict[str, Any]] = [
    {
        "id": "website_unavailable",
        "version": "1.0",
        "title": "Website unavailable",
        "applies_to": {"request_template_key": "website_unavailable", "ticket_type": "incident"},
        "recommended_capabilities": [
            "endpoint.dns.resolve",
            "endpoint.http.request",
            "server.http.request",
            "zabbix.problems.lookup",
            "observer.ticket.summary",
        ],
        "recommended_playbooks": ["diagnose.website"],
        "required_evidence_kinds": ["network.dns", "network.http"],
        "optional_evidence_kinds": ["logs.bundle", "remote_assist.session", "observer.summary"],
        "finding_rules": ["server_side_problem", "endpoint_network_or_proxy_problem", "monitoring_confirmed_service_problem"],
    },
    {
        "id": "generic",
        "version": "1.0",
        "title": "Generic diagnostics",
        "applies_to": {},
        "recommended_capabilities": ["diag.logs.collect", "observer.ticket.summary", "remote_assist.session.summary"],
        "recommended_playbooks": [],
        "required_evidence_kinds": [],
        "optional_evidence_kinds": ["logs.bundle", "remote_assist.session", "observer.summary"],
        "finding_rules": ["logs_available_for_l2"],
    },
]


def list_profiles() -> list[dict[str, Any]]:
    return [dict(item) for item in DIAGNOSTIC_PROFILES]


def get_profile(profile_id: str) -> dict[str, Any] | None:
    for profile in DIAGNOSTIC_PROFILES:
        if profile["id"] == profile_id:
            return dict(profile)
    return None


def resolve_ticket_profile(ticket: Any) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    request_template = custom_fields.get("request_template") if isinstance(custom_fields, dict) else None
    profile_id = None
    if isinstance(request_template, dict):
        profile_id = request_template.get("diagnostic_profile_id") or request_template.get("key")
    if profile_id:
        profile = get_profile(str(profile_id))
        if profile is not None:
            return profile
    return get_profile("generic") or DIAGNOSTIC_PROFILES[-1]
