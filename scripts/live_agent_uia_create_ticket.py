#!/usr/bin/env python
"""Drive the local Maria Agent create-ticket wizard through Microsoft UIA.

The script intentionally uses pywinauto's UIA backend and stable Qt
objectName/accessibility ids. Text input is done through Unicode clipboard
paste because pywinauto set_edit_text() corrupts Cyrillic text for the Qt
runtime used by the live agent.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import pywinauto
import win32clipboard
import win32gui
import win32process
from pywinauto import Application, keyboard


def _now_ms() -> int:
    return int(time.time() * 1000)


def _visible_windows() -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []

    def cb(hwnd: int, _arg: Any) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        windows.append(
            {
                "handle": hwnd,
                "pid": pid,
                "title": title,
                "class": win32gui.GetClassName(hwnd),
            }
        )

    win32gui.EnumWindows(cb, None)
    return windows


def _connect_window(pid: int | None, title_contains: str) -> Any:
    candidates = [
        item
        for item in _visible_windows()
        if (pid is None or item["pid"] == pid) and title_contains.casefold() in item["title"].casefold()
    ]
    if not candidates:
        raise RuntimeError(f"agent window not found: pid={pid!r} title_contains={title_contains!r}")
    hwnd = int(candidates[0]["handle"])
    app = Application(backend="uia").connect(handle=hwnd, timeout=5)
    window = app.window(handle=hwnd)
    window.set_focus()
    return window


def _deadline(seconds: float) -> int:
    return _now_ms() + int(seconds * 1000)


def _descendants_limited(root: Any, *, control_type: str | None = None, limit: int = 250) -> list[Any]:
    try:
        items = root.descendants(control_type=control_type) if control_type else root.descendants()
    except Exception:
        return []
    return list(items[:limit])


def _control_text(control: Any) -> str:
    try:
        return control.window_text() or ""
    except Exception:
        return ""


def _control_id(control: Any) -> str:
    try:
        return control.element_info.automation_id or ""
    except Exception:
        return ""


def _find(root: Any, *, auto_id_contains: str | None = None, name_contains: str | None = None, control_type: str | None = None, timeout: float = 8.0) -> Any:
    end = _deadline(timeout)
    while _now_ms() < end:
        for item in _descendants_limited(root, control_type=control_type):
            auto_id = _control_id(item)
            name = _control_text(item)
            if auto_id_contains and auto_id_contains not in auto_id:
                continue
            if name_contains and name_contains.casefold() not in name.casefold():
                continue
            return item
        time.sleep(0.2)
    raise RuntimeError(f"control not found: auto_id_contains={auto_id_contains!r} name_contains={name_contains!r} control_type={control_type!r}")


def _invoke(control: Any) -> None:
    try:
        control.invoke()
    except Exception:
        control.set_focus()
        keyboard.send_keys("{ENTER}")


def _clipboard_get() -> str:
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        return ""
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def _clipboard_set(value: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, value)
    finally:
        win32clipboard.CloseClipboard()


def _paste_text(control: Any, value: str) -> str:
    previous = _clipboard_get()
    try:
        control.set_focus()
        keyboard.send_keys("^a{BACKSPACE}")
        _clipboard_set(value)
        keyboard.send_keys("^v")
        time.sleep(0.2)
    finally:
        _clipboard_set(previous)
    actual = _control_text(control)
    if actual and value not in actual:
        raise RuntimeError(f"text verification failed: expected substring {value!r}, actual {actual!r}")
    return actual or value


def _set_value_pattern_text(control: Any, value: str) -> str:
    try:
        control.iface_value.SetValue(value)
    except Exception:
        return _paste_text(control, value)
    time.sleep(0.2)
    return _control_text(control) or value


def _select_first_nonempty_combo(control: Any) -> str:
    control.set_focus()
    before = _control_text(control)
    try:
        control.select(1)
    except Exception:
        keyboard.send_keys("{HOME}{DOWN}{ENTER}")
    time.sleep(0.2)
    after = _control_text(control)
    if after == before or not after or "Выберите" in after:
        control.set_focus()
        keyboard.send_keys("%{DOWN}{DOWN}{ENTER}")
        time.sleep(0.2)
        after = _control_text(control)
    return after


def _dump_tree(root: Any, *, limit: int = 90) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in _descendants_limited(root, limit=limit):
        result.append(
            {
                "type": getattr(item.element_info, "control_type", ""),
                "name": _control_text(item)[:160],
                "automation_id": _control_id(item),
            }
        )
    return result


def _read_status(port: int) -> dict[str, Any]:
    with urlopen(f"http://127.0.0.1:{port}/ui/automation/status", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def run(args: argparse.Namespace) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "pywinauto_version": pywinauto.__version__,
        "backend": "uia",
        "actions": [],
    }
    if pywinauto.__version__ != "0.6.9":
        raise RuntimeError(f"pywinauto 0.6.9 required, got {pywinauto.__version__}")

    window = _connect_window(args.pid, args.window_title)
    evidence["window_title"] = _control_text(window)

    create_btn = _find(window, auto_id_contains="SidebarCreateButton", control_type="Button", timeout=6)
    evidence["actions"].append({"action": "invoke_create", "name": _control_text(create_btn), "automation_id": _control_id(create_btn)})
    _invoke(create_btn)
    time.sleep(2.0)

    wizard = _find(window, auto_id_contains="TicketCreateWizardRoot", timeout=8)
    evidence["wizard_root"] = {"name": _control_text(wizard), "automation_id": _control_id(wizard)}

    cards = [
        item
        for item in _descendants_limited(window, control_type="Button", limit=220)
        if "TicketTypeCard" in _control_id(item)
    ]
    evidence["ticket_type_cards"] = [{"name": _control_text(item), "automation_id": _control_id(item)} for item in cards[:8]]
    if cards:
        target = next((item for item in cards if args.template.casefold() in _control_text(item).casefold()), cards[0])
        _invoke(target)
        evidence["actions"].append({"action": "select_template_card", "name": _control_text(target), "automation_id": _control_id(target)})
        time.sleep(0.8)

    next_btn = _find(window, auto_id_contains="TicketCreateNextButton", control_type="Button", timeout=5)
    _invoke(next_btn)
    evidence["actions"].append({"action": "next_to_description", "automation_id": _control_id(next_btn)})
    time.sleep(0.8)

    description = _find(window, auto_id_contains="TicketCreateDescriptionInput", timeout=8)
    _clipboard_set(args.description)
    try:
        paste_description = _find(window, auto_id_contains="TicketCreatePasteDescriptionButton", control_type="Button", timeout=2)
        _invoke(paste_description)
        actual_description = args.description
        evidence["actions"].append({"action": "invoke_paste_description", "automation_id": _control_id(paste_description)})
    except Exception:
        actual_description = _paste_text(description, args.description)
    evidence["actions"].append({"action": "paste_description", "value": actual_description})

    for item in _descendants_limited(window, limit=220):
        auto_id = _control_id(item)
        ctype = getattr(item.element_info, "control_type", "")
        if "DynamicFieldInput_" not in auto_id:
            continue
        if ctype == "ComboBox":
            selected = _select_first_nonempty_combo(item)
            evidence["actions"].append({"action": "select_dynamic_combo", "automation_id": auto_id, "selected": selected})
        elif ctype in {"Edit", "Document"} and not _control_text(item).strip():
            actual = _set_value_pattern_text(item, args.field_text)
            evidence["actions"].append({"action": "paste_dynamic_text", "automation_id": auto_id, "value": actual})

    _invoke(next_btn)
    evidence["actions"].append({"action": "next_to_confirmation", "automation_id": _control_id(next_btn)})
    time.sleep(1.0)

    window.set_focus()
    keyboard.send_keys("^+f")
    evidence["actions"].append({"action": "autofill_required_selects_shortcut_ctrl_shift_f"})
    time.sleep(0.5)
    try:
        autofill_btn = _find(window, auto_id_contains="TicketCreatePriorityAutofillButton", control_type="Button", timeout=2)
        _invoke(autofill_btn)
        evidence["actions"].append(
            {"action": "invoke_required_selects_autofill", "automation_id": _control_id(autofill_btn)}
        )
        time.sleep(0.5)
    except Exception as exc:
        evidence["actions"].append({"action": "required_selects_autofill_missing", "error": str(exc)})

    for auto_id_part, value in (
        ("TicketCreateImpactScopeSelect", ""),
        ("DynamicFieldInput_impact_scope", ""),
        ("TicketCreateWorkContinuitySelect", ""),
        ("DynamicFieldInput_work_continuity", ""),
        ("TicketCreateBusinessImportanceSelect", ""),
        ("DynamicFieldInput_business_importance", ""),
        ("TicketCreateUrgencyReasonInput", args.urgency_reason),
        ("TicketCreateImportanceReasonInput", args.importance_reason),
    ):
        try:
            control = _find(window, auto_id_contains=auto_id_part, timeout=1.2)
        except Exception:
            continue
        ctype = getattr(control.element_info, "control_type", "")
        if ctype == "ComboBox":
            selected = _select_first_nonempty_combo(control)
            evidence["actions"].append({"action": "select_priority_combo", "automation_id": _control_id(control), "selected": selected})
        elif value:
            actual = _set_value_pattern_text(control, value)
            evidence["actions"].append({"action": "paste_priority_text", "automation_id": _control_id(control), "value": actual})

    submit = _find(window, auto_id_contains="TicketCreateSubmitButton", control_type="Button", timeout=5)
    evidence["submit"] = {"name": _control_text(submit), "automation_id": _control_id(submit)}
    submit.set_focus()
    keyboard.send_keys("^({ENTER})")
    evidence["actions"].append({"action": "submit_shortcut_ctrl_enter"})
    time.sleep(0.8)
    keyboard.send_keys("{ENTER}")
    evidence["actions"].append({"action": "confirm_default_button_enter"})
    time.sleep(0.8)

    try:
        confirm = _find(window, name_contains="Подтверждаю", control_type="Button", timeout=4)
        evidence["confirm_dialog"] = {"name": _control_text(confirm), "automation_id": _control_id(confirm)}
        _invoke(confirm)
        evidence["actions"].append({"action": "confirm_submit"})
    except Exception as exc:
        evidence["confirm_dialog"] = {"missing": str(exc)}

    end = _deadline(20)
    success_texts: list[str] = []
    while _now_ms() < end:
        success_texts = [
            _control_text(item)
            for item in _descendants_limited(window, control_type="Text", limit=180)
            if _control_text(item).strip()
        ]
        if any("T-" in text for text in success_texts) or any("создан" in text.casefold() for text in success_texts):
            break
        time.sleep(0.5)
    evidence["visible_texts"] = success_texts[:80]
    evidence["status"] = _read_status(args.ui_port)

    if args.screenshot:
        image = window.capture_as_image()
        Path(args.screenshot).parent.mkdir(parents=True, exist_ok=True)
        image.save(args.screenshot)
        evidence["screenshot"] = str(Path(args.screenshot).resolve())

    evidence["control_tree_excerpt"] = _dump_tree(window)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", default="live-v3-deep")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--window-title", default="Maria Agent")
    parser.add_argument("--ui-port", type=int, default=8765)
    parser.add_argument("--title", default="Live V3 BUG03 UIA create")
    parser.add_argument("--description", required=True)
    parser.add_argument("--template", default="")
    parser.add_argument("--field-text", default="UIA field value")
    parser.add_argument("--urgency-reason", default="UIA urgency reason")
    parser.add_argument("--importance-reason", default="Live V3 BUG03 regression")
    parser.add_argument("--screenshot", default="artifacts/live-v3-bug03-uia-create.png")
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    evidence = run(args)
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "output_json": str(output), "ticket_id": evidence.get("status", {}).get("active_ticket_id")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
