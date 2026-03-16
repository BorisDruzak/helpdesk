"""
Модуль для снятия скриншотов и записи экрана.

Использует библиотеку mss (python-mss) для быстрого кроссплатформенного
захвата экрана. Запись видео — mss + ffmpeg (subprocess). Файлы сохраняются
локально и передаются через artifact pipeline.
"""

import asyncio
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

import mss
import mss.tools
from loguru import logger
from pydantic import BaseModel, Field

# Импортируем базовый класс из родительского пакета
from modules.base_module import BaseCollector
from pc_agent.config.config_loader import get_config
from core.registry import exposed_tool
from core.recording_controller import get_recording_controller

# Лимит размера видео (байт), план этап 1
SIZE_LIMIT_BYTES = 200 * 1024 * 1024


def _get_ffmpeg_path() -> Optional[str]:
    """
    Возвращает путь к исполняемому файлу ffmpeg.
    Сначала ищет в PATH, затем — в пакете imageio-ffmpeg (pip install imageio-ffmpeg).
    """
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    return None


class ScreenCollectParams(BaseModel):
    """Параметры для снятия скриншота."""
    monitor: int = 1
    include_cursor: bool = False  # Placeholder - пока не поддерживается


class ScreenRecordParams(BaseModel):
    """Параметры записи экрана (этап 5, раздел H плана)."""
    duration_sec: int = Field(ge=1, le=300, description="Длительность записи 1–300 сек")
    fps: int = Field(default=15, ge=5, le=30)
    max_width: int = Field(default=1920, ge=640, le=3840)
    quality_crf: int = Field(default=28, ge=18, le=40)
    monitor: int = Field(default=1)


class ScreenCollector(BaseCollector):
    """
    Коллектор для снятия скриншотов экрана.
    
    Использует:
    - mss для захвата экрана (самая быстрая кроссплатформенная библиотека)
    - Artifact pipeline для обработки файлов
    
    Особенности:
    - Захватывает все мониторы в один файл (mon=-1)
    - Сохраняет временные файлы в data_dir/temp/
    - Возвращает артефакты через _artifacts в observations
    - Orchestrator обрабатывает загрузку и очистку файлов
    """
    
    def __init__(self):
        """Инициализация коллектора скриншотов."""
        super().__init__()
        
        # Создаем экземпляр mss для захвата экрана
        self.sct = mss.mss()
        
        # Определяем директорию для временных файлов
        self.temp_dir = Path(get_config().paths.data_dir) / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"[{self.name}] ScreenCollector инициализирован")
        logger.debug(f"[{self.name}] Временная директория: {self.temp_dir}")
    
    @property
    def name(self) -> str:
        """Возвращает уникальное имя модуля."""
        return "screen"
    
    @exposed_tool(
        name="collect",
        description="Capture screenshot of the screen",
        risk_level="sensitive_read",
        params_model=ScreenCollectParams,
        presets=[
            {
                "id": "primary_monitor",
                "name": "Основной монитор",
                "description": "Снимок основного монитора (обычно первого)",
                "params": {"monitor": 1, "include_cursor": False}
            },
            {
                "id": "all_monitors",
                "name": "Все мониторы",
                "description": "Снимок всех подключенных мониторов в один файл",
                "params": {"monitor": -1, "include_cursor": False}
            },
            {
                "id": "secondary_monitor",
                "name": "Второй монитор",
                "description": "Снимок второго монитора (если подключен)",
                "params": {"monitor": 2, "include_cursor": False}
            }
        ],
        metadata_risk_level="sensitive_read",
        metadata_scopes=["screen"],
        metadata_requires_consent=False,
        metadata_allow_roles=["user", "agent", "llm", "support", "admin"],
    )
    async def collect(self, monitor: int = 1, include_cursor: bool = False) -> Dict[str, Any]:
        """
        Асинхронный сбор данных - снятие скриншота.
        
        Args:
            monitor: Номер монитора для захвата (по умолчанию 1). 
                    Используйте -1 для захвата всех мониторов в один файл.
            include_cursor: Включать ли курсор в скриншот (placeholder, пока не поддерживается)
        
        Процесс:
        1. Генерирует имя временного файла с timestamp
        2. Захватывает указанный монитор через mss
        3. Возвращает observations с артефактом и метаданными
        
        Returns:
            Dict[str, Any]: Словарь с информацией о скриншоте
            {
                "resolution": "WxH",
                "captured_at_epoch": <int>,
                "_artifacts": [
                    {
                        "kind": "screenshot",
                        "local_path": "<абсолютный/относительный путь>",
                        "name": "screenshot_<ts>.png",
                        "mime": "image/png"
                    }
                ],
                "_cleanup_paths": ["<путь к файлу>"]
            }
        
        Raises:
            mss.ScreenShotError: Ошибка захвата экрана
            FileNotFoundError: Временный файл не был создан
            Exception: Другие неожиданные ошибки
        """
        logger.debug(f"[{self.name}] Начинаю снятие скриншота (monitor={monitor}, include_cursor={include_cursor})")
        
        # Генерируем имя файла с timestamp
        timestamp = int(time.time())
        temp_path = self.temp_dir / f"screenshot_{timestamp}.png"
        
        try:
            # ЗАХВАТ ЭКРАНА
            # monitor=-1 означает захват всех мониторов в один файл
            # monitor=1, 2, 3... означает захват конкретного монитора
            logger.debug(f"[{self.name}] Захватываю экран (monitor={monitor})...")
            
            # sct.shot() захватывает экран и сохраняет в файл
            screenshot_path = self.sct.shot(mon=monitor, output=str(temp_path))
            
            logger.success(f"[{self.name}] Скриншот сохранен: {screenshot_path}")
            
            # Получаем информацию о разрешении
            # Если monitor=-1, используем последний монитор (все мониторы)
            # Иначе используем указанный монитор
            if monitor == -1:
                monitor_info = self.sct.monitors[-1]  # -1 = все мониторы
            else:
                # monitor=0 это все мониторы, monitor=1,2,3... это конкретные мониторы
                # В mss индексация: monitors[0] = все, monitors[1] = первый, monitors[2] = второй и т.д.
                if monitor == 0:
                    monitor_info = self.sct.monitors[0]
                else:
                    # Для monitor=1 используем monitors[1], для monitor=2 используем monitors[2] и т.д.
                    if monitor < len(self.sct.monitors):
                        monitor_info = self.sct.monitors[monitor]
                    else:
                        # Fallback на первый доступный монитор
                        logger.warning(f"Монитор {monitor} не найден, используем монитор 1")
                        monitor_info = self.sct.monitors[1] if len(self.sct.monitors) > 1 else self.sct.monitors[0]
            
            resolution = f"{monitor_info['width']}x{monitor_info['height']}"
            
            logger.debug(f"[{self.name}] Разрешение: {resolution}")
            
            # Формируем абсолютный путь для артефакта
            absolute_path = temp_path.resolve()
            
            # Формируем observations с артефактом
            observations = {
                "resolution": resolution,
                "captured_at_epoch": timestamp,
                "_artifacts": [
                    {
                        "kind": "screenshot",
                        "local_path": str(absolute_path),
                        "name": f"screenshot_{timestamp}.png",
                        "mime": "image/png"
                    }
                ],
                "_cleanup_paths": [str(absolute_path)]
            }
            
            logger.success(f"[{self.name}] Скриншот готов для обработки через artifact pipeline")
            return observations
        
        except mss.ScreenShotError as e:
            # Специфичная ошибка mss (нет дисплея, серверная винда и т.д.)
            logger.error(f"[{self.name}] Ошибка захвата экрана: {e}")
            # Удаляем файл, если он был создан, но произошла ошибка
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise
        
        except FileNotFoundError as e:
            # Ошибка, если временный файл не был создан
            logger.error(f"[{self.name}] Файл не найден: {e}")
            raise
        
        except Exception as e:
            # Любые другие ошибки
            logger.error(f"[{self.name}] Неожиданная ошибка: {e}", exc_info=True)
            # Удаляем файл, если он был создан, но произошла ошибка
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise

    @exposed_tool(
        name="record",
        description="Record screen to MP4 video (1–300 sec, up to 200MB)",
        risk_level="sensitive_read",
        params_model=ScreenRecordParams,
        presets=[
            {"id": "short", "name": "30 сек", "description": "Короткая запись 30 сек", "params": {"duration_sec": 30}},
            {"id": "long", "name": "5 мин", "description": "Длинная запись 5 мин", "params": {"duration_sec": 300}},
        ],
        metadata_risk_level="sensitive_read",
        metadata_scopes=["screen"],
        metadata_requires_consent=False,
        metadata_allow_roles=["user", "agent", "llm", "support", "admin"],
    )
    async def record(
        self,
        duration_sec: int = 300,
        fps: int = 15,
        max_width: int = 1920,
        quality_crf: int = 28,
        monitor: int = 1,
        operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Запись экрана в MP4 (этап 5, раздел H плана).
        
        Использует mss для захвата кадров и ffmpeg для кодирования. Поддерживает
        досрочную остановку через STOP-кнопку (RecordingController по operation_id).
        """
        ffmpeg_path = _get_ffmpeg_path()
        if not ffmpeg_path:
            raise RuntimeError(
                "ffmpeg не найден. Установите: системный ffmpeg (apt install ffmpeg / brew install ffmpeg) "
                "или pip install imageio-ffmpeg (бинарник в пакете)."
            )
        stop_event = get_recording_controller().get(operation_id) if operation_id else None
        timestamp = int(time.time())
        temp_path = self.temp_dir / f"recording_{timestamp}.mp4"
        try:
            result = await asyncio.to_thread(
                _record_sync,
                ffmpeg_path,
                monitor,
                fps,
                duration_sec,
                max_width,
                quality_crf,
                SIZE_LIMIT_BYTES,
                str(temp_path),
                stop_event,
            )
            if result.get("error"):
                raise RuntimeError(result["error"])
            frames_captured = result.get("frames_captured", 0)
            logger.success(f"[{self.name}] Запись завершена: {frames_captured} кадров, {temp_path}")
            absolute_path = temp_path.resolve()
            observations = {
                "frames_captured": frames_captured,
                "duration_sec": result.get("duration_actual_sec", 0),
                "file_size_bytes": absolute_path.stat().st_size,
                "_artifacts": [
                    {
                        "kind": "screen_recording",
                        "local_path": str(absolute_path),
                        "name": f"recording_{timestamp}.mp4",
                        "mime": "video/mp4",
                    }
                ],
                "_cleanup_paths": [str(absolute_path)],
            }
            return observations
        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise


def _record_sync(
    ffmpeg_path: str,
    monitor: int,
    fps: int,
    duration_sec: int,
    max_width: int,
    quality_crf: int,
    size_limit_bytes: int,
    output_path: str,
    stop_event: Optional[object],
) -> Dict[str, Any]:
    """
    Синхронная запись экрана: захват кадров mss + кодирование ffmpeg через pipe.
    Вызывается из asyncio.to_thread. MSS создаётся внутри потока (на Linux X11 display
    в thread-local, иначе '_thread._local' object has no attribute 'display').
    """
    import time as time_mod
    max_frames = fps * duration_sec
    # MSS создаём в этом же потоке: на Linux привязка к X11 display thread-local
    with mss.mss() as sct:
        mon_idx = 0 if monitor <= 0 else monitor
        if mon_idx >= len(sct.monitors):
            mon_idx = 1
        img = sct.grab(sct.monitors[mon_idx])
        w, h = img.width, img.height
        if w > max_width:
            scale = f"scale={max_width}:-2"
        else:
            scale = "copy"
        cmd = [
            ffmpeg_path, "-y",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{w}x{h}", "-r", str(fps),
            "-i", "pipe:0",
            "-vf", scale,
            "-c:v", "libx264", "-crf", str(quality_crf),
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        frames_captured = 0
        start = time_mod.time()
        try:
            for i in range(max_frames):
                if stop_event is not None and getattr(stop_event, "is_set", lambda: False) and stop_event.is_set():
                    break
                try:
                    img = sct.grab(sct.monitors[mon_idx])
                    proc.stdin.write(img.raw)
                    frames_captured += 1
                except BrokenPipeError:
                    break
                if frames_captured % (fps * 5) == 0 and frames_captured > 0:
                    if os.path.exists(output_path) and os.path.getsize(output_path) >= size_limit_bytes:
                        break
                time_mod.sleep(1.0 / fps)
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.wait(timeout=30)
    duration_actual = time_mod.time() - start
    if os.path.exists(output_path) and os.path.getsize(output_path) > size_limit_bytes:
        logger.warning(f"[screen] Размер записи превысил лимит {size_limit_bytes // (1024*1024)} MB")
    return {
        "frames_captured": frames_captured,
        "duration_actual_sec": round(duration_actual, 1),
        "error": None,
    }