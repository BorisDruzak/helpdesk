"""Low-overhead Qt GUI performance probe for field diagnostics."""

from __future__ import annotations

from collections import Counter
import os
import threading
import time
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, QEvent, QTimer
from PySide6.QtWidgets import QApplication, QWidget

try:
    import psutil
except Exception:  # pragma: no cover - optional in source tests, packaged in release
    psutil = None


def gui_performance_probe_enabled() -> bool:
    raw = os.environ.get("PC_AGENT_GUI_PROFILER", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def gui_performance_probe_interval_ms() -> int:
    raw = os.environ.get("PC_AGENT_GUI_PROFILER_INTERVAL_MS", "").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 5000
    return max(1000, min(value, 60000))


def _event_type_name(event_type: int) -> str:
    try:
        return QEvent.Type(event_type).name
    except Exception:
        return str(event_type)


def _widget_label(obj: Any) -> str:
    if obj is None:
        return "-"
    class_name = type(obj).__name__
    object_name = ""
    try:
        object_name = str(obj.objectName() or "").strip()
    except Exception:
        object_name = ""
    return f"{class_name}#{object_name}" if object_name else class_name


def _format_counter(counter: Counter[Any], *, limit: int = 10, event_names: bool = False) -> str:
    parts: list[str] = []
    for key, count in counter.most_common(limit):
        label = _event_type_name(int(key)) if event_names else str(key)
        parts.append(f"{label}:{count}")
    return ",".join(parts) if parts else "-"


class GuiPerformanceProbe(QObject):
    """Counts Qt events and process CPU periodically without blocking the GUI."""

    _HOT_EVENT_TYPES = frozenset(
        int(event_type)
        for event_type in (
            QEvent.Type.Paint,
            QEvent.Type.UpdateRequest,
            QEvent.Type.Timer,
            QEvent.Type.MouseMove,
            QEvent.Type.HoverMove,
            QEvent.Type.Enter,
            QEvent.Type.Leave,
            QEvent.Type.LayoutRequest,
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.PolishRequest,
            QEvent.Type.StyleChange,
            QEvent.Type.DynamicPropertyChange,
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
            QEvent.Type.WindowActivate,
            QEvent.Type.WindowDeactivate,
            QEvent.Type.ActivationChange,
            QEvent.Type.CursorChange,
        )
    )

    def __init__(self, app: QApplication, window: QWidget, *, interval_ms: int | None = None) -> None:
        super().__init__(app)
        self._app = app
        self._window = window
        self._interval_ms = interval_ms or gui_performance_probe_interval_ms()
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._emit_sample)
        self._event_counts: Counter[int] = Counter()
        self._receiver_counts: Counter[str] = Counter()
        self._last_total_events = 0
        self._samples = 0
        self._started = False
        self._process = psutil.Process() if psutil is not None else None
        self._last_thread_times: dict[int, float] = {}
        self._gui_thread_id = threading.get_native_id()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._app.installEventFilter(self)
        if self._process is not None:
            try:
                self._process.cpu_percent(None)
                self._last_thread_times = self._snapshot_thread_times()
            except Exception:
                self._process = None
        self._timer.start()
        logger.info(
            "[gui-profiler] started interval_ms={} enabled={} disable_with=PC_AGENT_GUI_PROFILER=0",
            self._interval_ms,
            gui_performance_probe_enabled(),
        )

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        self._timer.stop()
        try:
            self._app.removeEventFilter(self)
        except Exception:
            pass
        logger.info("[gui-profiler] stopped")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        event_type = int(event.type())
        self._event_counts[event_type] += 1
        if event_type in self._HOT_EVENT_TYPES:
            self._receiver_counts[f"{_event_type_name(event_type)}@{_widget_label(watched)}"] += 1
        return False

    def _snapshot_thread_times(self) -> dict[int, float]:
        if self._process is None:
            return {}
        result: dict[int, float] = {}
        for thread in self._process.threads():
            result[int(thread.id)] = float(thread.user_time or 0.0) + float(thread.system_time or 0.0)
        return result

    def _thread_delta_summary(self) -> str:
        if self._process is None:
            return "-"
        try:
            current = self._snapshot_thread_times()
        except Exception:
            return "-"
        deltas: list[tuple[int, float]] = []
        for thread_id, total_time in current.items():
            previous = self._last_thread_times.get(thread_id, total_time)
            delta = max(total_time - previous, 0.0)
            if delta > 0:
                deltas.append((thread_id, delta))
        self._last_thread_times = current
        deltas.sort(key=lambda item: item[1], reverse=True)
        if not deltas:
            return "-"
        return ",".join(f"{thread_id}:{delta:.3f}s" for thread_id, delta in deltas[:5])

    def _emit_sample(self) -> None:
        self._samples += 1
        total_events = sum(self._event_counts.values())
        delta_events = total_events - self._last_total_events
        self._last_total_events = total_events

        cpu_percent: float | None = None
        memory_mb: float | None = None
        threads_count: int | None = None
        if self._process is not None:
            try:
                cpu_percent = float(self._process.cpu_percent(None))
                memory_mb = float(self._process.memory_info().rss) / (1024 * 1024)
                threads_count = int(self._process.num_threads())
            except Exception:
                cpu_percent = None

        active = bool(self._window.isActiveWindow()) if self._window is not None else False
        visible = bool(self._window.isVisible()) if self._window is not None else False
        focus_widget = _widget_label(self._app.focusWidget())
        active_window = _widget_label(self._app.activeWindow())
        interval_sec = max(self._interval_ms / 1000.0, 0.001)
        events_per_sec = delta_events / interval_sec
        cpu_label = "-" if cpu_percent is None else f"{cpu_percent:.1f}"
        memory_label = "-" if memory_mb is None else f"{memory_mb:.1f}"
        threads_label = "-" if threads_count is None else str(threads_count)

        logger.info(
            "[gui-profiler] sample={} active={} visible={} cpu_percent={} rss_mb={} threads={} "
            "gui_tid={} events_delta={} events_per_sec={:.1f} focus={} active_window={} "
            "events_top={} receivers_top={} thread_cpu_top={}",
            self._samples,
            active,
            visible,
            cpu_label,
            memory_label,
            threads_label,
            self._gui_thread_id,
            delta_events,
            events_per_sec,
            focus_widget,
            active_window,
            _format_counter(self._event_counts, limit=12, event_names=True),
            _format_counter(self._receiver_counts, limit=12),
            self._thread_delta_summary(),
        )
