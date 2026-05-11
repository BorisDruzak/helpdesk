from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from pc_agent.config.config_loader import get_config
from pc_agent.remote_assist.thread import RemoteAssistThread as BundledRemoteAssistThread


REMOTE_ASSIST_RUNTIME_MODULE = "remote_assist_runtime"


RemoteAssistThreadFactory = Callable[..., Any]


def create_remote_assist_thread(
    *,
    signaling_url: str,
    token: str,
    ice_servers: list[dict[str, Any]] | None = None,
    mode: str = "view_only",
    media: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
    parent: Any = None,
    data_dir: str | Path | None = None,
) -> Any:
    """Create a Remote Assist thread from managed runtime module or fallback.

    The base agent owns consent, GUI lifecycle, auth and fallback. The managed
    runtime module may replace the WebRTC/capture/control implementation, but it
    must expose `create_remote_assist_thread(**kwargs)`.
    """

    kwargs = {
        "signaling_url": signaling_url,
        "token": token,
        "ice_servers": ice_servers,
        "mode": mode,
        "media": media,
        "features": features,
        "parent": parent,
    }
    factory = load_remote_assist_runtime_factory(data_dir=data_dir)
    if factory is not None:
        try:
            thread = factory(**kwargs)
            logger.info("Remote Assist runtime module loaded: module={}", REMOTE_ASSIST_RUNTIME_MODULE)
            return thread
        except Exception as exc:
            logger.warning("Remote Assist runtime module failed, using bundled fallback: {}", exc)
    return BundledRemoteAssistThread(**kwargs)


def load_remote_assist_runtime_factory(*, data_dir: str | Path | None = None) -> RemoteAssistThreadFactory | None:
    module_path = get_active_remote_assist_runtime_path(data_dir=data_dir)
    if module_path is None:
        return None
    module_file = module_path / "module.py"
    if not module_file.exists():
        logger.warning("Remote Assist runtime module has no module.py: {}", module_path)
        return None

    agent_dir = Path(__file__).resolve().parents[1]
    project_root = agent_dir.parent
    for index, path in enumerate((module_path, agent_dir, project_root)):
        path_str = str(path.resolve())
        if path_str in sys.path:
            sys.path.remove(path_str)
        sys.path.insert(index, path_str)

    import_key = f"_pcagent_runtime_{REMOTE_ASSIST_RUNTIME_MODULE}_{abs(hash(str(module_path.resolve())))}"
    sys.modules.pop(import_key, None)
    spec = importlib.util.spec_from_file_location(import_key, module_file)
    if spec is None or spec.loader is None:
        logger.warning("Remote Assist runtime module cannot create import spec: {}", module_file)
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[import_key] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        logger.warning("Remote Assist runtime module import failed: path={} error={}", module_file, exc)
        sys.modules.pop(import_key, None)
        return None

    factory = getattr(module, "create_remote_assist_thread", None)
    if not callable(factory):
        logger.warning("Remote Assist runtime module has no callable create_remote_assist_thread: {}", module_file)
        return None
    return factory


def get_active_remote_assist_runtime_path(*, data_dir: str | Path | None = None) -> Path | None:
    root = _resolve_data_dir(data_dir)
    module_dir = root / "modules_store" / REMOTE_ASSIST_RUNTIME_MODULE
    current_path = module_dir / "current.json"
    if not current_path.exists():
        return None
    try:
        current = json.loads(current_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Remote Assist runtime current.json is invalid: path={} error={}", current_path, exc)
        return None
    version = str(current.get("version") or "").strip()
    if not version:
        return None
    version_path = module_dir / version
    manifest_path = version_path / "manifest.json"
    if not version_path.exists() or not manifest_path.exists():
        logger.warning("Remote Assist runtime active version is missing: {}", version_path)
        return None
    return version_path


def _resolve_data_dir(data_dir: str | Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    return Path(get_config().paths.data_dir)
