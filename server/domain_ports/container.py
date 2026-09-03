"""Explicit composition container for external-domain dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import ssl
from urllib.parse import urlsplit

from .endpoint import EndpointPort
from .endpoint_modules import EndpointModulePort
from .knowledge import KnowledgePort
from .registry import RegistryPort
from .unavailable import (
    UnavailableEndpointModulePort,
    UnavailableEndpointPort,
    UnavailableKnowledgePort,
    UnavailableRegistryPort,
)


def _configured_knowledge_port_mode() -> str:
    try:
        import config
    except ModuleNotFoundError:  # Package import from the repository root.
        from server import config  # type: ignore[no-redef]

    return str(config.KNOWLEDGE_PORT_MODE or "").strip().lower()


def _configured_registry_port_mode() -> str:
    try:
        import config
    except ModuleNotFoundError:  # Package import from the repository root.
        from server import config  # type: ignore[no-redef]

    return str(config.REGISTRY_PORT_MODE or "").strip().lower()


def _configured_endpoint_port_mode() -> str:
    try:
        import config
    except ModuleNotFoundError:  # Package import from the repository root.
        from server import config  # type: ignore[no-redef]

    return str(config.ENDPOINT_PORT_MODE or "").strip().lower()


def _configured_endpoint_diagnostic_execution_mode() -> str:
    try:
        import config
    except ModuleNotFoundError:  # Package import from the repository root.
        from server import config  # type: ignore[no-redef]

    return str(config.ENDPOINT_DIAGNOSTIC_EXECUTION_MODE or "").strip().lower()


def _configured_endpoint_module_port_mode() -> str:
    try:
        import config
    except ModuleNotFoundError:  # Package import from the repository root.
        from server import config  # type: ignore[no-redef]

    return str(config.ENDPOINT_MODULE_PORT_MODE or "").strip().lower()


def _configured_endpoint_external_settings() -> tuple[str, str, str, float]:
    try:
        import config
    except ModuleNotFoundError:  # Package import from the repository root.
        from server import config  # type: ignore[no-redef]

    return (
        str(config.ENDPOINT_EXTERNAL_BASE_URL or ""),
        str(config.ENDPOINT_EXTERNAL_SERVICE_TOKEN or ""),
        str(config.ENDPOINT_EXTERNAL_CA_FILE or ""),
        float(config.ENDPOINT_EXTERNAL_TIMEOUT_SECONDS),
    )


def _configured_endpoint_module_external_settings() -> tuple[str, str, str, float]:
    try:
        import config
    except ModuleNotFoundError:  # Package import from the repository root.
        from server import config  # type: ignore[no-redef]

    return (
        str(config.ENDPOINT_EXTERNAL_BASE_URL or ""),
        str(config.ENDPOINT_MODULE_EXTERNAL_SERVICE_TOKEN or ""),
        str(config.ENDPOINT_EXTERNAL_CA_FILE or ""),
        float(config.ENDPOINT_EXTERNAL_TIMEOUT_SECONDS),
    )


def _endpoint_external_unavailable_code(
    *,
    base_url: str,
    service_token: str,
    ca_file: str,
) -> str | None:
    try:
        parsed = urlsplit(base_url)
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        return "endpoint_external_invalid_origin"
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return "endpoint_external_invalid_origin"
    if not service_token.strip():
        return "endpoint_external_service_token_missing"
    if not ca_file:
        return "endpoint_external_ca_missing"
    if not Path(ca_file).is_file():
        return "endpoint_external_ca_invalid"
    try:
        ssl.create_default_context(cafile=ca_file)
    except (OSError, ssl.SSLError):
        return "endpoint_external_ca_invalid"
    return None


def _configured_registry_http_settings() -> tuple[str, str, float]:
    try:
        import config
    except ModuleNotFoundError:  # Package import from the repository root.
        from server import config  # type: ignore[no-redef]

    return (
        str(config.REGISTRY_EXTERNAL_BASE_URL or ""),
        str(config.REGISTRY_EXTERNAL_SERVICE_TOKEN or ""),
        float(config.REGISTRY_EXTERNAL_TIMEOUT_SECONDS),
    )


@dataclass(frozen=True, slots=True)
class DomainPortContainer:
    knowledge: KnowledgePort
    registry: RegistryPort
    endpoint: EndpointPort
    endpoint_modules: EndpointModulePort = field(default_factory=UnavailableEndpointModulePort)

    @classmethod
    def from_config(
        cls,
        *,
        knowledge: KnowledgePort | None = None,
        registry: RegistryPort | None = None,
        endpoint: EndpointPort | None = None,
        endpoint_modules: EndpointModulePort | None = None,
        knowledge_mode: str | None = None,
        registry_mode: str | None = None,
        registry_session: object | None = None,
    ) -> "DomainPortContainer":
        if knowledge is None:
            mode = (
                _configured_knowledge_port_mode()
                if knowledge_mode is None
                else str(knowledge_mode or "").strip().lower()
            )
            if mode != "unavailable":
                raise ValueError(f"unsupported KNOWLEDGE_PORT_MODE: {mode!r}")
            knowledge = UnavailableKnowledgePort()

        if registry is None:
            mode = (
                _configured_registry_port_mode()
                if registry_mode is None
                else str(registry_mode or "").strip().lower()
            )
            if mode == "local":
                try:
                    from registry_adapter import LocalRegistryAdapter
                except ModuleNotFoundError as exc:
                    if exc.name != "registry_adapter":
                        raise
                    from server.registry_adapter import LocalRegistryAdapter

                registry = LocalRegistryAdapter(registry_session)
            elif mode == "unavailable":
                registry = UnavailableRegistryPort()
            elif mode == "external":
                try:
                    from registry_adapter import ExternalRegistryHttpAdapter, LocalRegistryAdapter, ShadowReadRegistryPort
                except ModuleNotFoundError as exc:
                    if exc.name != "registry_adapter":
                        raise
                    from server.registry_adapter import (
                        ExternalRegistryHttpAdapter,
                        LocalRegistryAdapter,
                        ShadowReadRegistryPort,
                    )

                base_url, service_token, timeout_seconds = _configured_registry_http_settings()
                local_commands = LocalRegistryAdapter(registry_session)
                external = ExternalRegistryHttpAdapter(
                    base_url=base_url,
                    service_token=service_token,
                    timeout_seconds=timeout_seconds,
                    command_port=local_commands,
                )
                if not external.configured:
                    registry = UnavailableRegistryPort(code="registry_external_unconfigured")
                else:
                    registry = ShadowReadRegistryPort(authoritative=local_commands, shadow=external)
            else:
                raise ValueError(f"unsupported REGISTRY_PORT_MODE: {mode!r}")

        if endpoint is None:
            diagnostic_mode = _configured_endpoint_diagnostic_execution_mode()
            if diagnostic_mode not in {"legacy", "endpoint"}:
                raise ValueError(
                    "unsupported ENDPOINT_DIAGNOSTIC_EXECUTION_MODE: "
                    f"{diagnostic_mode!r}"
                )
            endpoint_mode = _configured_endpoint_port_mode()
            if endpoint_mode == "unavailable":
                endpoint = UnavailableEndpointPort()
            elif endpoint_mode == "external":
                base_url, service_token, ca_file, timeout_seconds = (
                    _configured_endpoint_external_settings()
                )
                unavailable_code = _endpoint_external_unavailable_code(
                    base_url=base_url,
                    service_token=service_token,
                    ca_file=ca_file,
                )
                if unavailable_code is not None:
                    endpoint = UnavailableEndpointPort(code=unavailable_code)
                else:
                    try:
                        from endpoint_adapter import ExternalEndpointHttpAdapter
                    except ModuleNotFoundError as exc:
                        if exc.name != "endpoint_adapter":
                            raise
                        from server.endpoint_adapter import ExternalEndpointHttpAdapter

                    endpoint = ExternalEndpointHttpAdapter(
                        base_url=base_url,
                        service_token=service_token,
                        ca_file=ca_file,
                        timeout_seconds=timeout_seconds,
                    )
            else:
                raise ValueError(f"unsupported ENDPOINT_PORT_MODE: {endpoint_mode!r}")

        if endpoint_modules is None:
            module_mode = _configured_endpoint_module_port_mode()
            if module_mode == "unavailable":
                endpoint_modules = UnavailableEndpointModulePort()
            elif module_mode == "external":
                base_url, service_token, ca_file, timeout_seconds = (
                    _configured_endpoint_module_external_settings()
                )
                unavailable_code = _endpoint_external_unavailable_code(
                    base_url=base_url,
                    service_token=service_token,
                    ca_file=ca_file,
                )
                if unavailable_code is not None:
                    endpoint_modules = UnavailableEndpointModulePort(
                        code=f"endpoint_module_{unavailable_code.removeprefix('endpoint_')}",
                    )
                else:
                    try:
                        from endpoint_adapter import ExternalEndpointModuleHttpAdapter
                    except ModuleNotFoundError as exc:
                        if exc.name != "endpoint_adapter":
                            raise
                        from server.endpoint_adapter import ExternalEndpointModuleHttpAdapter

                    endpoint_modules = ExternalEndpointModuleHttpAdapter(
                        base_url=base_url,
                        service_token=service_token,
                        ca_file=ca_file,
                        timeout_seconds=timeout_seconds,
                    )
            else:
                raise ValueError(f"unsupported ENDPOINT_MODULE_PORT_MODE: {module_mode!r}")

        return cls(
            knowledge=knowledge,
            registry=registry,
            endpoint=endpoint,
            endpoint_modules=endpoint_modules,
        )
