from app.db.models import DeviceRegistrationClaim
from registry.registration_service import RegistrationService
import pytest

pytestmark = pytest.mark.no_db


def test_claim_projection_includes_possession_provenance_without_challenge_material():
    claim = DeviceRegistrationClaim(
        claim_id="fixture-claim", device_id="fixture-device", source="endpoint_possession_proof",
        status="conflict", claim_type="registration", relationship_type="primary_user",
        profile_snapshot={},
    )
    payload = RegistrationService.__new__(RegistrationService)._claim_payload(claim)
    assert payload["source"] == "endpoint_possession_proof"
    assert {"code", "challenge_digest", "token"}.isdisjoint(payload)
