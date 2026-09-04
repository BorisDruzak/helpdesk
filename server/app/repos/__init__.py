"""
Repository layer for database operations.
"""
from app.repos.job_events_repo import JobEventsRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.device_events_repo import DeviceEventsRepo
from app.repos.devices_repo import DevicesRepo
from app.repos.device_config_repo import DeviceConfigRepo
from app.repos.toolset_snapshots_repo import ToolsetSnapshotsRepo
from app.repos.operations_repo import OperationsRepo
from app.repos.operation_dependencies_repo import OperationDependenciesRepo
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.repos.artifacts_repo import ArtifactsRepo
from app.repos.notification_repo import NotificationRepo
from app.repos.notification_prefs_repo import NotificationPrefsRepo
from app.repos.problems_repo import ProblemsRepo
from app.repos.change_links_repo import ChangeLinksRepo
from app.repos.playbook_repo import PlaybookRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from app.repos.registry_repo import RegistryRepo
from app.repos.registration_repo import RegistrationRepo
from app.repos.remote_access_repo import RemoteAccessRepo
from app.repos.diagnostics_repo import DiagnosticRepo
from app.repos.diagnostic_provider_config_repo import DiagnosticProviderConfigRepo
from app.repos.service_catalog_repo import ServiceCatalogRepo
from app.repos.endpoint_operation_links_repo import EndpointOperationLinksRepo

__all__ = [
    "JobEventsRepo",
    "TicketEventsRepo",
    "DeviceEventsRepo",
    "DevicesRepo",
    "DeviceConfigRepo",
    "ToolsetSnapshotsRepo",
    "OperationsRepo",
    "OperationDependenciesRepo",
    "AuthTokensRepo",
    "ArtifactsRepo",
    "NotificationRepo",
    "NotificationPrefsRepo",
    "ProblemsRepo",
    "ChangeLinksRepo",
    "PlaybookRepo",
    "TicketFormPacksRepo",
    "RegistryRepo",
    "RegistrationRepo",
    "RemoteAccessRepo",
    "DiagnosticRepo",
    "DiagnosticProviderConfigRepo",
    "ServiceCatalogRepo",
    "EndpointOperationLinksRepo",
]
