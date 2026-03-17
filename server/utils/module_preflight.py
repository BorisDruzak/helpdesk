"""
Module ZIP preflight validation.
"""

import io
import json
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from utils.module_manifest import DEFAULT_ENTRYPOINT, attach_smoke_result, normalize_manifest

MAX_ZIP_ENTRIES = 10_000


def _find_manifest_name(namelist: List[str]) -> Optional[str]:
    if "manifest.json" in namelist:
        return "manifest.json"
    candidates = [name for name in namelist if name.rstrip("/").endswith("manifest.json")]
    return candidates[0] if candidates else None


def _validate_entry_names(namelist: List[str]) -> List[str]:
    errors: List[str] = []
    for name in namelist:
        normalized = name.rstrip("/")
        if ".." in normalized or normalized.startswith("/"):
            errors.append(f"Invalid entry name: {name}")
            break
        if normalized.startswith("."):
            errors.append(f"Hidden or invalid entry: {name}")
            break
    return errors


def _validate_entrypoint(zip_bytes: bytes, entrypoint: str) -> List[str]:
    errors: List[str] = []
    if ":" in entrypoint:
        parts = entrypoint.split(":", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            errors.append("manifest.json: entrypoint must be 'module:function' or a filename")
        return errors

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        all_names = set(zf.namelist())
    found = any(name == entrypoint or name.rstrip("/") == entrypoint or name.endswith("/" + entrypoint) for name in all_names)
    if not found:
        errors.append(f"manifest.json: entrypoint file '{entrypoint}' not found in archive")
    return errors


def preflight_module_zip(zip_bytes: bytes) -> Tuple[bool, Dict[str, Any], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Returns (ok, validation_json, manifest_json, manifest_summary).
    """
    if not zip_bytes or len(zip_bytes) < 22:
        return False, {
            "preflight_status": "failed",
            "validation_status": "failed",
            "legacy_manifest": False,
            "warnings": [],
            "errors": {"manifest": ["ZIP file is empty or too small"], "tools": [], "metadata": [], "smoke": []},
        }, None, None

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            namelist = zf.namelist()
    except zipfile.BadZipFile as exc:
        return False, {
            "preflight_status": "failed",
            "validation_status": "failed",
            "legacy_manifest": False,
            "warnings": [],
            "errors": {"manifest": [f"Invalid ZIP: {exc}"], "tools": [], "metadata": [], "smoke": []},
        }, None, None

    if len(namelist) > MAX_ZIP_ENTRIES:
        return False, {
            "preflight_status": "failed",
            "validation_status": "failed",
            "legacy_manifest": False,
            "warnings": [],
            "errors": {"manifest": [f"ZIP contains too many entries (>{MAX_ZIP_ENTRIES})"], "tools": [], "metadata": [], "smoke": []},
        }, None, None

    entry_errors = _validate_entry_names(namelist)
    manifest_name = _find_manifest_name(namelist)
    if not manifest_name:
        entry_errors.append("manifest.json not found in archive root")
    if entry_errors:
        return False, {
            "preflight_status": "failed",
            "validation_status": "failed",
            "legacy_manifest": False,
            "warnings": [],
            "errors": {"manifest": entry_errors, "tools": [], "metadata": [], "smoke": []},
        }, None, None

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            raw_manifest = zf.read(manifest_name)
    except Exception as exc:
        return False, {
            "preflight_status": "failed",
            "validation_status": "failed",
            "legacy_manifest": False,
            "warnings": [],
            "errors": {"manifest": [f"Failed to read manifest.json: {exc}"], "tools": [], "metadata": [], "smoke": []},
        }, None, None

    try:
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except UnicodeDecodeError as exc:
        return False, {
            "preflight_status": "failed",
            "validation_status": "failed",
            "legacy_manifest": False,
            "warnings": [],
            "errors": {"manifest": [f"manifest.json must be UTF-8: {exc}"], "tools": [], "metadata": [], "smoke": []},
        }, None, None
    except json.JSONDecodeError as exc:
        return False, {
            "preflight_status": "failed",
            "validation_status": "failed",
            "legacy_manifest": False,
            "warnings": [],
            "errors": {"manifest": [f"Invalid JSON in manifest.json: {exc}"], "tools": [], "metadata": [], "smoke": []},
        }, None, None

    manifest_json, validation_json, manifest_summary = normalize_manifest(manifest)
    if manifest_json:
        validation_json["errors"]["manifest"].extend(
            _validate_entrypoint(zip_bytes, manifest_json.get("entrypoint") or DEFAULT_ENTRYPOINT)
        )
        if any(validation_json["errors"].values()):
            validation_json["preflight_status"] = "failed"
            validation_json["validation_status"] = "failed"
            return False, validation_json, None, None
        return True, validation_json, manifest_json, manifest_summary

    return False, validation_json, None, None


def apply_smoke_validation(
    manifest_json: Optional[Dict[str, Any]],
    validation_json: Dict[str, Any],
    smoke_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return attach_smoke_result(manifest_json, validation_json, smoke_result)
