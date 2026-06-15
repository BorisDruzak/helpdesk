from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TOUCHED_TEXT_FILES = [
    "PLANS.md",
    "docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md",
    "docs/QUICK_LOOKUP.md",
    "server/docs/CODEMAP.md",
    "server/docs/REGISTRY_MANAGEMENT_CENTER.md",
    "webapp/src/pages/requester/index.tsx",
    "webapp/src/pages/requester/index.test.tsx",
    "webapp/src/pages/device-pairing/index.tsx",
    "webapp/src/pages/device-pairing/device-pairing-page.test.tsx",
    "webapp/src/features/auth/register-page.tsx",
    "webapp/src/features/auth/register-page.test.tsx",
    "webapp/src/features/admin/registry/registry-requests-tab.tsx",
    "webapp/src/pages/admin/registry-page.test.tsx",
    "pc_agent/ui_gui/account_gate.py",
    "pc_agent/ui_gui/main_window.py",
    "pc_agent/tests/test_account_gate.py",
    "pc_agent/tests/test_main_window_runtime_windows.py",
]

MOJIBAKE_MARKERS = (
    "\ufffd",
    "Ð",
    "Â",
    "Рџ",
    "Рђ",
    "Рµ",
    "Рё",
    "Рѕ",
)

FORBIDDEN_NORMAL_UI_SNIPPETS = {
    "webapp/src/pages/requester/index.tsx": (
        "Knowledge Ask:",
        "Knowledge Ask query:",
        "Knowledge Ask context was added",
        " · agent ",
        '|| "unknown"',
        '"status unknown"',
        ' ? "online" : "offline"',
        'aria-label="Create requester ticket"',
        'aria-label="Open requester profile detail"',
        'aria-label="Open requester knowledge suggestion"',
        "Open requester device detail",
    ),
    "webapp/src/features/admin/registry/registry-requests-tab.tsx": (
        "Блокер: {claim.conflict_reason}",
    ),
}


def test_web_first_registration_touched_files_have_no_mojibake() -> None:
    offenders: list[str] = []
    for relative_path in TOUCHED_TEXT_FILES:
        path = ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        for marker in MOJIBAKE_MARKERS:
            if marker in text:
                offenders.append(f"{relative_path}: contains {marker!r}")
    assert offenders == []


def test_web_first_registration_normal_ui_uses_russian_product_labels() -> None:
    offenders: list[str] = []
    for relative_path, snippets in FORBIDDEN_NORMAL_UI_SNIPPETS.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in text:
                offenders.append(f"{relative_path}: contains {snippet!r}")
    assert offenders == []
