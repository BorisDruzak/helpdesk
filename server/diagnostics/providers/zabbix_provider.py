from __future__ import annotations

import asyncio
import json
import ssl
from typing import Any, Dict, List
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from diagnostics.capability_models import CapabilityDescriptor


MAX_PROBLEMS = 50
MAX_HISTORY_POINTS = 100
DEFAULT_TIMEOUT_SEC = 10
MAX_TIMEOUT_SEC = 30


class ZabbixProviderError(Exception):
    def __init__(self, error_code: str, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details


def list_zabbix_capabilities() -> List[CapabilityDescriptor]:
    common = {
        "provider_id": "zabbix_connector",
        "provider_type": "server_connector",
        "execution_target": "server_connector",
        "tool_kind": "diagnostic",
        "risk_level": "low",
        "requires_device": False,
        "requires_integration": True,
        "integration_key": "zabbix",
        "requires_credentials": True,
        "requires_mapping": True,
        "requires_policy": True,
        "required_permission": "monitoring.zabbix.view",
        "policy_key": "monitoring.zabbix.enabled",
        "mapping_key": "zabbix.host",
        "platforms": ["any"],
        "source": "server_connector",
        "evidence": {
            "produces_evidence": True,
            "kind": "monitoring.problem",
            "domain": "monitoring",
            "perspective": "monitoring",
            "passport_eligible": True,
        },
    }
    return [
        CapabilityDescriptor(
            id="zabbix.problems.lookup",
            title="Zabbix: active problems lookup",
            description="Lookup active Zabbix problems for the mapped host or service.",
            params_schema={
                "type": "object",
                "properties": {
                    "hostid": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_PROBLEMS},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "problem_count": {"type": "integer"},
                    "problems": {"type": "array"},
                },
            },
            **common,
        ),
        CapabilityDescriptor(
            id="zabbix.host.health",
            title="Zabbix: host health",
            description="Lookup bounded Zabbix host health for the mapped host.",
            params_schema={"type": "object", "properties": {"hostid": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"host": {"type": "object"}}},
            evidence={**common["evidence"], "kind": "monitoring.host_health"},
            **{key: value for key, value in common.items() if key != "evidence"},
        ),
        CapabilityDescriptor(
            id="zabbix.item.history",
            title="Zabbix: item history",
            description="Lookup bounded Zabbix metric history for a mapped item.",
            params_schema={
                "type": "object",
                "properties": {
                    "itemid": {"type": "string"},
                    "history": {"type": "integer"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_HISTORY_POINTS},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "value_count": {"type": "integer"},
                    "values": {"type": "array"},
                },
            },
            evidence={**common["evidence"], "kind": "monitoring.metric_history"},
            **{key: value for key, value in common.items() if key != "evidence"},
        ),
    ]


class ZabbixJsonRpcClient:
    async def call(
        self,
        *,
        method: str,
        params: Dict[str, Any],
        config: Dict[str, Any],
        token: str,
        timeout_ms: int | None = None,
    ) -> Any:
        return await asyncio.to_thread(
            self._call_sync,
            method=method,
            params=params,
            config=config,
            token=token,
            timeout_ms=timeout_ms,
        )

    def _call_sync(
        self,
        *,
        method: str,
        params: Dict[str, Any],
        config: Dict[str, Any],
        token: str,
        timeout_ms: int | None = None,
    ) -> Any:
        url = _zabbix_url(config)
        timeout = _timeout_sec(config, timeout_ms)
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
            "auth": token,
        }
        request = urllib_request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        context = None
        if config.get("verify_tls") is False:
            context = ssl._create_unverified_context()
        try:
            with urllib_request.urlopen(request, timeout=timeout, context=context) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise ZabbixProviderError("ZABBIX_HTTP_ERROR", f"Zabbix HTTP error {exc.code}") from exc
        except URLError as exc:
            raise ZabbixProviderError("ZABBIX_UNAVAILABLE", str(exc.reason or exc)) from exc
        except TimeoutError as exc:
            raise ZabbixProviderError("ZABBIX_TIMEOUT", "Zabbix request timed out") from exc
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise ZabbixProviderError("ZABBIX_BAD_RESPONSE", "Zabbix returned invalid JSON") from exc
        if isinstance(data, dict) and data.get("error"):
            error = data["error"] if isinstance(data["error"], dict) else {}
            raise ZabbixProviderError(
                "ZABBIX_API_ERROR",
                str(error.get("message") or "Zabbix API error"),
                details={"code": error.get("code"), "data": error.get("data")},
            )
        if not isinstance(data, dict) or "result" not in data:
            raise ZabbixProviderError("ZABBIX_BAD_RESPONSE", "Zabbix response has no result")
        return data["result"]


class ZabbixProvider:
    def __init__(self, *, client: ZabbixJsonRpcClient | None = None) -> None:
        self.client = client or ZabbixJsonRpcClient()

    def list_capabilities(self) -> List[CapabilityDescriptor]:
        return list_zabbix_capabilities()

    async def run_query(self, capability: CapabilityDescriptor, **kwargs: Any) -> Dict[str, Any]:
        params = kwargs.get("params") if isinstance(kwargs.get("params"), dict) else {}
        config = _integration_config(params)
        token = _credential_token(params)
        if not config:
            return _error(capability, "INTEGRATION_NOT_CONFIGURED", "Zabbix integration is not configured")
        if not token:
            return _error(capability, "CREDENTIALS_MISSING", "Zabbix credentials are missing")
        try:
            if capability.id == "zabbix.problems.lookup":
                return await self._problems(capability, params, config, token, kwargs.get("timeout_ms"))
            if capability.id == "zabbix.host.health":
                return await self._host_health(capability, params, config, token, kwargs.get("timeout_ms"))
            if capability.id == "zabbix.item.history":
                return await self._item_history(capability, params, config, token, kwargs.get("timeout_ms"))
        except ZabbixProviderError as exc:
            return _error(capability, exc.error_code, exc.message, details=exc.details)
        return _error(capability, "CAPABILITY_TARGET_UNSUPPORTED", f"Unsupported Zabbix capability: {capability.id}")

    async def _problems(
        self,
        capability: CapabilityDescriptor,
        params: Dict[str, Any],
        config: Dict[str, Any],
        token: str,
        timeout_ms: int | None,
    ) -> Dict[str, Any]:
        hostid = _mapped_value(params, "hostid", "host_id", "zabbix_host_id")
        limit = _bounded_int(params.get("limit"), default=MAX_PROBLEMS, maximum=MAX_PROBLEMS)
        query = {
            "output": ["eventid", "objectid", "name", "severity", "clock"],
            "selectHosts": ["hostid", "host", "name"],
            "sortfield": ["eventid"],
            "sortorder": "DESC",
            "limit": limit,
        }
        if hostid:
            query["hostids"] = [hostid]
        result = await self.client.call(
            method="problem.get",
            params=query,
            config=config,
            token=token,
            timeout_ms=timeout_ms,
        )
        problems = [_problem_to_dict(item) for item in _as_list(result)[:limit]]
        return _success(
            capability,
            {
                "hostid": hostid,
                "problem_count": len(problems),
                "problems": problems,
                "summary": f"Zabbix active problems: {len(problems)}",
            },
        )

    async def _host_health(
        self,
        capability: CapabilityDescriptor,
        params: Dict[str, Any],
        config: Dict[str, Any],
        token: str,
        timeout_ms: int | None,
    ) -> Dict[str, Any]:
        hostid = _mapped_value(params, "hostid", "host_id", "zabbix_host_id")
        if not hostid:
            return _error(capability, "MAPPING_MISSING", "Zabbix host mapping is missing")
        result = await self.client.call(
            method="host.get",
            params={
                "output": ["hostid", "host", "name", "status", "available"],
                "hostids": [hostid],
                "limit": 1,
            },
            config=config,
            token=token,
            timeout_ms=timeout_ms,
        )
        host = _host_to_dict((_as_list(result) or [{}])[0])
        return _success(capability, {"host": host, "summary": f"Zabbix host health: {host.get('host') or hostid}"})

    async def _item_history(
        self,
        capability: CapabilityDescriptor,
        params: Dict[str, Any],
        config: Dict[str, Any],
        token: str,
        timeout_ms: int | None,
    ) -> Dict[str, Any]:
        itemid = _mapped_value(params, "itemid", "item_id", "zabbix_item_id")
        if not itemid:
            return _error(capability, "MAPPING_MISSING", "Zabbix item mapping is missing")
        limit = _bounded_int(params.get("limit"), default=20, maximum=MAX_HISTORY_POINTS)
        history_type = _bounded_int(params.get("history"), default=0, maximum=5)
        result = await self.client.call(
            method="history.get",
            params={
                "output": "extend",
                "history": history_type,
                "itemids": [itemid],
                "sortfield": "clock",
                "sortorder": "DESC",
                "limit": limit,
            },
            config=config,
            token=token,
            timeout_ms=timeout_ms,
        )
        values = [_history_to_dict(item) for item in _as_list(result)[:limit]]
        return _success(
            capability,
            {
                "itemid": itemid,
                "value_count": len(values),
                "values": values,
                "summary": f"Zabbix metric history points: {len(values)}",
            },
        )


def _integration_config(params: Dict[str, Any]) -> Dict[str, Any]:
    value = params.get("integration_config") or params.get("_integration_config")
    return dict(value) if isinstance(value, dict) else {}


def _credential_token(params: Dict[str, Any]) -> str | None:
    value = params.get("credentials_ref") or params.get("_credentials_ref") or params.get("credentials")
    if isinstance(value, dict):
        for key in ("api_token", "token", "auth_token", "value", "secret"):
            raw = str(value.get(key) or "").strip()
            if raw:
                return raw
        return None
    raw = str(value or "").strip()
    if not raw or raw.startswith("vault://"):
        return None
    return raw


def _mapped_value(params: Dict[str, Any], *keys: str) -> str | None:
    mapping = params.get("mapping") or params.get("_mapping")
    candidates: list[Any] = []
    if isinstance(mapping, dict):
        candidates.append(mapping)
        nested = mapping.get("zabbix.host")
        if isinstance(nested, dict):
            candidates.append(nested)
        nested = mapping.get("zabbix.item")
        if isinstance(nested, dict):
            candidates.append(nested)
    candidates.append(params)
    for source in candidates:
        if not isinstance(source, dict):
            continue
        for key in keys:
            raw = str(source.get(key) or "").strip()
            if raw:
                return raw
    return None


def _zabbix_url(config: Dict[str, Any]) -> str:
    url = str(config.get("url") or config.get("endpoint_url") or config.get("api_url") or "").strip()
    if not url:
        raise ZabbixProviderError("ZABBIX_CONFIG_INVALID", "Zabbix API URL is missing")
    return url


def _timeout_sec(config: Dict[str, Any], timeout_ms: int | None) -> int:
    if timeout_ms:
        return max(1, min(MAX_TIMEOUT_SEC, (int(timeout_ms) + 999) // 1000))
    return _bounded_int(config.get("timeout_sec"), default=DEFAULT_TIMEOUT_SEC, maximum=MAX_TIMEOUT_SEC)


def _bounded_int(value: Any, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(maximum, parsed))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _problem_to_dict(item: Any) -> Dict[str, Any]:
    row = item if isinstance(item, dict) else {}
    hosts = []
    for host in _as_list(row.get("hosts"))[:3]:
        if isinstance(host, dict):
            hosts.append(
                {
                    "hostid": str(host.get("hostid") or ""),
                    "host": str(host.get("host") or host.get("name") or ""),
                }
            )
    return {
        "eventid": str(row.get("eventid") or ""),
        "objectid": str(row.get("objectid") or ""),
        "name": str(row.get("name") or ""),
        "severity": str(row.get("severity") or ""),
        "clock": str(row.get("clock") or ""),
        "hosts": hosts,
    }


def _host_to_dict(item: Any) -> Dict[str, Any]:
    row = item if isinstance(item, dict) else {}
    return {
        "hostid": str(row.get("hostid") or ""),
        "host": str(row.get("host") or ""),
        "name": str(row.get("name") or ""),
        "status": str(row.get("status") or ""),
        "available": str(row.get("available") or ""),
    }


def _history_to_dict(item: Any) -> Dict[str, Any]:
    row = item if isinstance(item, dict) else {}
    return {
        "itemid": str(row.get("itemid") or ""),
        "clock": str(row.get("clock") or ""),
        "value": str(row.get("value") or ""),
    }


def _success(capability: CapabilityDescriptor, output: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "success",
        "capability_id": capability.id,
        "provider_id": capability.provider_id,
        "integration_key": capability.integration_key,
        "output": output,
        "summary": str(output.get("summary") or "Zabbix query completed"),
        "evidence": capability.evidence,
    }


def _error(
    capability: CapabilityDescriptor,
    error_code: str,
    message: str,
    *,
    details: Any = None,
) -> Dict[str, Any]:
    payload = {
        "status": "error",
        "error_code": error_code,
        "capability_id": capability.id,
        "provider_id": capability.provider_id,
        "integration_key": capability.integration_key,
        "message": message,
        "evidence": capability.evidence,
    }
    if details is not None:
        payload["details"] = details
    return payload
