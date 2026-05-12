from dataclasses import replace

import pytest

from diagnostics.capability_registry import CapabilityRegistry
from diagnostics.execution_router import CapabilityExecutionRouter
from diagnostics.readiness import CapabilityReadinessService, ReadinessContext


class FakeToolService:
    def __init__(self):
        self.run_calls = []
        self.device_tools = [
            {
                "tool": "diag.logs.collect",
                "module": "diag_logs",
                "aliases": ["diag.collect_logs"],
                "spec": {
                    "description": "Collect diagnostic logs",
                    "risk_level": "low",
                    "execution": {
                        "target": "agent_builtin",
                        "requires_device": True,
                        "requires_agent_online": True,
                        "supports_auto_install": False,
                        "requires_integration": False,
                    },
                    "deployment": {
                        "provider_id": "diag_logs",
                        "install_required_on_agent": False,
                        "package_type": "builtin",
                    },
                    "evidence": {
                        "produces_evidence": True,
                        "kind": "logs.bundle",
                        "domain": "logs",
                        "perspective": "endpoint",
                        "passport_eligible": True,
                    },
                    "artifacts": {"may_produce_artifacts": True, "artifact_kinds": ["logs_zip"]},
                },
            }
        ]
        self.server_tools = [
            {
                "tool": "endpoint.http.request",
                "module": "network_tools",
                "source": "managed_module",
                "install_required": True,
                "spec": {
                    "description": "HTTP request from endpoint",
                    "risk_level": "low",
                    "metadata": {"platforms": ["win32"]},
                    "execution": {
                        "target": "agent_managed_module",
                        "requires_device": True,
                        "requires_agent_online": True,
                        "supports_auto_install": True,
                        "requires_integration": False,
                    },
                    "deployment": {
                        "provider_id": "network_tools",
                        "install_required_on_agent": True,
                        "package_type": "zip",
                    },
                    "readiness": {
                        "requires_policy": True,
                        "required_permission": "module.tool.run.low_risk",
                        "policy_key": "diagnostics.enabled",
                    },
                },
            }
        ]

    async def get_tools_list(self, _device_id):
        return list(self.device_tools)

    async def get_tools_from_server(self, _device_id):
        return list(self.server_tools)

    async def run_tool(self, **kwargs):
        self.run_calls.append(kwargs)
        return {"status": "success", "operation_id": kwargs.get("operation_id")}


class FakeState:
    def __init__(self, online=True):
        self.online = online

    def is_agent_online(self, _device_id):
        return self.online


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_capability_registry_projects_agent_and_skeleton_provider_capabilities():
    registry = CapabilityRegistry(tool_service=FakeToolService(), state=FakeState())

    capabilities = await registry.list_capabilities(device_id="device-1")
    by_id = {cap.id: cap for cap in capabilities}

    assert by_id["diag.logs.collect"].execution_target == "agent_builtin"
    assert by_id["diag.logs.collect"].evidence["kind"] == "logs.bundle"
    assert by_id["endpoint.http.request"].execution_target == "agent_managed_module"
    assert by_id["server.dns.resolve"].execution_target == "server_builtin"
    assert by_id["zabbix.problems.lookup"].execution_target == "server_connector"
    assert by_id["observer.ticket.summary"].execution_target == "observer_query"
    assert by_id["observer.ticket.summary"].output_contract["kind"] == "observer.ticket_summary"
    assert by_id["observer.trace.bundle"].output_contract["kind"] == "observer.trace_bundle"
    assert by_id["remote_assist.request_view"].execution_target == "remote_assist"
    assert by_id["remote_assist.request_control"].required_permission == "remote_assist.control"
    assert by_id["remote_assist.request_control"].output_contract["kind"] == "remote_assist.session_request"
    assert by_id["remote_assist.session.summary"].output_contract["kind"] == "remote_assist.session_summary"
    assert by_id["manual.visual_check"].execution_target == "manual"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_readiness_calculates_agent_managed_and_server_connector_states():
    registry = CapabilityRegistry(tool_service=FakeToolService(), state=FakeState(online=True))
    service = CapabilityReadinessService(state=FakeState(online=True))
    capabilities = {cap.id: cap for cap in await registry.list_capabilities(device_id="device-1")}

    diag = await service.get_readiness(
        capabilities["diag.logs.collect"],
        ReadinessContext(ticket_id="ticket-1", device_id="device-1"),
    )
    managed = await service.get_readiness(
        capabilities["endpoint.http.request"],
        ReadinessContext(ticket_id="ticket-1", device_id="device-1"),
    )
    zabbix = await service.get_readiness(
        capabilities["zabbix.problems.lookup"],
        ReadinessContext(ticket_id="ticket-1", device_id="device-1"),
    )

    assert diag.readiness == "available"
    assert managed.readiness == "install_required"
    assert "install" in managed.actions
    assert zabbix.readiness == "integration_not_configured"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_readiness_marks_server_builtin_available_without_device_or_agent():
    registry = CapabilityRegistry(tool_service=FakeToolService(), state=FakeState(online=False))
    service = CapabilityReadinessService(state=FakeState(online=False))
    capabilities = {cap.id: cap for cap in await registry.list_capabilities(device_id=None)}

    readiness = await service.get_readiness(
        capabilities["server.dns.resolve"],
        ReadinessContext(ticket_id="ticket-1"),
    )

    assert readiness.readiness == "available"
    assert readiness.actions == ["run"]


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_readiness_uses_platform_install_dependency_policy_credentials_mapping_and_permissions():
    registry = CapabilityRegistry(tool_service=FakeToolService(), state=FakeState(online=True))
    service = CapabilityReadinessService(state=FakeState(online=True))
    capabilities = {cap.id: cap for cap in await registry.list_capabilities(device_id="device-1")}

    unsupported = await service.get_readiness(
        capabilities["endpoint.http.request"],
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="linux",
            permissions={"module.tool.run.low_risk"},
            policy_flags={"diagnostics.enabled": True},
        ),
    )
    installing = await service.get_readiness(
        capabilities["endpoint.http.request"],
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            installed_modules={"network_tools": {"version": "1.0.0", "active": False, "state": "installing"}},
            desired_modules={"network_tools": {"version": "1.0.0", "state": "installed"}},
            permissions={"module.tool.run.low_risk"},
            policy_flags={"diagnostics.enabled": True},
        ),
    )
    missing_dependency = await service.get_readiness(
        capabilities["endpoint.http.request"],
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            dependency_status={"endpoint.http.request": False},
            permissions={"module.tool.run.low_risk"},
            policy_flags={"diagnostics.enabled": True},
        ),
    )
    policy_denied = await service.get_readiness(
        capabilities["endpoint.http.request"],
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            permissions={"module.tool.run.low_risk"},
            policy_flags={"diagnostics.enabled": False},
        ),
    )
    permission_denied = await service.get_readiness(
        capabilities["endpoint.http.request"],
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            permissions=set(),
            policy_flags={"diagnostics.enabled": True},
        ),
    )
    zabbix = capabilities["zabbix.problems.lookup"]
    credentials_missing = await service.get_readiness(
        zabbix,
        ReadinessContext(
            ticket_id="ticket-1",
            integration_configs={"zabbix": {"url": "https://zabbix.local"}},
            credential_keys={"zabbix": False},
            mappings={"zabbix.host": {"hostid": "10101"}},
            permissions={"monitoring.zabbix.view"},
            policy_flags={"monitoring.zabbix.enabled": True},
        ),
    )
    mapping_missing = await service.get_readiness(
        zabbix,
        ReadinessContext(
            ticket_id="ticket-1",
            integration_configs={"zabbix": {"url": "https://zabbix.local"}},
            credential_keys={"zabbix": True},
            mappings={},
            permissions={"monitoring.zabbix.view"},
            policy_flags={"monitoring.zabbix.enabled": True},
        ),
    )

    assert unsupported.readiness == "unsupported_platform"
    assert installing.readiness == "installing"
    assert missing_dependency.readiness == "missing_dependency"
    assert policy_denied.readiness == "disabled_by_policy"
    assert permission_denied.readiness == "permission_denied"
    assert credentials_missing.readiness == "credentials_missing"
    assert mapping_missing.readiness == "mapping_missing"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_readiness_returns_stable_reason_codes_and_action_ids():
    registry = CapabilityRegistry(tool_service=FakeToolService(), state=FakeState(online=True))
    service = CapabilityReadinessService(state=FakeState(online=True))
    capabilities = {cap.id: cap for cap in await registry.list_capabilities(device_id="device-1")}

    no_device = await service.get_readiness(
        capabilities["diag.logs.collect"],
        ReadinessContext(ticket_id="ticket-1"),
    )
    desired_installing = await service.get_readiness(
        capabilities["endpoint.http.request"],
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            desired_modules={"network_tools": {"version": "1.0.0", "state": "queued"}},
            permissions={"module.tool.run.low_risk"},
            policy_flags={"diagnostics.enabled": True},
        ),
    )
    preflight_failed = await service.get_readiness(
        capabilities["endpoint.http.request"],
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            device_platform="win32",
            dependency_status={
                "endpoint.http.request": {
                    "status": "failed",
                    "reason_code": "PREFLIGHT_FAILED",
                    "reason": "preflight failed",
                }
            },
            permissions={"module.tool.run.low_risk"},
            policy_flags={"diagnostics.enabled": True},
        ),
    )
    connector_missing = await service.get_readiness(
        capabilities["zabbix.problems.lookup"],
        ReadinessContext(ticket_id="ticket-1", permissions={"monitoring.zabbix.view"}),
    )
    connector_no_credentials = await service.get_readiness(
        capabilities["zabbix.problems.lookup"],
        ReadinessContext(
            ticket_id="ticket-1",
            integration_configs={"zabbix": {"url": "https://zabbix.local"}},
            credential_keys={"zabbix": False},
            mappings={"zabbix.host": {"hostid": "10101"}},
            permissions={"monitoring.zabbix.view"},
            policy_flags={"monitoring.zabbix.enabled": True},
        ),
    )
    connector_no_mapping = await service.get_readiness(
        capabilities["zabbix.problems.lookup"],
        ReadinessContext(
            ticket_id="ticket-1",
            integration_configs={"zabbix": {"url": "https://zabbix.local"}},
            credential_keys={"zabbix": True},
            mappings={},
            permissions={"monitoring.zabbix.view"},
            policy_flags={"monitoring.zabbix.enabled": True},
        ),
    )
    remote_assist = await service.get_readiness(
        capabilities["remote_assist.request_view"],
        ReadinessContext(ticket_id="ticket-1", device_id="device-1"),
    )
    remote_assist_ready = await service.get_readiness(
        replace(capabilities["remote_assist.request_view"], requires_consent=False),
        ReadinessContext(ticket_id="ticket-1", device_id="device-1"),
    )
    remote_control_policy_denied = await service.get_readiness(
        capabilities["remote_assist.request_control"],
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            permissions={"remote_assist.control"},
            policy_flags={"remote_assist.interactive_control.enabled": False},
        ),
    )
    remote_summary = await service.get_readiness(
        capabilities["remote_assist.session.summary"],
        ReadinessContext(ticket_id="ticket-1", permissions={"remote_assist.view"}),
    )
    remote_active_exists = await service.get_readiness(
        replace(capabilities["remote_assist.request_view"], requires_consent=False),
        ReadinessContext(
            ticket_id="ticket-1",
            device_id="device-1",
            permissions={"remote_assist.request"},
            policy_flags={"remote_assist.enabled": True},
            remote_assist={"active_session": {"session_id": "session-1", "status": "active"}},
        ),
    )

    assert no_device.reason_code == "DEVICE_REQUIRED"
    assert no_device.actions == []
    assert desired_installing.readiness == "installing"
    assert desired_installing.reason_code == "MODULE_INSTALLING"
    assert preflight_failed.readiness == "missing_dependency"
    assert preflight_failed.reason_code == "PREFLIGHT_FAILED"
    assert connector_missing.reason_code == "INTEGRATION_NOT_CONFIGURED"
    assert connector_missing.actions == ["configure_integration"]
    assert connector_no_credentials.reason_code == "CREDENTIALS_MISSING"
    assert connector_no_credentials.actions == ["add_credentials"]
    assert connector_no_mapping.reason_code == "MAPPING_MISSING"
    assert connector_no_mapping.actions == ["configure_integration"]
    assert remote_assist.readiness == "consent_required"
    assert remote_assist.actions == ["request_consent"]
    assert remote_assist_ready.actions == ["open_remote_assist"]
    assert remote_control_policy_denied.readiness == "disabled_by_policy"
    assert remote_control_policy_denied.reason_code == "POLICY_DISABLED"
    assert remote_summary.readiness == "available"
    assert remote_summary.actions == ["open_remote_assist"]
    assert remote_active_exists.readiness == "unavailable"
    assert remote_active_exists.reason_code == "REMOTE_ASSIST_SESSION_ACTIVE"
    assert remote_active_exists.actions == ["open_remote_assist"]


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_readiness_agent_offline_for_endpoint_capabilities():
    registry = CapabilityRegistry(tool_service=FakeToolService(), state=FakeState(online=False))
    service = CapabilityReadinessService(state=FakeState(online=False))
    capabilities = {cap.id: cap for cap in await registry.list_capabilities(device_id="device-1")}

    status = await service.get_readiness(
        capabilities["diag.logs.collect"],
        ReadinessContext(ticket_id="ticket-1", device_id="device-1"),
    )

    assert status.readiness == "agent_offline"


class FakeProvider:
    def __init__(self, status):
        self.status = status
        self.calls = []

    async def run(self, capability, **kwargs):
        self.calls.append((capability.id, kwargs))
        return {"status": self.status, "capability_id": capability.id}


class FakeServerConnectorProvider:
    def __init__(self):
        self.query_calls = []

    def list_capabilities(self):
        return []

    async def get_readiness(self, capability, **kwargs):
        return {"readiness": "available"}

    async def run_query(self, capability, **kwargs):
        self.query_calls.append((capability.id, kwargs))
        return {"status": "success", "raw": {"problem_count": 0}}

    def normalize_result(self, capability, result, **kwargs):
        return {
            "status": result["status"],
            "capability_id": capability.id,
            "output": {"problem_count": result["raw"]["problem_count"]},
        }

    def map_evidence(self, capability, result, **kwargs):
        return {"kind": capability.evidence["kind"], "status": "ok"}


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_execution_router_routes_only_agent_capabilities_to_tool_execution_service():
    tool_service = FakeToolService()
    registry = CapabilityRegistry(tool_service=tool_service, state=FakeState())
    server_provider = FakeProvider("success")
    observer_provider = FakeProvider("success")
    remote_provider = FakeProvider("created")
    manual_provider = FakeProvider("created")
    router = CapabilityExecutionRouter(
        capability_registry=registry,
        tool_service=tool_service,
        server_connector_provider=server_provider,
        observer_provider=observer_provider,
        remote_assist_provider=remote_provider,
        manual_provider=manual_provider,
    )

    agent_result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="diag.logs.collect",
        params={"include_agent_logs": True},
        actor=None,
    )
    server_result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="zabbix.problems.lookup",
        params={},
        actor=None,
    )
    observer_result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="observer.ticket.summary",
        params={},
        actor=None,
    )
    remote_result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="remote_assist.request_view",
        params={},
        actor=None,
    )
    manual_result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="manual.visual_check",
        params={"summary": "Visual check passed"},
        actor=None,
    )

    assert agent_result["status"] == "success"
    assert tool_service.run_calls[0]["tool_name"] == "diag.logs.collect"
    assert server_result["status"] == "success"
    assert observer_result["status"] == "success"
    assert remote_result["status"] == "created"
    assert manual_result["status"] == "created"
    assert len(tool_service.run_calls) == 1
    assert server_provider.calls[0][0] == "zabbix.problems.lookup"
    assert observer_provider.calls[0][0] == "observer.ticket.summary"
    assert remote_provider.calls[0][0] == "remote_assist.request_view"
    assert manual_provider.calls[0][0] == "manual.visual_check"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_execution_router_returns_target_specific_envelope_and_provider_interface_metadata():
    tool_service = FakeToolService()
    registry = CapabilityRegistry(tool_service=tool_service, state=FakeState())
    server_provider = FakeServerConnectorProvider()
    observer_provider = FakeProvider("success")
    remote_provider = FakeProvider("created")
    manual_provider = FakeProvider("created")
    router = CapabilityExecutionRouter(
        capability_registry=registry,
        tool_service=tool_service,
        server_connector_provider=server_provider,
        observer_provider=observer_provider,
        remote_assist_provider=remote_provider,
        manual_provider=manual_provider,
    )

    agent_result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="diag.logs.collect",
        params={},
        actor=None,
        idempotency_key="idem-agent",
        timeout_ms=1000,
    )
    server_result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="zabbix.problems.lookup",
        params={"integration_config": {"url": "https://zabbix.local"}, "credentials_ref": "secret", "mapping": {"host": "web-1"}},
        actor=None,
        idempotency_key="idem-zabbix",
        timeout_ms=2000,
    )
    remote_result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="remote_assist.request_view",
        params={},
        actor=None,
        idempotency_key="idem-remote",
        timeout_ms=3000,
    )
    manual_result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="manual.visual_check",
        params={"summary": "ok"},
        actor=None,
        idempotency_key="idem-manual",
        timeout_ms=4000,
    )

    assert agent_result["execution_kind"] == "operation"
    assert agent_result["execution_target"] == "agent_builtin"
    assert agent_result["idempotency_key"] == "idem-agent"
    assert agent_result["timeout_ms"] == 1000
    assert tool_service.run_calls[0]["call_id"] == "idem-agent"
    assert server_result["execution_kind"] == "query"
    assert server_result["execution_target"] == "server_connector"
    assert server_result["idempotency_key"] == "idem-zabbix"
    assert server_result["timeout_ms"] == 2000
    assert server_result["evidence_preview"]["kind"] == "monitoring.problem"
    assert server_provider.query_calls[0][0] == "zabbix.problems.lookup"
    assert remote_result["execution_kind"] == "session"
    assert remote_result["idempotency_key"] == "idem-remote"
    assert manual_result["execution_kind"] == "manual_evidence"
    assert manual_result["idempotency_key"] == "idem-manual"
    assert len(tool_service.run_calls) == 1


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_execution_router_blocks_not_ready_capability_before_provider_or_tool_call():
    tool_service = FakeToolService()
    registry = CapabilityRegistry(tool_service=tool_service, state=FakeState())
    server_provider = FakeServerConnectorProvider()
    router = CapabilityExecutionRouter(
        capability_registry=registry,
        tool_service=tool_service,
        server_connector_provider=server_provider,
    )

    result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="device-1",
        capability_id="zabbix.problems.lookup",
        params={},
        actor=None,
        readiness={
            "readiness": "integration_not_configured",
            "reason_code": "INTEGRATION_NOT_CONFIGURED",
            "actions": ["configure_integration"],
        },
    )

    assert result["status"] == "error"
    assert result["error_code"] == "CAPABILITY_NOT_READY"
    assert result["reason_code"] == "INTEGRATION_NOT_CONFIGURED"
    assert result["execution_target"] == "server_connector"
    assert server_provider.query_calls == []
    assert tool_service.run_calls == []
