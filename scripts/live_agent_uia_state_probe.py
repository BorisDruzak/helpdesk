#!/usr/bin/env python3
"""Probe the local agent GUI semantic UIA state.

Test-only diagnostic. It connects to the real Windows GUI with
pywinauto==0.6.9 and backend="uia"; it does not use screenshots, OCR, or
coordinate clicks as pass criteria.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parent.parent
INSTANCE_ROOT = WORKSPACE / ".local-agent" / "instances"
SECRET_RE = re.compile(r"(authorization|cookie|session[_-]?token|token)\s*[:=]\s*[^;\s]+", re.IGNORECASE)
AGENT_WINDOW_TITLE_RE = ".*(Maria Agent|Авторизация).*"


def _redact(value: object) -> str:
    return SECRET_RE.sub(lambda m: f"{m.group(1)}=<redacted>", str(value or ""))


def _load_instance(instance: str | None) -> dict[str, Any] | None:
    if not instance:
        return None
    path = INSTANCE_ROOT / instance / "instance.json"
    if not path.exists():
        raise SystemExit(f"Unknown local agent instance: {instance}")
    return json.loads(path.read_text(encoding="utf-8"))


def _process_command_line(pid: int) -> str:
    command = (
        f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId = {int(pid)}\"; "
        "if ($null -eq $p) { exit 1 }; "
        "$p.CommandLine"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _redact(result.stdout.strip()) if result.returncode == 0 else ""


def _related_process_ids(root_pid: int | None) -> set[int]:
    if not root_pid:
        return set()
    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId, ParentProcessId | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return {int(root_pid)}
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return {int(root_pid)}
    rows = payload if isinstance(payload, list) else [payload]
    children_by_parent: dict[int, list[int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            pid = int(row.get("ProcessId") or 0)
            parent = int(row.get("ParentProcessId") or 0)
        except (TypeError, ValueError):
            continue
        if pid > 0:
            children_by_parent.setdefault(parent, []).append(pid)
    related = {int(root_pid)}
    queue = [int(root_pid)]
    while queue:
        parent = queue.pop(0)
        for child in children_by_parent.get(parent, []):
            if child not in related:
                related.add(child)
                queue.append(child)
    return related


def _help_text(wrapper: Any) -> str:
    try:
        return _redact(wrapper.iface_element.CurrentHelpText)
    except Exception:
        return ""


def _control_record(wrapper: Any, depth: int) -> dict[str, Any]:
    info = getattr(wrapper, "element_info", None)
    try:
        rect = wrapper.rectangle()
        rectangle = {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
        }
    except Exception:
        rectangle = None
    return {
        "depth": depth,
        "automation_id": _redact(getattr(info, "automation_id", "") if info else ""),
        "name": _redact(getattr(info, "name", "") if info else ""),
        "control_type": _redact(getattr(info, "control_type", "") if info else ""),
        "class_name": _redact(getattr(info, "class_name", "") if info else ""),
        "help_text": _help_text(wrapper),
        "rectangle": rectangle,
    }


def _walk_bounded(root: Any, *, max_depth: int, max_nodes: int, max_seconds: float) -> list[dict[str, Any]]:
    started = time.monotonic()
    records: list[dict[str, Any]] = []
    queue: list[tuple[Any, int]] = [(root, 0)]
    while queue and len(records) < max_nodes:
        if time.monotonic() - started > max_seconds:
            records.append({"depth": 0, "name": "uia_walk_timeout", "control_type": "diagnostic"})
            break
        wrapper, depth = queue.pop(0)
        records.append(_control_record(wrapper, depth))
        if depth >= max_depth:
            continue
        try:
            children = wrapper.children()
        except Exception:
            children = []
        for child in children[:80]:
            queue.append((child, depth + 1))
    return records


def _text_blob(record: dict[str, Any]) -> str:
    return " ".join(
        str(record.get(key) or "")
        for key in ("automation_id", "name", "help_text", "control_type", "class_name")
    )


def _find_records(records: list[dict[str, Any]], needle: str) -> list[dict[str, Any]]:
    needle_lower = needle.lower()
    return [record for record in records if needle_lower in _text_blob(record).lower()]


def _extract_field(records: list[dict[str, Any]], key: str) -> str | None:
    pattern = re.compile(rf"\b{re.escape(key)}=([^;]+)")
    for record in records:
        match = pattern.search(_text_blob(record))
        if match:
            return _redact(match.group(1).strip())
    return None


def _window_kind(title: str) -> str:
    if "Maria Agent" in title:
        return "main"
    if "Авторизация" in title:
        return "auth"
    return "unknown"


def _connect_window(pid: int | None, *, instance_payload: dict[str, Any] | None = None):
    import pywinauto
    from pywinauto import Application, Desktop

    if pywinauto.__version__ != "0.6.9":
        raise SystemExit(f"Expected pywinauto 0.6.9, got {pywinauto.__version__}")
    related_pids = _related_process_ids(pid)
    if instance_payload:
        data_dir = str(instance_payload.get("data_dir") or "")
        instance_pid = int(instance_payload.get("pid") or 0)
        related_pids = _related_process_ids(instance_pid)
        desktop = Desktop(backend="uia")
        windows = desktop.windows(title_re=AGENT_WINDOW_TITLE_RE, visible_only=True)
        for candidate in windows:
            try:
                candidate_pid = int(candidate.process_id())
            except Exception:
                candidate_pid = 0
            command_line = _process_command_line(candidate_pid)
            if candidate_pid in related_pids or (data_dir and data_dir.lower() in command_line.lower()):
                app = Application(backend="uia").connect(process=candidate_pid)
                return pywinauto.__version__, app, candidate
        if windows:
            candidate = windows[0]
            app = Application(backend="uia").connect(process=int(candidate.process_id()))
            return pywinauto.__version__, app, candidate
    if pid:
        candidates = [
            candidate
            for candidate in Desktop(backend="uia").windows(title_re=AGENT_WINDOW_TITLE_RE, visible_only=True)
            if int(candidate.process_id()) in related_pids
        ]
        for candidate in candidates:
            title = str(candidate.window_text() or "")
            if _window_kind(title) in {"main", "auth"}:
                app = Application(backend="uia").connect(process=int(candidate.process_id()))
                return pywinauto.__version__, app, candidate
        raise SystemExit(f"Maria Agent/Auth window not found for pid={pid}")
    desktop = Desktop(backend="uia")
    windows = desktop.windows(title_re=AGENT_WINDOW_TITLE_RE, visible_only=True)
    if not windows:
        raise SystemExit("Maria Agent/Auth window not found")
    return pywinauto.__version__, None, windows[0]


def _capture_screenshot_worker(process_id: int, output_path: str, queue: Any) -> None:
    try:
        from pywinauto import Desktop

        windows = Desktop(backend="uia").windows(title_re=AGENT_WINDOW_TITLE_RE, visible_only=True)
        target = None
        for candidate in windows:
            try:
                if int(candidate.process_id()) == int(process_id):
                    target = candidate
                    break
            except Exception:
                continue
        if target is None:
            raise RuntimeError(f"window for pid={process_id} not found")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            target.capture_as_image().save(output_path)
            queue.put(str(Path(output_path).resolve()))
            return
        except Exception as primary_exc:
            saved = _capture_window_with_native_fallbacks(target, process_id, output_path)
            if saved:
                queue.put(f"{saved} (fallback=PrintWindow, primary={type(primary_exc).__name__})")
                return
            raise primary_exc
    except Exception as exc:
        queue.put(f"capture_failed:{type(exc).__name__}:{exc}")


def _candidate_window_handles(target: Any, process_id: int) -> list[int]:
    handles: list[int] = []
    try:
        handle = int(getattr(target, "handle", 0) or getattr(getattr(target, "element_info", None), "handle", 0) or 0)
    except Exception:
        handle = 0
    if handle > 0:
        handles.append(handle)
    try:
        import win32gui

        def _collect(hwnd: int, _extra: object) -> bool:
            try:
                _thread_id, hwnd_pid = win32gui.GetWindowThreadProcessId(hwnd)
                title = str(win32gui.GetWindowText(hwnd) or "")
                if (
                    int(hwnd_pid) == int(process_id)
                    and win32gui.IsWindowVisible(hwnd)
                    and ("Maria Agent" in title or "Авторизация" in title)
                    and hwnd not in handles
                ):
                    handles.append(hwnd)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(_collect, None)
    except Exception:
        pass
    return handles


def _save_window_with_mss(rect: tuple[int, int, int, int], output_path: str) -> str | None:
    try:
        import mss
        from PIL import Image
    except Exception:
        return None
    left, top, right, bottom = rect
    width = max(1, int(right - left))
    height = max(1, int(bottom - top))
    try:
        with mss.mss() as sct:
            raw = sct.grab({"left": int(left), "top": int(top), "width": width, "height": height})
        image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return str(Path(output_path).resolve())
    except Exception:
        return None


def _save_window_with_printwindow(hwnd: int, rect: tuple[int, int, int, int], output_path: str) -> str | None:
    try:
        import win32con
        import win32gui
        import win32ui
        from PIL import Image
    except Exception:
        return None

    if hwnd <= 0:
        return None
    left, top, right, bottom = rect
    width = max(1, int(right - left))
    height = max(1, int(bottom - top))

    hwnd_dc = mfc_dc = save_dc = bitmap = None
    try:
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)
        result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
        if result != 1:
            result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0)
        if result != 1:
            return None
        info = bitmap.GetInfo()
        bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (int(info["bmWidth"]), int(info["bmHeight"])),
            bits,
            "raw",
            "BGRX",
            0,
            1,
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        return str(Path(output_path).resolve())
    except Exception:
        return None
    finally:
        if bitmap is not None:
            try:
                win32gui.DeleteObject(bitmap.GetHandle())
            except Exception:
                pass
        if save_dc is not None:
            try:
                save_dc.DeleteDC()
            except Exception:
                pass
        if mfc_dc is not None:
            try:
                mfc_dc.DeleteDC()
            except Exception:
                pass
        if hwnd_dc is not None:
            try:
                win32gui.ReleaseDC(hwnd, hwnd_dc)
            except Exception:
                pass


def _capture_window_with_native_fallbacks(target: Any, process_id: int, output_path: str) -> str | None:
    try:
        import win32gui
    except Exception:
        return None

    for hwnd in _candidate_window_handles(target, process_id):
        try:
            rect = tuple(int(value) for value in win32gui.GetWindowRect(hwnd))
        except Exception:
            continue
        if len(rect) != 4 or rect[2] <= rect[0] or rect[3] <= rect[1]:
            continue
        saved = _save_window_with_printwindow(hwnd, rect, output_path)
        if saved:
            return saved
        saved = _save_window_with_mss(rect, output_path)
        if saved:
            return saved
    return None


def _capture_screenshot_with_timeout(process_id: int, output_path: str, timeout_sec: float) -> str:
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=_capture_screenshot_worker, args=(process_id, output_path, queue))
    proc.start()
    proc.join(max(1.0, timeout_sec))
    if proc.is_alive():
        proc.terminate()
        proc.join(2)
        return "capture_timeout"
    try:
        return str(queue.get_nowait())
    except Exception:
        return "capture_failed:no_result"


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe local Maria Agent UIA semantic state")
    parser.add_argument("--instance", default=None, help="Local agent instance name from scripts/manage_local_agent.py")
    parser.add_argument("--pid", type=int, default=None, help="Agent GUI process id")
    parser.add_argument("--expect-connected", action="store_true")
    parser.add_argument("--expect-account", action="store_true")
    parser.add_argument("--expect-account-confirmed", action="store_true")
    parser.add_argument("--expect-auth-window", action="store_true")
    parser.add_argument("--expect-ticket-id", default=None)
    parser.add_argument("--expect-ticket-code", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--screenshot", default=None)
    parser.add_argument("--skip-screenshot", action="store_true", help="Do not call UIA screenshot capture")
    parser.add_argument("--screenshot-timeout-sec", type=float, default=5.0)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--max-nodes", type=int, default=500)
    parser.add_argument("--max-seconds", type=float, default=8.0)
    args = parser.parse_args()

    instance_payload = _load_instance(args.instance)
    pid = args.pid or (int(instance_payload.get("pid") or 0) if instance_payload else None)
    version, _app, window = _connect_window(args.pid, instance_payload=instance_payload if args.instance and not args.pid else None)
    try:
        process_id = int(window.process_id())
    except Exception:
        process_id = int(pid or 0)
    window_title = _redact(window.window_text())
    window_kind = _window_kind(window_title)

    records = _walk_bounded(window, max_depth=args.max_depth, max_nodes=args.max_nodes, max_seconds=args.max_seconds)
    found = {
        "agent.connection.state": _find_records(records, "agent.connection.state")[:5],
        "agent.connection.detail": _find_records(records, "agent.connection.detail")[:5],
        "agent.account.summary": _find_records(records, "agent.account.summary")[:5],
        "agent.account.mode": _find_records(records, "agent.account.mode")[:5],
        "agent.account.person": _find_records(records, "agent.account.person")[:5],
        "agent.tickets.list": _find_records(records, "agent.tickets.list")[:5],
        "agent.tickets.count": _find_records(records, "agent.tickets.count")[:5],
        "agent.ticket.active": _find_records(records, "agent.ticket.active")[:5],
    }
    connection_state = _extract_field(records, "connection_state")
    account_exists = _extract_field(records, "account_exists")
    account_mode = _extract_field(records, "account_mode")
    ticket_count = _extract_field(records, "ticket_count")
    ticket_matches: list[dict[str, Any]] = []
    if args.expect_ticket_id:
        ticket_matches.extend(_find_records(records, args.expect_ticket_id)[:5])
    if args.expect_ticket_code:
        ticket_matches.extend(_find_records(records, args.expect_ticket_code)[:5])

    screenshot_saved = None
    if not args.skip_screenshot:
        screenshot_path = args.screenshot
        if not screenshot_path:
            screenshot_path = str(Path(args.output).with_suffix(".png"))
        screenshot_saved = _capture_screenshot_with_timeout(process_id, screenshot_path, args.screenshot_timeout_sec)

    failures: list[str] = []
    if args.expect_auth_window and window_kind != "auth":
        failures.append(f"expected auth window, got {window_kind!r} title={window_title!r}")
    if args.expect_connected and connection_state != "connected":
        failures.append(f"expected connected, got {connection_state!r}")
    if args.expect_account and account_exists != "true":
        failures.append(f"expected account_exists=true, got {account_exists!r}")
    if args.expect_account_confirmed and account_mode not in {"confirmed_binding", "verified_other_account"}:
        failures.append(f"expected confirmed account, got {account_mode!r}")
    if (args.expect_ticket_id or args.expect_ticket_code) and not ticket_matches:
        failures.append("expected ticket marker not found in UIA tree")

    evidence = {
        "pywinauto_version": version,
        "backend": "uia",
        "window_title": window_title,
        "window_kind": window_kind,
        "process_id": process_id,
        "found_control_ids": found,
        "connection_state": connection_state,
        "account_exists": account_exists,
        "account_mode": account_mode,
        "ticket_count": ticket_count,
        "ticket_matches": ticket_matches,
        "tree_excerpt": records[: args.max_nodes],
        "screenshot_path": screenshot_saved,
        "failures": failures,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: evidence[k] for k in ("pywinauto_version", "backend", "window_title", "window_kind", "process_id", "connection_state", "account_exists", "account_mode", "ticket_count", "screenshot_path", "failures")}, ensure_ascii=False, indent=2))
    return 2 if failures else 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
