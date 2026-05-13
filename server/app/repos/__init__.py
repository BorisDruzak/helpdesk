"""
Repository layer for database operations.
"""
from app.repos.job_events_repo import JobEventsRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.device_events_repo import DeviceEventsRepo
from app.repos.device_outbox_repo import DeviceOutboxRepo
from app.repos.devices_repo import DevicesRepo
from app.repos.device_config_repo import DeviceConfigRepo
from app.repos.toolset_snapshots_repo import ToolsetSnapshotsRepo
from app.repos.operations_repo import OperationsRepo
from app.repos.operation_dependencies_repo import OperationDependenciesRepo
from app.repos.modules_repo import ModulesRepo
from app.repos.device_modules_repo import DeviceModulesRepo
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.repos.artifacts_repo import ArtifactsRepo
from app.repos.agent_builds_repo import AgentBuildsRepo
from app.repos.agent_rollout_repo import AgentRolloutRepo
from app.repos.module_rollout_repo import ModuleRolloutRepo
from app.repos.notification_repo import NotificationRepo
from app.repos.notification_prefs_repo import NotificationPrefsRepo
from app.repos.problems_repo import ProblemsRepo
from app.repos.change_links_repo import ChangeLinksRepo
from app.repos.playbook_repo import PlaybookRepo
from app.repos.device_desired_modules_repo import DeviceDesiredModulesRepo
from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from app.repos.registry_repo import RegistryRepo
from app.repos.remote_access_repo import RemoteAccessRepo
from app.repos.diagnostics_repo import DiagnosticRepo
from app.repos.diagnostic_provider_config_repo import DiagnosticProviderConfigRepo

__all__ = [
    "JobEventsRepo",
    "TicketEventsRepo",
    "DeviceEventsRepo",
    "DeviceOutboxRepo",
    "DevicesRepo",
    "DeviceConfigRepo",
    "ToolsetSnapshotsRepo",
    "OperationsRepo",
    "OperationDependenciesRepo",
    "ModulesRepo",
    "DeviceModulesRepo",
    "AuthTokensRepo",
    "ArtifactsRepo",
    "AgentBuildsRepo",
    "AgentRolloutRepo",
    "ModuleRolloutRepo",
    "NotificationRepo",
    "NotificationPrefsRepo",
    "ProblemsRepo",
    "ChangeLinksRepo",
    "PlaybookRepo",
    "DeviceDesiredModulesRepo",
    "AgentRuntimeAuditRepo",
    "TicketFormPacksRepo",
    "RegistryRepo",
    "RemoteAccessRepo",
    "DiagnosticRepo",
    "DiagnosticProviderConfigRepo",
]
