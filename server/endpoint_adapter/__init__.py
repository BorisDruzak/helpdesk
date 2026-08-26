"""Endpoint Operations API v1 adapters."""

from .http import ExternalEndpointHttpAdapter
from .modules_http import ExternalEndpointModuleHttpAdapter

__all__ = ("ExternalEndpointHttpAdapter", "ExternalEndpointModuleHttpAdapter")
