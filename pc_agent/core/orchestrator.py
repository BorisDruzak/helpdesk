"""
РЈРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№ РєРѕРЅС‚СЂРѕР»Р»РµСЂ Р°РіРµРЅС‚Р° (orchestrator).

Р­С‚РѕС‚ РјРѕРґСѓР»СЊ СЂРµР°Р»РёР·СѓРµС‚ РµРґРёРЅСѓСЋ С‚РѕС‡РєСѓ РІС…РѕРґР° РґР»СЏ РѕР±СЂР°Р±РѕС‚РєРё РІСЃРµС… РєРѕРјР°РЅРґ,
РїРѕСЃС‚СѓРїР°СЋС‰РёС… Рє Р°РіРµРЅС‚Сѓ. РЈРїСЂР°РІР»СЏРµС‚ РјРѕРґСѓР»СЏРјРё СЃР±РѕСЂР° РґР°РЅРЅС‹С…, РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚
РєРѕРјР°РЅРґС‹, Рё РІРѕР·РІСЂР°С‰Р°РµС‚ СѓРЅРёС„РёС†РёСЂРѕРІР°РЅРЅС‹Рµ РѕС‚РІРµС‚С‹.
"""

import time
import asyncio
import json
import uuid
import pathlib
import base64
import tempfile
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from time import perf_counter
from loguru import logger
import hashlib
try:
    import aiohttp
except ImportError:
    aiohttp = None
from modules import ModuleFactory, BaseCollector
from core.database import DatabaseManager
from core.validator import CodeValidator
from core.loader import DynamicModuleLoader
from core.process_provider import ProcessProvider
from core.registry import ModuleRegistry
from core.tool_response import ToolResponse, ToolMeta, ToolData, ErrorInfo, ok, fail, partial
from core.artifacts import ArtifactIntent, ArtifactManager
from core.tools import ToolSpec, check_policy, ToolMetadata
from core.policy_engine import PolicyEngine
from network.uploader import get_uploader
from core.identity import IdentityManager
from core.module_manager import ModuleManager
from core.job_manager import JobManager
from core.recording_controller import get_recording_controller
from pc_agent.config.config_loader import get_config
from pc_agent.version import AGENT_VERSION, EXIT_UPDATE_PENDING
from utils.toolset_hash import compute_toolset_hash
import inspect
import os

# РРјРїРѕСЂС‚ ValidationError РёР· pydantic (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
try:
    from pydantic import ValidationError
except ImportError:
    ValidationError = None


class AgentOrchestrator:
    """
    РЈРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№ РєРѕРЅС‚СЂРѕР»Р»РµСЂ Р°РіРµРЅС‚Р° РґР»СЏ РѕР±СЂР°Р±РѕС‚РєРё РєРѕРјР°РЅРґ.
    
    РћСЃРЅРѕРІРЅР°СЏ Р·Р°РґР°С‡Р° - РїСЂРёРЅРёРјР°С‚СЊ РєРѕРјР°РЅРґС‹ РІ РІРёРґРµ СЃР»РѕРІР°СЂРµР№, РѕР±СЂР°Р±Р°С‚С‹РІР°С‚СЊ РёС…
    Рё РІРѕР·РІСЂР°С‰Р°С‚СЊ СѓРЅРёС„РёС†РёСЂРѕРІР°РЅРЅС‹Рµ РѕС‚РІРµС‚С‹. РЈРїСЂР°РІР»СЏРµС‚ РјРѕРґСѓР»СЏРјРё СЃР±РѕСЂР° РґР°РЅРЅС‹С…
    Рё РѕР±РµСЃРїРµС‡РёРІР°РµС‚ РѕС‚РєР°Р·РѕСѓСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ СЃРёСЃС‚РµРјС‹.
    """
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        enabled_modules: Optional[List[str]] = None,
        agent_uuid: Optional[str] = None,
        identity_manager: Optional[IdentityManager] = None,
        data_root: Optional[Path] = None,
    ):
        """
        РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂР°.

        Args:
            db_manager: РњРµРЅРµРґР¶РµСЂ Р±Р°Р·С‹ РґР°РЅРЅС‹С… (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
            enabled_modules: РЎРїРёСЃРѕРє РёРјРµРЅ Р°РєС‚РёРІРЅС‹С… РјРѕРґСѓР»РµР№ (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
            agent_uuid: РРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ Р°РіРµРЅС‚Р° (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
            identity_manager: РњРµРЅРµРґР¶РµСЂ РёРґРµРЅС‚РёС„РёРєР°С†РёРё РґР»СЏ Р·Р°РіСЂСѓР·РєРё Р°СЂС‚РµС„Р°РєС‚РѕРІ (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
            data_root: РљРѕСЂРµРЅСЊ РґР°РЅРЅС‹С… (runtime_paths); РµСЃР»Рё Р·Р°РґР°РЅ, modules_store Рё temp РІ РЅС‘Рј
        """
        self.db_manager = db_manager
        self.enabled_modules = enabled_modules or []
        self._module_load_context = self._build_module_load_context()
        self.loaded_modules: List[BaseCollector] = []
        self.start_time = time.time()
        self.agent_uuid = agent_uuid
        self.identity_manager = identity_manager
        self.job_manager: Optional[JobManager] = None
        self._data_root = data_root

        # Р”Р»СЏ tools_changed event (Р­С‚Р°Рї B, C)
        self.device_id = agent_uuid  # device_id СЃРѕРІРїР°РґР°РµС‚ СЃ agent_uuid
        self._last_toolset_hash: Optional[str] = None

        # Р—Р°РіСЂСѓР·С‡РёРє РїР°РєРµС‚РЅС‹С… РјРѕРґСѓР»РµР№ (С‚РѕР»СЊРєРѕ load_module_from_path РґР»СЏ modules_store)
        self.loader = DynamicModuleLoader(data_root=data_root)

        # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј СЂРµРµСЃС‚СЂ РјРѕРґСѓР»РµР№
        self.registry = ModuleRegistry()

        # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј PolicyEngine РґР»СЏ РєРѕРЅС‚СЂРѕР»СЏ РґРѕСЃС‚СѓРїР°
        self.policy = PolicyEngine()

        # UI Bridge РґР»СЏ РїСѓР±Р»РёРєР°С†РёРё СЃРѕР±С‹С‚РёР№ (СѓСЃС‚Р°РЅР°РІР»РёРІР°РµС‚СЃСЏ РёР·РІРЅРµ)
        self.ui_bus = None

        # Tech debt (BOTTLENECKS): Р—Р°РєРѕРјРјРµРЅС‚РёСЂРѕРІР°РЅРЅС‹Р№ consent-РїСѓС‚СЊ; РїСЂРё РІРєР»СЋС‡РµРЅРёРё СЃРѕРіР»Р°СЃРѕРІР°С‚СЊ
        # СЃ С‚РµРєСѓС‰РµР№ РјРѕРґРµР»СЊСЋ consent РІ Р‘Р” Рё server waiting_consent. Р РЋР С. docs/BOTTLENECKS_AND_RISKS.md
        # self.pending_tool_calls: Dict[str, Dict[str, Any]] = {}  # consent_token -> dict
        # self.consent_cache: Dict[str, Dict[str, bool]] = {}  # session_key -> {consent_token: bool}

        # РњРµРЅРµРґР¶РµСЂ РјРѕРґСѓР»РµР№: data_root/modules_store Рё data_root/temp РїСЂРё РЅР°Р»РёС‡РёРё data_root
        cfg = get_config()
        if data_root is not None:
            data_dir = str(data_root)
            temp_dir = str(data_root / "temp")
        else:
            data_dir = cfg.paths.data_dir
            try:
                temp_dir = cfg.paths.temp_dir
            except AttributeError:
                temp_dir = str(pathlib.Path(data_dir) / "temp")
        self.module_manager = ModuleManager(data_dir=data_dir, temp_dir=temp_dir)
        
        # РљР РРўРР§РќРћ: Registry РґР»СЏ РѕС‚СЃР»РµР¶РёРІР°РЅРёСЏ РІС‹РїРѕР»РЅСЏСЋС‰РёС…СЃСЏ РѕРїРµСЂР°С†РёР№ (РґР»СЏ cancel)
        # РљР»СЋС‡: operation_id (РёР· meta.request_id), Р·РЅР°С‡РµРЅРёРµ: asyncio.Task
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info("СЂСџР‹Р‡ AgentOrchestrator РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
        logger.debug(f"РђРєС‚РёРІРЅС‹Рµ РјРѕРґСѓР»Рё: {self.enabled_modules}")

    def _build_module_load_context(self) -> Dict[str, Any]:
        """
        РЎРѕС…СЂР°РЅСЏРµС‚ РєРѕРЅС‚РµРєСЃС‚ Р·Р°РіСЂСѓР·РєРё built-in/extra-path РјРѕРґСѓР»РµР№ РЅР° lifetime orchestrator.
        """
        extra_paths: List[str] = []
        try:
            cfg = get_config()
            if hasattr(cfg, "modules") and hasattr(cfg.modules, "extra_paths"):
                extra_paths = list(cfg.modules.extra_paths or [])
        except Exception as exc:
            logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ extra_paths РёР· config: {exc}")
        return {
            "enabled_modules": list(self.enabled_modules),
            "extra_paths": extra_paths,
            "source": "builtin_or_extra_path",
        }

    def _load_builtin_modules(self) -> List[BaseCollector]:
        """
        Р—Р°РіСЂСѓР¶Р°РµС‚ built-in/extra-path РјРѕРґСѓР»Рё РёР· СЃРѕС…СЂР°РЅС‘РЅРЅРѕРіРѕ РєРѕРЅС‚РµРєСЃС‚Р°.
        """
        context = self._module_load_context or {}
        enabled_modules = context.get("enabled_modules") or []
        extra_paths = context.get("extra_paths") or []
        if not enabled_modules:
            return []
        return ModuleFactory.create_modules(enabled_modules, extra_paths=extra_paths)
    
    async def initialize(self) -> None:
        """
        РђСЃРёРЅС…СЂРѕРЅРЅР°СЏ РёРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂР°.
        
        Р—Р°РіСЂСѓР¶Р°РµС‚ РјРѕРґСѓР»Рё Рё РёРЅРёС†РёР°Р»РёР·РёСЂСѓРµС‚ Р±Р°Р·Сѓ РґР°РЅРЅС‹С….
        """
        try:
            # Р—Р°РіСЂСѓР¶Р°РµРј РјРѕРґСѓР»Рё
            if self.enabled_modules:
                logger.info(f"Р—Р°РіСЂСѓР¶Р°СЋ РјРѕРґСѓР»Рё: {self.enabled_modules}")
                self.loaded_modules = self._load_builtin_modules()
                logger.success(f"Р—Р°РіСЂСѓР¶РµРЅРѕ РјРѕРґСѓР»РµР№: {len(self.loaded_modules)}")
                
                # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј РјРѕРґСѓР»Рё РІ СЂРµРµСЃС‚СЂРµ
                for module in self.loaded_modules:
                    self.registry.register(module)
                    logger.debug(f"РњРѕРґСѓР»СЊ '{module.name}' Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ РІ СЂРµРµСЃС‚СЂРµ")
            # Tech debt: Р±Р»РѕРє РјРёРіСЂР°С†РёРё pending_tool_calls (Р°С‚СЂРёР±СѓС‚ Р·Р°РєРѕРјРјРµРЅС‚РёСЂРѕРІР°РЅ РІС‹С€Рµ)
            if hasattr(self, 'pending_tool_calls') and self.pending_tool_calls and self.db_manager:
                logger.info("Migrating in-memory pending_tool_calls to database...")
                for consent_token, pending_data in self.pending_tool_calls.items():
                    try:
                        await self.db_manager.add_pending_consent(
                            operation_id=consent_token,
                            tool_name=pending_data["tool_name"],
                            params=pending_data["params"],
                            payload_hash=self._hash_payload(pending_data["params"]),
                            actor_role=pending_data["actor_role"],
                            ticket_id=None,  # РњРѕР¶РµС‚ РѕС‚СЃСѓС‚СЃС‚РІРѕРІР°С‚СЊ РІ СЃС‚Р°СЂС‹С… РґР°РЅРЅС‹С…
                            expires_at=int(time.time()) + 1800
                        )
                    except Exception as e:
                        logger.error(f"Failed to migrate consent {consent_token}: {e}")
                self.pending_tool_calls.clear()

            # РљР РРўРР§РќРћ: РђРІС‚РѕР·Р°РіСЂСѓР·РєР° Р°РєС‚РёРІРЅС‹С… РјРѕРґСѓР»РµР№ РёР· modules_store
            # Р­С‚Рѕ РіР°СЂР°РЅС‚РёСЂСѓРµС‚, С‡С‚Рѕ РјРѕРґСѓР»Рё, СѓСЃС‚Р°РЅРѕРІР»РµРЅРЅС‹Рµ РґРѕ РїРµСЂРµР·Р°РїСѓСЃРєР°, Р±СѓРґСѓС‚ РґРѕСЃС‚СѓРїРЅС‹
            # РЎРїРёСЃРѕРє СЃР»РѕРјР°РЅРЅС‹С… РјРѕРґСѓР»РµР№, СѓРґР°Р»С‘РЅРЅС‹С… РїСЂРё СЃС‚Р°СЂС‚Рµ, РґР»СЏ РїРѕСЃР»РµРґСѓСЋС‰РµРіРѕ СѓРІРµРґРѕРјР»РµРЅРёСЏ СЃРµСЂРІРµСЂР°
            broken_modules_deleted: list = []
            if self.module_manager:
                logger.info("РђРІС‚РѕР·Р°РіСЂСѓР·РєР° Р°РєС‚РёРІРЅС‹С… РјРѕРґСѓР»РµР№ РёР· modules_store...")
                try:
                    installed = self.module_manager.list_installed()
                    active_modules_loaded = 0
                    
                    for m in installed.get("modules", []):
                        if not m.get("active"):
                            continue
                        
                        module_name = m.get("name")
                        if not module_name:
                            continue
                        
                        # РџРѕР»СѓС‡Р°РµРј РїСѓС‚СЊ Рє Р°РєС‚РёРІРЅРѕР№ РІРµСЂСЃРёРё РјРѕРґСѓР»СЏ
                        m_path = self.module_manager.get_active_path(module_name)
                        if not m_path:
                            logger.warning(
                                f"РђРєС‚РёРІРЅС‹Р№ РјРѕРґСѓР»СЊ '{module_name}' РЅР°Р№РґРµРЅ, РЅРѕ РїСѓС‚СЊ РЅРµ РґРѕСЃС‚СѓРїРµРЅ"
                            )
                            continue
                        
                        try:
                            # Р§РёС‚Р°РµРј manifest РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ entrypoint
                            manifest = self._read_json(m_path / "manifest.json")
                            entrypoint = manifest.get("entrypoint", "module:register")
                            
                            # Р—Р°РіСЂСѓР¶Р°РµРј РјРѕРґСѓР»СЊ
                            inst = self.loader.load_module_from_path(
                                module_name, 
                                m_path, 
                                entrypoint=entrypoint
                            )
                            
                            # Р”РѕР±Р°РІР»СЏРµРј РІ loaded_modules Рё СЂРµРіРёСЃС‚СЂРёСЂСѓРµРј
                            self.loaded_modules.append(inst)
                            self.registry.register(inst)
                            active_modules_loaded += 1
                            
                            logger.success(
                                f"РІСљвЂ¦ РђРІС‚РѕР·Р°РіСЂСѓР¶РµРЅ Р°РєС‚РёРІРЅС‹Р№ РјРѕРґСѓР»СЊ '{module_name}' "
                                f"РІРµСЂСЃРёРё {m.get('active', 'unknown')} РёР· modules_store"
                            )
                        except Exception as e:
                            logger.error(
                                f"РІСњРЉ РћС€РёР±РєР° Р°РІС‚РѕР·Р°РіСЂСѓР·РєРё Р°РєС‚РёРІРЅРѕРіРѕ РјРѕРґСѓР»СЏ '{module_name}': {e}"
                            )
                            logger.exception(e)
                            # РњРѕРґСѓР»СЊ РЅРµ Р·Р°РіСЂСѓР¶Р°РµС‚СЃСЏ РІР‚вЂќ СѓРґР°Р»СЏРµРј СЃ РґРёСЃРєР°, С‡С‚РѕР±С‹ РЅРµ РѕСЃС‚Р°РІР°Р»СЃСЏ В«СѓСЃС‚Р°РЅРѕРІР»РµРЅРЅС‹РјВ»
                            module_version = m_path.name
                            try:
                                self.module_manager.remove_version_force(module_name, module_version)
                                logger.warning(
                                    f"РњРѕРґСѓР»СЊ {module_name}@{module_version} СѓРґР°Р»С‘РЅ СЃ РґРёСЃРєР° (РЅРµ Р·Р°РіСЂСѓР¶Р°РµС‚СЃСЏ)"
                                )
                            except Exception as rm_e:
                                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ СЃР»РѕРјР°РЅРЅС‹Р№ РјРѕРґСѓР»СЊ {module_name}@{module_version}: {rm_e}")
                            else:
                                broken_modules_deleted.append(f"{module_name}@{module_version}")
                            continue
                    
                    if active_modules_loaded > 0:
                        logger.success(
                            f"РђРІС‚РѕР·Р°РіСЂСѓР¶РµРЅРѕ Р°РєС‚РёРІРЅС‹С… РјРѕРґСѓР»РµР№ РёР· modules_store: {active_modules_loaded}"
                        )
                    else:
                        logger.info("Р’ modules_store РЅРµ РЅР°Р№РґРµРЅРѕ Р°РєС‚РёРІРЅС‹С… РјРѕРґСѓР»РµР№ РґР»СЏ Р°РІС‚РѕР·Р°РіСЂСѓР·РєРё")
                except Exception as e:
                    logger.error(f"РћС€РёР±РєР° РїСЂРё Р°РІС‚РѕР·Р°РіСЂСѓР·РєРµ Р°РєС‚РёРІРЅС‹С… РјРѕРґСѓР»РµР№ РёР· modules_store: {e}")
                    logger.exception(e)
            else:
                logger.debug("ModuleManager РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ, РїСЂРѕРїСѓСЃРєР°РµРј Р°РІС‚РѕР·Р°РіСЂСѓР·РєСѓ РёР· modules_store")
            
            # ==================================
            
            # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј Р±Р°Р·Сѓ РґР°РЅРЅС‹С…
            if self.db_manager:
                await self.db_manager.init_db()
                logger.success("Р‘Р°Р·Р° РґР°РЅРЅС‹С… РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅР°")
                # РЈРІРµРґРѕРјР»СЏРµРј СЃРµСЂРІРµСЂ РѕР± СѓРґР°Р»С‘РЅРЅС‹С… СЃР»РѕРјР°РЅРЅС‹С… РјРѕРґСѓР»СЏС… (РїРѕСЃР»Рµ РіРѕС‚РѕРІРЅРѕСЃС‚Рё Р‘Р”)
                if broken_modules_deleted:
                    await self._emit_module_state_changed(
                        reason=f"broken_removed_at_startup:{','.join(broken_modules_deleted)}"
                    )
            
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РёРЅРёС†РёР°Р»РёР·Р°С†РёРё РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂР°: {e}")
            raise
    
    def attach_job_manager(self, job_manager: JobManager) -> None:
        """
        РџРѕРґРєР»СЋС‡Р°РµС‚ JobManager Рє РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂСѓ.
        
        Args:
            job_manager: Р­РєР·РµРјРїР»СЏСЂ JobManager
        """
        self.job_manager = job_manager
        logger.info("РІСљвЂ¦ JobManager РїРѕРґРєР»СЋС‡РµРЅ Рє РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂСѓ")
    
    async def handle_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Р•РґРёРЅР°СЏ С‚РѕС‡РєР° РІС…РѕРґР° РґР»СЏ РѕР±СЂР°Р±РѕС‚РєРё РєРѕРјР°РЅРґ.
        
        Args:
            command: РЎР»РѕРІР°СЂСЊ СЃ РєРѕРјР°РЅРґРѕР№, РЅР°РїСЂРёРјРµСЂ:
                    {'cmd': 'ping'} РёР»Рё
                    {'cmd': 'collect', 'modules': ['system']}
        
        Returns:
            Dict[str, Any]: РЈРЅРёС„РёС†РёСЂРѕРІР°РЅРЅС‹Р№ РѕС‚РІРµС‚ РІ С„РѕСЂРјР°С‚Рµ ToolResponse.model_dump()
        """
        cmd = command.get('cmd', '').lower()
        start_time = perf_counter()
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        
        # РР·РІР»РµРєР°РµРј request_id РёР· payload РёР»Рё РіРµРЅРµСЂРёСЂСѓРµРј РЅРѕРІС‹Р№ (fallback)
        payload_request_id = command.get('request_id')
        if payload_request_id:
            request_id = payload_request_id
        else:
            request_id = str(uuid.uuid4())
            logger.debug(f"request_id РЅРµ СѓРєР°Р·Р°РЅ РІ payload, СЃРіРµРЅРµСЂРёСЂРѕРІР°РЅ РЅРѕРІС‹Р№: {request_id}")
        
        device_id = command.get('device_id')
        ticket_id = command.get('ticket_id') or (command.get('params', {}) or {}).get('ticket_id')
        actor_role = command.get('actor_role')
        agent_id = self.agent_uuid if hasattr(self, 'agent_uuid') and self.agent_uuid else None
        
        # РЎРѕР·РґР°С‘Рј job РґР»СЏ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹ (command_job_id)
        command_job_id = str(uuid.uuid4())
        job_id = command_job_id  # Р”Р»СЏ РѕР±СЂР°С‚РЅРѕР№ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё РІ РЅР°С‡Р°Р»Рµ
        job_created = False
        
        meta = ToolMeta(
            timestamp_iso=timestamp_iso,
            command=cmd,
            request_id=request_id,
            agent_id=agent_id,
            duration_ms=None
        )
        
        # РџСЂРѕРІРµСЂРєР° СЃРѕРіР»Р°СЃРѕРІР°РЅРЅРѕСЃС‚Рё request_id: РµСЃР»Рё payload СЃРѕРґРµСЂР¶РёС‚ request_id,
        # С‚Рѕ meta.request_id РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЂР°РІРµРЅ РµРјСѓ
        if payload_request_id and meta.request_id != payload_request_id:
            logger.error(
                f"РІСњРЉ Р РђРЎРҐРћР–Р”Р•РќРР• request_id: payload.request_id={payload_request_id}, "
                f"meta.request_id={meta.request_id}. РџСЂРёРІРѕР¶Сѓ meta.request_id Рє payload.request_id"
            )
            meta.request_id = payload_request_id
            request_id = payload_request_id  # РћР±РЅРѕРІР»СЏРµРј РґР»СЏ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ РІ РґР°Р»СЊРЅРµР№С€РµРј
        
        logger.info(f"СЂСџвЂњРЃ РџРѕР»СѓС‡РµРЅР° РєРѕРјР°РЅРґР°: {cmd}, request_id={request_id}")
        logger.debug(f"РџРѕР»РЅС‹Р№ Р·Р°РїСЂРѕСЃ: {command}")
        
        if self.db_manager:
            try:
                meta_json = json.dumps(meta.model_dump(), ensure_ascii=False)
                await self.db_manager.create_job(
                    job_id=command_job_id,
                    request_id=request_id,
                    device_id=device_id,
                    command=cmd,
                    actor_role=actor_role,
                    meta_json=meta_json
                )
                job_created = True
                logger.info(f"РЎРѕР·РґР°РЅ job: {command_job_id}, command={cmd}")
            except Exception as db_error:
                logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР·РґР°С‚СЊ job РІ Р‘Р”: {db_error}")
        
        try:
            match cmd:
                case 'ping':
                    result = await self._handle_ping(meta)
                    
                case 'collect':
                    modules = command.get('modules')
                    result = await self._handle_collect(modules, meta)
                    
                case 'list_modules':
                    result = await self._handle_list_modules(meta)
                    
                case 'list_installed_modules':
                    result = await self._handle_list_installed_modules(meta)
                    
                case 'activate_module':
                    name = command.get('name')
                    version = command.get('version')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_activate_module(name, version, actor_role, meta)
                    
                case 'rollback_module':
                    name = command.get('name')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_rollback_module(name, actor_role, meta)
                    
                case 'deactivate_module':
                    name = command.get('name')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_deactivate_module(name, actor_role, meta)
                    
                case 'remove_module_version':
                    name = command.get('name')
                    version = command.get('version')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_remove_module_version(name, version, actor_role, meta)
                    
                case 'remove_module':
                    name = command.get('name')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_remove_module(name, actor_role, meta)
                    
                case 'update':
                    result = await self._handle_update(command, meta)
                    
                case 'install_module_package':
                    name = command.get('name') or command.get('module_name')
                    version = command.get('version') or command.get('module_version')
                    package_b64 = command.get('package_b64')
                    download_url = command.get('download_url')
                    sha256 = command.get('sha256')
                    size = command.get('size')
                    actor_role = command.get('actor_role', 'user')
                    replace_if_different_sha = command.get('replace_if_different_sha') or (command.get('params') or {}).get('replace_if_different_sha', False)
                    result = await self._handle_install_module_package(
                        name, version, package_b64, download_url, sha256, size, actor_role, meta,
                        replace_if_different_sha=replace_if_different_sha
                    )
                    
                case 'exec_script':
                    code = command.get('code')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_exec_script(code, actor_role, meta)
                    
                case 'get_manifest':
                    result = await self._handle_get_manifest(meta)
                    
                case 'list_tools':
                    result = await self._handle_list_tools(meta)
                    
                case 'describe_tool':
                    tool = command.get("tool")
                    result = await self._handle_describe_tool(tool, meta)
                    
                case 'cancel_operation':
                    # РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ cancel_operation
                    params = command.get("params", {})
                    target_operation_id = params.get("target_operation_id") or params.get("operation_id")
                    result = await self._handle_cancel_operation(target_operation_id, meta)
                    
                case 'run_tool' | 'call_tool':
                    # РџРѕРґРґРµСЂР¶РєР° РѕР±РѕРёС… С„РѕСЂРјР°С‚РѕРІ: tool РІ РєРѕСЂРЅРµ РёР»Рё РІ params
                    # call_tool - Р°Р»РёР°СЃ РґР»СЏ run_tool
                    tool = command.get("tool") or command.get("params", {}).get("tool")
                    tool_params = command.get("params", {}) or {}
                    chat_job_id = command.get("chat_job_id")
                    actor_role = command.get("actor_role", "user")
                    
                    # РЎРѕР·РґР°С‘Рј РѕР±С‘СЂС‚РєСѓ command_params СЃ tool, params, chat_job_id
                    command_params = {
                        "tool": tool,
                        "params": tool_params,
                        "chat_job_id": chat_job_id,
                        "ticket_id": ticket_id,
                        "job_id": command.get("job_id"),
                    }
                    result = await self._handle_run_tool(tool, command_params, actor_role, meta)
                    
                case 'start_job':
                    job_type = command.get('job_type')
                    params = command.get('params', {})
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_start_job(job_type, params, actor_role, device_id, meta)
                    
                case 'stop_job':
                    job_id = command.get('job_id')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_stop_job(job_id, actor_role, meta)
                    
                case 'get_job_status':
                    job_id = command.get('job_id')
                    result = await self._handle_get_job_status(job_id, meta)
                    
                case 'list_jobs':
                    limit = command.get('limit', 50)
                    result = await self._handle_list_jobs(limit, meta)
                    
                case 'job_send_event':
                    # РР·РІР»РµРєР°РµРј chat_job_id РёР· params (СЌС‚Рѕ job_id С‡Р°С‚Р°, РќР• command_job_id)
                    chat_job_id = command.get('job_id') or command.get('params', {}).get('job_id')
                    event = command.get('event') or command.get('params', {}).get('event')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_job_send_event(chat_job_id, event, actor_role, meta)
                    
                case 'consent_decision':
                    consent_token = command.get('consent_token')
                    approved = command.get('approved', False)
                    session_key = command.get('session_key')
                    result = await self._handle_consent_decision(consent_token, approved, session_key, meta)
                    
                case 'ui_notify':
                    # РѕР¶РёРґР°РµРј event dict: {"event":"chat_invite", "job_id":..., "ts":...}
                    ev = command.get("event") or command.get("params", {}).get("event")
                    if not isinstance(ev, dict):
                        result = fail(
                            code="BAD_REQUEST",
                            message="ui_notify С‚СЂРµР±СѓРµС‚ РїРѕР»Рµ event (dict)",
                            meta=meta
                        )
                    else:
                        if self.ui_bus:
                            await self.ui_bus.publish(ev)
                            logger.info(f"рџ“Ј UI notify published: {ev.get('event')} job_id={ev.get('job_id')}")
                        else:
                            logger.warning("ui_notify РїРѕР»СѓС‡РµРЅ, РЅРѕ ui_bus РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅ")
                        result = ok(
                            data=ToolData(observations={"published": True}),
                            meta=meta
                        )
                    
                case '':
                    result = fail(
                        code="UNKNOWN_COMMAND",
                        message='РќРµ СѓРєР°Р·Р°РЅР° РєРѕРјР°РЅРґР° (РїРѕР»Рµ "cmd" РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РёР»Рё РїСѓСЃС‚РѕРµ)',
                        meta=meta
                    )
                    
                case _:
                    result = fail(
                        code="UNKNOWN_COMMAND",
                        message=f'РќРµРёР·РІРµСЃС‚РЅР°СЏ РєРѕРјР°РЅРґР°: {cmd}',
                        meta=meta
                    )
            
            duration_ms = int((perf_counter() - start_time) * 1000)
            result.meta.duration_ms = duration_ms
            
            # РџСЂРѕРІРµСЂРєР° СЃРѕРіР»Р°СЃРѕРІР°РЅРЅРѕСЃС‚Рё request_id РІ СЂРµР·СѓР»СЊС‚Р°С‚Рµ
            if result.meta.request_id != request_id:
                logger.error(
                    f"РІСњРЉ Р РђРЎРҐРћР–Р”Р•РќРР• request_id РІ СЂРµР·СѓР»СЊС‚Р°С‚Рµ: "
                    f"РѕР¶РёРґР°Р»СЃСЏ request_id={request_id}, РїРѕР»СѓС‡РµРЅ result.meta.request_id={result.meta.request_id}. "
                    f"РСЃРїСЂР°РІР»СЏСЋ result.meta.request_id"
                )
                result.meta.request_id = request_id
            
            if self.db_manager and job_created:
                try:
                    error_json = None
                    if result.error:
                        error_json = json.dumps(result.error.model_dump(), ensure_ascii=False)
                    
                    # Р—Р°РІРµСЂС€Р°РµРј command_job_id (job РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹), Р° РЅРµ chat_job_id
                    await self.db_manager.finish_job(
                        job_id=command_job_id,
                        status=result.status,
                        error_json=error_json
                    )
                    
                    result_dict = result.model_dump()
                    if ticket_id:
                        outbox_id = await self.db_manager.enqueue_tool_response(
                            job_id=command_job_id,
                            request_id=request_id,
                            device_id=device_id,
                            ticket_id=ticket_id,
                            tool_response=result_dict
                        )
                        logger.info(
                            f"Enqueued tool_response to outbox: job_id={command_job_id}, "
                            f"request_id={request_id}, ticket_id={ticket_id}, outbox_id={outbox_id}"
                        )
                    else:
                        logger.debug(
                            f"Skip enqueue_tool_response for command_job_id={command_job_id}: missing ticket_id"
                        )
                    if cmd == 'collect':
                        logger.info(f"Collect command completed: outbox_written=1 (single canonical ToolResponse)")
                    logger.info(f"Р—Р°РІРµСЂС€РµРЅ job: {command_job_id}, status={result.status}")
                except Exception as db_error:
                    logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ СЂРµР·СѓР»СЊС‚Р°С‚ РІ Р‘Р”: {db_error}")
            
            logger.success(f"РІСљвЂ¦ РљРѕРјР°РЅРґР° '{cmd}' РІС‹РїРѕР»РЅРµРЅР° СѓСЃРїРµС€РЅРѕ (duration: {duration_ms}ms)")
            return result.model_dump()
            
        except Exception as e:
            duration_ms = int((perf_counter() - start_time) * 1000)
            meta.duration_ms = duration_ms
            
            # РЈР±РµР¶РґР°РµРјСЃСЏ, С‡С‚Рѕ meta.request_id СЃРѕРІРїР°РґР°РµС‚ СЃ request_id
            if meta.request_id != request_id:
                logger.error(
                    f"РІСњРЉ Р РђРЎРҐРћР–Р”Р•РќРР• request_id РІ meta РїСЂРё РѕС€РёР±РєРµ: "
                    f"РѕР¶РёРґР°Р»СЃСЏ request_id={request_id}, РїРѕР»СѓС‡РµРЅ meta.request_id={meta.request_id}. "
                    f"РСЃРїСЂР°РІР»СЏСЋ meta.request_id"
                )
                meta.request_id = request_id
            
            error_msg = f"РћС€РёР±РєР° РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹ '{cmd}': {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            result = fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
            
            # РџСЂРѕРІРµСЂРєР° СЃРѕРіР»Р°СЃРѕРІР°РЅРЅРѕСЃС‚Рё request_id РІ СЂРµР·СѓР»СЊС‚Р°С‚Рµ РѕС€РёР±РєРё
            if result.meta.request_id != request_id:
                logger.error(
                    f"РІСњРЉ Р РђРЎРҐРћР–Р”Р•РќРР• request_id РІ СЂРµР·СѓР»СЊС‚Р°С‚Рµ РѕС€РёР±РєРё: "
                    f"РѕР¶РёРґР°Р»СЃСЏ request_id={request_id}, РїРѕР»СѓС‡РµРЅ result.meta.request_id={result.meta.request_id}. "
                    f"РСЃРїСЂР°РІР»СЏСЋ result.meta.request_id"
                )
                result.meta.request_id = request_id
            
            if self.db_manager and job_created:
                try:
                    error_json = json.dumps(result.error.model_dump(), ensure_ascii=False) if result.error else None
                    await self.db_manager.finish_job(
                        job_id=command_job_id,
                        status=result.status,
                        error_json=error_json
                    )
                    
                    result_dict = result.model_dump()
                    if ticket_id:
                        outbox_id = await self.db_manager.enqueue_tool_response(
                            job_id=command_job_id,
                            request_id=request_id,
                            device_id=device_id,
                            ticket_id=ticket_id,
                            tool_response=result_dict
                        )
                        logger.info(
                            f"Enqueued tool_response to outbox: job_id={command_job_id}, "
                            f"request_id={request_id}, ticket_id={ticket_id}, outbox_id={outbox_id}"
                        )
                    else:
                        logger.debug(
                            f"Skip enqueue_tool_response for command_job_id={command_job_id}: missing ticket_id"
                        )
                    logger.info(f"Р—Р°РІРµСЂС€РµРЅ job: {command_job_id}, status={result.status}")
                except Exception as db_error:
                    logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕС…СЂР°РЅРёС‚СЊ РѕС€РёР±РєСѓ РІ Р‘Р”: {db_error}")
            
            return result.model_dump()
    
    async def _handle_ping(self, meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'ping' - РІРѕР·РІСЂР°С‰Р°РµС‚ Р±С‹СЃС‚СЂС‹Р№ СЃС‚Р°С‚СѓСЃ Р°РіРµРЅС‚Р°.
        
        Args:
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ РёРЅС„РѕСЂРјР°С†РёРµР№ Рѕ СЃС‚Р°С‚СѓСЃРµ Р°РіРµРЅС‚Р°
        """
        try:
            uptime = time.time() - self.start_time
            
            # РЎРїРёСЃРѕРє РёРјРµРЅ Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… РјРѕРґСѓР»РµР№
            module_names = [module.name for module in self.loaded_modules]
            
            agent_uuid = self.agent_uuid if hasattr(self, 'agent_uuid') and self.agent_uuid else None
            
            observations = {
                'message': 'Agent is alive',
                'agent': agent_uuid,
                'uptime': round(uptime, 2),
                'uptime_human': self._format_uptime(uptime),
                'modules_loaded': module_names,
                'modules_count': len(module_names)
            }
            
            logger.debug(f"Ping РѕС‚РІРµС‚: {observations}")
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РІ _handle_ping: {e}")
            raise
    
    async def _handle_collect(self, modules: Optional[List[str]], meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'collect' - СЃР±РѕСЂ РґР°РЅРЅС‹С… СЃ РјРѕРґСѓР»РµР№.
        
        Args:
            modules: РЎРїРёСЃРѕРє РёРјРµРЅ РјРѕРґСѓР»РµР№ РґР»СЏ СЃР±РѕСЂР° (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
                    Р•СЃР»Рё None - СЃРѕР±РёСЂР°СЋС‚СЃСЏ РґР°РЅРЅС‹Рµ СЃРѕ РІСЃРµС… РјРѕРґСѓР»РµР№
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЃРѕР±СЂР°РЅРЅС‹РјРё РґР°РЅРЅС‹РјРё РѕС‚ РјРѕРґСѓР»РµР№
        """
        try:
            warnings = []
            
            # РћРїСЂРµРґРµР»СЏРµРј, СЃ РєР°РєРёС… РјРѕРґСѓР»РµР№ СЃРѕР±РёСЂР°С‚СЊ РґР°РЅРЅС‹Рµ
            if modules:
                # Р¤РёР»СЊС‚СЂСѓРµРј С‚РѕР»СЊРєРѕ Р·Р°РїСЂРѕС€РµРЅРЅС‹Рµ РјРѕРґСѓР»Рё
                collectors_to_run = [
                    m for m in self.loaded_modules 
                    if m.name in modules
                ]
                
                # РџСЂРѕРІРµСЂСЏРµРј, РІСЃРµ Р»Рё РјРѕРґСѓР»Рё РЅР°Р№РґРµРЅС‹
                missing_modules = set(modules) - {m.name for m in collectors_to_run}
                if missing_modules:
                    warning_msg = f"РњРѕРґСѓР»Рё РЅРµ РЅР°Р№РґРµРЅС‹: {missing_modules}"
                    logger.warning(warning_msg)
                    warnings.append(warning_msg)
            else:
                # РЎРѕР±РёСЂР°РµРј РґР°РЅРЅС‹Рµ СЃРѕ РІСЃРµС… Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… РјРѕРґСѓР»РµР№
                collectors_to_run = self.loaded_modules
            
            if not collectors_to_run:
                return fail(
                    code="COLLECT_FAILED",
                    message='РќРµС‚ РґРѕСЃС‚СѓРїРЅС‹С… РјРѕРґСѓР»РµР№ РґР»СЏ СЃР±РѕСЂР° РґР°РЅРЅС‹С…',
                    meta=meta
                )
            
            logger.info(f"Р—Р°РїСѓСЃРєР°СЋ СЃР±РѕСЂ РґР°РЅРЅС‹С… СЃ РјРѕРґСѓР»РµР№: {[m.name for m in collectors_to_run]}")
            
            # РЎРѕР±РёСЂР°РµРј РІРµСЂСЃРёРё РјРѕРґСѓР»РµР№ РґР»СЏ meta
            module_versions = {}
            for collector in collectors_to_run:
                module_versions[collector.name] = collector.version()
            
            # Р—Р°РїСѓСЃРєР°РµРј СЃР±РѕСЂ РґР°РЅРЅС‹С… РїР°СЂР°Р»Р»РµР»СЊРЅРѕ
            tasks = [collector.collect() for collector in collectors_to_run]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Р¤РѕСЂРјРёСЂСѓРµРј СЂРµР·СѓР»СЊС‚Р°С‚ РІ СЃС‚СЂСѓРєС‚СѓСЂРёСЂРѕРІР°РЅРЅРѕРј С„РѕСЂРјР°С‚Рµ
            collected_data = {}
            errors_list = []
            success_count = 0
            artifact_intents: list[ArtifactIntent] = []
            cleanup_paths: list[pathlib.Path] = []
            
            for collector, result in zip(collectors_to_run, results):
                if isinstance(result, Exception):
                    # РњРѕРґСѓР»СЊ СѓРїР°Р» СЃ РѕС€РёР±РєРѕР№
                    error_info = ErrorInfo(
                        code="MODULE_COLLECT_FAILED",
                        message=f"РњРѕРґСѓР»СЊ {collector.name} Р·Р°РІРµСЂС€РёР»СЃСЏ СЃ РѕС€РёР±РєРѕР№: {str(result)}",
                        details={
                            "module_name": collector.name,
                            "exception_type": type(result).__name__,
                            "exception_message": str(result)
                        },
                        retriable=True
                    )
                    
                    collected_data[collector.name] = {
                        "ok": False,
                        "observations": {},
                        "error": error_info.model_dump()
                    }
                    
                    error_msg = f"module {collector.name} failed: {str(result)}"
                    logger.warning(error_msg)
                    warnings.append(error_msg)
                    errors_list.append(error_info)
                else:
                    # РњРѕРґСѓР»СЊ СѓСЃРїРµС€РЅРѕ СЃРѕР±СЂР°Р» РґР°РЅРЅС‹Рµ
                    # РљРѕРїРёСЂСѓРµРј result РґР»СЏ РѕР±СЂР°Р±РѕС‚РєРё СЃР»СѓР¶РµР±РЅС‹С… РєР»СЋС‡РµР№
                    observations = result.copy() if isinstance(result, dict) else result
                    
                    # РћР±СЂР°Р±Р°С‚С‹РІР°РµРј _artifacts
                    if isinstance(result, dict) and "_artifacts" in result:
                        artifacts_data = result["_artifacts"]
                        if isinstance(artifacts_data, list):
                            for item in artifacts_data:
                                if isinstance(item, dict) and "local_path" in item:
                                    try:
                                        artifact_intent = ArtifactIntent(
                                            local_path=pathlib.Path(item["local_path"]),
                                            name=item.get("name"),
                                            mime=item.get("mime"),
                                            kind=item.get("kind"),
                                            ttl_seconds=item.get("ttl_seconds"),
                                            meta=item.get("meta", {})
                                        )
                                        artifact_intents.append(artifact_intent)
                                        logger.debug(f"Р”РѕР±Р°РІР»РµРЅ Р°СЂС‚РµС„Р°РєС‚ РґР»СЏ Р·Р°РіСЂСѓР·РєРё: {item['local_path']}")
                                    except Exception as e:
                                        logger.warning(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ ArtifactIntent РґР»СЏ {item.get('local_path')}: {e}")
                        # РЈРґР°Р»СЏРµРј СЃР»СѓР¶РµР±РЅС‹Р№ РєР»СЋС‡ РёР· observations
                        del observations["_artifacts"]
                    
                    # РћР±СЂР°Р±Р°С‚С‹РІР°РµРј _cleanup_paths
                    if isinstance(result, dict) and "_cleanup_paths" in result:
                        cleanup_data = result["_cleanup_paths"]
                        if isinstance(cleanup_data, list):
                            for path_str in cleanup_data:
                                try:
                                    cleanup_path = pathlib.Path(path_str)
                                    cleanup_paths.append(cleanup_path)
                                    logger.debug(f"Р”РѕР±Р°РІР»РµРЅ РїСѓС‚СЊ РґР»СЏ РѕС‡РёСЃС‚РєРё: {path_str}")
                                except Exception as e:
                                    logger.warning(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ Path РґР»СЏ cleanup: {path_str}: {e}")
                        # РЈРґР°Р»СЏРµРј СЃР»СѓР¶РµР±РЅС‹Р№ РєР»СЋС‡ РёР· observations
                        del observations["_cleanup_paths"]
                    
                    collected_data[collector.name] = {
                        "ok": True,
                        "observations": observations
                    }
                    success_count += 1
            
            failed_count = len(errors_list)
            logger.success(f"РЎРѕР±СЂР°РЅС‹ РґР°РЅРЅС‹Рµ РѕС‚ {success_count}/{len(collectors_to_run)} РјРѕРґСѓР»РµР№ (СѓСЃРїРµС€РЅРѕ: {success_count}, РѕС€РёР±РѕРє: {failed_count})")
            
            # РћР±РЅРѕРІР»СЏРµРј meta СЃ РІРµСЂСЃРёСЏРјРё РјРѕРґСѓР»РµР№
            meta.module_versions = module_versions
            
            observations = {
                'results': collected_data
            }
            
            # Р—Р°РіСЂСѓР¶Р°РµРј Р°СЂС‚РµС„Р°РєС‚С‹, РµСЃР»Рё РѕРЅРё РµСЃС‚СЊ
            uploaded_artifacts = []
            upload_errors = []
            
            if artifact_intents:
                try:
                    # РЎРѕР·РґР°РµРј uploader Рё ArtifactManager
                    if self.identity_manager:
                        uploader = get_uploader(identity_manager=self.identity_manager)
                    else:
                        # РџС‹С‚Р°РµРјСЃСЏ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ СѓР¶Рµ РёРЅРёС†РёР°Р»РёР·РёСЂРѕРІР°РЅРЅС‹Р№ uploader
                        uploader = get_uploader()
                    
                    artifact_manager = ArtifactManager(uploader)
                    
                    logger.info(f"СЂСџвЂњВ¤ РќР°С‡РёРЅР°СЋ Р·Р°РіСЂСѓР·РєСѓ {len(artifact_intents)} Р°СЂС‚РµС„Р°РєС‚РѕРІ...")
                    uploaded_artifacts, upload_errors = await artifact_manager.upload_many(artifact_intents)
                    
                    logger.success(f"РІСљвЂ¦ Р—Р°РіСЂСѓР¶РµРЅРѕ Р°СЂС‚РµС„Р°РєС‚РѕРІ: {len(uploaded_artifacts)}/{len(artifact_intents)}")
                    
                    if upload_errors:
                        logger.warning(f"РІС™В РїС‘РЏ  РћС€РёР±РѕРє Р·Р°РіСЂСѓР·РєРё: {len(upload_errors)}")
                        # Р”РѕР±Р°РІР»СЏРµРј РѕС€РёР±РєРё Р·Р°РіСЂСѓР·РєРё РІ warnings Рё errors_list
                        for upload_error in upload_errors:
                            warnings.append(f"РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё Р°СЂС‚РµС„Р°РєС‚Р°: {upload_error.message}")
                            errors_list.append(upload_error)
                
                except Exception as e:
                    error_msg = f"РћС€РёР±РєР° РїСЂРё Р·Р°РіСЂСѓР·РєРµ Р°СЂС‚РµС„Р°РєС‚РѕРІ: {e}"
                    logger.error(f"вќЊ {error_msg}")
                    warnings.append(error_msg)
                    upload_error_info = ErrorInfo(
                        code="ARTIFACT_UPLOAD_SYSTEM_ERROR",
                        message=error_msg,
                        details={"exception_type": type(e).__name__, "exception_message": str(e)},
                        retriable=True
                    )
                    errors_list.append(upload_error_info)
            
            # РћС‡РёСЃС‚РєР° РІСЂРµРјРµРЅРЅС‹С… С„Р°Р№Р»РѕРІ
            if cleanup_paths:
                logger.info(f"СЂСџВ§в„– РћС‡РёСЃС‚РєР° {len(cleanup_paths)} РІСЂРµРјРµРЅРЅС‹С… С„Р°Р№Р»РѕРІ...")
                for cleanup_path in cleanup_paths:
                    try:
                        if cleanup_path.exists():
                            cleanup_path.unlink()
                            logger.debug(f"РІСљвЂ¦ РЈРґР°Р»РµРЅ РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р»: {cleanup_path}")
                        else:
                            logger.debug(f"РІвЂћв„–РїС‘РЏ  Р¤Р°Р№Р» СѓР¶Рµ РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚: {cleanup_path}")
                    except Exception as e:
                        # РћС€РёР±РєРё СѓРґР°Р»РµРЅРёСЏ - С‚РѕР»СЊРєРѕ warning, РЅРµ fail
                        warning_msg = f"РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р» {cleanup_path}: {e}"
                        logger.warning(f"вљ пёЏ  {warning_msg}")
                        warnings.append(warning_msg)
            
            # РћРїСЂРµРґРµР»СЏРµРј РёС‚РѕРіРѕРІС‹Р№ СЃС‚Р°С‚СѓСЃ СЃ СѓС‡РµС‚РѕРј РѕС€РёР±РѕРє Р·Р°РіСЂСѓР·РєРё Р°СЂС‚РµС„Р°РєС‚РѕРІ
            # Р•СЃР»Рё РµСЃС‚СЊ РѕС€РёР±РєРё upload, РЅРѕ СЃР±РѕСЂ РґР°РЅРЅС‹С… РµСЃС‚СЊ - СЃС‚Р°С‚СѓСЃ РјРѕР¶РµС‚ СЃС‚Р°С‚СЊ partial
            has_upload_errors = len(upload_errors) > 0
            has_data = success_count > 0
            
            # Р•СЃР»Рё РµСЃС‚СЊ РѕС€РёР±РєРё, РЅРѕ С…РѕС‚СЏ Р±С‹ РѕРґРёРЅ РјРѕРґСѓР»СЊ СѓСЃРїРµС€РµРЅ - partial
            # Р•СЃР»Рё РІСЃРµ РјРѕРґСѓР»Рё СѓРїР°Р»Рё - error
            # Р•СЃР»Рё РІСЃРµ СѓСЃРїРµС€РЅС‹ - success
            # Р•СЃР»Рё РµСЃС‚СЊ РѕС€РёР±РєРё Р·Р°РіСЂСѓР·РєРё Р°СЂС‚РµС„Р°РєС‚РѕРІ, РЅРѕ РґР°РЅРЅС‹Рµ РµСЃС‚СЊ - partial
            if errors_list and success_count > 0:
                # Р§Р°СЃС‚РёС‡РЅС‹Р№ СѓСЃРїРµС…: РµСЃС‚СЊ Рё СѓСЃРїРµС€РЅС‹Рµ, Рё РЅРµСѓСЃРїРµС€РЅС‹Рµ РјРѕРґСѓР»Рё
                data = ToolData(
                    observations=observations,
                    artifacts=uploaded_artifacts,
                    warnings=warnings,
                    errors=errors_list
                )
                result = partial(data=data, meta=meta, warnings=warnings, errors=errors_list)
            elif errors_list and success_count == 0:
                # Р’СЃРµ РјРѕРґСѓР»Рё СѓРїР°Р»Рё
                result = fail(
                    code="ALL_MODULES_FAILED",
                    message=f"Р’СЃРµ РјРѕРґСѓР»Рё Р·Р°РІРµСЂС€РёР»РёСЃСЊ СЃ РѕС€РёР±РєР°РјРё ({len(errors_list)} РјРѕРґСѓР»РµР№)",
                    meta=meta,
                    details={"module_errors": [e.model_dump() for e in errors_list]},
                    retriable=True
                )
            elif has_upload_errors and has_data:
                # Р•СЃС‚СЊ РѕС€РёР±РєРё Р·Р°РіСЂСѓР·РєРё Р°СЂС‚РµС„Р°РєС‚РѕРІ, РЅРѕ РґР°РЅРЅС‹Рµ СЃРѕР±СЂР°РЅС‹ - partial
                data = ToolData(
                    observations=observations,
                    artifacts=uploaded_artifacts,
                    warnings=warnings,
                    errors=errors_list if errors_list else []
                )
                result = partial(data=data, meta=meta, warnings=warnings, errors=errors_list if errors_list else [])
            else:
                # Р’СЃРµ РјРѕРґСѓР»Рё СѓСЃРїРµС€РЅС‹ Рё Р°СЂС‚РµС„Р°РєС‚С‹ Р·Р°РіСЂСѓР¶РµРЅС‹ (РёР»Рё РёС… РЅРµС‚)
                data = ToolData(
                    observations=observations,
                    artifacts=uploaded_artifacts,
                    warnings=warnings if warnings else []
                )
                result = ok(data=data, meta=meta)
            
            # Р›РѕРіРёСЂРѕРІР°РЅРёРµ РґР»СЏ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РѕС‚СЃСѓС‚СЃС‚РІРёСЏ РґСѓР±Р»РµР№ РІ outbox
            # Р—Р°РїРёСЃСЊ РІ outbox Р±СѓРґРµС‚ РІС‹РїРѕР»РЅРµРЅР° С‚РѕР»СЊРєРѕ РѕРґРёРЅ СЂР°Р· РІ handle_command
            logger.info(f"Collect completed: modules_ok={success_count}, modules_failed={failed_count}, outbox_written=0 (Р±СѓРґРµС‚ Р·Р°РїРёСЃР°РЅРѕ РІ handle_command)")
            return result
            
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РІ _handle_collect: {e}")
            raise
    
    async def _handle_list_modules(self, meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'list_modules' - РІРѕР·РІСЂР°С‰Р°РµС‚ СЃРїРёСЃРѕРє РґРѕСЃС‚СѓРїРЅС‹С… РјРѕРґСѓР»РµР№.
        
        Args:
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃРѕ СЃРїРёСЃРєРѕРј РјРѕРґСѓР»РµР№ Рё РёС… РѕРїРёСЃР°РЅРёРµРј
        """
        try:
            modules_info = []
            
            for module in self.loaded_modules:
                module_info = {
                    'name': module.name,
                    'class': module.__class__.__name__,
                    'description': module.__class__.__doc__.strip() if module.__class__.__doc__ else 'РќРµС‚ РѕРїРёСЃР°РЅРёСЏ'
                }
                modules_info.append(module_info)
            
            logger.debug(f"РЎРїРёСЃРѕРє РјРѕРґСѓР»РµР№: {[m['name'] for m in modules_info]}")
            
            observations = {
                'modules': modules_info,
                'total_count': len(modules_info),
                'enabled_modules': self.enabled_modules
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РІ _handle_list_modules: {e}")
            raise
    
    async def _handle_list_installed_modules(self, meta: ToolMeta) -> ToolResponse:
        try:
            data = self.module_manager.list_installed()
            observations = {
                "modules": data.get("modules", [])
            }
            return ok(data=ToolData(observations=observations), meta=meta)
        except Exception as e:
            return fail(code="LIST_INSTALLED_FAILED", message=str(e), meta=meta, retriable=True)
    
    def _read_json(self, path: pathlib.Path) -> Dict[str, Any]:
        """
        Helper С„СѓРЅРєС†РёСЏ РґР»СЏ С‡С‚РµРЅРёСЏ JSON С„Р°Р№Р»Р°.
        
        Args:
            path: РџСѓС‚СЊ Рє JSON С„Р°Р№Р»Сѓ
            
        Returns:
            Dict СЃ СЃРѕРґРµСЂР¶РёРјС‹Рј JSON С„Р°Р№Р»Р°
            
        Raises:
            FileNotFoundError: РµСЃР»Рё С„Р°Р№Р» РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚
            json.JSONDecodeError: РµСЃР»Рё С„Р°Р№Р» СЃРѕРґРµСЂР¶РёС‚ РЅРµРІР°Р»РёРґРЅС‹Р№ JSON
        """
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    async def _handle_activate_module(self, name: Optional[str], version: Optional[str], actor_role: str, meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'activate_module' - Р°РєС‚РёРІР°С†РёСЏ РІРµСЂСЃРёРё РјРѕРґСѓР»СЏ.
        
        Args:
            name: РРјСЏ РјРѕРґСѓР»СЏ
            version: Р’РµСЂСЃРёСЏ РјРѕРґСѓР»СЏ РґР»СЏ Р°РєС‚РёРІР°С†РёРё
            actor_role: Р РѕР»СЊ Р°РєС‚РѕСЂР° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂР°РІ РґРѕСЃС‚СѓРїР°
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј Р°РєС‚РёРІР°С†РёРё РјРѕРґСѓР»СЏ
        """
        try:
            # 1) gate
            if actor_role != "admin":
                return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)

            if not name or not version:
                return fail(code="ACTIVATE_FAILED", message="name and version required", meta=meta)

            # 2) activate in ModuleManager
            active_path = self.module_manager.activate(name, version)
            self._purge_module_runtime(name)

            # 3) rebuild registry from all active modules
            await self._rebuild_registry_from_active_modules()
            # emit module_state_changed
            await self._emit_module_state_changed(reason=f"activate:{name}@{version}")

            observations = {
                "activated": name,
                "version": version,
                "active_path": str(active_path)
            }
            return ok(data=ToolData(observations=observations), meta=meta)

        except Exception as e:
            return fail(code="ACTIVATE_FAILED", message=str(e), meta=meta, retriable=True)
    
    async def _rebuild_registry_from_active_modules(self) -> None:
        """
        РџРµСЂРµСЃРѕР±РёСЂР°РµС‚ СЂРµРµСЃС‚СЂ РјРѕРґСѓР»РµР№ РёР· Р°РєС‚РёРІРЅС‹С… РјРѕРґСѓР»РµР№.

        РћС‡РёС‰Р°РµС‚ registry Рё loaded_modules, Р·Р°С‚РµРј Р·Р°РіСЂСѓР¶Р°РµС‚:
        1. Built-in РјРѕРґСѓР»Рё РёР· enabled_modules (РµСЃР»Рё РµСЃС‚СЊ)
        2. Р’СЃРµ Р°РєС‚РёРІРЅС‹Рµ package РјРѕРґСѓР»Рё РёР· module_manager (modules_store)

        РџРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕР№ РїРµСЂРµСЃР±РѕСЂРєРё РѕС‚РїСЂР°РІР»СЏРµС‚ tools_changed device_event РїСЂРё РёР·РјРµРЅРµРЅРёРё toolset_hash.
        """
        self.registry.reset()
        self.loaded_modules = []
        if self.loader:
            self.loader.reset_runtime_cache()

        # Р—Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°С‚СЊ built-in РјРѕРґСѓР»Рё, РµСЃР»Рё РѕРЅРё РµСЃС‚СЊ РІ enabled_modules
        if self.enabled_modules:
            logger.info(f"РџРµСЂРµР·Р°РіСЂСѓР·РєР° РІСЃС‚СЂРѕРµРЅРЅС‹С… РјРѕРґСѓР»РµР№: {self.enabled_modules}")
            builtin_modules = self._load_builtin_modules()
            self.loaded_modules.extend(builtin_modules)
            for module in builtin_modules:
                self.registry.register(module)
                logger.debug(f"Р’СЃС‚СЂРѕРµРЅРЅС‹Р№ РјРѕРґСѓР»СЊ '{module.name}' Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ РІ СЂРµРµСЃС‚СЂРµ")

        # Р—Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°С‚СЊ Р’РЎР• Р°РєС‚РёРІРЅС‹Рµ package modules:
        if self.module_manager:
            installed = self.module_manager.list_installed()
            for m in installed.get("modules", []):
                if not m.get("active"):
                    continue
                m_path = self.module_manager.get_active_path(m["name"])
                if not m_path:
                    continue
                module_name = m["name"]
                module_version = m_path.name
                try:
                    manifest = self._read_json(m_path / "manifest.json")
                    entrypoint = manifest.get("entrypoint", "module:register")
                    inst = self.loader.load_module_from_path(module_name, m_path, entrypoint=entrypoint)
                    self.loaded_modules.append(inst)
                    self.registry.register(inst)
                    logger.debug(f"Package РјРѕРґСѓР»СЊ '{module_name}' Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ РІ СЂРµРµСЃС‚СЂРµ")
                except Exception as load_err:
                    # РњРѕРґСѓР»СЊ РЅР° РґРёСЃРєРµ РЅРµ Р·Р°РіСЂСѓР¶Р°РµС‚СЃСЏ РІР‚вЂќ СѓРґР°Р»СЏРµРј, С‡С‚РѕР±С‹ РЅРµ РѕСЃС‚Р°РІР°Р»СЃСЏ В«СѓСЃС‚Р°РЅРѕРІР»РµРЅРЅС‹Рј, РЅРѕ СЃР»РѕРјР°РЅРЅС‹РјВ»
                    logger.warning(f"РњРѕРґСѓР»СЊ {module_name}@{module_version} РЅРµ Р·Р°РіСЂСѓР¶Р°РµС‚СЃСЏ: {load_err}, СѓРґР°Р»СЏСЋ СЃ РґРёСЃРєР°")
                    try:
                        self.module_manager.remove_version_force(module_name, module_version)
                    except Exception as rm_e:
                        logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ СЃР»РѕРјР°РЅРЅС‹Р№ РјРѕРґСѓР»СЊ {module_name}@{module_version}: {rm_e}")
                    continue

        # РџРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕР№ РїРµСЂРµСЃР±РѕСЂРєРё РѕС‚РїСЂР°РІР»СЏРµРј tools_changed event
        # EDGE GUARD: РїСЂРѕРІРµСЂСЏРµРј, РёР·РјРµРЅРёР»СЃСЏ Р»Рё hash (РёР·Р±РµРіР°РµРј Р»РёС€РЅРёС… events)
        try:
            # РџРѕР»СѓС‡Р°РµРј tools_list Рё РІС‹С‡РёСЃР»СЏРµРј hash
            tools_list = self._build_tools_list()
            tools_count = len(tools_list)
            
            new_toolset_hash = compute_toolset_hash(tools_list) if tools_list else None
            
            # Edge guard: РїСЂРѕРІРµСЂСЏРµРј, РёР·РјРµРЅРёР»СЃСЏ Р»Рё hash
            if hasattr(self, '_last_toolset_hash') and self._last_toolset_hash == new_toolset_hash:
                logger.debug(f"toolset_hash РЅРµ РёР·РјРµРЅРёР»СЃСЏ ({new_toolset_hash}), РїСЂРѕРїСѓСЃРєР°РµРј tools_changed")
                return  # Hash РЅРµ РёР·РјРµРЅРёР»СЃСЏ, РЅРµ РѕС‚РїСЂР°РІР»СЏРµРј event
            
            # РЎРѕС…СЂР°РЅСЏРµРј РЅРѕРІС‹Р№ hash
            self._last_toolset_hash = new_toolset_hash
            
            # РћС‚РїСЂР°РІР»СЏРµРј device_event tools_changed
            if self.db_manager and self.device_id:
                await self.db_manager.enqueue_event(
                    device_id=self.device_id,
                    kind="tools_changed",
                    payload={
                        "event": "tools_changed",
                        "toolset_hash": new_toolset_hash,
                        "tools_count": tools_count,
                        "tools_version": "tools_v1",
                        "agent_version": AGENT_VERSION,
                        "reason": "registry_rebuilt"
                    },
                    actor_role="system",
                    ticket_id=None,  # Device event Р±РµР· ticket_id
                    trace_id=None,
                    span_id=None,
                    batch_seq=0
                )
                logger.info(f"рџ“‹ tools_changed event enqueued: toolset_hash={new_toolset_hash}, tools_count={tools_count}")
        except Exception as e:
            logger.error(f"Failed to enqueue tools_changed event: {e}", exc_info=True)
            # РќРµ РїР°РґР°РµРј, РµСЃР»Рё event РЅРµ РѕС‚РїСЂР°РІРёР»СЃСЏ

    def _purge_module_runtime(self, module_name: Optional[str]) -> None:
        """
        Remove stale runtime bindings for a module before lifecycle transitions.

        This protects the agent from continuing to execute a removed or
        deactivated package module from in-memory objects that survived the last
        operation.
        """
        if not module_name:
            return

        self.loaded_modules = [
            module
            for module in self.loaded_modules
            if getattr(module, "name", None) != module_name
        ]
        try:
            self.registry.unregister(module_name)
        except Exception:
            logger.debug(f"Failed to unregister module '{module_name}' from registry", exc_info=True)
        if self.loader:
            try:
                self.loader.unload_module(module_name)
            except Exception:
                logger.debug(f"Failed to unload runtime cache for module '{module_name}'", exc_info=True)

    def _get_loaded_module_instance(self, module_name: str):
        for module in self.loaded_modules:
            if getattr(module, "name", None) == module_name:
                return module
        return None

    def _get_module_source_path(self, module_instance: Any) -> Optional[Path]:
        if module_instance is None:
            return None
        try:
            source_path = inspect.getsourcefile(module_instance.__class__) or inspect.getfile(module_instance.__class__)
        except Exception:
            return None
        if not source_path:
            return None
        try:
            return Path(source_path).resolve()
        except Exception:
            return None

    def _is_dynamic_module_instance(self, module_instance: Any) -> bool:
        source_path = self._get_module_source_path(module_instance)
        if source_path is None:
            return False
        return any(part.lower() == "modules_store" for part in source_path.parts)

    def _get_expected_tool_method_from_active_manifest(
        self,
        module_name: str,
        full_tool_name: str,
    ) -> tuple[Optional[Path], Optional[str]]:
        if not self.module_manager:
            return None, None
        active_path = self.module_manager.get_active_path(module_name)
        if not active_path:
            return None, None
        try:
            manifest = self._read_json(active_path / "manifest.json")
        except Exception:
            return active_path, None

        short_tool_name = full_tool_name.split(".", 1)[1] if "." in full_tool_name else full_tool_name
        for tool_info in manifest.get("tools", []) or []:
            declared_tool = tool_info.get("tool")
            if declared_tool in (full_tool_name, short_tool_name, f"{module_name}.{short_tool_name}"):
                return active_path, tool_info.get("method")

        return active_path, None

    async def _ensure_module_runtime_matches_inventory(
        self,
        module_name: str,
        *,
        full_tool_name: Optional[str] = None,
    ) -> None:
        """
        Self-heals stale package runtime when inventory/current.json and in-memory
        registry diverge.

        This protects run_tool/list_tools from executing a removed or outdated
        package implementation after rollback/remove/restart edge cases.
        """
        if not module_name or not self.module_manager:
            return

        active_path, expected_method = self._get_expected_tool_method_from_active_manifest(
            module_name,
            full_tool_name or module_name,
        )
        loaded_instance = self._get_loaded_module_instance(module_name)
        registry_tool = self.registry.get_tool(full_tool_name) if full_tool_name else None
        registry_module = self.registry.get_module(module_name)
        source_path = self._get_module_source_path(loaded_instance)

        should_rebuild = False
        reasons: List[str] = []

        if active_path:
            active_path_resolved = active_path.resolve()
            if loaded_instance is None:
                should_rebuild = True
                reasons.append("loaded_instance_missing")
            elif source_path is not None and active_path_resolved not in source_path.parents:
                should_rebuild = True
                reasons.append(f"source_path_mismatch:{source_path}")

            if registry_module is None:
                should_rebuild = True
                reasons.append("registry_module_missing")

            if full_tool_name and expected_method:
                current_method = registry_tool.get("method_name") if registry_tool else None
                if current_method != expected_method:
                    should_rebuild = True
                    reasons.append(
                        f"tool_method_mismatch:{current_method or '<missing>'}!={expected_method}"
                    )
        else:
            if loaded_instance is not None and self._is_dynamic_module_instance(loaded_instance):
                should_rebuild = True
                reasons.append("stale_dynamic_runtime_without_active_version")
            elif registry_module is not None and loaded_instance is None and module_name not in self.enabled_modules:
                should_rebuild = True
                reasons.append("stale_registry_without_loaded_instance")

        if not should_rebuild:
            return

        logger.warning(
            f"[runtime_self_heal] Rebuilding registry for module '{module_name}' due to: {', '.join(reasons)}"
        )
        self._purge_module_runtime(module_name)
        await self._rebuild_registry_from_active_modules()

    async def _ensure_all_package_runtime_matches_inventory(self) -> None:
        if not self.module_manager:
            return

        module_names = {
            module_info.get("name")
            for module_info in self.module_manager.list_installed().get("modules", [])
            if module_info.get("name")
        }
        module_names.update(
            getattr(module, "name", None)
            for module in self.loaded_modules
            if self._is_dynamic_module_instance(module)
        )
        module_names.discard(None)

        for module_name in sorted(module_names):
            await self._ensure_module_runtime_matches_inventory(module_name)

    async def _emit_module_state_changed(self, reason: str = "unknown") -> None:
        """
        Publishes device_event module_state_changed with current modules snapshot.
        Server uses this to update actual state and trigger reconcile.
        """
        try:
            if not self.db_manager or not self.device_id or not self.module_manager:
                return
            snapshot = self.module_manager.list_installed().get("modules", [])
            await self.db_manager.enqueue_event(
                device_id=self.device_id,
                kind="module_state_changed",
                payload={
                    "event": "module_state_changed",
                    "reason": reason,
                    "modules_snapshot": snapshot,
                },
                actor_role="system",
                ticket_id=None,
                trace_id=None,
                span_id=None,
                batch_seq=0,
            )
            logger.info(f"[module_state_changed] Event enqueued: reason={reason} modules={len(snapshot)}")
        except Exception as e:
            logger.warning(f"[module_state_changed] Failed to enqueue event: {e}")

    async def _handle_rollback_module(self, name: Optional[str], actor_role: str, meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'rollback_module' - РѕС‚РєР°С‚ РјРѕРґСѓР»СЏ РЅР° РїСЂРµРґС‹РґСѓС‰СѓСЋ РІРµСЂСЃРёСЋ.
        
        Args:
            name: РРјСЏ РјРѕРґСѓР»СЏ
            actor_role: Р РѕР»СЊ Р°РєС‚РѕСЂР° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂР°РІ РґРѕСЃС‚СѓРїР°
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј РѕС‚РєР°С‚Р° РјРѕРґСѓР»СЏ
        """
        if actor_role != "admin":
            return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
        if not name:
            return fail(code="ROLLBACK_FAILED", message="name required", meta=meta)

        prev_path = self.module_manager.rollback(name)
        if not prev_path:
            return fail(code="ROLLBACK_FAILED", message="No previous version to rollback", meta=meta, retriable=False)

        # РџРѕСЃР»Рµ rollback РћР‘РЇР—РђРўР•Р›Р¬РќРћ РІС‹Р·РІР°С‚СЊ С‚Сѓ Р¶Рµ Р»РѕРіРёРєСѓ rebuild registry, С‡С‚Рѕ Рё РІ activate_module
        self._purge_module_runtime(name)
        await self._rebuild_registry_from_active_modules()
        await self._emit_module_state_changed(reason=f"rollback:{name}")

        return ok(
            data=ToolData(
                observations={
                    "rolled_back": name,
                    "active_path": str(prev_path),
                    "active_version": prev_path.name,
                }
            ),
            meta=meta,
        )
    
    async def _handle_deactivate_module(self, name: Optional[str], actor_role: str, meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'deactivate_module' - РґРµР°РєС‚РёРІР°С†РёСЏ РјРѕРґСѓР»СЏ.
        
        Args:
            name: РРјСЏ РјРѕРґСѓР»СЏ
            actor_role: Р РѕР»СЊ Р°РєС‚РѕСЂР° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂР°РІ РґРѕСЃС‚СѓРїР°
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј РґРµР°РєС‚РёРІР°С†РёРё РјРѕРґСѓР»СЏ
        """
        if actor_role != "admin":
            return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
        if not name:
            return fail(code="DEACTIVATE_FAILED", message="name required", meta=meta)

        self.module_manager.deactivate(name)
        self._purge_module_runtime(name)

        # rebuild
        await self._rebuild_registry_from_active_modules()
        # emit module_state_changed
        await self._emit_module_state_changed(reason=f"deactivate:{name}")

        return ok(data=ToolData(observations={"deactivated": name}), meta=meta)
    
    async def _handle_remove_module_version(
        self,
        name: Optional[str],
        version: Optional[str],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """Remove specific version of module."""
        if actor_role != "admin":
            return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
        if not name or not version:
            return fail(code="REMOVE_FAILED", message="name and version required", meta=meta)
        
        try:
            # Check if version is active before removal
            installed_info = self.module_manager.list_installed()
            for module_info in installed_info.get("modules", []):
                if module_info["name"] == name:
                    active_version = module_info.get("active")
                    if active_version == version:
                        return fail(
                            code="REMOVE_FAILED",
                            message=f"Cannot remove active version {version} of {name}. Deactivate first.",
                            meta=meta,
                            retriable=False
                        )
                    break
            
            removed = self.module_manager.remove_version(name, version)
            if removed:
                remaining_modules = {
                    module_info["name"]
                    for module_info in self.module_manager.list_installed().get("modules", [])
                }
                if name not in remaining_modules:
                    self._purge_module_runtime(name)
                    await self._rebuild_registry_from_active_modules()
                    await self._emit_module_state_changed(reason=f"remove_version:{name}@{version}")
                return ok(data=ToolData(observations={"removed": f"{name}@{version}"}), meta=meta)
            else:
                return fail(code="REMOVE_FAILED", message="Version not found", meta=meta, retriable=False)
        except ValueError as e:
            return fail(code="REMOVE_FAILED", message=str(e), meta=meta, retriable=False)

    async def _handle_remove_module(
        self,
        name: Optional[str],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """Remove all versions of module."""
        if actor_role != "admin":
            return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
        if not name:
            return fail(code="REMOVE_FAILED", message="name required", meta=meta)
        
        try:
            # Check if module has active version
            installed_info = self.module_manager.list_installed()
            for module_info in installed_info.get("modules", []):
                if module_info["name"] == name:
                    active_version = module_info.get("active")
                    if active_version is not None:
                        return fail(
                            code="REMOVE_FAILED",
                            message=f"Cannot remove module {name}: has active version {active_version}. Deactivate first.",
                            meta=meta,
                            retriable=False
                        )
                    break
            
            removed = self.module_manager.remove_module(name)
            if removed:
                self._purge_module_runtime(name)
                await self._rebuild_registry_from_active_modules()
                await self._emit_module_state_changed(reason=f"remove:{name}")
                return ok(data=ToolData(observations={"removed": name}), meta=meta)
            else:
                return fail(code="REMOVE_FAILED", message="Module not found", meta=meta, retriable=False)
        except ValueError as e:
            return fail(code="REMOVE_FAILED", message=str(e), meta=meta, retriable=False)
    
    async def _handle_cancel_operation(
        self,
        target_operation_id: Optional[str],
        meta: ToolMeta
    ) -> ToolResponse:
        """
        РћС‚РјРµРЅСЏРµС‚ РІС‹РїРѕР»РЅСЏСЋС‰СѓСЋСЃСЏ РѕРїРµСЂР°С†РёСЋ.
        
        РљР РРўРР§РќРћ: РСЃРїРѕР»СЊР·СѓРµС‚ timeout РґР»СЏ РїСЂРµРґРѕС‚РІСЂР°С‰РµРЅРёСЏ Р·Р°РІРёСЃР°РЅРёСЏ cancel-РєРѕРјР°РЅРґС‹.
        
        Args:
            target_operation_id: ID РѕРїРµСЂР°С†РёРё РґР»СЏ РѕС‚РјРµРЅС‹ (РґРѕР»Р¶РµРЅ СЃРѕРІРїР°РґР°С‚СЊ СЃ РєР»СЋС‡РѕРј РІ running_tasks)
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј РѕС‚РјРµРЅС‹
        """
        if not target_operation_id:
            return fail(
                code="INVALID_REQUEST",
                message="target_operation_id is required",
                meta=meta,
                retriable=False
            )
        
        if target_operation_id in self.running_tasks:
            task = self.running_tasks[target_operation_id]
            task.cancel()
            
            # РљР РРўРР§РќРћ: timeout РґР»СЏ РїСЂРµРґРѕС‚РІСЂР°С‰РµРЅРёСЏ Р·Р°РІРёСЃР°РЅРёСЏ cancel-РєРѕРјР°РЅРґС‹
            # Р•СЃР»Рё task РІС‹РїРѕР»РЅСЏРµС‚ Р±Р»РѕРєРёСЂСѓСЋС‰СѓСЋ РѕРїРµСЂР°С†РёСЋ РёР»Рё РїР»РѕС…Рѕ РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚ cancellation,
            # await task РјРѕР¶РµС‚ Р·Р°РІРёСЃРЅСѓС‚СЊ, Рё cancel-РєРѕРјР°РЅРґР° СЃР°РјР° СЃС‚Р°РЅРµС‚ "РІРµС‡РЅРѕР№"
            CANCEL_TIMEOUT = 2.0  # 2 СЃРµРєСѓРЅРґС‹ РјР°РєСЃРёРјСѓРј РЅР° graceful cancellation
            
            try:
                await asyncio.wait_for(task, timeout=CANCEL_TIMEOUT)
                cancel_status = "canceled"
            except asyncio.CancelledError:
                cancel_status = "canceled"
            except asyncio.TimeoutError:
                # Task РЅРµ РѕС‚РјРµРЅРёР»СЃСЏ Р·Р° timeout - РЅРѕ cancel-РєРѕРјР°РЅРґР° РґРѕР»Р¶РЅР° Р·Р°РІРµСЂС€РёС‚СЊСЃСЏ
                cancel_status = "cancel_requested"  # РёР»Рё "cannot_cancel_gracefully"
                logger.warning(
                    f"[cancel_operation] Task {target_operation_id} did not cancel gracefully within {CANCEL_TIMEOUT}s"
                )
            
            # РљР РРўРР§РќРћ: РћР±СЏР·Р°С‚РµР»СЊРЅРѕ РѕРїСѓР±Р»РёРєРѕРІР°С‚СЊ СЃРѕР±С‹С‚РёРµ canceled РґР»СЏ target РѕРїРµСЂР°С†РёРё
            # Р­С‚Рѕ РєСЂРёС‚РёС‡РЅРѕ РґР»СЏ UI Рё redundancy РЅР° СЃРµСЂРІРµСЂРµ
            # Р•СЃР»Рё cancel-РєРѕРјР°РЅРґР° success, Р° РѕР±РЅРѕРІР»РµРЅРёРµ target-op РЅР° СЃРµСЂРІРµСЂРµ РЅРµ РїСЂРѕС€Р»Рѕ (transient DB error),
            # СЃРѕР±С‹С‚РёРµ РѕС‚ Р°РіРµРЅС‚Р° РїРѕР·РІРѕР»РёС‚ РґРѕРІРµСЃС‚Рё operation РґРѕ canceled ("РІС‚РѕСЂР°СЏ Р»РёРЅРёСЏ")
            
            # РР·РІР»РµРєР°РµРј ticket_id РёР· meta РµСЃР»Рё РґРѕСЃС‚СѓРїРµРЅ
            ticket_id = getattr(meta, 'ticket_id', None)
            device_id = getattr(meta, 'device_id', None) or self.device_id
            
            if ticket_id and self.db_manager:
                try:
                    await self.db_manager.enqueue_job_event(
                        job_id=None,  # РњРѕР¶РµС‚ Р±С‹С‚СЊ None РґР»СЏ РѕРїРµСЂР°С†РёР№ Р±РµР· job
                        request_id=target_operation_id,
                        device_id=device_id,
                        event_payload={
                            "event": "tool_call_result",  # РёР»Рё "agent_action"
                            "ticket_id": ticket_id,
                            "operation_id": target_operation_id,
                            "status": "canceled",
                            "cancel_status": cancel_status
                        }
                    )
                except Exception as e:
                    logger.error(f"[cancel_operation] Failed to publish canceled event: {e}")
            
            return ok(
                data={
                    "cancel_status": cancel_status,
                    "target_operation_id": target_operation_id
                },
                meta=meta
            )
        else:
            # РћРїРµСЂР°С†РёСЏ РЅРµ РЅР°Р№РґРµРЅР° РёР»Рё СѓР¶Рµ Р·Р°РІРµСЂС€РµРЅР°
            return fail(
                code="UNKNOWN_OPERATION",
                message=f"Operation {target_operation_id} not found or already finished",
                meta=meta,
                retriable=False
            )
    
    async def _handle_update(self, command: Dict[str, Any], meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'update' - РѕР±РЅРѕРІР»РµРЅРёРµ Р°РіРµРЅС‚Р° (self-update).
        
        Args:
            command: РџРѕР»РЅС‹Р№ payload РєРѕРјР°РЅРґС‹ (params РёР· WS), РІРєР»СЋС‡Р°СЏ download_url/sha256/size/version.
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј РѕРїРµСЂР°С†РёРё РѕР±РЅРѕРІР»РµРЅРёСЏ
        """
        try:
            actor_role = (command.get("actor_role") or "user").lower()
            if actor_role != "admin":
                return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)

            version = command.get("version")
            target = command.get("target")
            channel = command.get("channel") or "stable"
            download_url = command.get("download_url")
            expected_sha256 = command.get("sha256")
            expected_size = command.get("size")
            restart_delay_sec = command.get("restart_delay_sec")
            archive_type = command.get("archive_type") or "zip"
            operation_id = (meta.request_id or "") if hasattr(meta, "request_id") else ""
            requested_by = (command.get("actor_role") or "admin").lower()

            if not version:
                return fail(code="UPDATE_FAILED", message="Missing version", meta=meta, retriable=False)
            if not download_url:
                return fail(code="UPDATE_FAILED", message="Missing download_url", meta=meta, retriable=False)
            if not expected_sha256:
                return fail(code="UPDATE_FAILED", message="Missing sha256", meta=meta, retriable=False)
            if archive_type not in ("zip", "tar.gz", "tgz"):
                return fail(code="UPDATE_FAILED", message="Unsupported archive_type", meta=meta, retriable=False)
            # tgz вЂ” Р°Р»РёР°СЃ РґР»СЏ tar.gz (launcher/installer РїРѕРґРґРµСЂР¶РёРІР°РµС‚ РѕР±Р°)

            # data_root/updates/downloads
            if self._data_root is not None:
                data_dir = self._data_root
            else:
                agent_dir = pathlib.Path(__file__).resolve().parent.parent
                data_dir = agent_dir / get_config().paths.data_dir
            updates_dir = data_dir / "updates"
            downloads_dir = updates_dir / "downloads"
            downloads_dir.mkdir(parents=True, exist_ok=True)
            ext = "zip" if archive_type == "zip" else "tar.gz"
            artifact_path = downloads_dir / f"build.{ext}"

            dl_sha256, dl_size = await self._download_file_to_path(
                url=download_url,
                dest_path=artifact_path,
                expected_sha256=expected_sha256,
                expected_size=expected_size,
            )

            received_at = datetime.now(timezone.utc).isoformat()
            # Launcher РѕР¶РёРґР°РµС‚ archive_type "zip" РёР»Рё "tar.gz"/"tgz"; СЃРѕС…СЂР°РЅСЏРµРј РЅРѕСЂРјР°Р»РёР·РѕРІР°РЅРЅС‹Р№ РґР»СЏ СЂР°СЃРїР°РєРѕРІРєРё
            pending_archive_type = "tar.gz" if archive_type == "tgz" else archive_type
            pending_payload = {
                "version": version,
                "target": target,
                "channel": channel,
                "archive_type": pending_archive_type,
                "artifact_path": str(artifact_path.resolve()),
                "received_at": received_at,
                "operation_id": operation_id,
                "requested_by": requested_by,
                "sha256": dl_sha256,
                "size": dl_size,
            }
            pending_path = updates_dir / "pending_update.json"
            pending_path.write_text(json.dumps(pending_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            restart_delay = 2
            if isinstance(restart_delay_sec, int) and 0 <= restart_delay_sec <= 60:
                restart_delay = restart_delay_sec
            try:
                loop = asyncio.get_running_loop()
                loop.call_later(restart_delay, lambda: os._exit(EXIT_UPDATE_PENDING))
            except Exception as e:
                logger.warning(f"[update] Failed to schedule exit: {e}")

            observations = {
                "message": "scheduled",
                "requested_version": version,
                "current_version": AGENT_VERSION,
                "target": target,
                "channel": channel,
                "archive_type": archive_type,
                "downloaded_sha256": dl_sha256,
                "downloaded_size": dl_size,
                "exit_code_pending": EXIT_UPDATE_PENDING,
            }
            return ok(data=ToolData(observations=observations), meta=meta)
            
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РІ _handle_update: {e}")
            raise

    async def _download_file_to_path(
        self,
        *,
        url: str,
        dest_path: pathlib.Path,
        expected_sha256: Optional[str],
        expected_size: Optional[int],
        chunk_size: int = 8192,
    ) -> tuple[str, int]:
        """
        Download a file to disk with streaming sha256 verification.

        Uses agent token for Authorization (Bearer) when available.
        """
        if aiohttp is None:
            raise ImportError("aiohttp is required for update downloads")

        headers: dict[str, str] = {}
        if self.identity_manager and self.identity_manager.has_token:
            token = self.identity_manager.token
            if token:
                headers["Authorization"] = f"Bearer {token}"
                logger.debug(f"[UpdateDownload] Using token for download: {token[:8]}...")

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

        sha256_hash = hashlib.sha256()
        total_size = 0

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 401:
                        raise RuntimeError("Download failed: HTTP 401 (AUTH_REQUIRED)")
                    if resp.status != 200:
                        raise RuntimeError(f"Download failed: HTTP {resp.status}")

                    content_length = resp.headers.get("Content-Length")
                    if expected_size and content_length and int(content_length) != int(expected_size):
                        raise ValueError(f"Size mismatch: expected {expected_size}, got {content_length}")

                    with open(tmp_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(chunk_size):
                            if not chunk:
                                break
                            total_size += len(chunk)
                            sha256_hash.update(chunk)
                            f.write(chunk)

            actual_sha256 = sha256_hash.hexdigest()
            if expected_sha256 and actual_sha256 != expected_sha256:
                raise ValueError(f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}")

            if expected_size and total_size != int(expected_size):
                raise ValueError(f"Size mismatch: expected {expected_size}, got {total_size}")

            tmp_path.replace(dest_path)
            return actual_sha256, total_size
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            raise
    
    async def _handle_install_module_package(
        self,
        name: Optional[str],
        version: Optional[str],
        package_b64: Optional[str],
        download_url: Optional[str],
        sha256: Optional[str],
        size: Optional[int],
        actor_role: str,
        meta: ToolMeta,
        *,
        replace_if_different_sha: bool = False
    ) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'install_module_package' - СѓСЃС‚Р°РЅРѕРІРєР° РґРёРЅР°РјРёС‡РµСЃРєРѕРіРѕ РјРѕРґСѓР»СЏ РёР· РїР°РєРµС‚Р°.
        
        РџРѕРґРґРµСЂР¶РёРІР°РµС‚ РґРІР° СЂРµР¶РёРјР°:
        1. download_url (РЅРѕРІС‹Р№): СЃРєР°С‡РёРІР°РµС‚ ZIP РїРѕ HTTP, РїСЂРѕРІРµСЂСЏРµС‚ sha256, СѓСЃС‚Р°РЅР°РІР»РёРІР°РµС‚
        2. package_b64 (fallback): СЂР°Р±РѕС‚Р°РµС‚ РєР°Рє СЂР°РЅСЊС€Рµ (РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё)
        
        Args:
            name: РРјСЏ РјРѕРґСѓР»СЏ
            version: Р’РµСЂСЃРёСЏ РјРѕРґСѓР»СЏ
            package_b64: ZIP-Р°СЂС…РёРІ РјРѕРґСѓР»СЏ РІ С„РѕСЂРјР°С‚Рµ base64 (fallback)
            download_url: URL РґР»СЏ СЃРєР°С‡РёРІР°РЅРёСЏ ZIP (РЅРѕРІС‹Р№ СЃРїРѕСЃРѕР±)
            sha256: SHA256 С…РµС€ Р°СЂС…РёРІР° (РѕР±СЏР·Р°С‚РµР»РµРЅ РґР»СЏ download_url)
            size: Р Р°Р·РјРµСЂ С„Р°Р№Р»Р° РІ Р±Р°Р№С‚Р°С… (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ, РґР»СЏ РїСЂРѕРІРµСЂРєРё)
            actor_role: Р РѕР»СЊ Р°РєС‚РѕСЂР° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂР°РІ РґРѕСЃС‚СѓРїР°
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
            replace_if_different_sha: РџСЂРё РєРѕРЅС„Р»РёРєС‚Рµ SHA (С‚Р° Р¶Рµ РІРµСЂСЃРёСЏ, РґСЂСѓРіРѕР№ С…РµС€) СѓРґР°Р»РёС‚СЊ СЃС‚Р°СЂС‹Р№ РєР°С‚Р°Р»РѕРі Рё СѓСЃС‚Р°РЅРѕРІРёС‚СЊ Р·Р°РЅРѕРІРѕ.
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј СѓСЃС‚Р°РЅРѕРІРєРё РјРѕРґСѓР»СЏ
        """
        try:
            # 1) Gate: РїСЂРѕРІРµСЂРєР° РїСЂР°РІ РґРѕСЃС‚СѓРїР° (admin вЂ” СЃ Р°РґРјРёРЅРєРё, system вЂ” СЃРµСЂРІРµСЂРЅР°СЏ СѓСЃС‚Р°РЅРѕРІРєР°, РЅР°РїСЂРёРјРµСЂ reconcile)
            if actor_role not in ("admin", "system"):
                return fail(
                    code="FORBIDDEN",
                    message="admin only",
                    meta=meta,
                    retriable=False
                )
            
            # 2) Validate input: РїСЂРѕРІРµСЂРєР° РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ
            if not name:
                return fail(
                    code="INSTALL_FAILED",
                    message='РќРµ СѓРєР°Р·Р°РЅРѕ РёРјСЏ РјРѕРґСѓР»СЏ (РїРѕР»Рµ "name" РёР»Рё "module_name")',
                    meta=meta
                )
            
            if not version:
                return fail(
                    code="INSTALL_FAILED",
                    message='РќРµ СѓРєР°Р·Р°РЅР° РІРµСЂСЃРёСЏ РјРѕРґСѓР»СЏ (РїРѕР»Рµ "version" РёР»Рё "module_version")',
                    meta=meta
                )
            
            zip_bytes = None
            
            # 3) Download or decode: РїРѕР»СѓС‡РµРЅРёРµ ZIP С„Р°Р№Р»Р°
            if download_url:
                # Р РµР¶РёРј 1: HTTP download
                if not sha256:
                    return fail(
                        code="INSTALL_FAILED",
                        message="sha256 is required when using download_url",
                        meta=meta
                    )
                
                if aiohttp is None:
                    return fail(
                        code="INSTALL_FAILED",
                        message="aiohttp is required for download_url mode",
                        meta=meta
                    )
                
                try:
                    zip_bytes = await self._download_module_zip(download_url, sha256, size)
                    logger.info(f"СЂСџвЂњВ¦ РњРѕРґСѓР»СЊ '{name}' РІРµСЂСЃРёРё '{version}' СЃРєР°С‡Р°РЅ РїРѕ HTTP")
                except Exception as e:
                    error_msg = f"РћС€РёР±РєР° СЃРєР°С‡РёРІР°РЅРёСЏ РјРѕРґСѓР»СЏ: {str(e)}"
                    logger.error(error_msg)
                    return fail(
                        code="MODULE_DOWNLOAD_FAILED",
                        message=error_msg,
                        meta=meta,
                        details={"exception_type": type(e).__name__, "exception_message": str(e)}
                    )
            elif package_b64:
                # Р РµР¶РёРј 2: Fallback (СЃС‚Р°СЂС‹Р№ СЃРїРѕСЃРѕР±)
                try:
                    zip_bytes = base64.b64decode(package_b64)
                    logger.info(f"СЂСџвЂњВ¦ РњРѕРґСѓР»СЊ '{name}' РІРµСЂСЃРёРё '{version}' РїРѕР»СѓС‡РµРЅ С‡РµСЂРµР· base64")
                except Exception as e:
                    error_msg = f"РћС€РёР±РєР° РґРµРєРѕРґРёСЂРѕРІР°РЅРёСЏ base64: {str(e)}"
                    logger.error(error_msg)
                    return fail(
                        code="INSTALL_FAILED",
                        message="invalid base64",
                        meta=meta,
                        details={"exception_type": type(e).__name__, "exception_message": str(e)}
                    )
            else:
                return fail(
                    code="INSTALL_FAILED",
                    message='РќРµ СѓРєР°Р·Р°РЅ РїР°РєРµС‚ РјРѕРґСѓР»СЏ (РїРѕР»Рµ "package_b64" РёР»Рё "download_url")',
                    meta=meta
                )
            
            logger.info(f"СЂСџвЂњВ¦ РЈСЃС‚Р°РЅРѕРІРєР° РјРѕРґСѓР»СЏ '{name}' РІРµСЂСЃРёРё '{version}' РёР· РїР°РєРµС‚Р°")
            
            # 4) Install: СѓСЃС‚Р°РЅРѕРІРєР° РјРѕРґСѓР»СЏ (РёРґРµРјРїРѕС‚РµРЅС‚РЅРѕ РїРѕ SHA: same name+version+same sha -> no-op)
            result = None
            already_installed = False
            try:
                result = self.module_manager.install_zip_bytes(
                    zip_bytes, expected_sha256=sha256, replace_if_different_sha=replace_if_different_sha
                )
            except ValueError as e:
                err_str = str(e)
                if "INSTALL_CONFLICT_SHA" in err_str:
                    return fail(
                        code="INSTALL_CONFLICT_SHA",
                        message="РўР° Р¶Рµ РёРјСЏ+РІРµСЂСЃРёСЏ СѓР¶Рµ СѓСЃС‚Р°РЅРѕРІР»РµРЅР° СЃ РґСЂСѓРіРёРј SHA. РЈРґР°Р»РёС‚Рµ РІРµСЂСЃРёСЋ РёР»Рё СѓСЃС‚Р°РЅРѕРІРёС‚Рµ РїР°РєРµС‚ СЃ С‚РµРј Р¶Рµ SHA.",
                        meta=meta,
                        details={"module_name": name, "module_version": version},
                        retriable=False,
                    )
                if "already installed" in err_str.lower():
                    already_installed = True
                    # РњРѕРґСѓР»СЊ СѓР¶Рµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ РІР‚вЂќ Р°РєС‚РёРІРёСЂСѓРµРј Рё Р·Р°РіСЂСѓР¶Р°РµРј, РІРѕР·РІСЂР°С‰Р°РµРј СѓСЃРїРµС…
                    target_path = self.module_manager.store_root / name / version
                    if not target_path.exists():
                        return fail(
                            code="INSTALL_FAILED",
                            message=str(e),
                            meta=meta,
                            details={"module_name": name, "module_version": version}
                        )
                    try:
                        import json
                        manifest_path = target_path / "manifest.json"
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                        result = {
                            "module_name": name,
                            "module_version": version,
                            "path": str(target_path),
                            "manifest": manifest
                        }
                        logger.info(f"РњРѕРґСѓР»СЊ '{name}' РІРµСЂСЃРёРё '{version}' СѓР¶Рµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ, Р°РєС‚РёРІРёСЂСѓРµРј Рё Р·Р°РіСЂСѓР¶Р°РµРј")
                    except Exception as read_e:
                        return fail(
                            code="INSTALL_FAILED",
                            message=f"РњРѕРґСѓР»СЊ СѓР¶Рµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ, РЅРѕ РЅРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕС‡РёС‚Р°С‚СЊ manifest: {read_e}",
                            meta=meta,
                            details={"module_name": name, "module_version": version}
                        )
                else:
                    raise
            except Exception as e:
                error_msg = f"РћС€РёР±РєР° СѓСЃС‚Р°РЅРѕРІРєРё РјРѕРґСѓР»СЏ: {str(e)}"
                logger.error(error_msg)
                logger.exception(e)
                return fail(
                    code="INSTALL_FAILED",
                    message=error_msg,
                    meta=meta,
                    details={"module_name": name, "module_version": version, "exception_type": type(e).__name__}
                )
            
            # РџСЂРѕРІРµСЂРєР° СЃРѕРѕС‚РІРµС‚СЃС‚РІРёСЏ РёРјРµРЅРё Рё РІРµСЂСЃРёРё
            if result["module_name"] != name:
                return fail(
                    code="INSTALL_FAILED",
                    message=f'РќРµСЃРѕРѕС‚РІРµС‚СЃС‚РІРёРµ РёРјРµРЅРё РјРѕРґСѓР»СЏ: РѕР¶РёРґР°Р»РѕСЃСЊ "{name}", РїРѕР»СѓС‡РµРЅРѕ "{result["module_name"]}"',
                    meta=meta,
                    details={"expected_name": name, "actual_name": result["module_name"]}
                )
            
            if result["module_version"] != version:
                return fail(
                    code="INSTALL_FAILED",
                    message=f'РќРµСЃРѕРѕС‚РІРµС‚СЃС‚РІРёРµ РІРµСЂСЃРёРё РјРѕРґСѓР»СЏ: РѕР¶РёРґР°Р»РѕСЃСЊ "{version}", РїРѕР»СѓС‡РµРЅРѕ "{result["module_version"]}"',
                    meta=meta,
                    details={"expected_version": version, "actual_version": result["module_version"]}
                )
            
            if already_installed:
                logger.success(f"РњРѕРґСѓР»СЊ '{name}' РІРµСЂСЃРёРё '{version}' СѓР¶Рµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ, Р°РєС‚РёРІР°С†РёСЏ Рё Р·Р°РіСЂСѓР·РєР° РІС‹РїРѕР»РЅРµРЅС‹")
            else:
                logger.success(f"РњРѕРґСѓР»СЊ '{name}' РІРµСЂСЃРёРё '{version}' СѓСЃРїРµС€РЅРѕ СѓСЃС‚Р°РЅРѕРІР»РµРЅ")
            
            # 5) Activate: Р°РєС‚РёРІР°С†РёСЏ РјРѕРґСѓР»СЏ
            try:
                active_path = self.module_manager.activate(name, version)
                logger.info(f"РњРѕРґСѓР»СЊ '{name}' РІРµСЂСЃРёРё '{version}' Р°РєС‚РёРІРёСЂРѕРІР°РЅ: {active_path}")
            except Exception as e:
                error_msg = f"РћС€РёР±РєР° Р°РєС‚РёРІР°С†РёРё РјРѕРґСѓР»СЏ: {str(e)}"
                logger.error(error_msg)
                logger.exception(e)
                # РћС‚РєР°С‚: РјРѕРґСѓР»СЊ РЅРµ РґРѕР»Р¶РµРЅ РѕСЃС‚Р°РІР°С‚СЊСЃСЏ РЅР° РґРёСЃРєРµ, РµСЃР»Рё РЅРµ СЂР°Р±РѕС‚Р°РµС‚
                try:
                    self.module_manager.remove_version_force(name, version)
                    logger.info(f"РћС‚РєР°С‚: РІРµСЂСЃРёСЏ {name}@{version} СѓРґР°Р»РµРЅР° СЃ РґРёСЃРєР° РїРѕСЃР»Рµ СЃР±РѕСЏ Р°РєС‚РёРІР°С†РёРё")
                except Exception as rollback_e:
                    logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ РєР°С‚Р°Р»РѕРі РїСЂРё РѕС‚РєР°С‚Рµ: {rollback_e}")
                return fail(
                    code="INSTALL_FAILED",
                    message=error_msg,
                    meta=meta,
                    details={"module_name": name, "module_version": version, "exception_type": type(e).__name__}
                )
            
            # 6) Validate load: РїСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РЅРѕРІР°СЏ РІРµСЂСЃРёСЏ РёРјРїРѕСЂС‚РёСЂСѓРµС‚СЃСЏ Р±РµР· runtime cache РѕС‚ РїСЂРµРґС‹РґСѓС‰РµР№.
            try:
                entrypoint = result["manifest"].get("entrypoint", "module:register")
                self.loader.load_module_from_path(name, active_path, entrypoint=entrypoint)
                self.loader.unload_module(name)
                logger.success(f"РњРѕРґСѓР»СЊ '{name}' СѓСЃРїРµС€РЅРѕ РїСЂРѕС€РµР» validate load")
            except Exception as e:
                self.loader.unload_module(name)
                error_msg = f"РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё РјРѕРґСѓР»СЏ: {str(e)}"
                logger.error(error_msg)
                logger.exception(e)
                # РћС‚РєР°С‚: РЅРµСЂР°Р±РѕС‡РёР№ РјРѕРґСѓР»СЊ РЅРµ РѕСЃС‚Р°РІР»СЏРµРј РЅР° РґРёСЃРєРµ (СЂРµС€Р°РµС‚ Р·Р°РІРёСЃС€РёРµ РјРѕРґСѓР»Рё Рё РєРѕРЅС„Р»РёРєС‚ SHA)
                try:
                    self.module_manager.remove_version_force(name, version)
                    logger.info(f"РћС‚РєР°С‚: РІРµСЂСЃРёСЏ {name}@{version} СѓРґР°Р»РµРЅР° СЃ РґРёСЃРєР° РїРѕСЃР»Рµ СЃР±РѕСЏ Р·Р°РіСЂСѓР·РєРё")
                except Exception as rollback_e:
                    logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ РєР°С‚Р°Р»РѕРі РїСЂРё РѕС‚РєР°С‚Рµ: {rollback_e}")
                return fail(
                    code="INSTALL_FAILED",
                    message=error_msg,
                    meta=meta,
                    details={"module_name": name, "module_version": version, "entrypoint": entrypoint, "exception_type": type(e).__name__}
                )
            
            # 7) Rebuild registry: РёСЃРїРѕР»СЊР·СѓРµРј rebuild РІРјРµСЃС‚Рѕ РїСЂСЏРјРѕРіРѕ register
            # Р­С‚Рѕ РѕР±РµСЃРїРµС‡РёС‚ РµРґРёРЅРѕРѕР±СЂР°Р·РЅСѓСЋ РѕР±СЂР°Р±РѕС‚РєСѓ Рё Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєСѓСЋ РѕС‚РїСЂР°РІРєСѓ tools_changed
            self._purge_module_runtime(name)
            await self._rebuild_registry_from_active_modules()
            logger.debug(f"Р РµРµСЃС‚СЂ РјРѕРґСѓР»РµР№ РїРµСЂРµСЃРѕР±СЂР°РЅ РїРѕСЃР»Рµ СѓСЃС‚Р°РЅРѕРІРєРё '{name}'")

            # 7b) GC: РѕСЃС‚Р°РІР»СЏРµРј С‚РѕР»СЊРєРѕ current+prev РІРµСЂСЃРёРё
            if self.module_manager:
                try:
                    removed_versions = self.module_manager.garbage_collect(name, keep=2)
                    if removed_versions:
                        logger.info(
                            f"[GC] РЈРґР°Р»РµРЅС‹ СЃС‚Р°СЂС‹Рµ РІРµСЂСЃРёРё {name}: {removed_versions} (РѕСЃС‚Р°РІР»РµРЅС‹ current+prev)"
                        )
                except Exception as gc_e:
                    logger.warning(f"[GC] РћС€РёР±РєР° GC РґР»СЏ '{name}': {gc_e}")

            # 7c) РџСѓР±Р»РёРєСѓРµРј module_state_changed device_event
            await self._emit_module_state_changed(reason=f"install:{name}@{version}")

            # 8) Return ok
            observations = {
                "installed": name,
                "version": version,
                "path": str(active_path),
                "mode": "package"
            }
            if already_installed:
                observations["already_installed"] = True
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° СѓСЃС‚Р°РЅРѕРІРєРё РјРѕРґСѓР»СЏ '{name}': {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="INSTALL_FAILED",
                message=error_msg,
                meta=meta,
                details={"module_name": name, "module_version": version, "exception_type": type(e).__name__}
            )
    
    async def _download_module_zip(
        self,
        download_url: str,
        expected_sha256: Optional[str],
        expected_size: Optional[int]
    ) -> bytes:
        """
        РЎРєР°С‡РёРІР°РµС‚ ZIP РјРѕРґСѓР»СЏ РїРѕ HTTP СЃ РїСЂРѕРІРµСЂРєРѕР№ sha256.
        
        Phase 6: РћС‚РїСЂР°РІР»СЏРµС‚ С‚РѕРєРµРЅ РІ Authorization header (Bearer token).
        
        Args:
            download_url: URL РґР»СЏ СЃРєР°С‡РёРІР°РЅРёСЏ
            expected_sha256: РћР¶РёРґР°РµРјС‹Р№ SHA256 С…РµС€ (РѕР±СЏР·Р°С‚РµР»РµРЅ)
            expected_size: РћР¶РёРґР°РµРјС‹Р№ СЂР°Р·РјРµСЂ С„Р°Р№Р»Р° (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
        
        Returns:
            bytes: Р‘Р°Р№С‚С‹ ZIP С„Р°Р№Р»Р°
        
        Raises:
            ValueError: Р•СЃР»Рё sha256 РЅРµ СЃРѕРІРїР°РґР°РµС‚
            aiohttp.ClientError: Р•СЃР»Рё download failed
        """
        if aiohttp is None:
            raise ImportError("aiohttp is required for download_url mode")
        
        # Phase 6: РџРѕР»СѓС‡Р°РµРј С‚РѕРєРµРЅ РёР· identity_manager РґР»СЏ Р°СѓС‚РµРЅС‚РёС„РёРєР°С†РёРё
        headers = {}
        if self.identity_manager and self.identity_manager.has_token:
            token = self.identity_manager.token
            if token:
                headers["Authorization"] = f"Bearer {token}"
                logger.debug(f"[DownloadModule] Using token for download: {token[:8]}...")
            else:
                logger.warning("[DownloadModule] Identity manager has token flag but token is None")
        else:
            logger.warning("[DownloadModule] No token available for download authentication")
        
        # РЎРєР°С‡РёРІР°РµРј РІРѕ РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р» (streaming)
        temp_file = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, headers=headers) as response:
                    if response.status == 401:
                        raise aiohttp.ClientError(
                            f"Download failed: Authentication required (HTTP 401). "
                            f"Token may be missing or invalid."
                        )
                    if response.status != 200:
                        raise aiohttp.ClientError(f"Download failed: HTTP {response.status}")
                    
                    # РџСЂРѕРІРµСЂРєР° СЂР°Р·РјРµСЂР° (РµСЃР»Рё СѓРєР°Р·Р°РЅ)
                    if expected_size:
                        content_length = response.headers.get('Content-Length')
                        if content_length and int(content_length) != expected_size:
                            raise ValueError(f"Size mismatch: expected {expected_size}, got {content_length}")
                    
                    # РЎРѕР·РґР°РµРј РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р»
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                    
                    # РџРѕС‚РѕРєРѕРІРѕРµ СЃРєР°С‡РёРІР°РЅРёРµ СЃ РІС‹С‡РёСЃР»РµРЅРёРµРј sha256
                    sha256_hash = hashlib.sha256()
                    async for chunk in response.content.iter_chunked(8192):
                        temp_file.write(chunk)
                        sha256_hash.update(chunk)
                    
                    temp_file.close()
                    
                    # РџСЂРѕРІРµСЂРєР° sha256
                    actual_sha256 = sha256_hash.hexdigest()
                    if expected_sha256 and actual_sha256 != expected_sha256:
                        os.unlink(temp_file.name)
                        raise ValueError(f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}")
                    
                    # РўР•РҐРќРР§Р•РЎРљРР™ Р”РћР›Р“: РЎРµР№С‡Р°СЃ С‡РёС‚Р°РµРј С„Р°Р№Р» РІ РїР°РјСЏС‚СЊ, С‚.Рє. install_zip_bytes РѕР¶РёРґР°РµС‚ bytes.
                    # Р’ РїРµСЂСЃРїРµРєС‚РёРІРµ: РёР·РјРµРЅРёС‚СЊ install_zip_bytes С‡С‚РѕР±С‹ РїСЂРёРЅРёРјР°С‚СЊ path/file-like РѕР±СЉРµРєС‚,
                    # С‡С‚РѕР±С‹ Р±РѕР»СЊС€РёРµ Р°СЂС…РёРІС‹ (>100MB) РЅРµ РґРµСЂР¶Р°Р»РёСЃСЊ РІ RAM.
                    with open(temp_file.name, 'rb') as f:
                        zip_bytes = f.read()
                    
                    # РЈРґР°Р»СЏРµРј РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р»
                    os.unlink(temp_file.name)
                    
                    return zip_bytes
        
        except Exception as e:
            # РћС‡РёСЃС‚РєР° РїСЂРё РѕС€РёР±РєРµ
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise
    
    async def _handle_exec_script(
        self, 
        code: Optional[str],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'exec_script' - РІС‹РїРѕР»РЅРµРЅРёРµ СЃРєСЂРёРїС‚Р° РІ РїР°РјСЏС‚Рё.
        
        Args:
            code: РСЃС…РѕРґРЅС‹Р№ РєРѕРґ СЃРєСЂРёРїС‚Р° (РґРѕР»Р¶РµРЅ СЃРѕРґРµСЂР¶Р°С‚СЊ async С„СѓРЅРєС†РёСЋ run)
            actor_role: Р РѕР»СЊ Р°РєС‚РѕСЂР° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂР°РІ РґРѕСЃС‚СѓРїР°
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј РІС‹РїРѕР»РЅРµРЅРёСЏ СЃРєСЂРёРїС‚Р°
        """
        try:
            # РџСЂРѕРІРµСЂРєР° РїСЂР°РІ РґРѕСЃС‚СѓРїР°: С‚РѕР»СЊРєРѕ admin
            if actor_role != "admin":
                return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
            
            # РџСЂРѕРІРµСЂРєР° РЅР°СЃС‚СЂРѕР№РєРё Р±РµР·РѕРїР°СЃРЅРѕСЃС‚Рё: allow_remote_code РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ True
            if get_config().security.allow_remote_code != True:
                return fail(code="REMOTE_CODE_DISABLED", message="Remote code execution disabled", meta=meta, retriable=False)
            
            # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ РєРѕРґР°
            if not code:
                return fail(
                    code="EXEC_DISABLED",
                    message='РќРµ СѓРєР°Р·Р°РЅ РєРѕРґ СЃРєСЂРёРїС‚Р° (РїРѕР»Рµ "code")',
                    meta=meta
                )
            
            logger.info("СЂСџС™Р‚ Р’С‹РїРѕР»РЅРµРЅРёРµ СЃРєСЂРёРїС‚Р° РІ РїР°РјСЏС‚Рё")
            
            # Р’Р°Р»РёРґР°С†РёСЏ РєРѕРґР°
            validation_result = CodeValidator.validate(code)
            
            if validation_result != 'function':
                error_msg = f"РљРѕРґ РґРѕР»Р¶РµРЅ СЃРѕРґРµСЂР¶Р°С‚СЊ Р°СЃРёРЅС…СЂРѕРЅРЅСѓСЋ С„СѓРЅРєС†РёСЋ 'run'. РџРѕР»СѓС‡РµРЅ С‚РёРї: {validation_result}"
                logger.error(error_msg)
                return fail(
                    code="EXEC_DISABLED",
                    message=error_msg,
                    meta=meta,
                    details={"validation_result": validation_result}
                )
            
            logger.success("РљРѕРґ СЃРєСЂРёРїС‚Р° РІР°Р»РёРґРµРЅ")
            
            # ========== РЎРћР—Р”РђРќРР• РљРћРќРўР•РљРЎРўРђ Р’Р«РџРћР›РќР•РќРРЇ ==========
            # Р‘Р°Р·РѕРІС‹Р№ namespace СЃ РІСЃС‚СЂРѕРµРЅРЅС‹РјРё С„СѓРЅРєС†РёСЏРјРё
            script_globals = {
                '__builtins__': __builtins__,
                # Р‘Р°Р·РѕРІС‹Рµ Р±РёР±Р»РёРѕС‚РµРєРё
                'json': json,
                'datetime': datetime,
                'timedelta': timedelta,
                # Р›РѕРіРіРµСЂ
                'logger': logger,
                # ProcessProvider (СЃРёРЅРіР»С‚РѕРЅ)
                'ProcessProvider': ProcessProvider,
                'registry': self.registry,
            }
            
            # ========== РђР’РўРћРњРђРўРР§Р•РЎРљРР™ РџР РћР‘Р РћРЎ РњРћР”РЈР›Р•Р™ ==========
            # РС‚РµСЂР°С†РёСЏ РїРѕ РІСЃРµРј Р·Р°РіСЂСѓР¶РµРЅРЅС‹Рј РјРѕРґСѓР»СЏРј
            modules_added = []
            for module in self.loaded_modules:
                module_name = module.name
                
                # РџСЂРѕРІРµСЂРєР° РєРѕРЅС„Р»РёРєС‚Р° РёРјРµРЅ
                if module_name in script_globals:
                    # РљРѕРЅС„Р»РёРєС‚ СЃ СЃРёСЃС‚РµРјРЅРѕР№ РїРµСЂРµРјРµРЅРЅРѕР№
                    prefixed_name = f"mod_{module_name}"
                    logger.warning(
                        f"РІС™В РїС‘РЏ РљРѕРЅС„Р»РёРєС‚ РёРјРµРЅ: РјРѕРґСѓР»СЊ '{module_name}' РїРµСЂРµРёРјРµРЅРѕРІР°РЅ РІ '{prefixed_name}'"
                    )
                    script_globals[prefixed_name] = module
                    modules_added.append(prefixed_name)
                else:
                    # РќРѕСЂРјР°Р»СЊРЅРѕРµ РґРѕР±Р°РІР»РµРЅРёРµ РјРѕРґСѓР»СЏ
                    script_globals[module_name] = module
                    modules_added.append(module_name)
            
            logger.info(f"СЂСџвЂњВ¦ РњРѕРґСѓР»Рё РґРѕСЃС‚СѓРїРЅС‹ РІ СЃРєСЂРёРїС‚Рµ: {modules_added}")
            
            # ========== Р’Р«РџРћР›РќР•РќРР• РљРћР”Рђ ==========
            exec(code, script_globals)
            
            # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ С„СѓРЅРєС†РёСЏ run СЃСѓС‰РµСЃС‚РІСѓРµС‚
            if 'run' not in script_globals:
                return fail(
                    code="EXEC_FAILED",
                    message='Р¤СѓРЅРєС†РёСЏ run РЅРµ РЅР°Р№РґРµРЅР° РІ РєРѕРґРµ',
                    meta=meta
                )
            
            # Р’С‹Р·С‹РІР°РµРј Р°СЃРёРЅС…СЂРѕРЅРЅСѓСЋ С„СѓРЅРєС†РёСЋ run
            result = await script_globals['run']()
            
            logger.success(f"РІСљвЂ¦ РЎРєСЂРёРїС‚ РІС‹РїРѕР»РЅРµРЅ СѓСЃРїРµС€РЅРѕ. Р РµР·СѓР»СЊС‚Р°С‚: {result}")
            
            # Р’РѕР·РІСЂР°С‰Р°РµРј СЂРµР·СѓР»СЊС‚Р°С‚ С‡РµСЂРµР· observations
            observations = {
                'result': result,
                'modules_available': modules_added
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° РІС‹РїРѕР»РЅРµРЅРёСЏ СЃРєСЂРёРїС‚Р°: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="EXEC_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    async def _handle_get_manifest(self, meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'get_manifest' - РїРѕР»СѓС‡РµРЅРёРµ РјР°РЅРёС„РµСЃС‚Р° РІСЃРµС… РјРѕРґСѓР»РµР№.
        
        Р’РѕР·РІСЂР°С‰Р°РµС‚ РјР°РЅРёС„РµСЃС‚ РІ С„РѕСЂРјР°С‚Рµ:
        {
            'module_name': {
                'description': '...',
                'methods': {
                    'tool_name': {
                        'tool_name': '...',
                        'module_name': '...',
                        'description': '...',
                        'parameters': [...],
                        'async': True/False
                    }
                }
            }
        }
        
        Args:
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ РїРѕР»РЅС‹Рј РјР°РЅРёС„РµСЃС‚РѕРј СЃРёСЃС‚РµРјС‹ (РјРѕРґСѓР»Рё + core РєРѕРјР°РЅРґС‹)
        """
        try:
            logger.info("СЂСџвЂњвЂ№ РџРѕР»СѓС‡РµРЅРёРµ РјР°РЅРёС„РµСЃС‚Р° РјРѕРґСѓР»РµР№")
            
            # РџРѕР»СѓС‡Р°РµРј РјР°РЅРёС„РµСЃС‚ РѕС‚ РІСЃРµС… Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅРЅС‹С… РјРѕРґСѓР»РµР№
            manifest = self.registry.get_all()
            
            # Р”РѕР±Р°РІР»СЏРµРј СЃРµРєС†РёСЋ "core" СЃ СЃРёСЃС‚РµРјРЅС‹РјРё РєРѕРјР°РЅРґР°РјРё
            manifest['core'] = {
                'description': 'РЎРёСЃС‚РµРјРЅС‹Рµ РєРѕРјР°РЅРґС‹ СЏРґСЂР° РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂР°',
                'methods': {
                    'exec_script': {
                        'tool_name': 'exec_script',
                        'module_name': 'core',
                        'description': 'Р’С‹РїРѕР»РЅРµРЅРёРµ СЃРєСЂРёРїС‚Р° РІ РїР°РјСЏС‚Рё. РЎРєСЂРёРїС‚ РґРѕР»Р¶РµРЅ СЃРѕРґРµСЂР¶Р°С‚СЊ Р°СЃРёРЅС…СЂРѕРЅРЅСѓСЋ С„СѓРЅРєС†РёСЋ run(). Р’ РєРѕРЅС‚РµРєСЃС‚Рµ РґРѕСЃС‚СѓРїРЅС‹ РІСЃРµ Р·Р°РіСЂСѓР¶РµРЅРЅС‹Рµ РјРѕРґСѓР»Рё, logger, ProcessProvider Рё СЃС‚Р°РЅРґР°СЂС‚РЅС‹Рµ Р±РёР±Р»РёРѕС‚РµРєРё (json, datetime, timedelta).',
                        'parameters': [
                            {
                                'name': 'code',
                                'type': 'str',
                                'kind': 'positional_or_keyword'
                            }
                        ],
                        'async': True,
                        'risk_level': 'break_glass',
                        'metadata': {
                            'risk_level': 'code_exec',
                            'scopes': [],
                            'requires_consent': False,
                            'allow_roles': ['admin']
                        }
                    },
                    'install_module_package': {
                        'tool_name': 'install_module_package',
                        'module_name': 'core',
                        'description': 'РЈСЃС‚Р°РЅРѕРІРєР° РґРёРЅР°РјРёС‡РµСЃРєРѕРіРѕ РјРѕРґСѓР»СЏ РёР· РїР°РєРµС‚Р° (ZIP РІ base64). РўСЂРµР±СѓРµС‚ СЂРѕР»СЊ admin.',
                        'parameters': [
                            {
                                'name': 'name',
                                'type': 'str',
                                'kind': 'positional_or_keyword'
                            },
                            {
                                'name': 'version',
                                'type': 'str',
                                'kind': 'positional_or_keyword'
                            },
                            {
                                'name': 'package_b64',
                                'type': 'str',
                                'kind': 'positional_or_keyword'
                            },
                            {
                                'name': 'sha256',
                                'type': 'Optional[str]',
                                'kind': 'positional_or_keyword',
                                'default': None
                            }
                        ],
                        'async': True,
                        'risk_level': 'write_action',
                        'metadata': {
                            'risk_level': 'system_write',
                            'scopes': ['pkg'],
                            'requires_consent': False,
                            'allow_roles': ['admin']
                        }
                    },
                    'update_agent': {
                        'tool_name': 'update_agent',
                        'module_name': 'core',
                        'description': 'РћР±РЅРѕРІР»РµРЅРёРµ Р°РіРµРЅС‚Р° РґРѕ СѓРєР°Р·Р°РЅРЅРѕР№ РІРµСЂСЃРёРё (РёР»Рё РґРѕ РїРѕСЃР»РµРґРЅРµР№ РґРѕСЃС‚СѓРїРЅРѕР№ РІРµСЂСЃРёРё, РµСЃР»Рё РІРµСЂСЃРёСЏ РЅРµ СѓРєР°Р·Р°РЅР°). РЎРєР°С‡РёРІР°РµС‚, РїСЂРѕРІРµСЂСЏРµС‚ Рё РїСЂРёРјРµРЅСЏРµС‚ РѕР±РЅРѕРІР»РµРЅРёРµ.',
                        'parameters': [
                            {
                                'name': 'version',
                                'type': 'Optional[str]',
                                'kind': 'positional_or_keyword',
                                'default': None
                            }
                        ],
                        'async': True
                    }
                }
            }
            
            logger.success(f"РњР°РЅРёС„РµСЃС‚ РїРѕР»СѓС‡РµРЅ: {len(manifest)} СЂР°Р·РґРµР»РѕРІ")
            logger.debug(f"Р Р°Р·РґРµР»С‹ РјР°РЅРёС„РµСЃС‚Р°: {list(manifest.keys())}")
            
            observations = {
                'manifest': manifest
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РјР°РЅРёС„РµСЃС‚Р°: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    def _build_tools_list(self) -> List[Dict[str, Any]]:
        """
        РЎС‚СЂРѕРёС‚ СЃРїРёСЃРѕРє tools РІ С„РѕСЂРјР°С‚Рµ list_tools (РґР»СЏ handshake hash Рё list_tools РѕС‚РІРµС‚Р°).
        
        РљР РРўРР§РќРћ: Р­С‚РѕС‚ РјРµС‚РѕРґ РґРѕР»Р¶РµРЅ РІРѕР·РІСЂР°С‰Р°С‚СЊ РўРћР§РќРћ С‚РѕС‚ Р¶Рµ С„РѕСЂРјР°С‚, С‡С‚Рѕ Рё _handle_list_tools().
        Hash СЃС‡РёС‚Р°РµС‚СЃСЏ РѕС‚ РїРѕР»РЅРѕРіРѕ tool_info (РЅРµ СѓРїСЂРѕС‰С‘РЅРЅРѕРіРѕ), С‡С‚РѕР±С‹ РёР·РјРµРЅРµРЅРёСЏ spec 
        (params_schema, metadata) РїСЂР°РІРёР»СЊРЅРѕ РѕС‚СЂР°Р¶Р°Р»РёСЃСЊ РІ hash.
        
        Returns:
            РЎРїРёСЃРѕРє tool dictionaries СЃ РїРѕР»СЏРјРё tool, module, spec (РїРѕР»РЅС‹Р№ С„РѕСЂРјР°С‚)
        """
        # РџРѕР»СѓС‡Р°РµРј РїР»РѕСЃРєРёР№ СЃРїРёСЃРѕРє РІСЃРµС… tools РёР· registry
        tools_flat = self.registry.get_tools_flat()
        
        # Р¤РѕСЂРјРёСЂСѓРµРј СЃРїРёСЃРѕРє РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ (РїРѕР»РЅС‹Р№ С„РѕСЂРјР°С‚ РєР°Рє РІ _handle_list_tools)
        tools_list = []
        for tool_data in tools_flat:
            tool_name = tool_data.get('tool')
            module_name = tool_data.get('module')
            spec = tool_data.get('spec', {})
            
            # РР·РІР»РµРєР°РµРј metadata РёР· spec
            metadata = spec.get('metadata', {})
            if not metadata:
                # Р•СЃР»Рё metadata РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚, РїСЂРѕСЃС‚Р°РІР»СЏРµРј default
                metadata = {
                    'risk_level': 'safe_read',
                    'scopes': [],
                    'requires_consent': False,
                    'allow_roles': None
                }
            
            # РџРѕР»СѓС‡Р°РµРј presets РёР· spec
            presets = spec.get('presets', [])
            
            # Р•СЃР»Рё presets РїСѓСЃС‚Рѕ Рё РјРѕРґСѓР»СЊ РЅРµ С‚СЂРµР±СѓРµС‚ РїР°СЂР°РјРµС‚СЂРѕРІ (РёР»Рё РёРјРµРµС‚ С‚РѕР»СЊРєРѕ РѕРїС†РёРѕРЅР°Р»СЊРЅС‹Рµ),
            # РґРѕР±Р°РІР»СЏРµРј РґРµС„РѕР»С‚РЅС‹Р№ РїСЂРµСЃРµС‚ "Р—Р°РїСѓСЃС‚РёС‚СЊ"
            params_schema = spec.get('params_schema', {})
            properties = params_schema.get('properties', {})
            
            # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ РїР°СЂР°РјРµС‚СЂС‹
            has_required_params = False
            if properties:
                for prop_name, prop_schema in properties.items():
                    # Р•СЃР»Рё РїР°СЂР°РјРµС‚СЂ РЅРµ РёРјРµРµС‚ default Р·РЅР°С‡РµРЅРёСЏ, СЃС‡РёС‚Р°РµРј РµРіРѕ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Рј
                    if 'default' not in prop_schema:
                        has_required_params = True
                        break
            
            # Р•СЃР»Рё РЅРµС‚ presets Рё РЅРµС‚ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ, РґРѕР±Р°РІР»СЏРµРј РґРµС„РѕР»С‚РЅС‹Р№ РїСЂРµСЃРµС‚
            if not presets and not has_required_params:
                presets = [{
                    'id': 'default',
                    'name': 'в–¶пёЏ Р—Р°РїСѓСЃС‚РёС‚СЊ',
                    'description': 'Р—Р°РїСѓСЃС‚РёС‚СЊ СЃ РїР°СЂР°РјРµС‚СЂР°РјРё РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ',
                    'params': {}
                }]
            
            # Р¤РѕСЂРјРёСЂСѓРµРј СЃС‚СЂСѓРєС‚СѓСЂСѓ tool СЃ РІР»РѕР¶РµРЅРЅС‹Рј spec (РїРѕР»РЅС‹Р№ С„РѕСЂРјР°С‚)
            tool_info = {
                'tool': tool_name,
                'module': module_name,
                'spec': {
                    'description': spec.get('description', 'РћРїРёСЃР°РЅРёРµ РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚'),
                    'risk_level': spec.get('risk_level', 'safe_readonly'),
                    'capabilities': spec.get('capabilities'),
                    'params_schema': params_schema,
                    'presets': presets,
                    'metadata': {
                        'risk_level': metadata.get('risk_level', 'safe_read'),
                        'scopes': metadata.get('scopes', []),
                        'requires_consent': metadata.get('requires_consent', False),
                        'allow_roles': metadata.get('allow_roles')
                    }
                }
            }
            tools_list.append(tool_info)
        
        # РќР• СЃРѕСЂС‚РёСЂСѓРµРј Р·РґРµСЃСЊ - СЃРѕСЂС‚РёСЂРѕРІРєР° РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ РІ compute_toolset_hash()
        return tools_list
    
    async def _handle_list_tools(self, meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'list_tools' - РІРѕР·РІСЂР°С‰Р°РµС‚ СЃРїРёСЃРѕРє РІСЃРµС… РґРѕСЃС‚СѓРїРЅС‹С… РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ.
        
        Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃРїРёСЃРѕРє РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ Р±РµР· РїРѕР»РЅРѕР№ РёРЅС„РѕСЂРјР°С†РёРё Рѕ РїР°СЂР°РјРµС‚СЂР°С…
        (С‚РѕР»СЊРєРѕ name, module, description, risk_level, capabilities).
        
        Args:
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃРѕ СЃРїРёСЃРєРѕРј РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ РІ observations.tools
        """
        try:
            logger.info("СЂСџвЂњвЂ№ РџРѕР»СѓС‡РµРЅРёРµ СЃРїРёСЃРєР° РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ")

            await self._ensure_all_package_runtime_matches_inventory()
            
            # РСЃРїРѕР»СЊР·СѓРµРј _build_tools_list() РґР»СЏ РµРґРёРЅРѕРѕР±СЂР°Р·РёСЏ
            tools_list = self._build_tools_list()
            
            logger.success(f"РќР°Р№РґРµРЅРѕ РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ: {len(tools_list)}")
            
            observations = {
                'tools': tools_list
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    async def _handle_describe_tool(self, tool_name: Optional[str], meta: ToolMeta) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'describe_tool' - РІРѕР·РІСЂР°С‰Р°РµС‚ РїРѕР»РЅСѓСЋ РёРЅС„РѕСЂРјР°С†РёСЋ РѕР± РёРЅСЃС‚СЂСѓРјРµРЅС‚Рµ.
        
        Р’РѕР·РІСЂР°С‰Р°РµС‚ РїРѕР»РЅСѓСЋ РёРЅС„РѕСЂРјР°С†РёСЋ РѕР± РёРЅСЃС‚СЂСѓРјРµРЅС‚Рµ, РІРєР»СЋС‡Р°СЏ parameters, params_schema,
        risk_level, capabilities, async СЃС‚Р°С‚СѓСЃ.
        
        Args:
            tool_name: РРјСЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° РґР»СЏ РѕРїРёСЃР°РЅРёСЏ
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ РїРѕР»РЅРѕР№ РёРЅС„РѕСЂРјР°С†РёРµР№ РѕР± РёРЅСЃС‚СЂСѓРјРµРЅС‚Рµ РІ observations.tool
            РёР»Рё fail СЃ РєРѕРґРѕРј TOOL_NOT_FOUND, РµСЃР»Рё РёРЅСЃС‚СЂСѓРјРµРЅС‚ РЅРµ РЅР°Р№РґРµРЅ
        """
        try:
            if not tool_name:
                return fail(
                    code="TOOL_NOT_FOUND",
                    message='РќРµ СѓРєР°Р·Р°РЅРѕ РёРјСЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° (РїРѕР»Рµ "tool" РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РёР»Рё РїСѓСЃС‚РѕРµ)',
                    meta=meta,
                    retriable=False
                )
            
            logger.info(f"СЂСџвЂњвЂ№ РџРѕР»СѓС‡РµРЅРёРµ РѕРїРёСЃР°РЅРёСЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°: {tool_name}")
            
            # РџРѕР»СѓС‡Р°РµРј РїР»РѕСЃРєРёР№ СЃРїРёСЃРѕРє РІСЃРµС… tools РёР· registry
            tools_flat = self.registry.get_tools_flat()
            
            # РС‰РµРј tool РїРѕ РёРјРµРЅРё
            tool_found = None
            for tool_data in tools_flat:
                if tool_data.get('tool') == tool_name:
                    tool_found = tool_data
                    break
            
            if not tool_found:
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=f'РРЅСЃС‚СЂСѓРјРµРЅС‚ "{tool_name}" РЅРµ РЅР°Р№РґРµРЅ РІ СЂРµРµСЃС‚СЂРµ',
                    meta=meta,
                    retriable=False
                )
            
            # Р¤РѕСЂРјРёСЂСѓРµРј РїРѕР»РЅСѓСЋ РёРЅС„РѕСЂРјР°С†РёСЋ РѕР± РёРЅСЃС‚СЂСѓРјРµРЅС‚Рµ
            spec = tool_found.get('spec', {})
            tool_info = {
                'name': tool_found.get('tool'),
                'module': tool_found.get('module'),
                'description': spec.get('description', 'РћРїРёСЃР°РЅРёРµ РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚'),
                'parameters': spec.get('parameters', []),
                'params_schema': spec.get('params_schema', {}),
                'risk_level': spec.get('risk_level', 'safe_readonly'),
                'capabilities': spec.get('capabilities'),
                'async': spec.get('async', False)
            }
            
            logger.success(f"РРЅСЃС‚СЂСѓРјРµРЅС‚ РЅР°Р№РґРµРЅ: {tool_name}")
            
            observations = {
                'tool': tool_info
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РѕРїРёСЃР°РЅРёСЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    def _session_key_from_command(self, meta: ToolMeta, params: Dict[str, Any]) -> str:
        """
        РР·РІР»РµРєР°РµС‚ session_key РёР· РїР°СЂР°РјРµС‚СЂРѕРІ РєРѕРјР°РЅРґС‹.
        
        MVP: РІРѕР·РІСЂР°С‰Р°РµС‚ params.get("chat_job_id") or meta.request_id
        
        Args:
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РєРѕРјР°РЅРґС‹
            params: РџР°СЂР°РјРµС‚СЂС‹ РєРѕРјР°РЅРґС‹
        
        Returns:
            session_key: СЃС‚СЂРѕРєР°-РєР»СЋС‡ СЃРµСЃСЃРёРё
        """
        return (
            params.get("chat_job_id")
            or params.get("session_key")
            or meta.request_id
            or str(uuid.uuid4())
        )
    
    def _redact_params(self, tool: Optional[str], params: Dict[str, Any]) -> Dict[str, Any]:
        def _hash_payload(self, params: Dict[str, Any]) -> str:
            """Р’С‹С‡РёСЃР»СЏРµС‚ SHA256 С…РµС€ РїР°СЂР°РјРµС‚СЂРѕРІ РґР»СЏ РёРґРµРјРїРѕС‚РµРЅС‚РЅРѕСЃС‚Рё."""
            canonical = json.dumps(params, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        """
        РЎРєСЂС‹РІР°РµС‚ С‡СѓРІСЃС‚РІРёС‚РµР»СЊРЅС‹Рµ РєР»СЋС‡Рё РІ РїР°СЂР°РјРµС‚СЂР°С… РґР»СЏ Р±РµР·РѕРїР°СЃРЅРѕРіРѕ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ.
        
        РЎРєСЂС‹РІР°РµС‚ РєР»СЋС‡Рё РїРѕ РјР°СЃРєРµ: password, token, secret, api_key, key, auth
        
        Args:
            tool: РРјСЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ, РґР»СЏ Р±СѓРґСѓС‰РµРіРѕ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ)
            params: РЎР»РѕРІР°СЂСЊ РїР°СЂР°РјРµС‚СЂРѕРІ
        
        Returns:
            РЎР»РѕРІР°СЂСЊ СЃ СЃРєСЂС‹С‚С‹РјРё С‡СѓРІСЃС‚РІРёС‚РµР»СЊРЅС‹РјРё Р·РЅР°С‡РµРЅРёСЏРјРё
        """
        if not isinstance(params, dict):
            return params
        
        redacted = {}
        sensitive_patterns = ["password", "token", "secret", "api_key", "key", "auth"]
        
        for key, value in params.items():
            key_lower = key.lower()
            # РџСЂРѕРІРµСЂСЏРµРј, СЃРѕРґРµСЂР¶РёС‚ Р»Рё РєР»СЋС‡ С‡СѓРІСЃС‚РІРёС‚РµР»СЊРЅС‹Р№ РїР°С‚С‚РµСЂРЅ
            is_sensitive = any(pattern in key_lower for pattern in sensitive_patterns)
            
            if is_sensitive:
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self._redact_params(tool, value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_params(tool, item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted
    
    async def _publish_chat_event(self, job_id: str, meta: ToolMeta, payload: dict, ticket_id: Optional[str] = None):
        if not job_id or not self.db_manager:
            return
        try:
            ev = dict(payload)
            ev.setdefault("job_id", job_id)
            ev.setdefault("ts", time.time())
            # РљР РРўРР§РќРћ: ticket_id РІ РїСЂРёРѕСЂРёС‚РµС‚Рµ РёР· Р°СЂРіСѓРјРµРЅС‚Р°, Р·Р°С‚РµРј РёР· payload.
            event_ticket_id = ticket_id or ev.get("ticket_id")
            if event_ticket_id:
                ev["ticket_id"] = event_ticket_id
            event_device_id = getattr(meta, "device_id", None) or self.device_id
            if not event_device_id:
                logger.error(f"[chat_event] missing device_id for job_id={job_id}, event={ev.get('event')}")
                return
            await self.db_manager.enqueue_job_event(
                job_id=job_id,
                request_id=getattr(meta, "request_id", None),
                device_id=event_device_id,
                event_payload=ev
            )
            logger.debug(f"[chat_event] enqueued job_id={job_id} ticket_id={event_ticket_id} event={ev.get('event')}")
        except Exception as e:
            logger.exception(f"Failed to enqueue chat_event job_id={job_id}: {e}")
    
    async def _publish_screen_ui_done(self, tool: str, operation_id: str) -> None:
        """РџСѓР±Р»РёРєСѓРµС‚ screen_capture_done РёР»Рё screen_recording_done Рё СЃРЅРёРјР°РµС‚ СЂРµРіРёСЃС‚СЂР°С†РёСЋ Р·Р°РїРёСЃРё (СЌС‚Р°Рї 4)."""
        if tool == "screen.record":
            get_recording_controller().unregister(operation_id)
        event_type = "screen_capture_done" if tool == "screen.collect" else "screen_recording_done"
        if tool not in ("screen.collect", "screen.record"):
            return
        if self.ui_bus:
            event = {
                "event_type": event_type,
                "data": {"operation_id": operation_id},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.ui_bus.publish(event)
    
    async def _handle_run_tool(
        self,
        tool: Optional[str],
        params: Optional[Dict[str, Any]],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """
        РЈРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№ handler РґР»СЏ Р·Р°РїСѓСЃРєР° Р»СЋР±РѕРіРѕ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅРЅРѕРіРѕ tool.
        
        РџРѕРґРґРµСЂР¶РёРІР°РµС‚:
        - Р’СЃС‚СЂРѕРµРЅРЅС‹Рµ tools Рё tools РёР· РїР°РєРµС‚РЅС‹С… РјРѕРґСѓР»РµР№
        - Policy РїСЂРѕРІРµСЂРєСѓ С‡РµСЂРµР· check_policy
        - Artifacts intent (_artifacts, _cleanup_paths)
        - Р’Р°Р»РёРґР°С†РёСЋ РїР°СЂР°РјРµС‚СЂРѕРІ С‡РµСЂРµР· params_model (pydantic)
        - Р•РґРёРЅС‹Р№ С„РѕСЂРјР°С‚ ToolResponse
        
        Args:
            tool: РРјСЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°
            params: РџР°СЂР°РјРµС‚СЂС‹ РґР»СЏ РїРµСЂРµРґР°С‡Рё РІ tool (dict РёР»Рё None)
            actor_role: Р РѕР»СЊ Р°РєС‚РѕСЂР° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїРѕР»РёС‚РёРєРё РґРѕСЃС‚СѓРїР°
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј РІС‹РїРѕР»РЅРµРЅРёСЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°
        """
        start_ts = time.time()
        
        # Р Р°Р·РґРµР»СЏРµРј command_params Рё tool_params РґР»СЏ СѓСЃС‚СЂР°РЅРµРЅРёСЏ Р±Р°РіР° "params РїРµСЂРµР·Р°С‚С‘СЂР»Рё"
        command_params = params  # С‚РµРїРµСЂСЊ СЌС‚Рѕ РѕР±С‘СЂС‚РєР°
        if command_params is None:
            command_params = {}
        
        # РР·РІР»РµРєР°РµРј tool РёР· command_params
        tool = command_params.get("tool")
        
        tool_params = command_params.get("params", {}) or {}
        chat_job_id = command_params.get("chat_job_id")
        # РљР РРўРР§РќРћ: РР·РІР»РµРєР°РµРј ticket_id РёР· command_params (РїРµСЂРµРґР°РµС‚СЃСЏ РёР· envelope РєРѕРјР°РЅРґС‹)
        ticket_id = command_params.get("ticket_id") or tool_params.get("ticket_id")
        
        # 4.1 Р”Рѕ PolicyEngine / РґРѕ РІС‹РїРѕР»РЅРµРЅРёСЏ tool
        # РЎСЂР°Р·Сѓ РїРѕСЃР»Рµ РІС‹С‡РёСЃР»РµРЅРёСЏ tool/tool_params/chat_job_id РїСѓР±Р»РёРєСѓРµРј tool_requested
        if chat_job_id:
            await self._publish_chat_event(chat_job_id, meta, {
                "event": "tool_requested",
                "tool": tool or "<empty>",
                "actor_role": actor_role,
                "params_redacted": self._redact_params(tool, tool_params),
            }, ticket_id=ticket_id)
        
        # 3.1 Р’Р°Р»РёРґР°С†РёСЏ РІС…РѕРґР°
        if not tool:
            logger.error(f"[AGENT] run_tool fail tool=<empty> code=INVALID_REQUEST")
            if chat_job_id:
                await self._publish_chat_event(chat_job_id, meta, {
                    "event": "tool_result",
                    "tool": tool or "<empty>",
                    "ok": False,
                    "error": "INVALID_REQUEST: tool is required",
                }, ticket_id=ticket_id)
            return fail(
                code="INVALID_REQUEST",
                message="tool is required",
                meta=meta,
                retriable=False
            )
        
        # Р”РёР°РіРЅРѕСЃС‚РёРєР°
        logger.info(f"[AGENT] run_tool tool={tool} chat_job_id={chat_job_id} tool_params_keys={list(tool_params.keys())}")
        
        logger.info(f"[AGENT] run_tool start tool={tool} actor_role={actor_role} request_id={meta.request_id}")
        
        try:
            
            # РљРѕРЅС‚СЂР°РєС‚ (Р­С‚Р°Рї 3 Playbook): С‚РѕР»СЊРєРѕ С„РѕСЂРјР°С‚ "module.tool"; РєРѕСЂРѕС‚РєРѕРµ РёРјСЏ РЅРµ РґРѕРїСѓСЃРєР°РµС‚СЃСЏ
            if "." not in tool:
                error_msg = 'РСЃРїРѕР»СЊР·СѓР№С‚Рµ С„РѕСЂРјР°С‚ "module.tool" (РЅР°РїСЂРёРјРµСЂ ping_check.ping_host). РљРѕСЂРѕС‚РєРѕРµ РёРјСЏ РЅРµ РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ.'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"INVALID_TOOL_FORMAT: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="INVALID_TOOL_FORMAT",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            parts = tool.split(".", 1)
            module_name = parts[0]
            tool_name = parts[1]
            module_info = None  # Р±СѓРґРµС‚ Р·Р°РїРѕР»РЅРµРЅ С‡РµСЂРµР· get_tool
            await self._ensure_module_runtime_matches_inventory(module_name, full_tool_name=tool)
            tool_data_from_registry = self.registry.get_tool(tool)
            if not tool_data_from_registry:
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f'TOOL_NOT_FOUND: РРЅСЃС‚СЂСѓРјРµРЅС‚ "{tool}" РЅРµ РЅР°Р№РґРµРЅ. РСЃРїРѕР»СЊР·СѓР№С‚Рµ С„РѕСЂРјР°С‚ module.tool.',
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=f'РРЅСЃС‚СЂСѓРјРµРЅС‚ "{tool}" РЅРµ РЅР°Р№РґРµРЅ. РСЃРїРѕР»СЊР·СѓР№С‚Рµ С„РѕСЂРјР°С‚ module.tool.',
                    meta=meta,
                    retriable=False
                )
            module_info = self.registry.get_module(module_name)
            if not module_info:
                error_msg = f'РњРѕРґСѓР»СЊ "{module_name}" РЅРµ РЅР°Р№РґРµРЅ РІ СЂРµРµСЃС‚СЂРµ'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"MODULE_NOT_FOUND: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="MODULE_NOT_FOUND",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            methods_info = module_info.get('methods', {})
            method_name = tool_data_from_registry.get("method_name")
            if not method_name:
                for method_name_key, method_info_item in methods_info.items():
                    method_tool_name = method_info_item.get('tool_name', method_name_key)
                    if method_tool_name == tool_name or f"{module_name}.{method_tool_name}" == tool:
                        method_name = method_info_item.get('real_method_name', method_name_key)
                        break
            if not method_name:
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result", "tool": tool, "ok": False,
                        "error": f"TOOL_NOT_FOUND: РјРµС‚РѕРґ РґР»СЏ {tool} РЅРµ РЅР°Р№РґРµРЅ РІ СЂРµРµСЃС‚СЂРµ",
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=f'РњРµС‚РѕРґ РґР»СЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° "{tool}" РЅРµ РЅР°Р№РґРµРЅ',
                    meta=meta,
                    retriable=False
                )
            
            # РќР°С…РѕРґРёРј instance РјРѕРґСѓР»СЏ
            module_instance = None
            for module in self.loaded_modules:
                if module.name == module_name:
                    module_instance = module
                    break
            
            if not module_instance:
                error_msg = f'Р­РєР·РµРјРїР»СЏСЂ РјРѕРґСѓР»СЏ "{module_name}" РЅРµ РЅР°Р№РґРµРЅ РІ loaded_modules'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"MODULE_NOT_FOUND: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="MODULE_NOT_FOUND",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            
            # РџРѕР»СѓС‡Р°РµРј РјРµС‚РѕРґ РёР· instance (method_name РІР‚вЂќ РёРјСЏ РјРµС‚РѕРґР° РІ РјРѕРґСѓР»Рµ)
            if not hasattr(module_instance, method_name):
                error_msg = f'РњРµС‚РѕРґ "{method_name}" РЅРµ РЅР°Р№РґРµРЅ РІ РјРѕРґСѓР»Рµ "{module_name}"'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"TOOL_NOT_FOUND: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            
            method = getattr(module_instance, method_name)
            if not callable(method):
                error_msg = f'РђС‚СЂРёР±СѓС‚ "{method_name}" РІ РјРѕРґСѓР»Рµ "{module_name}" РЅРµ СЏРІР»СЏРµС‚СЃСЏ РІС‹Р·С‹РІР°РµРјС‹Рј'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"TOOL_NOT_CALLABLE: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_CALLABLE",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            
            # РџРѕР»СѓС‡Р°РµРј method_info РёР· registry РґР»СЏ policy check
            # (module_info СѓР¶Рµ РїРѕР»СѓС‡РµРЅ РІС‹С€Рµ, РµСЃР»Рё tool РЅРµ СЃРѕРґРµСЂР¶Р°Р» С‚РѕС‡РєСѓ)
            if module_info is None:
                module_info = self.registry.get_module(module_name)
                if not module_info:
                    error_msg = f'РњРѕРґСѓР»СЊ "{module_name}" РЅРµ РЅР°Р№РґРµРЅ РІ СЂРµРµСЃС‚СЂРµ'
                    if chat_job_id:
                        await self._publish_chat_event(chat_job_id, meta, {
                            "event": "tool_result",
                            "tool": tool,
                            "ok": False,
                            "error": f"MODULE_NOT_FOUND: {error_msg}",
                        }, ticket_id=ticket_id)
                    return fail(
                        code="MODULE_NOT_FOUND",
                        message=error_msg,
                        meta=meta,
                        retriable=False
                    )
            
            methods_info = module_info.get('methods', {})
            method_info = methods_info.get(method_name)
            
            if not method_info:
                # Fallback: РµСЃР»Рё РјРµС‚РѕРґ РЅРµ РЅР°Р№РґРµРЅ РІ registry, РЅРѕ РµСЃС‚СЊ РІ instance
                method_info = {
                    'description': f'РњРµС‚РѕРґ {method_name} РјРѕРґСѓР»СЏ {module_name}',
                    'risk_level': 'safe_readonly',
                    'capabilities': None,
                    'params_schema': {}
                }
            
            # 2) Р’Р°Р»РёРґР°С†РёСЏ РїР°СЂР°РјРµС‚СЂРѕРІ С‡РµСЂРµР· params_model (РµСЃР»Рё Р·Р°РґР°РЅ)
            validated_dict = None
            params_model = getattr(method, '__tool_params_model__', None)
            
            if params_model is not None:
                # params_model Р·Р°РґР°РЅ - РІР°Р»РёРґРёСЂСѓРµРј РІС…РѕРґРЅРѕР№ params
                if ValidationError is None:
                    logger.warning(
                        f"params_model Р·Р°РґР°РЅ РґР»СЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° {tool}, РЅРѕ pydantic РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ. "
                        "РџСЂРѕРїСѓСЃРєР°СЋ РІР°Р»РёРґР°С†РёСЋ."
                    )
                else:
                    try:
                        # Р’Р°Р»РёРґРёСЂСѓРµРј tool_params С‡РµСЂРµР· params_model
                        validated = params_model(**tool_params)
                        # РџСЂРµРѕР±СЂР°Р·СѓРµРј РІ dict
                        validated_dict = validated.model_dump()
                        logger.debug(f"РџР°СЂР°РјРµС‚СЂС‹ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° {tool} СѓСЃРїРµС€РЅРѕ РІР°Р»РёРґРёСЂРѕРІР°РЅС‹ С‡РµСЂРµР· {params_model.__name__}")
                    except ValidationError as e:
                        # РћС€РёР±РєР° РІР°Р»РёРґР°С†РёРё - РІРѕР·РІСЂР°С‰Р°РµРј fail
                        error_msg = "Parameters validation failed"
                        if chat_job_id:
                            await self._publish_chat_event(chat_job_id, meta, {
                                "event": "tool_result",
                                "tool": tool,
                                "ok": False,
                                "error": f"INVALID_PARAMS: {error_msg}",
                            }, ticket_id=ticket_id)
                        return fail(
                            code="INVALID_PARAMS",
                            message=error_msg,
                            meta=meta,
                            details={
                                "errors": e.errors(),
                                "tool": tool
                            },
                            retriable=False
                        )
            
            # 3) Policy gate С‡РµСЂРµР· PolicyEngine
            # РџРѕР»СѓС‡Р°РµРј spec С‡РµСЂРµР· registry.get_tool РґР»СЏ РµРґРёРЅРѕР№ С‚РѕС‡РєРё РєРѕРЅС‚СЂРѕР»СЏ РґРѕСЃС‚СѓРїР°
            tool_spec = self.registry.get_tool(tool)
            if not tool_spec:
                error_msg = f'РРЅСЃС‚СЂСѓРјРµРЅС‚ "{tool}" РЅРµ РЅР°Р№РґРµРЅ РІ СЂРµРµСЃС‚СЂРµ'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"TOOL_NOT_FOUND: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            
            # РР·РІР»РµРєР°РµРј metadata РёР· spec
            spec_dict = tool_spec.get('spec', {})
            metadata_dict = spec_dict.get('metadata', {})
            
            # Р•СЃР»Рё metadata РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚, РїСЂРѕСЃС‚Р°РІР»СЏРµРј default Р·РЅР°С‡РµРЅРёСЏ
            if not metadata_dict:
                metadata_dict = {
                    'risk_level': 'safe_read',
                    'scopes': [],
                    'requires_consent': False,
                    'allow_roles': None
                }
            
            # РџСЂРµРѕР±СЂР°Р·СѓРµРј metadata РІ ToolMetadata
            try:
                metadata = ToolMetadata(**metadata_dict)
            except Exception as e:
                logger.warning(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ ToolMetadata РґР»СЏ {tool}: {e}, РёСЃРїРѕР»СЊР·СѓРµРј default")
                metadata = ToolMetadata()
            
            # Р’С‹Р·С‹РІР°РµРј PolicyEngine РґР»СЏ РїСЂРёРЅСЏС‚РёСЏ СЂРµС€РµРЅРёСЏ
            decision = self.policy.decide(
                actor_role=actor_role,
                tool_name=tool,
                metadata=metadata,
                params=tool_params,
                context={
                    "request_id": meta.request_id,
                    "command": meta.command or "run_tool"
                }
            )
            
            # РџСЂРѕРІРµСЂСЏРµРј СЂРµС€РµРЅРёРµ РїРѕР»РёС‚РёРєРё
            # PolicyDecision - TypedDict (СЃР»РѕРІР°СЂСЊ), РґРѕСЃС‚СѓРї С‡РµСЂРµР· СЃР»РѕРІР°СЂСЊ
            decision_allow = decision.get("allow", False)
            decision_requires_consent = decision.get("requires_consent", False)
            decision_reason = decision.get("reason")
            decision_required_role = decision.get("required_role")
            
            if not decision_allow:
                # Р•СЃР»Рё С‚СЂРµР±СѓРµС‚СЃСЏ СЃРѕРіР»Р°СЃРёРµ, СЃРѕР·РґР°РµРј pending tool call Рё РїСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ
                if decision_requires_consent:
                    consent_token = str(uuid.uuid4())
                    session_key = self._session_key_from_command(meta, command_params)
                    
                    # РЎРѕС…СЂР°РЅСЏРµРј pending tool call
                    if self.db_manager:
                        try:
                            await self.db_manager.add_pending_consent(
                                operation_id=consent_token,
                                device_id=self.device_id or self.agent_uuid or "unknown",
                                tool_name=tool,
                                params=tool_params,
                                payload_hash=self._hash_payload(tool_params),
                                request_id=meta.request_id,
                                session_key=session_key,
                                actor_role=actor_role,
                                ticket_id=command_params.get("ticket_id"),
                                job_id=command_params.get("job_id") or chat_job_id,
                                expires_at=int(time.time()) + 1800  # 30 РјРёРЅСѓС‚
                            )
                            logger.info(f"Pending consent saved to DB: operation_id={consent_token}")
                        except Exception as e:
                            logger.error(f"Failed to save pending consent: {e}")
                            # Fallback to in-memory if DB fails (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
                    else:
                        logger.warning("db_manager not available, consent not persisted")
                    
                    # Р¤РѕСЂРјРёСЂСѓРµРј СЃРѕР±С‹С‚РёРµ consent_required
                    event = {
                        "event_type": "consent_required",
                        "data": {
                            "consent_token": consent_token,
                            "session_key": session_key,
                            "request_id": meta.request_id,
                            "device_id": getattr(meta, "device_id", None),
                            "actor_role": actor_role,
                            "tool_name": tool,
                            "reason": decision_reason,
                            "params_preview": self._redact_params(tool, tool_params),
                            "expires_in_sec": 3600
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # РџСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ С‡РµСЂРµР· EventBus
                    if self.ui_bus:
                        await self.ui_bus.publish(event)
                        logger.info(f"СЂСџвЂњвЂ№ РЎРѕР±С‹С‚РёРµ consent_required РѕРїСѓР±Р»РёРєРѕРІР°РЅРѕ: consent_token={consent_token}, tool={tool}")
                    
                    # 7.2 РџСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ tool_waiting_consent РІ chat job
                    if chat_job_id:
                        await self._publish_chat_event(chat_job_id, meta, {
                            "event": "tool_waiting_consent",
                            "tool": tool,
                            "consent_token": consent_token,
                            "risk_level": metadata.risk_level,
                            "reason": decision_reason,
                        }, ticket_id=ticket_id)
                    
                    # Р’РѕР·РІСЂР°С‰Р°РµРј command_result СЃ requires_consent
                    return fail(
                        code="CONSENT_REQUIRED",
                        message=decision_reason or f'РўСЂРµР±СѓРµС‚СЃСЏ СЃРѕРіР»Р°СЃРёРµ РґР»СЏ РІС‹РїРѕР»РЅРµРЅРёСЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° "{tool}"',
                        meta=meta,
                        details={
                            "requires_consent": True,
                            "consent_token": consent_token,
                            "session_key": session_key,
                            "tool": tool,
                            "risk_level": metadata.risk_level,
                            "reason": decision_reason,
                        },
                        retriable=False
                    )
                
                # Р”Р»СЏ РґСЂСѓРіРёС… СЃР»СѓС‡Р°РµРІ (РЅРµ requires_consent) РІРѕР·РІСЂР°С‰Р°РµРј РѕР±С‹С‡РЅСѓСЋ РѕС€РёР±РєСѓ
                # РћРїСЂРµРґРµР»СЏРµРј РєРѕРґ РѕС€РёР±РєРё РЅР° РѕСЃРЅРѕРІРµ reason
                if decision_reason in ("ROLE_NOT_ALLOWED", "NOT_PERMITTED", "REMOTE_CODE_DISABLED"):
                    error_code = "FORBIDDEN"
                else:
                    # Р”Р»СЏ РІСЃРµС… РѕСЃС‚Р°Р»СЊРЅС‹С… СЃР»СѓС‡Р°РµРІ РёСЃРїРѕР»СЊР·СѓРµРј FORBIDDEN
                    error_code = "FORBIDDEN"
                
                # Р¤РѕСЂРјРёСЂСѓРµРј details
                details = {
                    "tool": tool,
                    "risk_level": metadata.risk_level,
                    "requires_consent": False,
                    "required_role": decision_required_role
                }
                
                error_msg = decision_reason or f'Р”РѕСЃС‚СѓРї Рє РёРЅСЃС‚СЂСѓРјРµРЅС‚Сѓ "{tool}" Р·Р°РїСЂРµС‰РµРЅ РґР»СЏ СЂРѕР»Рё "{actor_role}"'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"{error_code}: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code=error_code,
                    message=error_msg,
                    meta=meta,
                    details=details,
                    retriable=False
                )
            
            # 4) Р’Р°Р»РёРґР°С†РёСЏ tool_params (РµСЃР»Рё params_model РЅРµ Р·Р°РґР°РЅ)
            if validated_dict is None:
                # params_model РЅРµ Р·Р°РґР°РЅ - РїСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ tool_params СЌС‚Рѕ dict
                if not isinstance(tool_params, dict):
                    error_msg = f'РџР°СЂР°РјРµС‚СЂС‹ РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ СЃР»РѕРІР°СЂРµРј (dict), РїРѕР»СѓС‡РµРЅ С‚РёРї: {type(tool_params).__name__}'
                    if chat_job_id:
                        await self._publish_chat_event(chat_job_id, meta, {
                            "event": "tool_result",
                            "tool": tool,
                            "ok": False,
                            "error": f"INVALID_PARAMS: {error_msg}",
                        }, ticket_id=ticket_id)
                    return fail(
                        code="INVALID_PARAMS",
                        message=error_msg,
                        meta=meta,
                        retriable=False
                    )
                # РСЃРїРѕР»СЊР·СѓРµРј РѕСЂРёРіРёРЅР°Р»СЊРЅС‹Рµ tool_params
                params_to_use = tool_params
            else:
                # РСЃРїРѕР»СЊР·СѓРµРј РІР°Р»РёРґРёСЂРѕРІР°РЅРЅС‹Рµ params
                params_to_use = validated_dict
            
            # Р¤РёР»СЊС‚СЂСѓРµРј params_to_use: РїРµСЂРµРґР°С‘Рј РІ РјРµС‚РѕРґ С‚РѕР»СЊРєРѕ РѕР±СЉСЏРІР»РµРЅРЅС‹Рµ РїР°СЂР°РјРµС‚СЂС‹ (СЃРµСЂРІРµСЂ РјРѕР¶РµС‚ РїСЂРёСЃС‹Р»Р°С‚СЊ preset_id Рё РґСЂ.)
            try:
                sig = inspect.signature(method)
                has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                if not has_kwargs:
                    allowed = {k for k in sig.parameters if k != 'self'}
                    params_to_use = {k: v for k, v in params_to_use.items() if k in allowed}
            except Exception:
                pass
            
            # 5) РСЃРїРѕР»РЅРµРЅРёРµ
            # 7.3 РџСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ tool_running РїРµСЂРµРґ РІС‹Р·РѕРІРѕРј РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° (РїРѕСЃР»Рµ СЂР°Р·СЂРµС€РµРЅРёСЏ policy)
            if chat_job_id:
                await self._publish_chat_event(chat_job_id, meta, {
                    "event": "tool_running",
                    "tool": tool
                }, ticket_id=ticket_id)
            
            # РљР РРўРР§РќРћ: operation_id Р±РµСЂРµС‚СЃСЏ РёР· meta.request_id (СЌС‚Рѕ Р¶Рµ command_id РІ Protocol V3)
            operation_id = meta.request_id
            
            # Р­С‚Р°Рї 4: СЃРѕР±С‹С‚РёСЏ UI РґР»СЏ СЃРєСЂРёРЅС€РѕС‚Р°/Р·Р°РїРёСЃРё РІР‚вЂќ РјРёРЅРёРјРёР·Р°С†РёСЏ РѕРєРЅР° Рё STOP-РєРЅРѕРїРєР°
            if tool == "screen.collect" and self.ui_bus:
                await self.ui_bus.publish({
                    "event_type": "prepare_screen_capture",
                    "data": {"operation_id": operation_id},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                # Р”Р°С‘Рј GUI РІСЂРµРјСЏ СЃРІРµСЂРЅСѓС‚СЊ РѕРєРЅРѕ РґРѕ Р·Р°С…РІР°С‚Р°, РёРЅР°С‡Рµ РІ РєР°РґСЂ РїРѕРїР°РґС‘С‚ СЃР°РјРѕ РїСЂРёР»РѕР¶РµРЅРёРµ
                await asyncio.sleep(1.2)
            elif tool == "screen.record":
                get_recording_controller().register(operation_id)
                if self.ui_bus:
                    await self.ui_bus.publish({
                        "event_type": "prepare_screen_recording",
                        "data": {"operation_id": operation_id},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    await asyncio.sleep(1.2)
                # Р­С‚Р°Рї 5: РїРµСЂРµРґР°С‘Рј operation_id РІ РјРѕРґСѓР»СЊ РґР»СЏ РґРѕСЃС‚СѓРїР° Рє stop_event (RecordingController)
                params_to_use = dict(params_to_use)
                params_to_use["operation_id"] = operation_id
            
            # РЎРѕР·РґР°РµРј task РґР»СЏ РІС‹РїРѕР»РЅРµРЅРёСЏ tool Рё СЂРµРіРёСЃС‚СЂРёСЂСѓРµРј РІ running_tasks
            async def _execute_tool():
                """Р’РЅСѓС‚СЂРµРЅРЅСЏСЏ С„СѓРЅРєС†РёСЏ РґР»СЏ РІС‹РїРѕР»РЅРµРЅРёСЏ tool РІ task."""
                try:
                    is_async = inspect.iscoroutinefunction(method)
                    
                    if is_async:
                        return await method(**params_to_use)
                    else:
                        # Р’С‹РїРѕР»РЅСЏРµРј sync РјРµС‚РѕРґ РІ threadpool
                        return await asyncio.to_thread(method, **params_to_use)
                finally:
                    # РЈРґР°Р»СЏРµРј РёР· running_tasks РїРѕСЃР»Рµ Р·Р°РІРµСЂС€РµРЅРёСЏ
                    self.running_tasks.pop(operation_id, None)
            
            # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј task РІ running_tasks
            task = asyncio.create_task(_execute_tool())
            self.running_tasks[operation_id] = task
            
            try:
                observations = await task
                
                # РЈР±РµР¶РґР°РµРјСЃСЏ, С‡С‚Рѕ СЂРµР·СѓР»СЊС‚Р°С‚ - dict
                if not isinstance(observations, dict):
                    # Р•СЃР»Рё РјРµС‚РѕРґ РІРµСЂРЅСѓР» РЅРµ dict, РѕР±РѕСЂР°С‡РёРІР°РµРј РІ dict
                    observations = {"result": observations}
                
            except Exception as e:
                error_msg = f'РћС€РёР±РєР° РІС‹РїРѕР»РЅРµРЅРёСЏ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° "{tool}": {str(e)}'
                logger.error(error_msg)
                logger.exception(e)
                
                # 7.5 РџСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ tool_result РїСЂРё РѕС€РёР±РєРµ tool
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": str(e),
                    }, ticket_id=ticket_id)
                
                # Р­С‚Р°Рї 4: СѓРІРµРґРѕРјР»РµРЅРёРµ GUI Рѕ Р·Р°РІРµСЂС€РµРЅРёРё Р·Р°С…РІР°С‚Р°/Р·Р°РїРёСЃРё (РѕРєРЅРѕ РІРѕСЃСЃС‚Р°РЅРѕРІРёС‚СЊ, STOP СЃРєСЂС‹С‚СЊ)
                await self._publish_screen_ui_done(tool, operation_id)
                
                return fail(
                    code="TOOL_EXEC_FAILED",
                    message=error_msg,
                    meta=meta,
                    details={
                        "tool": tool,
                        "exc_type": type(e).__name__,
                        "exc_message": str(e)
                    },
                    retriable=True
                )
            
            # Р­С‚Р°Рї 4: СѓРІРµРґРѕРјР»РµРЅРёРµ GUI Рѕ Р·Р°РІРµСЂС€РµРЅРёРё Р·Р°С…РІР°С‚Р°/Р·Р°РїРёСЃРё (СѓСЃРїРµС€РЅС‹Р№ РїСѓС‚СЊ)
            await self._publish_screen_ui_done(tool, operation_id)
            
            # 3.6 РќРѕСЂРјР°Р»РёР·Р°С†РёСЏ СЂРµР·СѓР»СЊС‚Р°С‚Р°
            # РћР¶РёРґР°РЅРёРµ: observations СЌС‚Рѕ dict СЃ РґР°РЅРЅС‹РјРё Рё РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ _artifacts/_cleanup_paths
            if not isinstance(observations, dict):
                observations = {"result": observations}
            
            # РР·РІР»РµРєР°РµРј artifacts intents
            artifact_intents_data = observations.get("_artifacts", [])
            cleanup_paths_data = observations.get("_cleanup_paths", [])
            
            # РР·РІР»РµРєР°РµРј РЅР°Р±Р»СЋРґРµРЅРёСЏ (Р±РµР· РєР»СЋС‡РµР№ РЅР°С‡РёРЅР°СЋС‰РёС…СЃСЏ СЃ "_")
            observations_clean = {k: v for k, v in observations.items() if not k.startswith("_")}
            
            # 3.7 РћР±СЂР°Р±РѕС‚РєР° artifacts intents
            artifact_intents: list[ArtifactIntent] = []
            cleanup_paths: list[pathlib.Path] = []
            
            # Р¤РѕСЂРјРёСЂСѓРµРј ArtifactIntent РёР· РґР°РЅРЅС‹С…; РґРѕР±Р°РІР»СЏРµРј ticket_id Рё operation_id РІ meta РґР»СЏ СЃРµСЂРІРµСЂР° (РґРѕСЃС‚СѓРї UI Рє Р°СЂС‚РµС„Р°РєС‚Сѓ РїРѕ С‚РёРєРµС‚Сѓ)
            operation_id_for_upload = getattr(meta, "request_id", None)
            if artifact_intents_data and not ticket_id:
                logger.warning(
                    "[AGENT] Upload Р°СЂС‚РµС„Р°РєС‚РѕРІ Р±РµР· ticket_id РІР‚вЂќ РІ Р‘Р” artifact.ticket_id Р±СѓРґРµС‚ null; "
                    "РґРѕСЃС‚СѓРї РёР· UI С‚РѕР»СЊРєРѕ РїРѕ ticket_id РІ query (fallback РїРѕ ticket_events)"
                )
            for item in artifact_intents_data:
                if isinstance(item, dict) and "local_path" in item:
                    try:
                        intent_meta = dict(item.get("meta") or {})
                        if ticket_id:
                            intent_meta["ticket_id"] = ticket_id
                        if operation_id_for_upload:
                            intent_meta["operation_id"] = operation_id_for_upload
                        artifact_intent = ArtifactIntent(
                            local_path=pathlib.Path(item["local_path"]),
                            name=item.get("name"),
                            mime=item.get("mime"),
                            kind=item.get("kind"),
                            ttl_seconds=item.get("ttl_seconds"),
                            meta=intent_meta
                        )
                        artifact_intents.append(artifact_intent)
                        logger.debug(f"Р”РѕР±Р°РІР»РµРЅ Р°СЂС‚РµС„Р°РєС‚ РґР»СЏ Р·Р°РіСЂСѓР·РєРё: {item['local_path']}")
                    except Exception as e:
                        logger.warning(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ ArtifactIntent РґР»СЏ {item.get('local_path')}: {e}")
            
            # Р¤РѕСЂРјРёСЂСѓРµРј cleanup_paths
            for path_str in cleanup_paths_data:
                try:
                    cleanup_path = pathlib.Path(path_str)
                    cleanup_paths.append(cleanup_path)
                    logger.debug(f"Р”РѕР±Р°РІР»РµРЅ РїСѓС‚СЊ РґР»СЏ РѕС‡РёСЃС‚РєРё: {path_str}")
                except Exception as e:
                    logger.warning(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ Path РґР»СЏ cleanup: {path_str}: {e}")
            
            # Р—Р°РіСЂСѓР¶Р°РµРј Р°СЂС‚РµС„Р°РєС‚С‹, РµСЃР»Рё РѕРЅРё РµСЃС‚СЊ
            uploaded_artifacts = []
            upload_errors = []
            
            if artifact_intents:
                try:
                    # РЎРѕР·РґР°РµРј uploader Рё ArtifactManager
                    if self.identity_manager:
                        uploader = get_uploader(identity_manager=self.identity_manager)
                    else:
                        uploader = get_uploader()
                    
                    artifact_manager = ArtifactManager(uploader)
                    
                    logger.info(f"СЂСџвЂњВ¤ РќР°С‡РёРЅР°СЋ Р·Р°РіСЂСѓР·РєСѓ {len(artifact_intents)} Р°СЂС‚РµС„Р°РєС‚РѕРІ...")
                    uploaded_artifacts, upload_errors = await artifact_manager.upload_many(artifact_intents)
                    
                    logger.success(f"РІСљвЂ¦ Р—Р°РіСЂСѓР¶РµРЅРѕ Р°СЂС‚РµС„Р°РєС‚РѕРІ: {len(uploaded_artifacts)}/{len(artifact_intents)}")
                    
                    if upload_errors:
                        logger.warning(f"РІС™В РїС‘РЏ  РћС€РёР±РѕРє Р·Р°РіСЂСѓР·РєРё: {len(upload_errors)}")
                
                except Exception as e:
                    error_msg = f"РћС€РёР±РєР° РїСЂРё Р·Р°РіСЂСѓР·РєРµ Р°СЂС‚РµС„Р°РєС‚РѕРІ: {e}"
                    logger.error(f"вќЊ {error_msg}")
                    upload_error_info = ErrorInfo(
                        code="ARTIFACT_UPLOAD_SYSTEM_ERROR",
                        message=error_msg,
                        details={"exception_type": type(e).__name__, "exception_message": str(e)},
                        retriable=True
                    )
                    upload_errors.append(upload_error_info)
            
            # РћС‡РёСЃС‚РєР° РІСЂРµРјРµРЅРЅС‹С… С„Р°Р№Р»РѕРІ (best-effort)
            if cleanup_paths:
                logger.info(f"СЂСџВ§в„– РћС‡РёСЃС‚РєР° {len(cleanup_paths)} РІСЂРµРјРµРЅРЅС‹С… С„Р°Р№Р»РѕРІ...")
                for cleanup_path in cleanup_paths:
                    try:
                        if cleanup_path.exists():
                            cleanup_path.unlink()
                            logger.debug(f"РІСљвЂ¦ РЈРґР°Р»РµРЅ РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р»: {cleanup_path}")
                    except Exception as e:
                        logger.warning(f"РІС™В РїС‘РЏ  РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ РІСЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р» {cleanup_path}: {e}")
            
            # 3.8 Р¤РѕСЂРјРёСЂРѕРІР°РЅРёРµ ToolResponse
            duration_ms = int((time.time() - start_ts) * 1000)
            meta.duration_ms = duration_ms
            meta.command = "run_tool"
            
            warnings = []
            if upload_errors:
                warnings.extend([f"РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё Р°СЂС‚РµС„Р°РєС‚Р°: {e.message}" for e in upload_errors])
            
            data = ToolData(
                observations=observations_clean,
                artifacts=uploaded_artifacts,
                warnings=warnings if warnings else []
            )
            
            # 7.4 РџСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ tool_result РїРѕСЃР»Рµ СѓСЃРїРµС€РЅРѕРіРѕ СЂРµР·СѓР»СЊС‚Р°С‚Р°
            if chat_job_id:
                await self._publish_chat_event(chat_job_id, meta, {
                    "event": "tool_result",
                    "tool": tool,
                    "ok": True,
                }, ticket_id=ticket_id)
            
            # Р•СЃР»Рё РµСЃС‚СЊ РѕС€РёР±РєРё Р·Р°РіСЂСѓР·РєРё, РЅРѕ РѕСЃРЅРѕРІРЅРѕР№ СЂРµР·СѓР»СЊС‚Р°С‚ СѓСЃРїРµС€РµРЅ - partial
            if upload_errors:
                logger.warning(f"[AGENT] run_tool partial tool={tool} duration_ms={duration_ms} artifacts={len(uploaded_artifacts)} upload_errors={len(upload_errors)}")
                return partial(data=data, meta=meta, warnings=warnings, errors=upload_errors)
            else:
                logger.success(f"[AGENT] run_tool ok tool={tool} duration_ms={duration_ms} artifacts={len(uploaded_artifacts)}")
                return ok(data=data, meta=meta)
            
        except Exception as e:
            duration_ms = int((time.time() - start_ts) * 1000)
            error_msg = f"РћС€РёР±РєР° РІ _handle_run_tool: {str(e)}"
            logger.error(f"[AGENT] run_tool fail tool={tool} code=COMMAND_FAILED exc={type(e).__name__}")
            logger.exception(e)
            
            # 7.5 РџСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ tool_result РїСЂРё РѕС€РёР±РєРµ tool (РІРЅРµС€РЅРёР№ exception handler)
            if chat_job_id:
                await self._publish_chat_event(chat_job_id, meta, {
                    "event": "tool_result",
                    "tool": tool,
                    "ok": False,
                    "error": str(e),
                }, ticket_id=ticket_id)
            
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    async def _handle_consent_decision(
        self,
        consent_token: Optional[str],
        approved: bool,
        session_key: Optional[str],
        meta: ToolMeta
    ) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'consent_decision' - СЂРµС€РµРЅРёРµ Рѕ СЃРѕРіР»Р°СЃРёРё РЅР° РІС‹РїРѕР»РЅРµРЅРёРµ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°.
        
        Args:
            consent_token: РўРѕРєРµРЅ СЃРѕРіР»Р°СЃРёСЏ
            approved: РћРґРѕР±СЂРµРЅРѕ Р»Рё РґРµР№СЃС‚РІРёРµ
            session_key: РљР»СЋС‡ СЃРµСЃСЃРёРё (РµСЃР»Рё РЅРµ СѓРєР°Р·Р°РЅ, РІС‹С‡РёСЃР»СЏРµС‚СЃСЏ РёР· meta)
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј РѕР±СЂР°Р±РѕС‚РєРё СЂРµС€РµРЅРёСЏ
        """
        try:
            # Р’Р°Р»РёРґР°С†РёСЏ РїР°СЂР°РјРµС‚СЂРѕРІ
            if not consent_token:
                return fail(
                    code="INVALID_REQUEST",
                    message="consent_token is required",
                    meta=meta,
                    retriable=False
                )
            
            # Р•СЃР»Рё session_key РЅРµ СѓРєР°Р·Р°РЅ, РёСЃРїРѕР»СЊР·СѓРµРј request_id РєР°Рє fallback
            if not session_key:
                session_key = meta.request_id or str(uuid.uuid4())
            
            # Р—Р°РїРёСЃС‹РІР°РµРј СЂРµС€РµРЅРёРµ РІ consent_cache
            if session_key not in self.consent_cache:
                self.consent_cache[session_key] = {}
            self.consent_cache[session_key][consent_token] = approved
            logger.info(f"СЂСџвЂњвЂ№ Р РµС€РµРЅРёРµ Рѕ СЃРѕРіР»Р°СЃРёРё Р·Р°РїРёСЃР°РЅРѕ: consent_token={consent_token}, approved={approved}, session_key={session_key}")
            
            # РќР°С…РѕРґРёРј pending tool call
            pending = None
            if self.db_manager:
                try:
                    pending = await self.db_manager.get_pending_consent(consent_token)
                except Exception as e:
                    logger.error(f"Failed to get pending consent: {e}")

            if not pending:
                return fail(
                    code="UNKNOWN_CONSENT_TOKEN",
                    message=f"Unknown consent_token: {consent_token}",
                    meta=meta,
                    retriable=False
                )
            
            # РР·РІР»РµРєР°РµРј РґР°РЅРЅС‹Рµ РёР· pending
            tool_name = pending["tool_name"]
            tool_params = pending["params"]  # СЌС‚Рѕ tool_params, РЅРµ command_params
            actor_role = pending["actor_role"]
            pending_request_id = pending["request_id"]
            pending_device_id = pending.get("device_id")
            pending_session_key = pending.get("session_key")
            pending_ticket_id = pending.get("ticket_id")
            pending_job_id = pending.get("job_id")
            
            # РЈРґР°Р»СЏРµРј pending РІРЅРµ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё РѕС‚ outcome
            if self.db_manager:
                try:
                    await self.db_manager.remove_pending_consent(consent_token)
                    logger.info(f"Pending consent removed from DB: operation_id={consent_token}")
                except Exception as e:
                    logger.error(f"Failed to remove pending consent: {e}")
            
            if approved:
                # Р’С‹РїРѕР»РЅСЏРµРј РёРЅСЃС‚СЂСѓРјРµРЅС‚
                logger.info(f"РІСљвЂ¦ РЎРѕРіР»Р°СЃРёРµ РїРѕР»СѓС‡РµРЅРѕ, РІС‹РїРѕР»РЅСЏСЋ tool: {tool_name}, consent_token={consent_token}")
                
                # Р”РѕР±Р°РІР»СЏРµРј consent_token РІ tool_params, С‡С‚РѕР±С‹ PolicyEngine СЂР°Р·СЂРµС€РёР» РІС‹РїРѕР»РЅРµРЅРёРµ
                tool_params_with_consent = tool_params.copy()
                tool_params_with_consent["consent_token"] = consent_token
                
                # Р’РѕСЃСЃС‚Р°РЅР°РІР»РёРІР°РµРј command_params СЃС‚СЂСѓРєС‚СѓСЂСѓ СЃ РїРѕР»РЅС‹Рј РєРѕРЅС‚РµРєСЃС‚РѕРј.
                command_params = {
                    "tool": tool_name,
                    "params": tool_params_with_consent,
                    "chat_job_id": pending_job_id,
                    "job_id": pending_job_id,
                    "ticket_id": pending_ticket_id,
                }
                if pending_session_key:
                    command_params["session_key"] = pending_session_key
                
                # Р’С‹Р·С‹РІР°РµРј _handle_run_tool СЃ РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРЅРѕР№ command_params СЃС‚СЂСѓРєС‚СѓСЂРѕР№
                result = await self._handle_run_tool(
                    tool=tool_name,
                    params=command_params,
                    actor_role=actor_role,
                    meta=meta
                )
                
                # Р¤РѕСЂРјРёСЂСѓРµРј СЃРѕР±С‹С‚РёРµ tool_executed
                result_preview = None
                if result.status == "success" and result.data:
                    observations = result.data.observations if result.data.observations else {}
                    # Р‘РµСЂРµРј РїРµСЂРІС‹Рµ 200 СЃРёРјРІРѕР»РѕРІ СЂРµР·СѓР»СЊС‚Р°С‚Р° РєР°Рє preview
                    result_str = str(observations)[:200]
                    result_preview = result_str + ("..." if len(str(observations)) > 200 else "")
                elif result.error:
                    result_preview = f"Error: {result.error.code} - {result.error.message}"
                
                event = {
                    "event_type": "tool_executed",
                    "data": {
                        "consent_token": consent_token,
                        "session_key": session_key,
                        "tool_name": tool_name,
                        "ok": result.status == "success",
                        "result_preview": result_preview,
                        "request_id": pending_request_id,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # РџСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ
                if self.ui_bus:
                    await self.ui_bus.publish(event)
                    logger.info(f"СЂСџвЂњвЂ№ РЎРѕР±С‹С‚РёРµ tool_executed РѕРїСѓР±Р»РёРєРѕРІР°РЅРѕ: consent_token={consent_token}, tool={tool_name}")
                
                return result
            else:
                # РћС‚РєР»РѕРЅРµРЅРѕ - РїСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ tool_denied
                logger.info(f"РІСњРЉ РЎРѕРіР»Р°СЃРёРµ РѕС‚РєР»РѕРЅРµРЅРѕ: consent_token={consent_token}, tool={tool_name}")
                
                event = {
                    "event_type": "tool_denied",
                    "data": {
                        "consent_token": consent_token,
                        "session_key": session_key,
                        "tool_name": tool_name,
                        "request_id": pending_request_id,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # РџСѓР±Р»РёРєСѓРµРј СЃРѕР±С‹С‚РёРµ
                if self.ui_bus:
                    await self.ui_bus.publish(event)
                    logger.info(f"СЂСџвЂњвЂ№ РЎРѕР±С‹С‚РёРµ tool_denied РѕРїСѓР±Р»РёРєРѕРІР°РЅРѕ: consent_token={consent_token}, tool={tool_name}")
                
                return fail(
                    code="CONSENT_DENIED",
                    message=f"РЎРѕРіР»Р°СЃРёРµ РЅР° РІС‹РїРѕР»РЅРµРЅРёРµ РёРЅСЃС‚СЂСѓРјРµРЅС‚Р° '{tool_name}' РѕС‚РєР»РѕРЅРµРЅРѕ",
                    meta=meta,
                    details={
                        "consent_token": consent_token,
                        "session_key": session_key,
                        "tool": tool_name,
                    },
                    retriable=False
                )
        
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё consent_decision: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    async def _handle_start_job(
        self,
        job_type: Optional[str],
        params: Dict[str, Any],
        actor_role: str,
        device_id: Optional[str],
        meta: ToolMeta
    ) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'start_job' - Р·Р°РїСѓСЃРє С„РѕРЅРѕРІРѕР№ Р·Р°РґР°С‡Рё.
        
        Args:
            job_type: РўРёРї Р·Р°РґР°С‡Рё (РЅР°РїСЂРёРјРµСЂ, "chat_echo")
            params: РџР°СЂР°РјРµС‚СЂС‹ Р·Р°РґР°С‡Рё
            actor_role: Р РѕР»СЊ Р°РєС‚РѕСЂР° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂР°РІ РґРѕСЃС‚СѓРїР°
            device_id: РРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ СѓСЃС‚СЂРѕР№СЃС‚РІР°
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј Р·Р°РїСѓСЃРєР° Р·Р°РґР°С‡Рё
        """
        try:
            # РџСЂРѕРІРµСЂРєР° РїСЂР°РІ РґРѕСЃС‚СѓРїР°
            # admin РјРѕР¶РµС‚ Р·Р°РїСѓСЃРєР°С‚СЊ Р»СЋР±С‹Рµ job
            # support РјРѕР¶РµС‚ Р·Р°РїСѓСЃРєР°С‚СЊ support_chat Рё support_ticket
            # agent РјРѕР¶РµС‚ Р·Р°РїСѓСЃРєР°С‚СЊ support_chat Рё support_ticket (РґР»СЏ РёРЅРёС†РёР°С†РёРё С‡Р°С‚Р° СЃ РїРѕРґРґРµСЂР¶РєРѕР№)
            if actor_role == "admin":
                # admin РёРјРµРµС‚ РґРѕСЃС‚СѓРї РєРѕ РІСЃРµРј job
                pass
            elif actor_role == "support" and job_type in ["support_chat", "support_ticket"]:
                # support РјРѕР¶РµС‚ Р·Р°РїСѓСЃРєР°С‚СЊ С‚РѕР»СЊРєРѕ support_chat Рё support_ticket
                pass
            elif actor_role == "agent" and job_type in ["support_chat", "support_ticket"]:
                # agent РјРѕР¶РµС‚ Р·Р°РїСѓСЃРєР°С‚СЊ support_chat Рё support_ticket РґР»СЏ РёРЅРёС†РёР°С†РёРё С‡Р°С‚Р°
                pass
            else:
                return fail(
                    code="FORBIDDEN",
                    message="Admin only" if actor_role not in ["support", "agent"] else f"{actor_role} role can only start support_chat and support_ticket jobs",
                    meta=meta,
                    retriable=False
                )
            
            # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ job_manager
            if not self.job_manager:
                return fail(
                    code="JOB_MANAGER_NOT_ATTACHED",
                    message="JobManager not attached to orchestrator",
                    meta=meta,
                    retriable=False
                )
            
            # РџСЂРѕРІРµСЂРєР° РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ
            if not job_type:
                return fail(
                    code="INVALID_REQUEST",
                    message='РќРµ СѓРєР°Р·Р°РЅ С‚РёРї Р·Р°РґР°С‡Рё (РїРѕР»Рµ "job_type")',
                    meta=meta,
                    retriable=False
                )
            
            # РСЃРїРѕР»СЊР·СѓРµРј device_id РёР· РїР°СЂР°РјРµС‚СЂР° РёР»Рё fallback РЅР° agent_uuid
            final_device_id = device_id or self.agent_uuid or "unknown"
            
            logger.info(f"СЂСџС™Р‚ Р—Р°РїСѓСЃРє Р·Р°РґР°С‡Рё: job_type={job_type}, actor_role={actor_role}, device_id={final_device_id}")
            
            # Р—Р°РїСѓСЃРєР°РµРј Р·Р°РґР°С‡Сѓ С‡РµСЂРµР· JobManager
            job_result = await self.job_manager.start_job(
                job_type=job_type,
                device_id=final_device_id,
                actor_role=actor_role,
                params=params
            )
            
            # Р¤РѕСЂРјРёСЂСѓРµРј РѕС‚РІРµС‚ РІ С‚СЂРµР±СѓРµРјРѕРј С„РѕСЂРјР°С‚Рµ: payload.data.result.job_id
            result_data = {
                "ok": True,
                "job_id": job_result.get("job_id"),
                "job_type": job_result.get("job_type")
            }
            
            # РСЃРїРѕР»СЊР·СѓРµРј РїРѕР»Рµ result РІРјРµСЃС‚Рѕ observations РґР»СЏ РїСЂСЏРјРѕРіРѕ РґРѕСЃС‚СѓРїР° Рє job_id
            data = ToolData(result=result_data)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° Р·Р°РїСѓСЃРєР° Р·Р°РґР°С‡Рё: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            return fail(
                code="START_JOB_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__},
                retriable=True
            )
    
    async def _handle_stop_job(
        self,
        job_id: Optional[str],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'stop_job' - РѕСЃС‚Р°РЅРѕРІРєР° С„РѕРЅРѕРІРѕР№ Р·Р°РґР°С‡Рё.
        
        Args:
            job_id: РРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ Р·Р°РґР°С‡Рё
            actor_role: Р РѕР»СЊ Р°РєС‚РѕСЂР° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂР°РІ РґРѕСЃС‚СѓРїР°
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј РѕСЃС‚Р°РЅРѕРІРєРё Р·Р°РґР°С‡Рё
        """
        try:
            # РџСЂРѕРІРµСЂРєР° РїСЂР°РІ РґРѕСЃС‚СѓРїР°: С‚РѕР»СЊРєРѕ admin
            if actor_role != "admin":
                return fail(
                    code="FORBIDDEN",
                    message="Admin only",
                    meta=meta,
                    retriable=False
                )
            
            # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ job_manager
            if not self.job_manager:
                return fail(
                    code="JOB_MANAGER_NOT_ATTACHED",
                    message="JobManager not attached to orchestrator",
                    meta=meta,
                    retriable=False
                )
            
            # РџСЂРѕРІРµСЂРєР° РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ
            if not job_id:
                return fail(
                    code="INVALID_REQUEST",
                    message='РќРµ СѓРєР°Р·Р°РЅ РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ Р·Р°РґР°С‡Рё (РїРѕР»Рµ "job_id")',
                    meta=meta,
                    retriable=False
                )
            
            logger.info(f"СЂСџвЂєвЂ РћСЃС‚Р°РЅРѕРІРєР° Р·Р°РґР°С‡Рё: job_id={job_id}, actor_role={actor_role}")
            
            # РћСЃС‚Р°РЅР°РІР»РёРІР°РµРј Р·Р°РґР°С‡Сѓ С‡РµСЂРµР· JobManager
            result = await self.job_manager.stop_job(job_id)
            
            if "error" in result:
                return fail(
                    code="JOB_NOT_FOUND",
                    message=f"Р—Р°РґР°С‡Р° РЅРµ РЅР°Р№РґРµРЅР°: {job_id}",
                    meta=meta,
                    retriable=False
                )
            
            observations = {
                "job_id": result.get("job_id"),
                "status": result.get("status")
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° РѕСЃС‚Р°РЅРѕРІРєРё Р·Р°РґР°С‡Рё: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            return fail(
                code="STOP_JOB_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__},
                retriable=True
            )
    
    async def _handle_get_job_status(
        self,
        job_id: Optional[str],
        meta: ToolMeta
    ) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'get_job_status' - РїРѕР»СѓС‡РµРЅРёРµ СЃС‚Р°С‚СѓСЃР° Р·Р°РґР°С‡Рё.
        
        Args:
            job_id: РРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ Р·Р°РґР°С‡Рё
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ РёРЅС„РѕСЂРјР°С†РёРµР№ Рѕ Р·Р°РґР°С‡Рµ
        """
        try:
            # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ job_manager
            if not self.job_manager:
                return fail(
                    code="JOB_MANAGER_NOT_ATTACHED",
                    message="JobManager not attached to orchestrator",
                    meta=meta,
                    retriable=False
                )
            
            # РџСЂРѕРІРµСЂРєР° РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ
            if not job_id:
                return fail(
                    code="INVALID_REQUEST",
                    message='РќРµ СѓРєР°Р·Р°РЅ РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ Р·Р°РґР°С‡Рё (РїРѕР»Рµ "job_id")',
                    meta=meta,
                    retriable=False
                )
            
            logger.info(f"СЂСџвЂњР‰ РџРѕР»СѓС‡РµРЅРёРµ СЃС‚Р°С‚СѓСЃР° Р·Р°РґР°С‡Рё: job_id={job_id}")
            
            # РџРѕР»СѓС‡Р°РµРј СЃС‚Р°С‚СѓСЃ Р·Р°РґР°С‡Рё С‡РµСЂРµР· JobManager
            job_data = await self.job_manager.get_job_status(job_id)
            
            if not job_data:
                return fail(
                    code="JOB_NOT_FOUND",
                    message=f"Р—Р°РґР°С‡Р° РЅРµ РЅР°Р№РґРµРЅР°: {job_id}",
                    meta=meta,
                    retriable=False
                )
            
            observations = {
                "job": job_data
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃС‚Р°С‚СѓСЃР° Р·Р°РґР°С‡Рё: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            return fail(
                code="GET_JOB_STATUS_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__},
                retriable=True
            )
    
    async def _handle_list_jobs(
        self,
        limit: int,
        meta: ToolMeta
    ) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'list_jobs' - РїРѕР»СѓС‡РµРЅРёРµ СЃРїРёСЃРєР° Р·Р°РґР°С‡.
        
        Args:
            limit: РњР°РєСЃРёРјР°Р»СЊРЅРѕРµ РєРѕР»РёС‡РµСЃС‚РІРѕ Р·Р°РїРёСЃРµР№
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃРѕ СЃРїРёСЃРєРѕРј Р·Р°РґР°С‡
        """
        try:
            # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ job_manager
            if not self.job_manager:
                return fail(
                    code="JOB_MANAGER_NOT_ATTACHED",
                    message="JobManager not attached to orchestrator",
                    meta=meta,
                    retriable=False
                )
            
            logger.info(f"СЂСџвЂњвЂ№ РџРѕР»СѓС‡РµРЅРёРµ СЃРїРёСЃРєР° Р·Р°РґР°С‡: limit={limit}")
            
            # РџРѕР»СѓС‡Р°РµРј СЃРїРёСЃРѕРє Р·Р°РґР°С‡ С‡РµСЂРµР· JobManager
            result = await self.job_manager.list_jobs(limit=limit)
            
            observations = {
                "jobs": result.get("jobs", []),
                "count": len(result.get("jobs", []))
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° Р·Р°РґР°С‡: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            return fail(
                code="LIST_JOBS_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__},
                retriable=True
            )
    
    async def _handle_job_send_event(
        self,
        job_id: Optional[str],
        event: Optional[dict],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """
        РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ 'job_send_event' - РґРѕСЃС‚Р°РІРєР° СЃРѕР±С‹С‚РёСЏ РІ Р·Р°РґР°С‡Сѓ.
        
        Args:
            job_id: РРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ Р·Р°РґР°С‡Рё (chat_job_id, РЅР°РїСЂРёРјРµСЂ support_chat job_id)
            event: РЎР»РѕРІР°СЂСЊ СЃ СЃРѕР±С‹С‚РёРµРј
            actor_role: Р РѕР»СЊ Р°РєС‚РѕСЂР° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїСЂР°РІ РґРѕСЃС‚СѓРїР°
            meta: РњРµС‚Р°РґР°РЅРЅС‹Рµ РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹
        
        Returns:
            ToolResponse СЃ СЂРµР·СѓР»СЊС‚Р°С‚РѕРј РґРѕСЃС‚Р°РІРєРё СЃРѕР±С‹С‚РёСЏ
        
        Note:
            Р­С‚РѕС‚ РјРµС‚РѕРґ РќР• Р·Р°РІРµСЂС€Р°РµС‚ job_id. Р—Р°РІРµСЂС€Р°РµС‚СЃСЏ С‚РѕР»СЊРєРѕ command_job_id
            (job РІС‹РїРѕР»РЅРµРЅРёСЏ РєРѕРјР°РЅРґС‹) РІ РѕР±С‰РµРј wrapper handle_command.
        """
        try:
            # РџСЂРѕРІРµСЂРєР° РїСЂР°РІ РґРѕСЃС‚СѓРїР°: С‚РѕР»СЊРєРѕ admin РёР»Рё support
            if actor_role != "admin" and actor_role != "support":
                return fail(
                    code="FORBIDDEN",
                    message="Admin or support only",
                    meta=meta,
                    retriable=False
                )
            
            # РџСЂРѕРІРµСЂРєР° РЅР°Р»РёС‡РёСЏ job_manager
            if not self.job_manager:
                return fail(
                    code="JOB_MANAGER_NOT_READY",
                    message="JobManager not ready",
                    meta=meta,
                    retriable=False
                )
            
            # РџСЂРѕРІРµСЂРєР° РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїР°СЂР°РјРµС‚СЂРѕРІ
            if not job_id or event is None:
                return fail(
                    code="INVALID_REQUEST",
                    message='РќРµ СѓРєР°Р·Р°РЅ job_id РёР»Рё event',
                    meta=meta,
                    retriable=False
                )
            
            logger.info(f"СЂСџвЂњРЃ Р”РѕСЃС‚Р°РІРєР° СЃРѕР±С‹С‚РёСЏ РІ Р·Р°РґР°С‡Сѓ: job_id={job_id}, actor_role={actor_role}")
            
            # Р”РѕСЃС‚Р°РІР»СЏРµРј СЃРѕР±С‹С‚РёРµ С‡РµСЂРµР· JobManager
            res = await self.job_manager.deliver_event(job_id, event)
            
            if not res.get("ok", False):
                error_code = res.get("error", "JOB_NOT_FOUND")
                return fail(
                    code=error_code,
                    message=f"Р—Р°РґР°С‡Р° РЅРµ РЅР°Р№РґРµРЅР°: {job_id}",
                    meta=meta,
                    retriable=False,
                    details={
                        "chat_job_id": job_id,
                        "message_id": event.get("message_id") if event else None
                    }
                )
            
            # РџСЂРѕР±СЂР°СЃС‹РІР°РµРј observations 1-РІ-1 РёР· deliver_event
            data = ToolData(observations=res)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"РћС€РёР±РєР° РґРѕСЃС‚Р°РІРєРё СЃРѕР±С‹С‚РёСЏ: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            return fail(
                code="JOB_SEND_EVENT_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__},
                retriable=True
            )
    
    def _format_uptime(self, seconds: float) -> str:
        """
        Р¤РѕСЂРјР°С‚РёСЂСѓРµС‚ uptime РІ С‡РµР»РѕРІРµРєРѕС‡РёС‚Р°РµРјС‹Р№ С„РѕСЂРјР°С‚.
        
        Args:
            seconds: РљРѕР»РёС‡РµСЃС‚РІРѕ СЃРµРєСѓРЅРґ uptime
        
        Returns:
            РЎС‚СЂРѕРєР° РІРёРґР° "1Рґ 2С‡ 30Рј 15СЃ"
        """
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}Рґ")
        if hours > 0:
            parts.append(f"{hours}С‡")
        if minutes > 0:
            parts.append(f"{minutes}Рј")
        if secs > 0 or not parts:
            parts.append(f"{secs}СЃ")
        
        return " ".join(parts)
    
    async def shutdown(self) -> None:
        """
        РљРѕСЂСЂРµРєС‚РЅРѕРµ Р·Р°РІРµСЂС€РµРЅРёРµ СЂР°Р±РѕС‚С‹ РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂР°.
        """
        logger.info("СЂСџвЂєвЂ Р—Р°РІРµСЂС€РµРЅРёРµ СЂР°Р±РѕС‚С‹ AgentOrchestrator")
        
        # Р—РґРµСЃСЊ РјРѕР¶РЅРѕ РґРѕР±Р°РІРёС‚СЊ Р»РѕРіРёРєСѓ РѕС‡РёСЃС‚РєРё СЂРµСЃСѓСЂСЃРѕРІ
        # - Р—Р°РєСЂС‹С‚РёРµ СЃРѕРµРґРёРЅРµРЅРёР№
        # - РЎРѕС…СЂР°РЅРµРЅРёРµ СЃРѕСЃС‚РѕСЏРЅРёСЏ
        # - Р—Р°РІРµСЂС€РµРЅРёРµ С„РѕРЅРѕРІС‹С… Р·Р°РґР°С‡
        
        logger.success("AgentOrchestrator РѕСЃС‚Р°РЅРѕРІР»РµРЅ")


# ==================== РўР•РЎРўРР РћР’РђРќРР• ====================

async def test_tool_response_format():
    """
    Unit-С‚РµСЃС‚С‹ РґР»СЏ РїСЂРѕРІРµСЂРєРё С„РѕСЂРјР°С‚Р° ToolResponse.
    """
    from core.database import db_manager
    
    logger.info("=" * 70)
    logger.info("СЂСџВ§Р„ Unit-С‚РµСЃС‚С‹ С„РѕСЂРјР°С‚Р° ToolResponse")
    logger.info("=" * 70)
    
    try:
        # РЎРѕР·РґР°РµРј РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂ СЃ С‚РµСЃС‚РѕРІС‹РјРё РјРѕРґСѓР»СЏРјРё
        orchestrator = AgentOrchestrator(
            db_manager=db_manager,
            enabled_modules=["system"],
            agent_uuid="test-agent-123"
        )
        
        # РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ
        await orchestrator.initialize()
        
        # РўРµСЃС‚ 1: ping РІРѕР·РІСЂР°С‰Р°РµС‚ ToolResponse
        logger.info("\n1РїС‘РЏРІС“Р€ РўРµСЃС‚ ping - С„РѕСЂРјР°С‚ ToolResponse...")
        result = await orchestrator.handle_command({'cmd': 'ping', 'request_id': 'test-request-1'})
        assert result['status'] in ['success', 'error', 'partial'], f"РќРµРІРµСЂРЅС‹Р№ СЃС‚Р°С‚СѓСЃ: {result.get('status')}"
        assert 'meta' in result, "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РїРѕР»Рµ meta"
        assert 'timestamp_iso' in result['meta'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ timestamp_iso РІ meta"
        assert 'command' in result['meta'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ command РІ meta"
        assert result['meta']['command'] == 'ping', f"РќРµРІРµСЂРЅР°СЏ РєРѕРјР°РЅРґР°: {result['meta']['command']}"
        assert result['meta']['request_id'] == 'test-request-1', "РќРµРІРµСЂРЅС‹Р№ request_id"
        assert result['meta']['agent_id'] == 'test-agent-123', "РќРµРІРµСЂРЅС‹Р№ agent_id"
        assert 'duration_ms' in result['meta'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ duration_ms РІ meta"
        if result['status'] == 'success':
            assert 'data' in result, "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РїРѕР»Рµ data"
            assert 'observations' in result['data'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ observations РІ data"
            assert 'message' in result['data']['observations'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ message РІ observations"
            assert 'agent' in result['data']['observations'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ agent РІ observations"
        logger.success("РІСљвЂ¦ ping РІРѕР·РІСЂР°С‰Р°РµС‚ РєРѕСЂСЂРµРєС‚РЅС‹Р№ ToolResponse")
        
        # РўРµСЃС‚ 2: list_modules РІРѕР·РІСЂР°С‰Р°РµС‚ ToolResponse
        logger.info("\n2РїС‘РЏРІС“Р€ РўРµСЃС‚ list_modules - С„РѕСЂРјР°С‚ ToolResponse...")
        result = await orchestrator.handle_command({'cmd': 'list_modules'})
        assert result['status'] == 'success', f"РќРµРІРµСЂРЅС‹Р№ СЃС‚Р°С‚СѓСЃ: {result.get('status')}"
        assert 'data' in result, "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РїРѕР»Рµ data"
        assert 'observations' in result['data'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ observations РІ data"
        assert 'modules' in result['data']['observations'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ modules РІ observations"
        assert isinstance(result['data']['observations']['modules'], list), "modules РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЃРїРёСЃРєРѕРј"
        logger.success("РІСљвЂ¦ list_modules РІРѕР·РІСЂР°С‰Р°РµС‚ РєРѕСЂСЂРµРєС‚РЅС‹Р№ ToolResponse")
        
        # РўРµСЃС‚ 3: collect РІРѕР·РІСЂР°С‰Р°РµС‚ ToolResponse СЃ observations.results
        logger.info("\n3РїС‘РЏРІС“Р€ РўРµСЃС‚ collect - С„РѕСЂРјР°С‚ ToolResponse...")
        result = await orchestrator.handle_command({'cmd': 'collect', 'modules': ['system']})
        assert result['status'] in ['success', 'partial'], f"РќРµРІРµСЂРЅС‹Р№ СЃС‚Р°С‚СѓСЃ: {result.get('status')}"
        assert 'data' in result, "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РїРѕР»Рµ data"
        assert 'observations' in result['data'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ observations РІ data"
        assert 'results' in result['data']['observations'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ results РІ observations"
        assert isinstance(result['data']['observations']['results'], dict), "results РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЃР»РѕРІР°СЂРµРј"
        logger.success("РІСљвЂ¦ collect РІРѕР·РІСЂР°С‰Р°РµС‚ РєРѕСЂСЂРµРєС‚РЅС‹Р№ ToolResponse")
        
        # РўРµСЃС‚ 4: РЅРµРёР·РІРµСЃС‚РЅР°СЏ РєРѕРјР°РЅРґР° РІРѕР·РІСЂР°С‰Р°РµС‚ fail СЃ РєРѕРґРѕРј UNKNOWN_COMMAND
        logger.info("\n4РїС‘РЏРІС“Р€ РўРµСЃС‚ РЅРµРёР·РІРµСЃС‚РЅРѕР№ РєРѕРјР°РЅРґС‹ - РєРѕРґ РѕС€РёР±РєРё UNKNOWN_COMMAND...")
        result = await orchestrator.handle_command({'cmd': 'unknown_command'})
        assert result['status'] == 'error', f"РќРµРІРµСЂРЅС‹Р№ СЃС‚Р°С‚СѓСЃ: {result.get('status')}"
        assert 'error' in result, "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РїРѕР»Рµ error"
        assert result['error']['code'] == 'UNKNOWN_COMMAND', f"РќРµРІРµСЂРЅС‹Р№ РєРѕРґ РѕС€РёР±РєРё: {result['error']['code']}"
        logger.success("РІСљвЂ¦ РЅРµРёР·РІРµСЃС‚РЅР°СЏ РєРѕРјР°РЅРґР° РІРѕР·РІСЂР°С‰Р°РµС‚ fail СЃ РєРѕРґРѕРј UNKNOWN_COMMAND")
        
        # РўРµСЃС‚ 5: РїСѓСЃС‚Р°СЏ РєРѕРјР°РЅРґР° РІРѕР·РІСЂР°С‰Р°РµС‚ fail СЃ РєРѕРґРѕРј UNKNOWN_COMMAND
        logger.info("\n5РїС‘РЏРІС“Р€ РўРµСЃС‚ РїСѓСЃС‚РѕР№ РєРѕРјР°РЅРґС‹ - РєРѕРґ РѕС€РёР±РєРё UNKNOWN_COMMAND...")
        result = await orchestrator.handle_command({})
        assert result['status'] == 'error', f"РќРµРІРµСЂРЅС‹Р№ СЃС‚Р°С‚СѓСЃ: {result.get('status')}"
        assert result['error']['code'] == 'UNKNOWN_COMMAND', f"РќРµРІРµСЂРЅС‹Р№ РєРѕРґ РѕС€РёР±РєРё: {result['error']['code']}"
        logger.success("РІСљвЂ¦ РїСѓСЃС‚Р°СЏ РєРѕРјР°РЅРґР° РІРѕР·РІСЂР°С‰Р°РµС‚ fail СЃ РєРѕРґРѕРј UNKNOWN_COMMAND")
        
        # РўРµСЃС‚ 6: collect СЃ РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРј РјРѕРґСѓР»РµРј РІРѕР·РІСЂР°С‰Р°РµС‚ partial СЃ warnings
        logger.info("\n6РїС‘РЏРІС“Р€ РўРµСЃС‚ collect СЃ РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРј РјРѕРґСѓР»РµРј - partial СЃ warnings...")
        result = await orchestrator.handle_command({'cmd': 'collect', 'modules': ['nonexistent_module']})
        assert result['status'] in ['partial', 'error'], f"РќРµРІРµСЂРЅС‹Р№ СЃС‚Р°С‚СѓСЃ: {result.get('status')}"
        if result['status'] == 'partial':
            assert 'data' in result, "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РїРѕР»Рµ data"
            assert 'warnings' in result['data'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ warnings РІ data"
            assert len(result['data']['warnings']) > 0, "Р”РѕР»Р¶РЅС‹ Р±С‹С‚СЊ warnings"
        logger.success("РІСљвЂ¦ collect СЃ РЅРµСЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРј РјРѕРґСѓР»РµРј РІРѕР·РІСЂР°С‰Р°РµС‚ partial СЃ warnings")
        
        # РўРµСЃС‚ 7: exec_script РІРѕР·РІСЂР°С‰Р°РµС‚ СЂРµР·СѓР»СЊС‚Р°С‚ С‡РµСЂРµР· observations
        logger.info("\n7РїС‘РЏРІС“Р€ РўРµСЃС‚ exec_script - СЂРµР·СѓР»СЊС‚Р°С‚ С‡РµСЂРµР· observations...")
        test_code = """
async def run():
    return {"test": "result"}
"""
        result = await orchestrator.handle_command({'cmd': 'exec_script', 'code': test_code})
        assert result['status'] == 'success', f"РќРµРІРµСЂРЅС‹Р№ СЃС‚Р°С‚СѓСЃ: {result.get('status')}"
        assert 'data' in result, "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РїРѕР»Рµ data"
        assert 'observations' in result['data'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ observations РІ data"
        assert 'result' in result['data']['observations'], "РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚ result РІ observations"
        logger.success("РІСљвЂ¦ exec_script РІРѕР·РІСЂР°С‰Р°РµС‚ СЂРµР·СѓР»СЊС‚Р°С‚ С‡РµСЂРµР· observations")
        
        # РўРµСЃС‚ 8: РїСЂРѕРІРµСЂРєР° РѕС‚СЃСѓС‚СЃС‚РІРёСЏ С‚РѕРї-Р»РµРІРµР» timestamp
        logger.info("\n8РїС‘РЏРІС“Р€ РўРµСЃС‚ РѕС‚СЃСѓС‚СЃС‚РІРёСЏ С‚РѕРї-Р»РµРІРµР» timestamp...")
        result = await orchestrator.handle_command({'cmd': 'ping'})
        assert 'timestamp' not in result, "РќРµ РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ С‚РѕРї-Р»РµРІРµР» timestamp"
        assert 'timestamp_iso' in result['meta'], "timestamp_iso РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІ meta"
        logger.success("РІСљвЂ¦ С‚РѕРї-Р»РµРІРµР» timestamp РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚, timestamp_iso РІ meta")
        
        # Р—Р°РІРµСЂС€РµРЅРёРµ
        await orchestrator.shutdown()
        
        logger.info("=" * 70)
        logger.success("РІСљвЂ¦ Р’СЃРµ unit-С‚РµСЃС‚С‹ РїСЂРѕР№РґРµРЅС‹ СѓСЃРїРµС€РЅРѕ!")
        logger.info("=" * 70)
        
    except AssertionError as e:
        logger.error(f"РІСњРЉ РћС€РёР±РєР° РІ unit-С‚РµСЃС‚Рµ: {e}")
        raise
    except Exception as e:
        logger.error(f"РІСњРЉ РћС€РёР±РєР° РІРѕ РІСЂРµРјСЏ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ: {e}")
        logger.exception(e)
        raise


async def test_orchestrator():
    """
    РўРµСЃС‚РѕРІР°СЏ С„СѓРЅРєС†РёСЏ РґР»СЏ РїСЂРѕРІРµСЂРєРё СЂР°Р±РѕС‚С‹ AgentOrchestrator.
    """
    from core.database import db_manager
    
    logger.info("=" * 70)
    logger.info("СЂСџВ§Р„ РќР°С‡Р°Р»Рѕ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ AgentOrchestrator")
    logger.info("=" * 70)
    
    try:
        # РЎРѕР·РґР°РµРј РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂ СЃ С‚РµСЃС‚РѕРІС‹РјРё РјРѕРґСѓР»СЏРјРё
        orchestrator = AgentOrchestrator(
            db_manager=db_manager,
            enabled_modules=["system"]
        )
        
        # РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ
        logger.info("\n1РїС‘РЏРІС“Р€ РРЅРёС†РёР°Р»РёР·Р°С†РёСЏ РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂР°...")
        await orchestrator.initialize()
        
        # РўРµСЃС‚ РєРѕРјР°РЅРґС‹ ping
        logger.info("\n2РїС‘РЏРІС“Р€ РўРµСЃС‚ РєРѕРјР°РЅРґС‹ 'ping'...")
        result = await orchestrator.handle_command({'cmd': 'ping'})
        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ ping: {result}")
        
        # РўРµСЃС‚ РєРѕРјР°РЅРґС‹ list_modules
        logger.info("\n3РїС‘РЏРІС“Р€ РўРµСЃС‚ РєРѕРјР°РЅРґС‹ 'list_modules'...")
        result = await orchestrator.handle_command({'cmd': 'list_modules'})
        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ list_modules: {result}")
        
        # РўРµСЃС‚ РєРѕРјР°РЅРґС‹ collect (РІСЃРµ РјРѕРґСѓР»Рё)
        logger.info("\n4РїС‘РЏРІС“Р€ РўРµСЃС‚ РєРѕРјР°РЅРґС‹ 'collect' (РІСЃРµ РјРѕРґСѓР»Рё)...")
        result = await orchestrator.handle_command({'cmd': 'collect'})
        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ collect: {result}")
        
        # РўРµСЃС‚ РєРѕРјР°РЅРґС‹ collect (РєРѕРЅРєСЂРµС‚РЅС‹Р№ РјРѕРґСѓР»СЊ)
        logger.info("\n5РїС‘РЏРІС“Р€ РўРµСЃС‚ РєРѕРјР°РЅРґС‹ 'collect' (РјРѕРґСѓР»СЊ system)...")
        result = await orchestrator.handle_command({
            'cmd': 'collect',
            'modules': ['system']
        })
        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ collect (system): {result}")
        
        # РўРµСЃС‚ РєРѕРјР°РЅРґС‹ update
        logger.info("\n6РїС‘РЏРІС“Р€ РўРµСЃС‚ РєРѕРјР°РЅРґС‹ 'update'...")
        result = await orchestrator.handle_command({
            'cmd': 'update',
            'version': '2.0.0'
        })
        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ update: {result}")
        
        # РўРµСЃС‚ РєРѕРјР°РЅРґС‹ exec_script
        logger.info("\n7РїС‘РЏРІС“Р€ РўРµСЃС‚ РєРѕРјР°РЅРґС‹ 'exec_script'...")
        test_code = """
async def run():
    return {"test": "result"}
"""
        result = await orchestrator.handle_command({
            'cmd': 'exec_script',
            'code': test_code
        })
        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ exec_script: {result}")
        
        # РўРµСЃС‚ РЅРµРёР·РІРµСЃС‚РЅРѕР№ РєРѕРјР°РЅРґС‹
        logger.info("\n8РїС‘РЏРІС“Р€ РўРµСЃС‚ РЅРµРёР·РІРµСЃС‚РЅРѕР№ РєРѕРјР°РЅРґС‹...")
        result = await orchestrator.handle_command({'cmd': 'unknown_command'})
        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ unknown_command: {result}")
        
        # РўРµСЃС‚ РїСѓСЃС‚РѕР№ РєРѕРјР°РЅРґС‹
        logger.info("\n9РїС‘РЏРІС“Р€ РўРµСЃС‚ РїСѓСЃС‚РѕР№ РєРѕРјР°РЅРґС‹...")
        result = await orchestrator.handle_command({})
        logger.info(f"Р РµР·СѓР»СЊС‚Р°С‚ РїСѓСЃС‚РѕР№ РєРѕРјР°РЅРґС‹: {result}")
        
        # Р—Р°РІРµСЂС€РµРЅРёРµ
        await orchestrator.shutdown()
        
        logger.info("=" * 70)
        logger.success("РІСљвЂ¦ РўРµСЃС‚РёСЂРѕРІР°РЅРёРµ Р·Р°РІРµСЂС€РµРЅРѕ СѓСЃРїРµС€РЅРѕ!")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"РІСњРЉ РћС€РёР±РєР° РІРѕ РІСЂРµРјСЏ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ: {e}")
        logger.exception(e)
        raise


if __name__ == "__main__":
    import asyncio
    
    # Р—Р°РїСѓСЃРєР°РµРј С‚РµСЃС‚РёСЂРѕРІР°РЅРёРµ
    asyncio.run(test_orchestrator())


