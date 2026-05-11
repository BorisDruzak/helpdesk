import pytest

from tickets.form_business_validation import (
    FormBusinessValidationContext,
    validate_form_pack_business,
)


def _pack(form: dict) -> dict:
    return {
        "pack_key": "request_forms",
        "title": "Request catalog",
        "forms": [form],
    }


def _base_form(**overrides) -> dict:
    form = {
        "key": "website_unavailable",
        "request_kind": "website_unavailable",
        "title": "Website unavailable",
        "fields": [
            {
                "key": "impact_scope",
                "label": "Who is affected?",
                "type": "select",
                "required": True,
                "help_text": "Select impact scope.",
                "options": [{"value": "single_user", "label": "Only me"}],
            }
        ],
        "field_roles": {"impact_scope": ["priority_impact"]},
    }
    form.update(overrides)
    return form


@pytest.mark.no_db
def test_business_validation_blocks_missing_visible_when_field():
    form = _base_form(
        fields=[
            {
                "key": "room",
                "label": "Room",
                "type": "text",
                "required": True,
                "help_text": "Enter room.",
                "visible_when": {"field": "missing_switch", "equals": "yes"},
            }
        ]
    )

    report = validate_form_pack_business(_pack(form))

    assert any(issue["code"] == "VISIBLE_WHEN_FIELD_NOT_FOUND" for issue in report.errors)
    assert report.summary["can_publish"] is False


@pytest.mark.no_db
def test_business_validation_reports_missing_queue_playbook_approval_and_closure_evidence():
    form = _base_form(
        default_queue_id=404,
        playbook_triggers=[
            {
                "event": "ticket_created",
                "playbook_key": "diagnose.website",
                "module_kind": "diagnostic",
                "enabled": True,
            }
        ],
        approval_policy={"required": True},
        closure_policy={"evidence": {"required": True}},
    )
    context = FormBusinessValidationContext(
        queue_ids={17},
        playbook_keys={"diagnose.printer"},
    )

    report = validate_form_pack_business(_pack(form), context=context)
    codes = {issue["code"] for issue in report.errors}

    assert "ROUTING_QUEUE_NOT_FOUND" in codes
    assert "DIAGNOSTIC_PLAYBOOK_NOT_FOUND" in codes
    assert "APPROVAL_APPROVER_SOURCE_MISSING" in codes
    assert "CLOSURE_EVIDENCE_FIELD_MISSING" in codes
    assert report.summary == {"errors_count": 4, "warnings_count": 2, "can_publish": False}


@pytest.mark.no_db
def test_business_validation_warns_about_publish_quality_gaps():
    form = _base_form(
        title="",
        field_roles={},
        fields=[
            {
                "key": "room",
                "label": "Room",
                "type": "text",
                "required": True,
                "options": [],
            }
        ],
    )

    report = validate_form_pack_business(_pack(form))
    codes = {issue["code"] for issue in report.warnings}

    assert report.errors == []
    assert {
        "PRIORITY_FACT_FIELDS_MISSING",
        "REQUIRED_FIELD_HELP_TEXT_MISSING",
        "PUBLIC_TITLE_MISSING",
        "SLA_POLICY_MISSING",
    } <= codes
    assert report.summary["can_publish"] is True


@pytest.mark.no_db
def test_business_validation_blocks_duplicate_singleton_priority_roles():
    form = _base_form(
        fields=[
            {
                "key": "impact_scope",
                "label": "Who is affected?",
                "type": "select",
                "required": True,
                "help_text": "Select impact scope.",
                "options": [{"value": "single_user", "label": "Only me"}],
            },
            {
                "key": "impact_scope_alt",
                "label": "Who else is affected?",
                "type": "select",
                "required": False,
                "help_text": "Select additional impact scope.",
                "options": [{"value": "department", "label": "Department"}],
            },
        ],
        field_roles={
            "impact_scope": ["priority_impact"],
            "impact_scope_alt": ["priority_impact"],
        },
    )

    report = validate_form_pack_business(_pack(form))

    assert any(issue["code"] == "FIELD_ROLE_DUPLICATE_SINGLETON" for issue in report.errors)
    assert report.summary["can_publish"] is False


@pytest.mark.no_db
def test_business_validation_blocks_diagnostic_input_without_param_mapping_when_autorun_enabled():
    form = _base_form(
        fields=[
            {
                "key": "target_url",
                "label": "Website URL",
                "type": "url",
                "required": True,
                "help_text": "Enter URL.",
            }
        ],
        field_roles={"target_url": ["diagnostic_input"]},
        diagnostic_policy={
            "auto_run": {"enabled": True},
            "suggested_playbooks": ["diagnose.website"],
        },
    )

    report = validate_form_pack_business(_pack(form))

    assert any(issue["code"] == "DIAGNOSTIC_INPUT_MAPPING_MISSING" for issue in report.errors)
    assert report.summary["can_publish"] is False


@pytest.mark.no_db
def test_business_validation_allows_diagnostic_input_with_param_mapping():
    form = _base_form(
        fields=[
            {
                "key": "target_url",
                "label": "Website URL",
                "type": "url",
                "required": True,
                "help_text": "Enter URL.",
                "process_mapping": {
                    "roles": ["diagnostic_input"],
                    "diagnostic_param": "target_url",
                },
            }
        ],
        diagnostic_policy={
            "auto_run": {"enabled": True},
            "suggested_playbooks": ["diagnose.website"],
        },
    )

    report = validate_form_pack_business(_pack(form))

    assert not any(issue["code"] == "DIAGNOSTIC_INPUT_MAPPING_MISSING" for issue in report.errors)


@pytest.mark.no_db
def test_business_validation_blocks_incompatible_approval_subject_field():
    form = _base_form(
        fields=[
            {
                "key": "needs_approval",
                "label": "Needs approval",
                "type": "checkbox",
                "required": True,
                "help_text": "Confirm approval subject.",
            }
        ],
        field_roles={"needs_approval": ["approval_subject"]},
        approval_policy={
            "required": True,
            "approver_source": {"type": "form_field", "field": "needs_approval"},
        },
    )

    report = validate_form_pack_business(_pack(form))

    assert any(issue["code"] == "APPROVAL_SUBJECT_FIELD_INCOMPATIBLE" for issue in report.errors)
    assert report.summary["can_publish"] is False


@pytest.mark.no_db
def test_business_validation_allows_compatible_approval_subject_field():
    form = _base_form(
        fields=[
            {
                "key": "approver",
                "label": "Approver",
                "type": "user_picker",
                "required": True,
                "help_text": "Select approver.",
            }
        ],
        field_roles={"approver": ["approval_subject"]},
        approval_policy={
            "required": True,
            "approver_source": {"type": "form_field", "field": "approver"},
        },
    )

    report = validate_form_pack_business(_pack(form))

    assert not any(issue["code"] == "APPROVAL_SUBJECT_FIELD_INCOMPATIBLE" for issue in report.errors)


@pytest.mark.no_db
def test_business_validation_blocks_incompatible_closure_evidence_field():
    form = _base_form(
        fields=[
            {
                "key": "evidence_confirmed",
                "label": "Evidence confirmed",
                "type": "checkbox",
                "required": True,
                "help_text": "Confirm evidence.",
            }
        ],
        field_roles={"evidence_confirmed": ["closure_evidence"]},
        closure_policy={"evidence": {"required": True}},
    )

    report = validate_form_pack_business(_pack(form))

    assert any(issue["code"] == "CLOSURE_EVIDENCE_FIELD_INCOMPATIBLE" for issue in report.errors)
    assert report.summary["can_publish"] is False


@pytest.mark.no_db
def test_business_validation_blocks_unknown_policy_refs():
    form = _base_form(
        priority_policy_ref="incident_priority_v2",
        routing_policy_code="website_routing_v5",
    )
    context = FormBusinessValidationContext(
        policy_refs={
            "priority": {"incident_priority_v1"},
            "routing": {"website_routing_v4"},
        }
    )

    report = validate_form_pack_business(_pack(form), context=context)
    codes = {issue["code"] for issue in report.errors}

    assert codes == {"POLICY_REF_NOT_FOUND"}
    assert report.summary["errors_count"] == 2
    assert {issue["source"] for issue in report.errors} == {"policy_ref"}


@pytest.mark.no_db
def test_business_validation_blocks_unknown_policy_refs_dict_entries():
    form = _base_form(
        policy_refs={
            "priority": "incident_priority_v2",
            "routing": {"code": "website_routing_v5"},
        }
    )
    context = FormBusinessValidationContext(
        policy_refs={
            "priority": {"incident_priority_v1"},
            "routing": {"website_routing_v4"},
        }
    )

    report = validate_form_pack_business(_pack(form), context=context)

    assert [issue["path"] for issue in report.errors] == [
        "forms[0].policy_refs.priority",
        "forms[0].policy_refs.routing",
    ]
    assert {issue["source"] for issue in report.errors} == {"policy_ref"}


@pytest.mark.no_db
def test_business_validation_blocks_ola_required_queue_without_policy():
    form = _base_form(default_queue_id=17)
    context = FormBusinessValidationContext(queue_ola_queue_ids={17})

    report = validate_form_pack_business(_pack(form), context=context)

    assert any(issue["code"] == "OLA_POLICY_MISSING" for issue in report.errors)
    assert report.summary["can_publish"] is False


@pytest.mark.no_db
def test_business_validation_blocks_non_diagnostic_safe_playbook():
    form = _base_form(
        playbook_triggers=[
            {
                "event": "ticket_created",
                "playbook_key": "restart.service",
                "module_kind": "diagnostic",
                "enabled": True,
            }
        ],
    )
    context = FormBusinessValidationContext(
        playbook_keys={"restart.service"},
        diagnostic_playbook_keys={"diagnose.website"},
    )

    report = validate_form_pack_business(_pack(form), context=context)

    assert any(issue["code"] == "DIAGNOSTIC_PLAYBOOK_NOT_DIAGNOSTIC_SAFE" for issue in report.errors)
    assert not any(issue["code"] == "DIAGNOSTIC_PLAYBOOK_NOT_FOUND" for issue in report.errors)


@pytest.mark.no_db
def test_business_validation_warns_when_process_form_has_no_preview_samples():
    form = _base_form(default_queue_id=17, routing_policy={"rules": []})

    report = validate_form_pack_business(_pack(form))

    assert any(issue["code"] == "PREVIEW_SAMPLE_MISSING" for issue in report.warnings)


@pytest.mark.no_db
def test_business_validation_warns_about_field_key_change_without_alias_or_note():
    base_pack = _pack(
        _base_form(
            fields=[
                {"key": "target_url", "label": "URL", "type": "text", "required": True, "help_text": "Enter URL."}
            ]
        )
    )
    form = _base_form(
        fields=[
            {"key": "website_url", "label": "URL", "type": "text", "required": True, "help_text": "Enter URL."}
        ]
    )
    context = FormBusinessValidationContext(base_pack=base_pack)

    report = validate_form_pack_business(_pack(form), context=context)

    assert any(issue["code"] == "FIELD_KEY_CHANGED_WITHOUT_ALIAS" for issue in report.warnings)


@pytest.mark.no_db
def test_business_validation_allows_field_key_change_with_alias():
    base_pack = _pack(
        _base_form(
            fields=[
                {"key": "target_url", "label": "URL", "type": "text", "required": True, "help_text": "Enter URL."}
            ]
        )
    )
    form = _base_form(
        fields=[
            {"key": "website_url", "label": "URL", "type": "text", "required": True, "help_text": "Enter URL."}
        ],
        field_aliases={"website_url": "target_url"},
    )
    context = FormBusinessValidationContext(base_pack=base_pack)

    report = validate_form_pack_business(_pack(form), context=context)

    assert not any(issue["code"] == "FIELD_KEY_CHANGED_WITHOUT_ALIAS" for issue in report.warnings)
