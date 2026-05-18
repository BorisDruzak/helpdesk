"""
Module Registry Service
Автоматический анализ возможностей модулей с использованием inspect.
"""

import inspect
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING
from functools import wraps

try:
    from shared.tool_contracts import normalize_risk_level, to_legacy_risk_level
except ModuleNotFoundError:  # pragma: no cover - defensive path for nested cwd entrypoints
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from shared.tool_contracts import normalize_risk_level, to_legacy_risk_level

if TYPE_CHECKING:
    from pydantic import BaseModel
else:
    try:
        from pydantic import BaseModel
    except ImportError:
        # Fallback для случаев, когда pydantic не установлен
        BaseModel = None


def _agent_default_execution() -> Dict[str, Any]:
    return {
        "target": "agent_builtin",
        "requires_device": True,
        "requires_agent_online": True,
        "supports_auto_install": False,
        "requires_integration": False,
    }


def _agent_default_deployment(module_name: str) -> Dict[str, Any]:
    return {
        "provider_id": module_name,
        "install_required_on_agent": False,
        "package_type": "builtin",
    }


def _agent_default_safety(metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "side_effects": bool(metadata.get("side_effects", False)),
        "requires_consent": bool(metadata.get("requires_consent", False)),
        "idempotent": bool(metadata.get("idempotent", False)),
    }


def _agent_default_artifacts(artifact_types: List[Dict[str, Any]]) -> Dict[str, Any]:
    kinds = [
        artifact.get("kind")
        for artifact in artifact_types
        if isinstance(artifact, dict) and isinstance(artifact.get("kind"), str) and artifact.get("kind")
    ]
    if not kinds:
        return {}
    return {"may_produce_artifacts": True, "artifact_kinds": kinds}


def exposed_tool(
    name: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    description: Optional[str] = None,
    risk_level: Optional[str] = None,
    capabilities: Optional[List[str]] = None,
    params_schema: Optional[Dict[str, Any]] = None,
    params_model: Optional['type[BaseModel]'] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    output_contract: Optional[Dict[str, Any]] = None,
    presentation_schema: Optional[Dict[str, Any]] = None,
    presets: Optional[List[Dict[str, Any]]] = None,
    # Параметры для metadata (PolicyEngine)
    metadata_risk_level: Optional[str] = None,
    metadata_scopes: Optional[List[str]] = None,
    metadata_requires_consent: Optional[bool] = None,
    metadata_allow_roles: Optional[List[str]] = None,
    metadata_domain: Optional[str] = None,
    metadata_platforms: Optional[List[str]] = None,
    metadata_timeout_sec: Optional[int] = None,
    metadata_idempotent: Optional[bool] = None,
    metadata_origin: Optional[str] = None,
    metadata_side_effects: Optional[bool] = None,
    contract_version: Optional[str] = None,
    dependencies: Optional[Dict[str, Any]] = None,
    lifecycle: Optional[str] = None,
    error_codes: Optional[List[str]] = None,
    artifact_types: Optional[List[Dict[str, Any]]] = None,
    redaction: Optional[Dict[str, Any]] = None,
    resources: Optional[Dict[str, Any]] = None,
    execution: Optional[Dict[str, Any]] = None,
    deployment: Optional[Dict[str, Any]] = None,
    safety: Optional[Dict[str, Any]] = None,
    readiness: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
    artifacts: Optional[Dict[str, Any]] = None,
) -> Callable:
    """
    Декоратор для пометки методов модуля как экспонируемых инструментов (tools) для MCP.
    
    Методы, помеченные этим декоратором, будут автоматически зарегистрированы
    в ModuleRegistry и доступны через get_manifest().
    
    Args:
        name: Имя инструмента (опционально). Если не указано, используется имя метода.
        description: Описание инструмента (опционально). Если не указано, используется docstring метода.
        risk_level: Уровень риска инструмента (опционально). По умолчанию "safe_readonly".
        capabilities: Список возможностей инструмента (опционально).
        params_schema: Схема параметров в формате JSON Schema (опционально, устаревший параметр).
            Используется только если params_model не задан. По умолчанию пустой dict.
        params_model: Pydantic-модель параметров (опционально). Если задана, автоматически генерируется
            JSON Schema через model_json_schema(). Приоритет над params_schema.
        presets: Список предустановленных конфигураций (опционально). Каждый пресет - это словарь с полями:
            - id: уникальный идентификатор пресета
            - name: человеко-читаемое название
            - description: описание пресета
            - params: словарь с параметрами для запуска tool
        metadata_risk_level: Уровень риска для PolicyEngine (опционально). По умолчанию "safe_read".
        metadata_scopes: Список областей доступа (опционально). По умолчанию [].
        metadata_requires_consent: Требуется ли согласие пользователя (опционально). По умолчанию False.
        metadata_allow_roles: Список разрешенных ролей (опционально). По умолчанию None.
    
    Returns:
        Декорированная функция с атрибутами __exposed_tool__, __tool_name__, __tool_desc__,
        __tool_risk_level__, __tool_capabilities__, __tool_params_model__, __tool_params_schema__,
        __tool_presets__, __tool_metadata__
    
    Example:
        from pydantic import BaseModel
        
        class SystemParams(BaseModel):
            interval: int = 1
        
        @exposed_tool(
            name="get_system_info",
            description="Получить системную информацию",
            risk_level="safe_readonly",
            capabilities=["read"],
            params_model=SystemParams,
            metadata_risk_level="safe_read",
            metadata_scopes=["system.read"],
            metadata_requires_consent=False
        )
        async def collect(self) -> Dict[str, Any]:
            return {"cpu": 50, "ram": 60}
    """
    def decorator(func: Callable) -> Callable:
        # Обрабатываем params_model
        if params_model is not None:
            if BaseModel is None:
                raise ImportError(
                    "pydantic не установлен. Установите его для использования params_model: "
                    "pip install pydantic"
                )
            if not issubclass(params_model, BaseModel):
                raise TypeError(
                    f"params_model должен быть подклассом pydantic.BaseModel, "
                    f"получен: {type(params_model)}"
                )
            # Генерируем JSON Schema из Pydantic модели
            params_schema_value = params_model.model_json_schema()
            params_model_value = params_model
        else:
            # Обратная совместимость: используем params_schema если задан
            params_schema_value = params_schema if params_schema is not None else {}
            params_model_value = None
        
        # Формируем metadata для PolicyEngine
        metadata_dict = {
            'domain': metadata_domain,
            'platforms': metadata_platforms,
            'risk_level': normalize_risk_level(metadata_risk_level, "safe_read"),
            'scopes': metadata_scopes if metadata_scopes is not None else [],
            'requires_consent': metadata_requires_consent if metadata_requires_consent is not None else False,
            'allow_roles': metadata_allow_roles,
            'timeout_sec': metadata_timeout_sec,
            'idempotent': metadata_idempotent if metadata_idempotent is not None else False,
            'origin': metadata_origin,
            'side_effects': metadata_side_effects if metadata_side_effects is not None else False,
        }
        legacy_risk_level = to_legacy_risk_level(risk_level if risk_level is not None else metadata_dict["risk_level"])
        
        # Устанавливаем атрибуты для пометки функции
        func.__exposed_tool__ = True
        func.__tool_name__ = name if name is not None else func.__name__
        func.__tool_aliases__ = aliases if aliases is not None else []
        func.__tool_desc__ = description if description is not None else None
        func.__tool_risk_level__ = legacy_risk_level
        func.__tool_capabilities__ = capabilities if capabilities is not None else None
        func.__tool_params_model__ = params_model_value
        func.__tool_params_schema__ = params_schema_value
        func.__tool_output_schema__ = output_schema if isinstance(output_schema, dict) else {}
        func.__tool_output_contract__ = output_contract if isinstance(output_contract, dict) else {}
        func.__tool_presentation_schema__ = presentation_schema if isinstance(presentation_schema, dict) else {}
        func.__tool_presets__ = presets if presets is not None else []
        func.__tool_metadata__ = metadata_dict
        func.__tool_contract_version__ = str(contract_version or "1.0.0")
        func.__tool_dependencies__ = dependencies if isinstance(dependencies, dict) else {}
        func.__tool_lifecycle__ = str(lifecycle or "stable")
        func.__tool_error_codes__ = list(error_codes or [])
        func.__tool_artifact_types__ = list(artifact_types or [])
        func.__tool_redaction__ = redaction if isinstance(redaction, dict) else {}
        func.__tool_resources__ = resources if isinstance(resources, dict) else {}
        func.__tool_execution__ = execution if isinstance(execution, dict) else {}
        func.__tool_deployment__ = deployment if isinstance(deployment, dict) else {}
        func.__tool_safety__ = safety if isinstance(safety, dict) else {}
        func.__tool_readiness__ = readiness if isinstance(readiness, dict) else {}
        func.__tool_evidence__ = evidence if isinstance(evidence, dict) else {}
        func.__tool_artifacts__ = artifacts if isinstance(artifacts, dict) else {}
        
        # Проверяем, является ли функция асинхронной
        if inspect.iscoroutinefunction(func):
            # Для async функций создаем async wrapper
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Копируем атрибуты на async wrapper
            async_wrapper.__exposed_tool__ = func.__exposed_tool__
            async_wrapper.__tool_name__ = func.__tool_name__
            async_wrapper.__tool_aliases__ = func.__tool_aliases__
            async_wrapper.__tool_desc__ = func.__tool_desc__
            async_wrapper.__tool_risk_level__ = func.__tool_risk_level__
            async_wrapper.__tool_capabilities__ = func.__tool_capabilities__
            async_wrapper.__tool_params_model__ = func.__tool_params_model__
            async_wrapper.__tool_params_schema__ = func.__tool_params_schema__
            async_wrapper.__tool_output_schema__ = func.__tool_output_schema__
            async_wrapper.__tool_output_contract__ = func.__tool_output_contract__
            async_wrapper.__tool_presentation_schema__ = func.__tool_presentation_schema__
            async_wrapper.__tool_presets__ = func.__tool_presets__
            async_wrapper.__tool_metadata__ = func.__tool_metadata__
            async_wrapper.__tool_contract_version__ = func.__tool_contract_version__
            async_wrapper.__tool_dependencies__ = func.__tool_dependencies__
            async_wrapper.__tool_lifecycle__ = func.__tool_lifecycle__
            async_wrapper.__tool_error_codes__ = func.__tool_error_codes__
            async_wrapper.__tool_artifact_types__ = func.__tool_artifact_types__
            async_wrapper.__tool_redaction__ = func.__tool_redaction__
            async_wrapper.__tool_resources__ = func.__tool_resources__
            async_wrapper.__tool_execution__ = func.__tool_execution__
            async_wrapper.__tool_deployment__ = func.__tool_deployment__
            async_wrapper.__tool_safety__ = func.__tool_safety__
            async_wrapper.__tool_readiness__ = func.__tool_readiness__
            async_wrapper.__tool_evidence__ = func.__tool_evidence__
            async_wrapper.__tool_artifacts__ = func.__tool_artifacts__
            return async_wrapper
        else:
            # Для sync функций создаем обычный wrapper
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            
            # Копируем атрибуты на sync wrapper
            sync_wrapper.__exposed_tool__ = func.__exposed_tool__
            sync_wrapper.__tool_name__ = func.__tool_name__
            sync_wrapper.__tool_aliases__ = func.__tool_aliases__
            sync_wrapper.__tool_desc__ = func.__tool_desc__
            sync_wrapper.__tool_risk_level__ = func.__tool_risk_level__
            sync_wrapper.__tool_capabilities__ = func.__tool_capabilities__
            sync_wrapper.__tool_params_model__ = func.__tool_params_model__
            sync_wrapper.__tool_params_schema__ = func.__tool_params_schema__
            sync_wrapper.__tool_output_schema__ = func.__tool_output_schema__
            sync_wrapper.__tool_output_contract__ = func.__tool_output_contract__
            sync_wrapper.__tool_presentation_schema__ = func.__tool_presentation_schema__
            sync_wrapper.__tool_presets__ = func.__tool_presets__
            sync_wrapper.__tool_metadata__ = func.__tool_metadata__
            sync_wrapper.__tool_contract_version__ = func.__tool_contract_version__
            sync_wrapper.__tool_dependencies__ = func.__tool_dependencies__
            sync_wrapper.__tool_lifecycle__ = func.__tool_lifecycle__
            sync_wrapper.__tool_error_codes__ = func.__tool_error_codes__
            sync_wrapper.__tool_artifact_types__ = func.__tool_artifact_types__
            sync_wrapper.__tool_redaction__ = func.__tool_redaction__
            sync_wrapper.__tool_resources__ = func.__tool_resources__
            sync_wrapper.__tool_execution__ = func.__tool_execution__
            sync_wrapper.__tool_deployment__ = func.__tool_deployment__
            sync_wrapper.__tool_safety__ = func.__tool_safety__
            sync_wrapper.__tool_readiness__ = func.__tool_readiness__
            sync_wrapper.__tool_evidence__ = func.__tool_evidence__
            sync_wrapper.__tool_artifacts__ = func.__tool_artifacts__
            return sync_wrapper
    
    return decorator


class ModuleRegistry:
    """
    Singleton-класс для регистрации и анализа модулей.
    Извлекает метаданные о классах и их методах для построения манифеста.
    """
    
    _instance: Optional['ModuleRegistry'] = None
    
    def __new__(cls):
        """Реализация Singleton паттерна."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Инициализация реестра модулей."""
        if self._initialized:
            return
        self._manifest: Dict[str, Dict[str, Any]] = {}
        self._instances: Dict[str, Any] = {}  # Храним экземпляры модулей для вызова методов
        self._tool_index: Dict[str, Dict[str, Any]] = {}
        self._initialized = True
    
    def register(self, instance: Any) -> None:
        """
        Регистрирует экземпляр модуля и извлекает его метаданные.
        
        Регистрирует только методы, помеченные декоратором @exposed_tool.
        Если у модуля нет помеченных методов и он является BaseCollector,
        регистрирует метод collect как дефолтный tool.
        
        Args:
            instance: Экземпляр модуля для регистрации
        
        Raises:
            AttributeError: Если у экземпляра нет атрибута 'name'
        """
        if not hasattr(instance, 'name'):
            raise AttributeError(
                f"Экземпляр {type(instance).__name__} должен иметь атрибут 'name'"
            )
        
        module_name = instance.name
        
        # Извлекаем docstring класса
        class_doc = inspect.getdoc(instance.__class__)
        if not class_doc:
            class_doc = "Описание отсутствует"
        
        # Анализируем методы класса - только помеченные декоратором @exposed_tool
        methods_info: Dict[str, Dict[str, Any]] = {}
        
        # Получаем все атрибуты класса
        exposed_methods_found = False
        
        for attr_name in dir(instance):
            # Пропускаем приватные и защищенные методы
            if attr_name.startswith('_'):
                continue
            
            try:
                attr = getattr(instance, attr_name)
            except Exception:
                # Пропускаем атрибуты, которые не могут быть получены
                continue
            
            # Проверяем, является ли атрибут вызываемым
            if not callable(attr):
                continue
            
            # Проверяем, помечен ли метод декоратором @exposed_tool
            if hasattr(attr, '__exposed_tool__') and getattr(attr, '__exposed_tool__', False):
                exposed_methods_found = True
                # Извлекаем информацию о методе
                method_info = self._extract_method_info(attr, instance)
                # КРИТИЧНО: Сохраняем реальное имя метода в method_info для поиска в instance
                method_info['real_method_name'] = attr_name
                methods_info[attr_name] = method_info
        
        # Fallback: если нет помеченных методов и instance является BaseCollector,
        # регистрируем collect как дефолтный tool
        if not exposed_methods_found:
            from pc_agent.modules.base_module import BaseCollector
            if isinstance(instance, BaseCollector) and hasattr(instance, 'collect'):
                collect_method = getattr(instance, 'collect')
                if callable(collect_method):
                    method_info = self._extract_method_info(collect_method, instance)
                    method_info['real_method_name'] = 'collect'
                    methods_info['collect'] = method_info
        
        # Сохраняем в манифест
        self._manifest[module_name] = {
            'description': class_doc,
            'methods': methods_info
        }
        
        # Сохраняем экземпляр для последующего вызова методов
        self._instances[module_name] = instance
        self._rebuild_tool_index()
    
    def _extract_method_info(self, method: callable, instance: Any) -> Dict[str, Any]:
        """
        Извлекает информацию о методе: docstring, аргументы, async/sync статус,
        risk_level, capabilities, params_model, params_schema.
        
        Args:
            method: Метод для анализа
            instance: Экземпляр модуля (для определения имени модуля)
            
        Returns:
            Словарь с информацией о методе:
            - parameters: "человеко-ориентированная" информация из inspect.signature
            - params_schema: "машинная" JSON Schema из Pydantic модели или params_schema
            - params_model: имя класса Pydantic модели (если задана)
        """
        # Проверяем, есть ли описание из декоратора
        tool_desc = getattr(method, '__tool_desc__', None)
        
        # Извлекаем docstring (приоритет у описания из декоратора)
        if tool_desc:
            method_doc = tool_desc
        else:
            method_doc = inspect.getdoc(method)
            if not method_doc:
                method_doc = "Описание отсутствует"
        
        # Определяем, является ли метод асинхронным
        is_async = inspect.iscoroutinefunction(method)
        
        # Извлекаем аргументы (человеко-ориентированная информация)
        try:
            signature = inspect.signature(method)
            arguments: List[Dict[str, Any]] = []
            
            for param_name, param in signature.parameters.items():
                # Пропускаем self и cls
                if param_name in ('self', 'cls'):
                    continue
                
                arg_info: Dict[str, Any] = {
                    'name': param_name
                }
                
                # Добавляем значение по умолчанию, если есть
                if param.default != inspect.Parameter.empty:
                    arg_info['default'] = param.default
                
                # Добавляем аннотацию типа, если есть
                if param.annotation != inspect.Parameter.empty:
                    # Преобразуем аннотацию в строку для сериализации
                    arg_info['type'] = str(param.annotation)
                
                # Определяем тип параметра (позиционный, keyword-only и т.д.)
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    arg_info['kind'] = '*args'
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    arg_info['kind'] = '**kwargs'
                elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                    arg_info['kind'] = 'keyword_only'
                else:
                    arg_info['kind'] = 'positional_or_keyword'
                
                arguments.append(arg_info)
        
        except (ValueError, TypeError) as e:
            # Если не удалось получить сигнатуру, возвращаем пустой список
            arguments = []
        
        # Получаем имя модуля
        module_name = getattr(instance, 'name', 'unknown')

        # Каноническое имя инструмента может быть semantic key (dns.resolve) или legacy module.tool.
        tool_name_raw = getattr(method, '__tool_name__', method.__name__)
        tool_name = str(tool_name_raw).strip() or method.__name__
        if "." not in tool_name:
            tool_name = f"{module_name}.{tool_name}"
        short_name = tool_name.split(".", 1)[-1]
        aliases = []
        for alias in getattr(method, '__tool_aliases__', []) or []:
            alias_value = str(alias or "").strip()
            if not alias_value:
                continue
            aliases.append(alias_value if "." in alias_value else f"{module_name}.{alias_value}")
        legacy_alias = f"{module_name}.{short_name}"
        if legacy_alias != tool_name:
            aliases.append(legacy_alias)
        aliases = list(dict.fromkeys(aliases))
        
        # Извлекаем дополнительные атрибуты из декоратора
        risk_level = getattr(method, '__tool_risk_level__', "safe_readonly")
        capabilities = getattr(method, '__tool_capabilities__', None)
        
        # Извлекаем params_model и params_schema
        params_model = getattr(method, '__tool_params_model__', None)
        params_schema = getattr(method, '__tool_params_schema__', {})
        output_schema = getattr(method, '__tool_output_schema__', {})
        output_contract = getattr(method, '__tool_output_contract__', {})
        presentation_schema = getattr(method, '__tool_presentation_schema__', {})
        
        # Формируем имя модели (строкой)
        params_model_name = None
        if params_model is not None:
            params_model_name = params_model.__name__
        
        # Извлекаем пресеты
        presets = getattr(method, '__tool_presets__', [])
        
        # Извлекаем metadata из декоратора или проставляем default
        metadata_dict = getattr(method, '__tool_metadata__', None)
        if metadata_dict is None:
            # Если metadata не указано, проставляем default значения
            metadata_dict = {
                'domain': module_name,
                'platforms': ['any'],
                'risk_level': 'safe_read',
                'scopes': [],
                'requires_consent': False,
                'allow_roles': None,
                'timeout_sec': None,
                'idempotent': False,
                'origin': 'builtin',
                'side_effects': False,
                'tool_kind': 'diagnostic',
            }
        else:
            metadata_dict = {
                'domain': metadata_dict.get('domain') or module_name,
                'platforms': metadata_dict.get('platforms') or ['any'],
                'risk_level': normalize_risk_level(metadata_dict.get('risk_level'), 'safe_read'),
                'scopes': metadata_dict.get('scopes', []),
                'requires_consent': metadata_dict.get('requires_consent', False),
                'allow_roles': metadata_dict.get('allow_roles'),
                'timeout_sec': metadata_dict.get('timeout_sec'),
                'idempotent': metadata_dict.get('idempotent', False),
                'origin': metadata_dict.get('origin', 'builtin'),
                'side_effects': metadata_dict.get('side_effects', False),
                'tool_kind': metadata_dict.get('tool_kind', 'diagnostic'),
            }
        artifact_types_value = list(getattr(method, '__tool_artifact_types__', []) or [])
        execution = dict(getattr(method, '__tool_execution__', {}) or _agent_default_execution())
        deployment = dict(getattr(method, '__tool_deployment__', {}) or _agent_default_deployment(module_name))
        safety = dict(getattr(method, '__tool_safety__', {}) or _agent_default_safety(metadata_dict))
        readiness = dict(getattr(method, '__tool_readiness__', {}) or {
            "requires_credentials": False,
            "requires_mapping": False,
            "requires_policy": False,
        })
        evidence = dict(getattr(method, '__tool_evidence__', {}) or {"produces_evidence": False})
        artifacts = dict(getattr(method, '__tool_artifacts__', {}) or _agent_default_artifacts(artifact_types_value))
        
        return {
            'tool_name': tool_name,
            'aliases': aliases,
            'short_name': short_name,
            'module_name': module_name,
            'description': method_doc,
            'parameters': arguments,  # Человеко-ориентированная информация
            'async': is_async,
            'risk_level': to_legacy_risk_level(risk_level),
            'capabilities': capabilities,
            'params_model': params_model_name,  # Имя класса модели
            'params_schema': params_schema,  # Машинная JSON Schema
            'output_schema': output_schema,
            'output_contract': output_contract,
            'presentation_schema': presentation_schema,
            'presets': presets,  # Предустановленные конфигурации
            'metadata': metadata_dict,  # Метаданные для PolicyEngine
            'contract_version': getattr(method, '__tool_contract_version__', "1.0.0"),
            'dependencies': getattr(method, '__tool_dependencies__', {}),
            'lifecycle': getattr(method, '__tool_lifecycle__', "stable"),
            'error_codes': list(getattr(method, '__tool_error_codes__', []) or []),
            'artifact_types': artifact_types_value,
            'redaction': getattr(method, '__tool_redaction__', {}) or {},
            'resources': getattr(method, '__tool_resources__', {}) or {},
            'execution': execution,
            'deployment': deployment,
            'safety': safety,
            'readiness': readiness,
            'evidence': evidence,
            'artifacts': artifacts,
        }
    
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает весь накопленный манифест всех зарегистрированных модулей.
        
        Returns:
            Словарь с информацией обо всех зарегистрированных модулях
        """
        return self._manifest.copy()
    
    def get_module(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает информацию о конкретном модуле.
        
        Args:
            module_name: Имя модуля
            
        Returns:
            Словарь с информацией о модуле или None, если модуль не найден
        """
        return self._manifest.get(module_name)
    
    def clear(self) -> None:
        """Очищает весь манифест."""
        self._manifest.clear()
        self._tool_index.clear()
    
    def reset(self) -> None:
        """
        Сбрасывает все внутренние структуры registry.
        Очищает манифест, после чего list_tools возвращает пустой список.
        """
        self._manifest.clear()
        self._instances.clear()
        self._tool_index.clear()
    
    def unregister(self, module_name: str) -> bool:
        """
        Удаляет модуль из реестра.
        
        Args:
            module_name: Имя модуля для удаления
            
        Returns:
            True, если модуль был удален, False, если модуль не был найден
        """
        if module_name in self._manifest:
            del self._manifest[module_name]
            if module_name in self._instances:
                del self._instances[module_name]
            self._rebuild_tool_index()
            return True
        return False

    def _build_tool_spec(self, tool_info: Dict[str, Any]) -> Dict[str, Any]:
        metadata = tool_info.get('metadata')
        if metadata is None:
            metadata = {
                'risk_level': 'safe_read',
                'scopes': [],
                'requires_consent': False,
                'allow_roles': None,
            }
        return {
            'description': tool_info.get('description', 'Описание отсутствует'),
            'risk_level': tool_info.get('risk_level', 'safe_readonly'),
            'capabilities': tool_info.get('capabilities'),
            'params_model': tool_info.get('params_model'),
            'params_schema': tool_info.get('params_schema', {}),
            'output_schema': tool_info.get('output_schema', {}),
            'output_contract': tool_info.get('output_contract', {}),
            'presentation_schema': tool_info.get('presentation_schema', {}),
            'parameters': tool_info.get('parameters', []),
            'presets': tool_info.get('presets', []),
            'async': tool_info.get('async', False),
            'metadata': metadata,
            'contract_version': tool_info.get('contract_version', '1.0.0'),
            'dependencies': tool_info.get('dependencies', {}),
            'lifecycle': tool_info.get('lifecycle', 'stable'),
            'error_codes': tool_info.get('error_codes', []),
            'artifact_types': tool_info.get('artifact_types', []),
            'redaction': tool_info.get('redaction', {}),
            'resources': tool_info.get('resources', {}),
            'execution': tool_info.get('execution', _agent_default_execution()),
            'deployment': tool_info.get('deployment', _agent_default_deployment("unknown")),
            'safety': tool_info.get('safety', _agent_default_safety(metadata)),
            'readiness': tool_info.get('readiness', {
                "requires_credentials": False,
                "requires_mapping": False,
                "requires_policy": False,
            }),
            'evidence': tool_info.get('evidence', {"produces_evidence": False}),
            'artifacts': tool_info.get('artifacts', {}),
        }

    def _rebuild_tool_index(self) -> None:
        self._tool_index = {}
        for module_name, module_info in self._manifest.items():
            methods_info = module_info.get('methods', {})
            for method_name, tool_info in methods_info.items():
                canonical_tool = str(tool_info.get('tool_name') or '').strip()
                if not canonical_tool:
                    continue
                entry = {
                    "tool": canonical_tool,
                    "module": module_name,
                    "spec": self._build_tool_spec(tool_info),
                    "method_name": tool_info.get('real_method_name') or method_name,
                    "real_method_name": tool_info.get('real_method_name') or method_name,
                    "instance": self._instances.get(module_name),
                    "aliases": list(tool_info.get('aliases') or []),
                }
                self._tool_index[canonical_tool] = entry
                for alias in entry["aliases"]:
                    self._tool_index.setdefault(alias, entry)
    
    def get_module_names(self) -> List[str]:
        """
        Возвращает список имен всех зарегистрированных модулей.
        
        Returns:
            Список имен модулей
        """
        return list(self._manifest.keys())
    
    def get_tools_flat(self) -> List[Dict[str, Any]]:
        """
        Возвращает плоский список всех tools в формате MCP-ready.
        
        Для каждого tool формирует уникальное имя:
        - Если tool_name уникален среди всех модулей, используется просто tool_name
        - Иначе используется формат "module_name.tool_name"
        
        Returns:
            Список словарей с информацией о каждом tool:
            [{
                "tool": "<module>.<tool_name>" или "<tool_name>",
                "module": "<module_name>",
                "spec": {
                    "description": ...,
                    "risk_level": ...,
                    "capabilities": ...,
                    "params_model": ...,
                    "params_schema": ...,
                    "parameters": ...,
                    "async": ...
                }
            }]
        """
        all_tools: List[Dict[str, Any]] = []
        for module_name, module_info in self._manifest.items():
            methods_info = module_info.get('methods', {})
            for method_name, tool_info in methods_info.items():
                all_tools.append({
                    'module_name': module_name,
                    'tool_name': tool_info.get('tool_name') or f"{module_name}.{method_name}",
                    'tool_info': tool_info
                })
        
        # Второй проход: формируем финальный список с правильными именами
        result: List[Dict[str, Any]] = []
        
        for tool_data in all_tools:
            module_name = tool_data['module_name']
            tool_name = tool_data['tool_name']
            tool_info = tool_data['tool_info']
            
            result.append({
                'tool': tool_name,
                'module': module_name,
                'aliases': list(tool_info.get('aliases') or []),
                'spec': self._build_tool_spec(tool_info)
            })
        
        return result
    
    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Получает спецификацию инструмента по имени.
        
        Поддерживается только формат "module.tool_name" (контракт Этап 3).
        Короткое имя без точки не разрешается — возвращается None.
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            Словарь с информацией об инструменте:
            {
                "tool": str,  # Полное имя инструмента
                "module": str,  # Имя модуля
                "spec": {
                    "description": str,
                    "risk_level": str,
                    "capabilities": list,
                    "params_model": str | None,
                    "params_schema": dict,
                    "parameters": list,
                    "async": bool
                },
                "method_name": str,  # Имя метода в модуле
                "instance": Any  # Экземпляр модуля
            }
            или None, если инструмент не найден
        """
        tool_found = self._tool_index.get(tool_name)
        if not tool_found:
            return None
        instance = tool_found.get("instance") or self._instances.get(tool_found.get("module"))
        if not instance:
            return None
        return {
            "tool": tool_found.get("tool"),
            "module": tool_found.get("module"),
            "spec": tool_found.get("spec", {}),
            "method_name": tool_found.get("method_name"),
            "real_method_name": tool_found.get("real_method_name"),
            "instance": instance,
            "aliases": list(tool_found.get("aliases") or []),
        }
    
    async def call_tool(self, tool_name: str, **params) -> Any:
        """
        Вызывает инструмент по имени с переданными параметрами.
        
        Args:
            tool_name: Имя инструмента
            **params: Параметры для передачи в метод
            
        Returns:
            Результат выполнения метода (может быть coroutine или обычное значение)
            
        Raises:
            ValueError: Если инструмент не найден
            AttributeError: Если метод не найден в модуле
        """
        tool_info = self.get_tool(tool_name)
        if not tool_info:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        instance = tool_info.get("instance")
        method_name = tool_info.get("method_name")
        
        if not instance or not method_name:
            raise ValueError(f"Tool '{tool_name}' instance or method not found")
        
        # Получаем метод
        if not hasattr(instance, method_name):
            raise AttributeError(f"Method '{method_name}' not found in module '{tool_info.get('module')}'")
        
        method = getattr(instance, method_name)
        if not callable(method):
            raise AttributeError(f"Attribute '{method_name}' is not callable")
        
        # Вызываем метод
        import inspect
        if inspect.iscoroutinefunction(method):
            return await method(**params)
        else:
            return method(**params)
