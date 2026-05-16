import asyncio
import pathlib
from typing import List, Optional

from pc_agent.core.artifacts import ArtifactIntent, ArtifactManager
from pc_agent.core.tool_response import ErrorInfo, ToolData, ToolMeta, ToolResponse, fail, ok, partial
from pc_agent.network.uploader import get_uploader
from pc_agent.core.orchestrator_shared import logger


async def handle_collect(orchestrator, modules: Optional[List[str]], meta: ToolMeta) -> ToolResponse:
    try:
        warnings = []
        if modules:
            collectors_to_run = [module for module in orchestrator.loaded_modules if module.name in modules]
            missing_modules = set(modules) - {module.name for module in collectors_to_run}
            if missing_modules:
                warning_msg = f"Модули не найдены: {missing_modules}"
                logger.warning(warning_msg)
                warnings.append(warning_msg)
        else:
            collectors_to_run = orchestrator.loaded_modules

        if not collectors_to_run:
            return fail(code="COLLECT_FAILED", message="Нет доступных модулей для сбора данных", meta=meta)

        logger.info(f"Запускаю сбор данных с модулей: {[module.name for module in collectors_to_run]}")
        meta.module_versions = {collector.name: collector.version() for collector in collectors_to_run}
        results = await asyncio.gather(*[collector.collect() for collector in collectors_to_run], return_exceptions=True)

        collected_data = {}
        errors_list = []
        success_count = 0
        artifact_intents: list[ArtifactIntent] = []
        cleanup_paths: list[pathlib.Path] = []

        for collector, result in zip(collectors_to_run, results):
            if isinstance(result, Exception):
                error_info = ErrorInfo(
                    code="MODULE_COLLECT_FAILED",
                    message=f"Модуль {collector.name} завершился с ошибкой: {str(result)}",
                    details={
                        "module_name": collector.name,
                        "exception_type": type(result).__name__,
                        "exception_message": str(result),
                    },
                    retriable=True,
                )
                collected_data[collector.name] = {"ok": False, "observations": {}, "error": error_info.model_dump()}
                warnings.append(f"module {collector.name} failed: {str(result)}")
                errors_list.append(error_info)
                continue

            observations = result.copy() if isinstance(result, dict) else result
            if isinstance(result, dict) and "_artifacts" in result:
                for item in result.get("_artifacts") or []:
                    if isinstance(item, dict) and "local_path" in item:
                        try:
                            artifact_intents.append(
                                ArtifactIntent(
                                    local_path=pathlib.Path(item["local_path"]),
                                    name=item.get("name"),
                                    mime=item.get("mime"),
                                    kind=item.get("kind"),
                                    ttl_seconds=item.get("ttl_seconds"),
                                    meta=item.get("meta", {}),
                                )
                            )
                        except Exception as exc:
                            logger.warning(f"Ошибка создания ArtifactIntent для {item.get('local_path')}: {exc}")
                del observations["_artifacts"]

            if isinstance(result, dict) and "_cleanup_paths" in result:
                for path_str in result.get("_cleanup_paths") or []:
                    try:
                        cleanup_paths.append(pathlib.Path(path_str))
                    except Exception as exc:
                        logger.warning(f"Ошибка создания Path для cleanup: {path_str}: {exc}")
                del observations["_cleanup_paths"]

            collected_data[collector.name] = {"ok": True, "observations": observations}
            success_count += 1

        uploaded_artifacts = []
        upload_errors = []
        if artifact_intents:
            try:
                uploader = get_uploader(identity_manager=orchestrator.identity_manager) if orchestrator.identity_manager else get_uploader()
                uploaded_artifacts, upload_errors = await ArtifactManager(uploader).upload_many(artifact_intents)
                for upload_error in upload_errors:
                    warnings.append(f"Ошибка загрузки артефакта: {upload_error.message}")
                    errors_list.append(upload_error)
            except Exception as exc:
                error_msg = f"Ошибка при загрузке артефактов: {exc}"
                warnings.append(error_msg)
                errors_list.append(
                    ErrorInfo(
                        code="ARTIFACT_UPLOAD_SYSTEM_ERROR",
                        message=error_msg,
                        details={"exception_type": type(exc).__name__, "exception_message": str(exc)},
                        retriable=True,
                    )
                )

        for cleanup_path in cleanup_paths:
            try:
                if cleanup_path.exists():
                    cleanup_path.unlink()
            except Exception as exc:
                warnings.append(f"Не удалось удалить временный файл {cleanup_path}: {exc}")

        observations = {"results": collected_data}
        if errors_list and success_count > 0:
            return partial(
                data=ToolData(observations=observations, artifacts=uploaded_artifacts, warnings=warnings, errors=errors_list),
                meta=meta,
                warnings=warnings,
                errors=errors_list,
            )
        if errors_list and success_count == 0:
            return fail(
                code="ALL_MODULES_FAILED",
                message=f"Все модули завершились с ошибками ({len(errors_list)} модулей)",
                meta=meta,
                details={"module_errors": [error.model_dump() for error in errors_list]},
                retriable=True,
            )
        if upload_errors and success_count > 0:
            return partial(
                data=ToolData(observations=observations, artifacts=uploaded_artifacts, warnings=warnings, errors=errors_list),
                meta=meta,
                warnings=warnings,
                errors=errors_list,
            )
        return ok(
            data=ToolData(observations=observations, artifacts=uploaded_artifacts, warnings=warnings if warnings else []),
            meta=meta,
        )
    except Exception as exc:
        logger.error(f"Ошибка в _handle_collect: {exc}")
        raise
