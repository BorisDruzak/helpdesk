import json
from pathlib import Path

import pytest

from scripts.production_release_gate import validate_acceptance_evidence


SHA = "a" * 40
PROVIDER = "b" * 40
DIGEST = "c" * 64


def evidence():
    return dict(helpdesk_git_sha=SHA, endpoint_provider_sha=PROVIDER, endpoint_openapi_sha256=DIGEST,
                schema_revision="143", webapp_build_digest=DIGEST, configuration_profile="production-v1",
                environment="staging", backup_status="success", restore_drill_status="success",
                business_smoke="success", windows_endpoint_acceptance="success",
                endpoint_degraded_acceptance="success", contract_acceptance="success",
                staging_deployment_topology=topology(), production_deployment_topology=topology())


def topology():
    return dict(server_instances=1, application_workers=1, helpdesk_backends=1,
                ha_enabled=False, load_balancing_enabled=False)


def test_exact_staging_acceptance_passes():
    validate_acceptance_evidence(evidence(), SHA, PROVIDER, DIGEST, "143", DIGEST)


@pytest.mark.parametrize("name,value", [
    ("helpdesk_git_sha", "d" * 40), ("endpoint_provider_sha", "e" * 40),
    ("webapp_build_digest", "f" * 64), ("environment", "fixture"),
    ("schema_revision", "142"), ("business_smoke", "missing"),
    ("windows_endpoint_acceptance", "skipped"), ("backup_status", "failed"),
    ("endpoint_degraded_acceptance", "unknown"), ("restore_drill_status", "missing"),
])
def test_missing_or_mismatched_evidence_fails(name, value):
    payload = evidence(); payload[name] = value
    with pytest.raises(ValueError):
        validate_acceptance_evidence(payload, SHA, PROVIDER, DIGEST, "143", DIGEST)


@pytest.mark.parametrize("surface", ["staging_deployment_topology", "production_deployment_topology"])
@pytest.mark.parametrize("field,value", [
    ("server_instances", 2), ("application_workers", 2), ("helpdesk_backends", 2),
    ("ha_enabled", True), ("load_balancing_enabled", True),
    ("server_instances", True), ("application_workers", "1"), ("helpdesk_backends", 0),
])
def test_topology_change_reopens_scale036_gate(surface, field, value):
    payload = evidence(); payload[surface][field] = value
    with pytest.raises(ValueError, match="SCALE-036"):
        validate_acceptance_evidence(payload, SHA, PROVIDER, DIGEST, "143", DIGEST)


@pytest.mark.parametrize("surface", ["staging_deployment_topology", "production_deployment_topology"])
def test_missing_topology_cannot_use_single_instance_risk_exception(surface):
    payload = evidence(); del payload[surface]
    with pytest.raises(ValueError, match="SCALE-036"):
        validate_acceptance_evidence(payload, SHA, PROVIDER, DIGEST, "143", DIGEST)
