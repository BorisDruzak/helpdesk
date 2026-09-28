"""Registry ownership following a trusted, single-use Endpoint possession proof."""
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.db.models import Device, RegistryEndpointDeviceMapping, RegistryPerson
from app.repos.registration_repo import RegistrationRepo
from domain_ports.registry_contracts import BindingRef, RegistrationRef, RegistryCommandResult
from registry.registration_service import RegistrationService, is_person_active


class EndpointMappingUnavailable(Exception):
    pass


class EndpointPossessionService:
    def __init__(self, session):
        self.session = session
        self.repo = RegistrationRepo(session)
        self.registration = RegistrationService(session)

    async def _mapping(self, request, now):
        mapping = await self.session.get(RegistryEndpointDeviceMapping, request.endpoint_device_ref)
        if mapping is not None:
            return mapping
        # A diagnostic target on a ticket does not prove that its retired
        # local device is the same computer. Never derive Registry ownership
        # from ticket targets, hostname equality or coincident UUIDs.
        local_id = request.endpoint_device_ref
        try:
            async with self.session.begin_nested():
                existing = await self.session.get(Device, local_id, with_for_update=True)
                if existing is None:
                    self.session.add(Device(device_id=local_id, protocol_version="endpoint_projection_v1",
                        agent_version="unknown", hostname=request.hostname,
                        os={"windows": "Windows", "linux": "Linux", "unknown": None}[request.platform],
                        capabilities={}, device_metadata={"source": "endpoint_platform"},
                        first_seen_at=now, last_seen_at=now, last_handshake_at=now))
                    await self.session.flush()
                elif existing.protocol_version != "endpoint_projection_v1" or existing.device_metadata != {"source": "endpoint_platform"}:
                    raise EndpointMappingUnavailable()
                mapping = RegistryEndpointDeviceMapping(endpoint_device_ref=request.endpoint_device_ref,
                    device_id=local_id, verified_at=now)
                self.session.add(mapping)
                await self.session.flush()
        except IntegrityError:
            mapping = await self.session.get(RegistryEndpointDeviceMapping, request.endpoint_device_ref,
                populate_existing=True)
            if mapping is None:
                raise EndpointMappingUnavailable() from None
        return mapping

    async def bind(self, request):
        now = datetime.now(timezone.utc)
        # Person and device rows serialize policy checks and primary activation.
        person = await self.session.get(RegistryPerson, request.person_id, with_for_update=True, populate_existing=True)
        if not is_person_active(person):
            return RegistryCommandResult(operation_id=request.operation_id, status="unavailable",
                code="registry_person_unavailable", idempotency_status="not_evaluated")
        mapping = await self._mapping(request, now)
        device = await self.session.get(Device, mapping.device_id, with_for_update=True, populate_existing=True)
        if device is None or device.deleted_at is not None:
            raise EndpointMappingUnavailable()
        rows = await self.repo.list_active_bindings_for_device(device.device_id)
        same = next((row for row in rows if row.person_id == person.person_id and row.relationship_type == "primary_user"), None)
        if same is not None and len(rows) == 1:
            await self.repo.append_event(event_type="endpoint_possession_idempotent", device_id=device.device_id,
                person_id=person.person_id, binding_id=same.binding_id, actor_id=request.actor_id,
                actor_role="user", payload={"endpoint_device_ref": request.endpoint_device_ref})
            return RegistryCommandResult(operation_id=request.operation_id, status="replayed",
                binding=BindingRef(external_id=same.binding_id), idempotency_status="replayed")
        conflict = "ambiguous_active_relationships" if rows else await self.registration.detect_conflicts(
            device.device_id, person.person_id, "primary_user")
        asset = await self.registration._ensure_asset_for_device(device)
        claim = await self.repo.find_pending_claim(device_id=device.device_id, person_id=person.person_id,
            source="endpoint_possession_proof")
        if claim is None:
            claim = await self.repo.create_claim(device_id=device.device_id, asset_id=asset.asset_id,
                person_id=person.person_id, claim_type="self_reported", status="conflict" if conflict else "approved",
                relationship_type="primary_user", profile_snapshot={},
                device_snapshot={"endpoint_device_ref": request.endpoint_device_ref, "hostname": request.hostname, "platform": request.platform},
                source="endpoint_possession_proof", source_ref=request.actor_id, user_confirmed_at=now,
                conflict_reason=conflict, metadata_json={"verification": "endpoint_possession_proof", "verified_at": now.isoformat()})
        if conflict:
            claim.status = "conflict"
            claim.conflict_reason = conflict
            await self.repo.append_event(event_type="conflict_detected", claim_id=claim.claim_id,
                device_id=device.device_id, person_id=person.person_id, actor_id=request.actor_id, actor_role="user",
                payload={"reason": conflict, "source": "endpoint_possession_proof"})
            return RegistryCommandResult(operation_id=request.operation_id, status="accepted",
                registration=RegistrationRef(external_id=claim.claim_id),
                code="endpoint_possession_pending_admin_review", idempotency_status="new")
        binding = await self.repo.create_binding(device_id=device.device_id, asset_id=asset.asset_id,
            person_id=person.person_id, relationship_type="primary_user", status="active",
            source_claim_id=claim.claim_id, source="endpoint_possession_proof", valid_from=now,
            confirmed_by_user_at=now, confirmed_at=now,
            metadata_json={"endpoint_device_ref": request.endpoint_device_ref, "verification": "endpoint_possession_proof"})
        claim.status = "approved"
        await self.registration.sync_asset_from_active_binding(binding)
        await self.registration.sync_inventory_from_active_binding(binding, profile={})
        await self.repo.append_event(event_type="binding_activated", claim_id=claim.claim_id,
            binding_id=binding.binding_id, device_id=device.device_id, person_id=person.person_id,
            actor_id=request.actor_id, actor_role="user", payload={"source": "endpoint_possession_proof"})
        await self.session.flush()
        return RegistryCommandResult(operation_id=request.operation_id, status="applied",
            binding=BindingRef(external_id=binding.binding_id), registration=RegistrationRef(external_id=claim.claim_id),
            idempotency_status="new")
