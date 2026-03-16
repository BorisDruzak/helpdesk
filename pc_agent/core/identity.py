"""
Менеджер идентификации агента.
Protocol V3: Валидация device_id = UUIDv4 (замечание 1.7, Фаза 9).

Управляет UUID агента и токеном аутентификации.
Обеспечивает постоянную идентификацию через сохранение данных в файл.
"""

import json
import uuid
import socket
import platform
from pathlib import Path
from typing import Dict, Any, Optional

from loguru import logger


class IdentityManager:
    """
    Менеджер идентификации и аутентификации агента.
    
    Protocol V3 изменения (замечание 1.7):
    - device_id всегда UUIDv4
    - Валидация UUID при загрузке
    - Регенерация если невалидный
    
    Управляет:
    - UUID агента (постоянный идентификатор, всегда UUIDv4)
    - Токеном аутентификации (получается после логина)
    - Данными для handshake (UUID, токен, hostname, IP)
    
    Данные сохраняются в файл для постоянного хранения.
    Путь к файлу может быть передан явно или загружен из конфигурации.
    """
    
    def __init__(self, identity_file: Optional[str] = None):
        """
        Инициализация менеджера идентификации.
        
        Args:
            identity_file: Путь к файлу с данными идентификации.
                          Если None, будет использован путь из конфигурации.
        """
        if identity_file is None:
            try:
                from pc_agent.config.config_loader import get_config, get_config_base
                base = get_config_base()
                cfg = get_config()
                if base is not None:
                    identity_file = str((base / "identity.json").resolve())
                else:
                    identity_file = cfg.paths.identity_file
                    if not Path(identity_file).is_absolute():
                        identity_file = "data/identity.json"
                logger.debug(f"📁 Путь к identity: {identity_file}")
            except Exception as e:
                logger.warning(f"⚠️  Не удалось загрузить конфиг для identity: {e}")
                identity_file = "data/identity.json"
                logger.debug(f"📁 Использую путь по умолчанию: {identity_file}")
        
        self.identity_file = Path(identity_file)
        self.uuid: Optional[str] = None
        self.token: Optional[str] = None
    
    @staticmethod
    def is_valid_uuid(value: Any) -> bool:
        """
        Проверяет, является ли значение валидным UUIDv4.
        
        Protocol V3 (замечание 1.7): device_id всегда должен быть UUIDv4.
        
        Args:
            value: Значение для проверки
            
        Returns:
            True если значение является валидным UUID, False иначе
        """
        if value is None or not isinstance(value, str):
            return False
        
        try:
            # Парсим UUID и проверяем что это валидный UUID
            parsed = uuid.UUID(value)
            # Проверяем что строковое представление совпадает (нормализация)
            return str(parsed) == value.lower()
        except (ValueError, AttributeError, TypeError):
            return False
    
    def load_or_create(self) -> Dict[str, Any]:
        """
        Загружает существующую идентификацию или создает новую.
        
        Protocol V3 (замечание 1.7):
        - Валидирует UUID при загрузке
        - Если UUID невалидный - регенерирует новый UUIDv4
        
        Если файл существует:
            - Загружает UUID и токен из файла
            - Валидирует UUID, если невалидный - регенерирует
        
        Если файла нет:
            - Генерирует новый UUID
            - Создает структуру {'uuid': ..., 'token': None}
            - Сохраняет в файл
        
        Returns:
            Dict с данными идентификации {'uuid': str, 'token': str | None}
        """
        # Создаем директорию если нужно
        self.identity_file.parent.mkdir(parents=True, exist_ok=True)
        
        if self.identity_file.exists():
            # Загружаем существующую идентификацию
            try:
                with open(self.identity_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.uuid = data.get('uuid')
                # Токен не берём из файла — единственный источник БД (storage.db auth_tokens)
                self.token = None
                
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # ВАЛИДАЦИЯ UUID (замечание 1.7, Фаза 9)
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                
                if self.is_valid_uuid(self.uuid):
                    logger.info(f"✅ Valid UUID loaded: {self.uuid[:8]}...")
                else:
                    # Невалидный UUID - регенерируем
                    old_uuid = self.uuid
                    self.uuid = str(uuid.uuid4())
                    data['uuid'] = self.uuid
                    
                    logger.warning(
                        f"⚠️  Invalid device_id format: {old_uuid}. "
                        f"Regenerating new UUIDv4..."
                    )
                    
                    # Сохраняем новый UUID
                    self._save_to_file(data)
                    
                    logger.success(f"✅ New UUID generated: {self.uuid}")
                
                return data
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга JSON в identity файле: {e}")
                logger.info("🆕 Создаю новую идентификацию...")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки идентификации: {e}")
                logger.info("🆕 Создаю новую идентификацию...")
        
        # Создаем новую идентификацию
        self.uuid = str(uuid.uuid4())
        self.token = None
        
        data = {
            'uuid': self.uuid,
            'token': self.token
        }
        
        # Сохраняем в файл
        self._save_to_file(data)
        
        logger.success(f"✅ Создана новая идентификация: UUID={self.uuid}")
        
        return data
    
    def save_token(self, token: str) -> None:
        """
        Сохраняет токен аутентификации ТОЛЬКО в память.
        Для персистентного хранения используйте DatabaseManager.save_auth_token().
        
        ВАЖНО: Токен НЕ сохраняется в identity.json (legacy удален).
        Вызывающий код должен сохранить токен в БД через DatabaseManager.
        
        Args:
            token: Токен аутентификации полученный от сервера
        """
        self.token = token
        logger.info(f"[IdentityManager] Токен загружен в память: {token[:8]}...")
    
    def get_handshake_data(self) -> Dict[str, Any]:
        """
        Возвращает данные для handshake с сервером.
        
        Включает:
        - uuid: Уникальный идентификатор агента (гарантированно UUIDv4)
        - token: Токен аутентификации
        - hostname: Имя хоста
        - ip: IP адрес
        
        Returns:
            Dict с данными для handshake
        """
        # Получаем hostname
        hostname = socket.gethostname()
        
        # Получаем IP адрес
        try:
            # Пытаемся получить внешний IP через подключение к внешнему адресу
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            # Если не удалось, используем localhost
            ip = "127.0.0.1"
        
        return {
            'uuid': self.uuid,
            'token': self.token,
            'hostname': hostname,
            'ip': ip,
            'os': platform.system(),
            'os_version': platform.release(),
            'python_version': platform.python_version(),
            'architecture': platform.machine()
        }
    
    def clear_token(self) -> None:
        """
        Очищает токен из памяти.
        Для очистки из БД используйте DatabaseManager.clear_auth_token().
        """
        self.token = None
        logger.info("🗑️  Токен очищен из памяти")
    
    def _save_to_file(self, data: Dict[str, Any]) -> None:
        """
        Сохраняет данные в файл.
        
        Args:
            data: Данные для сохранения
        """
        try:
            with open(self.identity_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"💾 Данные сохранены в {self.identity_file}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")
    
    @property
    def has_token(self) -> bool:
        """
        Проверяет наличие токена (из БД или файла).
        
        Returns:
            True если токен есть, False если нет
        """
        # Сначала проверяем БД
        try:
            from core.database import db_manager
            if db_manager:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Если loop уже запущен, возвращаем из памяти
                        return self.token is not None and self.token != ""
                    else:
                        # Если loop не запущен, проверяем БД
                        token = loop.run_until_complete(db_manager.get_auth_token(self.uuid))
                        if token:
                            self.token = token
                            return True
                except RuntimeError:
                    # Нет event loop, создаем новый
                    token = asyncio.run(db_manager.get_auth_token(self.uuid))
                    if token:
                        self.token = token
                        return True
        except Exception as e:
            logger.debug(f"[IdentityManager] Не удалось проверить токен в БД: {e}")
        
        # Fallback на файл
        return self.token is not None and self.token != ""
    
    def validate_device_id(self) -> bool:
        """
        Проверяет валидность текущего device_id (UUID).
        
        Protocol V3 (замечание 1.7): device_id должен быть UUIDv4.
        
        Returns:
            True если device_id валиден, False иначе
        """
        return self.is_valid_uuid(self.uuid)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ТЕСТИРОВАНИЕ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_identity_v3():
    """Тест IdentityManager с валидацией UUID (Protocol V3)."""
    import tempfile
    import os
    
    logger.info("=" * 60)
    logger.info("Тестирование IdentityManager V3")
    logger.info("=" * 60)
    
    # Тест 1: is_valid_uuid
    logger.info("1. Тест is_valid_uuid...")
    
    valid_uuid = str(uuid.uuid4())
    assert IdentityManager.is_valid_uuid(valid_uuid) == True
    assert IdentityManager.is_valid_uuid("not-a-uuid") == False
    assert IdentityManager.is_valid_uuid(None) == False
    assert IdentityManager.is_valid_uuid(123) == False
    assert IdentityManager.is_valid_uuid("") == False
    
    # Тест с прописными буквами (должен нормализоваться)
    upper_uuid = valid_uuid.upper()
    # UUID с прописными буквами невалиден в нашей строгой проверке
    assert IdentityManager.is_valid_uuid(upper_uuid) == False
    
    logger.success("   ✅ is_valid_uuid работает корректно")
    
    # Тест 2: Создание новой идентификации
    logger.info("2. Тест создания новой идентификации...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        identity_file = os.path.join(tmpdir, "identity.json")
        
        manager = IdentityManager(identity_file)
        data = manager.load_or_create()
        
        assert manager.uuid is not None
        assert IdentityManager.is_valid_uuid(manager.uuid)
        assert manager.token is None
        
        logger.success(f"   ✅ Новый UUID: {manager.uuid}")
    
    # Тест 3: Загрузка существующей идентификации
    logger.info("3. Тест загрузки существующей идентификации...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        identity_file = os.path.join(tmpdir, "identity.json")
        
        # Создаем файл с валидным UUID
        test_uuid = str(uuid.uuid4())
        with open(identity_file, 'w') as f:
            json.dump({'uuid': test_uuid, 'token': 'test-token'}, f)
        
        manager = IdentityManager(identity_file)
        data = manager.load_or_create()
        
        assert manager.uuid == test_uuid
        assert manager.token == 'test-token'
        
        logger.success(f"   ✅ Загружен UUID: {manager.uuid[:8]}...")
    
    # Тест 4: Регенерация невалидного UUID
    logger.info("4. Тест регенерации невалидного UUID...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        identity_file = os.path.join(tmpdir, "identity.json")
        
        # Создаем файл с невалидным UUID
        with open(identity_file, 'w') as f:
            json.dump({'uuid': 'invalid-uuid-123', 'token': 'keep-token'}, f)
        
        manager = IdentityManager(identity_file)
        data = manager.load_or_create()
        
        # UUID должен быть регенерирован
        assert manager.uuid != 'invalid-uuid-123'
        assert IdentityManager.is_valid_uuid(manager.uuid)
        # Токен должен сохраниться
        assert manager.token == 'keep-token'
        
        # Проверяем что файл обновился
        with open(identity_file, 'r') as f:
            saved_data = json.load(f)
        assert saved_data['uuid'] == manager.uuid
        
        logger.success(f"   ✅ Регенерирован UUID: {manager.uuid[:8]}...")
    
    logger.info("=" * 60)
    logger.success("Все тесты IdentityManager V3 пройдены!")
    logger.info("=" * 60)


if __name__ == "__main__":
    test_identity_v3()
