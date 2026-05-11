"""
Модуль для сбора диагностических логов.

Собирает логи из различных источников (системные логи, логи приложений,
journalctl на Linux) и упаковывает их в zip-архив для передачи.
"""

import os
import platform
import time
import fnmatch
import zipfile
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Literal, List

from pydantic import BaseModel
from loguru import logger

from pc_agent.config.config_loader import get_config
from pc_agent.core.runtime_paths import resolve_data_root, resolve_logs_dir

try:
    from modules.base_module import BaseCollector
except ImportError:
    from pc_agent.modules.base_module import BaseCollector

try:
    from core.registry import exposed_tool
except ImportError:
    from pc_agent.core.registry import exposed_tool


def _agent_app_log_sources() -> List[str]:
    try:
        from pc_agent.config.config_loader import get_config_base

        data_root = get_config_base() or resolve_data_root()
    except Exception:
        data_root = resolve_data_root()
    return [str(resolve_logs_dir(Path(data_root)).resolve())]


class DiagLogsCollectParams(BaseModel):
    """Параметры для сбора диагностических логов."""
    mode: Literal["preset", "paths"] = "preset"
    preset: Literal["system", "app", "all"] = "system"
    paths: List[str] = []
    include_journal: bool = True
    tail_lines: int = 2000
    max_total_bytes: int = 10_000_000
    max_files: int = 50
    redact_patterns: List[str] = []
    include_globs: List[str] = []
    exclude_globs: List[str] = []


class DiagLogsModule(BaseCollector):
    """
    Коллектор диагностических логов.
    
    Собирает логи из различных источников и упаковывает их в zip-архив.
    Поддерживает различные режимы сбора: preset (системные/приложения/все)
    или paths (указанные пути).
    """
    
    @property
    def name(self) -> str:
        """Возвращает уникальное имя модуля."""
        return "diag_logs"
    
    @exposed_tool(
        name="diag.logs.collect",
        description="Collect diagnostic logs into a zip artifact (admin only).",
        risk_level="sensitive_read",
        capabilities=["read:fs", "read:logs"],
        params_model=DiagLogsCollectParams,
        metadata_risk_level="sensitive_read",
        metadata_scopes=["logs"],
        metadata_requires_consent=True,
        execution={
            "target": "agent_builtin",
            "requires_device": True,
            "requires_agent_online": True,
            "supports_auto_install": False,
            "requires_integration": False,
        },
        deployment={
            "provider_id": "diag_logs",
            "install_required_on_agent": False,
            "package_type": "builtin",
        },
        safety={"side_effects": False, "requires_consent": True, "idempotent": True},
        evidence={
            "produces_evidence": True,
            "kind": "logs.bundle",
            "domain": "logs",
            "perspective": "endpoint",
            "passport_eligible": True,
        },
        artifacts={"may_produce_artifacts": True, "artifact_kinds": ["logs_zip"]},
    )
    async def collect(self, **params) -> Dict[str, Any]:
        with self.trace_span("tool.entry", details={"tool_name": "diag.logs.collect"}):
            return await self._collect_impl(**params)

    async def _collect_impl(self, **params) -> Dict[str, Any]:
        """
        Асинхронный сбор диагностических логов.
        
        Args:
            **params: Параметры сбора логов (см. DiagLogsCollectParams)
        
        Returns:
            Dict[str, Any]: Словарь с информацией о собранных логах
        """
        # Вычисляем os_name и epoch
        os_name = platform.system().lower()
        epoch = int(time.time())
        
        # Определяем temp_dir (используем тот же подход, что в screen.py)
        temp_dir = Path(get_config().paths.data_dir) / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Параметры по умолчанию
        mode = params.get("mode", "preset")
        preset = params.get("preset", "system")
        paths = params.get("paths", [])
        max_total_bytes = params.get("max_total_bytes", 10_000_000)
        max_files = params.get("max_files", 50)
        include_globs = params.get("include_globs", [])
        exclude_globs = params.get("exclude_globs", [])
        include_journal = params.get("include_journal", True)
        tail_lines = params.get("tail_lines", 2000)
        
        # Определяем исходные пути
        if mode == "paths":
            sources = paths
        else:
            # Preset mode
            if os_name == "linux":
                system_paths = [
                    "/var/log", "/var/log/syslog", "/var/log/messages",
                    "/var/log/auth.log", "/var/log/secure", "/var/log/dmesg",
                    "/var/log/kern.log"
                ]
            elif os_name == "windows":
                system_paths = [
                    "C:\\Windows\\Logs",
                    "C:\\Windows\\System32\\LogFiles"
                ]
            else:
                system_paths = []
            
            app_paths = _agent_app_log_sources()
            
            if preset == "system":
                sources = system_paths
            elif preset == "app":
                sources = app_paths
            elif preset == "all":
                sources = system_paths + app_paths
            else:
                sources = system_paths
        self.trace_event(
            "collect.resolve_sources",
            details={"mode": mode, "preset": preset, "sources_count": len(sources)},
        )
        
        # Определяем allowlist dirs
        if os_name == "linux":
            allowlist_dirs = ["/var/log", *_agent_app_log_sources()]
        elif os_name == "windows":
            allowlist_dirs = [
                "C:\\Windows\\Logs",
                "C:\\Windows\\System32\\LogFiles",
                "C:\\ProgramData",
                *_agent_app_log_sources(),
            ]
        else:
            allowlist_dirs = []
        
        # Deny patterns
        deny_patterns = [".ssh", "id_rsa", "id_ed25519", "shadow", "secrets", "passwd"]
        
        # Функция проверки пути на allowlist
        def is_allowed_path(path_str: str) -> bool:
            """Проверяет, разрешен ли путь по allowlist."""
            try:
                path = Path(path_str).resolve()
                path_str_normalized = str(path).lower()
            except (OSError, ValueError):
                return False
            
            # Проверка deny patterns
            for pattern in deny_patterns:
                if pattern.lower() in path_str_normalized:
                    return False
            
            # Проверка allowlist для директорий
            if path.is_dir():
                for allowed_dir in allowlist_dirs:
                    try:
                        allowed_path = Path(allowed_dir).resolve()
                        if str(path) == str(allowed_path) or str(path).startswith(str(allowed_path) + os.sep):
                            return True
                    except (OSError, ValueError):
                        continue
                return False
            
            # Для файлов проверяем, находится ли он в allowlist директории
            for allowed_dir in allowlist_dirs:
                try:
                    allowed_path = Path(allowed_dir).resolve()
                    if str(path).startswith(str(allowed_path) + os.sep):
                        return True
                except (OSError, ValueError):
                    continue
            
            return False
        
        # Функция проверки glob паттернов
        def matches_globs(path_str: str, include_globs: List[str], exclude_globs: List[str]) -> bool:
            """Проверяет соответствие пути glob паттернам."""
            path_lower = path_str.lower()
            
            # Если задан include_globs, путь должен совпадать хотя бы с одним
            if include_globs:
                if not any(fnmatch.fnmatch(path_lower, glob.lower()) or 
                          fnmatch.fnmatch(Path(path_str).name.lower(), glob.lower())
                          for glob in include_globs):
                    return False
            
            # Если задан exclude_globs, путь не должен совпадать ни с одним
            if exclude_globs:
                if any(fnmatch.fnmatch(path_lower, glob.lower()) or 
                      fnmatch.fnmatch(Path(path_str).name.lower(), glob.lower())
                      for glob in exclude_globs):
                    return False
            
            return True
        
        # Собираем файлы
        collected_files = []
        collected_bytes = 0
        file_count = 0
        truncated = False
        
        for source in sources:
            if truncated:
                break
            
            source_path = Path(source)
            if not source_path.exists():
                logger.warning(f"[{self.name}] Путь не существует: {source}")
                continue
            
            # Проверяем allowlist
            if not is_allowed_path(str(source_path)):
                logger.warning(f"[{self.name}] Путь не разрешен по allowlist: {source}")
                continue
            
            if source_path.is_file():
                # Это файл - добавляем его
                if not matches_globs(str(source_path), include_globs, exclude_globs):
                    continue
                
                if file_count >= max_files:
                    truncated = True
                    break
                
                try:
                    file_size = source_path.stat().st_size
                    if collected_bytes + file_size > max_total_bytes:
                        truncated = True
                        break
                    
                    collected_files.append((source_path, None))  # None означает нет базовой директории для относительного пути
                    collected_bytes += file_size
                    file_count += 1
                except (OSError, ValueError) as e:
                    logger.warning(f"[{self.name}] Не удалось получить размер файла {source_path}: {e}")
                    continue
            
            elif source_path.is_dir():
                # Это директория - рекурсивно обходим
                try:
                    for root, dirs, files in os.walk(str(source_path)):
                        if truncated:
                            break
                        
                        # Фильтруем директории (не заходим в запрещенные)
                        dirs[:] = [d for d in dirs if is_allowed_path(os.path.join(root, d))]
                        
                        for file in files:
                            if file_count >= max_files:
                                truncated = True
                                break
                            
                            file_path = Path(root) / file
                            file_str = str(file_path)
                            
                            # Проверяем glob паттерны
                            if not matches_globs(file_str, include_globs, exclude_globs):
                                continue
                            
                            # Проверяем allowlist
                            if not is_allowed_path(file_str):
                                continue
                            
                            try:
                                file_size = file_path.stat().st_size
                                if collected_bytes + file_size > max_total_bytes:
                                    truncated = True
                                    break
                                
                                collected_files.append((file_path, source_path))
                                collected_bytes += file_size
                                file_count += 1
                            except (OSError, ValueError) as e:
                                logger.warning(f"[{self.name}] Ошибка при обработке файла {file_path}: {e}")
                                continue
                except (OSError, ValueError) as e:
                    logger.warning(f"[{self.name}] Ошибка при обходе директории {source_path}: {e}")
                    continue

        self.trace_event(
            "collect.files_enumerated",
            details={
                "file_count": file_count,
                "collected_bytes": collected_bytes,
                "truncated": truncated,
            },
        )
        
        # Создаем zip файл
        zip_path = temp_dir / f"diagnostics_logs_{epoch}.zip"
        max_read_bytes = 512 * 1024  # 512 KB
        
        tail_applied_count = 0
        
        # Переменные для journalctl
        journal_available = False
        journal_included = False
        journal_error = None
        
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for file_path, base_dir in collected_files:
                try:
                    file_size = file_path.stat().st_size
                    
                    # Определяем имя файла в zip
                    if base_dir is None:
                        # Одиночный файл
                        if os_name == "linux":
                            arcname = f"var_log/{file_path.name}"
                        else:  # windows
                            arcname = f"windows_logs/{file_path.name}"
                    else:
                        # Файл из директории - сохраняем относительный путь
                        try:
                            rel_path = file_path.relative_to(base_dir)
                            if os_name == "linux":
                                arcname = f"var_log/{rel_path}"
                            else:  # windows
                                arcname = f"windows_logs/{rel_path}"
                        except ValueError:
                            # Если не получается вычислить относительный путь
                            arcname = f"logs/{file_path.name}"
                    
                    # Читаем файл (tail для больших файлов)
                    if file_size > max_read_bytes:
                        # Читаем последние max_read_bytes байт
                        with open(file_path, "rb") as f:
                            f.seek(max(0, file_size - max_read_bytes))
                            content = f.read()
                        zipf.writestr(f"{arcname}.tail", content)
                        tail_applied_count += 1
                    else:
                        # Читаем файл целиком
                        zipf.write(file_path, arcname)
                
                except (OSError, ValueError, zipfile.BadZipFile) as e:
                    logger.warning(f"[{self.name}] Ошибка при добавлении файла {file_path} в zip: {e}")
                    continue
            
            # Добавляем journalctl логи (Linux)
            if os_name.startswith("linux") and shutil.which("journalctl"):
                journal_available = True
                if include_journal:
                    try:
                        cmd = ["journalctl", "--no-pager", "-n", str(tail_lines)]
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            timeout=15,
                            check=False
                        )
                        
                        if result.returncode == 0:
                            # Декодируем stdout с обработкой ошибок
                            journal_content = result.stdout.decode("utf-8", errors="replace")
                            journal_bytes = journal_content.encode("utf-8")
                            
                            # Ограничиваем размер, если лимит включён
                            remaining_bytes = max_total_bytes - collected_bytes
                            if remaining_bytes > 0 and len(journal_bytes) > remaining_bytes:
                                # Обрезаем до оставшегося лимита
                                journal_content = journal_content[:remaining_bytes]
                                journal_bytes = journal_content.encode("utf-8")
                            
                            # Добавляем в zip
                            zipf.writestr("journal/journal_tail.txt", journal_bytes)
                            journal_included = True
                            collected_bytes += len(journal_bytes)
                        else:
                            journal_error = f"journalctl returned code {result.returncode}: {result.stderr.decode('utf-8', errors='replace')[:200]}"
                            logger.warning(f"[{self.name}] {journal_error}")
                    except subprocess.TimeoutExpired:
                        journal_error = "journalctl timeout (15s)"
                        logger.warning(f"[{self.name}] {journal_error}")
                    except Exception as e:
                        journal_error = f"journalctl error: {str(e)[:200]}"
                        logger.warning(f"[{self.name}] {journal_error}")
        
        logger.info(f"[{self.name}] Собрано файлов: {file_count}, байт: {collected_bytes}, truncated: {truncated}")
        self.trace_event(
            "collect.archive_ready",
            summary="diagnostic logs archive created",
            details={
                "file_count": file_count,
                "collected_bytes": collected_bytes,
                "journal_included": journal_included,
                "tail_applied_count": tail_applied_count,
            },
        )
        
        # Формируем observations
        providers_used = ["file"]
        if journal_included:
            providers_used.append("journalctl")
        
        observations = {
            "os": platform.system(),
            "mode": mode,
            "preset": preset,
            "selected_sources": sources,
            "providers_used": providers_used,
            "collected_files": file_count,
            "collected_bytes": collected_bytes,
            "truncated": truncated,
            "tail_applied": tail_applied_count > 0,
            "journal_available": journal_available,
            "journal_included": journal_included,
            "journal_lines": tail_lines,
            "_artifacts": [{
                "kind": "logs_zip",
                "local_path": str(zip_path.resolve()),
                "name": zip_path.name,
                "mime": "application/zip"
            }],
            "_cleanup_paths": [str(zip_path.resolve())]
        }
        
        # Добавляем journal_error, если есть
        if journal_error:
            observations["journal_error"] = journal_error
        
        return observations
