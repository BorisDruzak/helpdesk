"""RegistryPort adapters."""

from .http import ExternalRegistryHttpAdapter, ShadowReadRegistryPort
from .local import LocalRegistryAdapter

__all__ = ("ExternalRegistryHttpAdapter", "LocalRegistryAdapter", "ShadowReadRegistryPort")
