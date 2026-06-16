from pathlib import Path
import re


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
    "content_packs/knowledge/primary-agent-requester-guides.yaml",
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

NORMAL_UI_RAW_ID_FILES = [
    "webapp/src/pages/requester/index.tsx",
    "pc_agent/ui_gui/account_gate.py",
    "pc_agent/ui_gui/main_window.py",
]

FORBIDDEN_NORMAL_UI_RAW_ID_TERMS = (
    "affected_person_id",
    "target_device_id",
    "binding_id",
    "claim_id",
)

PA11_HELP_ARTICLES = {
    "Как создать обращение за другого сотрудника",
    "Что делать, если мой ПК не включается",
    "Как запросить смену владельца устройства",
    "Как привязать устройство к аккаунту",
}


def _string_literals(text: str) -> list[tuple[int, str, bool]]:
    pattern = re.compile(r"(?P<quote>['\"`])(?P<value>(?:\\.|(?!\1).)*?)(?P=quote)", re.DOTALL)
    literals: list[tuple[int, str, bool]] = []
    for match in pattern.finditer(text):
        before = text[max(0, match.start() - 64) : match.start()]
        line_number = text.count("\n", 0, match.start()) + 1
        is_technical_key_lookup = bool(re.search(r"(?:\.get\(|\[\s*)\s*$", before))
        literals.append((line_number, match.group("value"), is_technical_key_lookup))
    return literals


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


def test_web_first_registration_normal_ui_does_not_render_raw_ids() -> None:
    offenders: list[str] = []
    for relative_path in NORMAL_UI_RAW_ID_FILES:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for line_number, literal, is_technical_key_lookup in _string_literals(text):
            if is_technical_key_lookup:
                continue
            for term in FORBIDDEN_NORMAL_UI_RAW_ID_TERMS:
                if term in literal:
                    offenders.append(f"{relative_path}:{line_number}: user-visible string contains {term!r}")
    assert offenders == []


def test_web_first_registration_pa11_help_articles_are_present() -> None:
    text = (ROOT / "content_packs/knowledge/primary-agent-requester-guides.yaml").read_text(encoding="utf-8")
    missing = [title for title in sorted(PA11_HELP_ARTICLES) if title not in text]
    forbidden = [term for term in FORBIDDEN_NORMAL_UI_RAW_ID_TERMS if term in text]
    assert missing == []
    assert forbidden == []
