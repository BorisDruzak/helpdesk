"""
Cross-platform single-instance lock based on an OS file lock.
При падении/убийстве процесса lock освобождается ядром, но файл может остаться.
Если acquire не удался, проверяем PID в файле: если процесс мёртв — удаляем lock и повторяем попытку.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, TextIO
import os


def _is_process_alive(pid: int) -> bool:
    """Проверка, что процесс с данным PID ещё существует."""
    try:
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if h:
                kernel32.CloseHandle(h)
                return True
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, AttributeError):
        return False


class SingleInstanceLock:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = Path(lock_path)
        self._fh: Optional[TextIO] = None

    def _try_acquire(self) -> bool:
        """Одна попытка захвата lock. При неудаче _fh уже открыт — caller должен закрыть."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.lock_path.open("a+", encoding="utf-8")
        try:
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False

        self._fh.seek(0)
        self._fh.truncate(0)
        self._fh.write(str(os.getpid()))
        self._fh.flush()
        return True

    def acquire(self) -> bool:
        if self._try_acquire():
            return True
        self._close_handle()

        # Не удалось захватить — возможно, зависший lock от мёртвого процесса
        if not self.lock_path.exists():
            if self._try_acquire():
                return True
            self._close_handle()
            return False

        try:
            pid_str = self.lock_path.read_text(encoding="utf-8").strip()
            pid = int(pid_str)
        except (OSError, ValueError):
            try:
                self.lock_path.unlink()
            except OSError:
                pass
            if self._try_acquire():
                return True
            self._close_handle()
            return False

        if _is_process_alive(pid):
            return False  # Действительно другой живой процесс

        try:
            self.lock_path.unlink()
        except OSError:
            pass
        if self._try_acquire():
            return True
        self._close_handle()
        return False

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self._close_handle()

    def _close_handle(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

    def __enter__(self) -> "SingleInstanceLock":
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lock: {self.lock_path}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

