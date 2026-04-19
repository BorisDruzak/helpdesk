"""
Установка версии агента из архива: распаковка с защитой от path traversal, verify, backup/rollback БД.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Tuple
import os
import sys

# Без зависимостей от pc_agent при импорте (launcher может быть отдельным бинарем)

UPDATE_HISTORY_LIMIT = 100
DOWNLOAD_RETENTION_LIMIT = 8
DB_BACKUP_RETENTION_LIMIT = 10


def _record_launcher_update_trace(
    *,
    data_root: Path,
    operation_id: Any,
    stage: str,
    status: str,
    summary: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    try:
        from pc_agent.core.action_trace import record_external_action_trace

        record_external_action_trace(
            data_root=data_root,
            source="launcher",
            action="agent.update.apply",
            category="update",
            operation_id=operation_id,
            request_id=operation_id,
            tool_name="update",
            stage=stage,
            status=status,
            summary=summary,
            details=details or {},
        )
    except Exception:
        # Launcher update flow must keep running even if the observer bridge is unavailable.
        return


def _safe_join(base: Path, path: str) -> Path:
    """Проверка path traversal: итоговый путь должен быть внутри base."""
    resolved = (base / path).resolve()
    base_resolved = base.resolve()
    if not str(resolved).startswith(str(base_resolved)):
        raise ValueError(f"Path traversal not allowed: {path}")
    return resolved


def extract_artifact(archive_type: str, artifact_path: Path, staging_dir: Path) -> None:
    """
    Распаковывает архив в staging_dir. Защита от zip-slip: все пути внутри staging_dir.

    :param archive_type: "zip" или "tar.gz"
    :param artifact_path: путь к файлу архива
    :param staging_dir: директория для распаковки (создаётся)
    """
    staging_dir = staging_dir.resolve()
    staging_dir.mkdir(parents=True, exist_ok=True)
    if archive_type == "zip":
        with zipfile.ZipFile(artifact_path, "r") as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/").lstrip("/")
                if not name:
                    continue
                if info.is_dir():
                    target = _safe_join(staging_dir, name.rstrip("/"))
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target = _safe_join(staging_dir, name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src:
                        with open(target, "wb") as dst:
                            dst.write(src.read())
    elif archive_type in ("tar.gz", "tgz"):
        with tarfile.open(artifact_path, "r:gz") as tf:
            for member in tf.getmembers():
                name = member.name.replace("\\", "/").lstrip("/")
                if not name:
                    continue
                dest = _safe_join(staging_dir, name)
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if member.isfile():
                        with tf.extractfile(member) as src:
                            if src:
                                with open(dest, "wb") as dst:
                                    dst.write(src.read())
                    # symlinks etc. можно пропустить или обработать при необходимости
    else:
        raise ValueError(f"Unsupported archive_type: {archive_type}")


def _find_agent_binary(version_dir: Path) -> Path:
    """Ищет исполняемый файл агента в version_dir (или в единственной поддиректории)."""
    if os.name == "nt":
        exe_name = "pc_agent.exe"
    else:
        exe_name = "pc_agent"
    direct = version_dir / exe_name
    if direct.exists():
        return direct
    # Одна поддиректория (onedir output)
    subdirs = [d for d in version_dir.iterdir() if d.is_dir()]
    if len(subdirs) == 1:
        candidate = subdirs[0] / exe_name
        if candidate.exists():
            return candidate
    # Перебор поддиректорий
    for d in version_dir.rglob(exe_name):
        if d.is_file():
            return d
    raise FileNotFoundError(f"Agent binary not found in {version_dir}")


def backup_storage_db(data_root: Path, db_backups_dir: Path) -> Path:
    """Копирует storage.db в db_backups_dir с timestamp. Возвращает путь к backup."""
    db_backups_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_root / "storage.db"
    if not db_path.exists():
        return db_path
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = db_backups_dir / f"storage.db.{ts}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def _read_history(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []
    try:
        raw = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _write_history(history_path: Path, items: list[dict[str, Any]]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = items[-UPDATE_HISTORY_LIMIT:]
    history_path.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_history(history_path: Path, entry: dict[str, Any]) -> None:
    history = _read_history(history_path)
    history.append(entry)
    _write_history(history_path, history)


def _archive_failed_pending(
    pending_path: Path,
    updates_dir: Path,
    *,
    payload: Optional[dict[str, Any]],
    error_message: str,
) -> None:
    archive_path = updates_dir / "last_failed_pending_update.json"
    raw_pending = None
    try:
        raw_pending = pending_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raw_pending = None
    archive_payload = {
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "error_message": error_message,
        "pending_payload": payload or {},
        "pending_text": raw_pending,
    }
    updates_dir.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(json.dumps(archive_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        pending_path.unlink()
    except Exception:
        pass


def _prune_paths(paths: list[Path], keep: int) -> None:
    if keep < 0:
        keep = 0
    existing = [path for path in paths if path.exists()]
    existing.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in existing[keep:]:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except Exception:
            pass


def _cleanup_update_artifacts(updates_dir: Path, artifact_path: Optional[Path]) -> None:
    if artifact_path and artifact_path.exists():
        try:
            artifact_path.unlink(missing_ok=True)
        except Exception:
            pass
    downloads_dir = updates_dir / "downloads"
    db_backups_dir = updates_dir / "db_backups"
    if downloads_dir.exists():
        _prune_paths(list(downloads_dir.glob("*")), keep=DOWNLOAD_RETENTION_LIMIT)
    if db_backups_dir.exists():
        _prune_paths(list(db_backups_dir.glob("storage.db.*")), keep=DB_BACKUP_RETENTION_LIMIT)


def run_verify(
    binary_path: Path,
    data_root: Path,
    install_root: Path,
    timeout_sec: int = 90,
) -> bool:
    """
    Запускает агент с --verify. Возвращает True при exit code 0.
    """
    env = os.environ.copy()
    env["PC_AGENT_DATA_DIR"] = str(data_root)
    env["PC_AGENT_INSTALL_ROOT"] = str(install_root)
    try:
        result = subprocess.run(
            [str(binary_path), "--verify"],
            env=env,
            cwd=str(binary_path.parent),
            timeout=timeout_sec,
            capture_output=True,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def apply_update(
    install_root: Path,
    data_root: Path,
    pending_path: Path,
    log_message: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """
    Читает pending_update.json, распаковывает артефакт, делает backup БД, запускает verify,
    при успехе обновляет current.json и update_history; при провале — восстанавливает БД.

    :return: (success, message)
    """
    def log(msg: str) -> None:
        if log_message:
            log_message(msg)

    updates_dir = data_root / "updates"
    history_path = updates_dir / "update_history.json"
    if not pending_path.exists():
        return False, "pending_update.json not found"
    try:
        payload = json.loads(pending_path.read_text(encoding="utf-8"))
    except Exception as e:
        _archive_failed_pending(
            pending_path,
            updates_dir,
            payload=None,
            error_message=f"Invalid pending_update.json: {e}",
        )
        return False, f"Invalid pending_update.json: {e}"
    version = payload.get("version")
    archive_type = payload.get("archive_type", "zip")
    artifact_path = Path(payload.get("artifact_path", ""))
    operation_id = payload.get("operation_id")
    versions_dir = install_root / "versions"
    current_path = install_root / "current.json"
    db_backups_dir = updates_dir / "db_backups"
    staging = install_root / "versions" / "_staging" / str(version or "_unknown")

    _record_launcher_update_trace(
        data_root=data_root,
        operation_id=operation_id,
        stage="start",
        status="started",
        summary="launcher started applying update",
        details={
            "version": version,
            "archive_type": archive_type,
            "artifact_path": str(artifact_path),
            "requested_by": payload.get("requested_by"),
            "requested_reason": payload.get("requested_reason"),
        },
    )

    def fail_update(reason: str, message: str) -> Tuple[bool, str]:
        _record_launcher_update_trace(
            data_root=data_root,
            operation_id=operation_id,
            stage="finish",
            status="error",
            summary=message,
            details={
                "reason": reason,
                "version": version,
                "archive_type": archive_type,
                "artifact_path": str(artifact_path),
            },
        )
        entry = {
            "version": version,
            "success": False,
            "at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "message": message,
            "operation_id": payload.get("operation_id"),
            "requested_by": payload.get("requested_by"),
            "requested_reason": payload.get("requested_reason"),
            "target": payload.get("target"),
            "channel": payload.get("channel"),
        }
        _append_history(history_path, entry)
        _archive_failed_pending(pending_path, updates_dir, payload=payload, error_message=message)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        return False, message

    if not version or not artifact_path.exists():
        return fail_update("invalid_payload", "Missing version or artifact_path")

    # Очистить staging
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        extract_artifact(archive_type, artifact_path, staging)
        _record_launcher_update_trace(
            data_root=data_root,
            operation_id=operation_id,
            stage="extract",
            status="ok",
            summary="update artifact extracted",
            details={"staging_path": str(staging)},
        )
    except Exception as e:
        log(f"Extract failed: {e}")
        return fail_update("extract_failed", str(e))

    # Backup DB
    backup_storage_db(data_root, db_backups_dir)
    _record_launcher_update_trace(
        data_root=data_root,
        operation_id=operation_id,
        stage="backup",
        status="ok",
        summary="database backup completed",
        details={"backup_dir": str(db_backups_dir)},
    )
    log("DB backup done")

    # Verify new version
    try:
        binary_path = _find_agent_binary(staging)
    except FileNotFoundError as e:
        log(str(e))
        return fail_update("binary_not_found", "Agent binary not found in extracted archive")
    if not run_verify(binary_path, data_root, install_root):
        log("Verify failed, rolling back DB")
        # Restore DB from latest backup
        backups = sorted(db_backups_dir.glob("storage.db.*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if backups:
            shutil.copy2(backups[0], data_root / "storage.db")
        return fail_update("verify_failed", "Verify failed")
    _record_launcher_update_trace(
        data_root=data_root,
        operation_id=operation_id,
        stage="verify",
        status="ok",
        summary="launcher verify succeeded",
        details={"binary_path": str(binary_path)},
    )
    # Publish: move staging -> versions/<version>
    previous = None
    if current_path.exists():
        try:
            current = json.loads(current_path.read_text(encoding="utf-8"))
            previous = current.get("version")
        except Exception:
            previous = None
    try:
        target_version_dir = versions_dir / version
        if target_version_dir.exists():
            shutil.rmtree(target_version_dir, ignore_errors=True)
        shutil.move(str(staging), str(target_version_dir))
        current_path.write_text(
            json.dumps({"version": version, "previous": previous or version}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _record_launcher_update_trace(
            data_root=data_root,
            operation_id=operation_id,
            stage="publish",
            status="ok",
            summary="launcher published new version",
            details={"version_dir": str(target_version_dir), "previous_version": previous},
        )
    except Exception as e:
        log(f"Publish failed: {e}")
        return fail_update("publish_failed", f"Publish failed: {e}")
    _append_history(
        history_path,
        {
            "version": version,
            "success": True,
            "at": datetime.now(timezone.utc).isoformat(),
            "operation_id": payload.get("operation_id"),
            "requested_by": payload.get("requested_by"),
            "requested_reason": payload.get("requested_reason"),
            "target": payload.get("target"),
            "channel": payload.get("channel"),
            "previous_version": previous,
        },
    )
    # Remove or move pending
    try:
        pending_path.unlink()
    except Exception:
        pass
    _cleanup_update_artifacts(updates_dir, artifact_path)
    _record_launcher_update_trace(
        data_root=data_root,
        operation_id=operation_id,
        stage="finish",
        status="ok",
        summary="update applied successfully",
        details={"version": version, "previous_version": previous},
    )
    log(f"Update to {version} applied")
    return True, version
