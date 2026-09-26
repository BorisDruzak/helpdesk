import pytest

from scripts.production_readiness_audit import refresh_risk_audit, validate_risk_audit


SHA = "a" * 40


def audit(**overrides):
    item = dict(id="R1", priority="P0", status="verified", release_blocker=True,
                source_revision=SHA, verification=["exact-SHA regression and live evidence"])
    item.update(overrides)
    return {"source_revision": SHA, "bugs": [item]}


def test_verified_current_risk_passes():
    validate_risk_audit(audit(), SHA)


@pytest.mark.parametrize("override", [
    {"status": "open"}, {"status": "fixed-local"}, {"status": "unknown"},
    {"source_revision": "b" * 40}, {"verification": []},
    {"priority": "P1", "status": "unverified", "release_blocker": False},
])
def test_unproven_high_priority_risk_blocks(override):
    with pytest.raises(ValueError):
        validate_risk_audit(audit(**override), SHA)


def test_historical_registry_cannot_prove_current_readiness():
    with pytest.raises(ValueError):
        validate_risk_audit({"head": "b" * 40, "bugs": []}, SHA)


def test_refresh_preserves_risks_but_does_not_promote_historical_fixes():
    result = refresh_risk_audit({"head": "b" * 40, "bugs": [
        dict(id="R1", priority="P0", release_blocker=True, fix_status="fixed-local")
    ]}, SHA)
    assert result["bugs"][0]["status"] == "unverified"
    with pytest.raises(ValueError):
        validate_risk_audit(result, SHA)
