"""Explicit composition container for external-domain dependencies."""

from __future__ import annotations

from dataclasses import dataclass

from .endpoint import EndpointPort
from .knowledge import KnowledgePort
from .registry import RegistryPort
from .unavailable import UnavailableEndpointPort, UnavailableKnowledgePort, UnavailableRegistryPort


def _configured_knowledge_port_mode() -> str:
    try:
        import config
    except ModuleNotFoundError:  # Package import from the repository root.
        from server import config  # type: ignore[no-redef]

    return str(config.KNOWLEDGE_PORT_MODE or "").strip().lower()


@dataclass(frozen=True, slots=True)
class DomainPortContainer:
    knowledge: KnowledgePort
    registry: RegistryPort
    endpoint: EndpointPort

    @classmethod
    def from_config(
        cls,
        *,
        knowledge: KnowledgePort | None = None,
        registry: RegistryPort | None = None,
        endpoint: EndpointPort | None = None,
        knowledge_mode: str | None = None,
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

        return cls(
            knowledge=knowledge,
            registry=registry if registry is not None else UnavailableRegistryPort(),
            endpoint=endpoint if endpoint is not None else UnavailableEndpointPort(),
        )
