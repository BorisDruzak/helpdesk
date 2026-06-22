from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

TOUCHED_TEXT_FILES = [
    "PLANS.md",
    "docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md",
    "docs/QUICK_LOOKUP.md",
    "server/docs/CODEMAP.md",
    "server/docs/REGISTRY_MANAGEMENT_CENTER.md",
    "webapp/src/app/navigation.tsx",
    "webapp/src/features/requester/api.ts",
    "webapp/src/features/requester/queries.ts",
    "webapp/src/pages/requester/home-page.tsx",
    "webapp/src/pages/requester/home-page.test.tsx",
    "webapp/src/pages/requester/new-request-page.tsx",
    "webapp/src/pages/requester/new-request-workflow.tsx",
    "webapp/src/pages/requester/new-request-page.test.tsx",
    "webapp/src/pages/requester/tickets-page.tsx",
    "webapp/src/pages/requester/tickets-workflow.tsx",
    "webapp/src/pages/requester/tickets-page.test.tsx",
    "webapp/src/pages/requester/profile-page.tsx",
    "webapp/src/pages/requester/profile-workflow.ts",
    "webapp/src/pages/requester/profile-page.test.tsx",
    "webapp/src/pages/requester/devices-page.tsx",
    "webapp/src/pages/requester/devices-workflow.ts",
    "webapp/src/pages/requester/devices-page.test.tsx",
    "webapp/src/features/requester/labels.ts",
    "webapp/src/features/requester/labels.test.ts",
    "webapp/src/features/requester/consent-card.tsx",
    "webapp/src/features/requester/consent-card.test.tsx",
    "webapp/src/features/requester/dynamic-form/index.tsx",
    "webapp/src/features/requester/dynamic-form/dynamic-form.test.tsx",
    "webapp/src/features/requester/profile-runtime/index.tsx",
    "webapp/src/features/requester/profile-runtime/profile-runtime.test.tsx",
    "webapp/src/features/request-template-studio/form-field-editor.tsx",
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
    "server/tickets/service_catalog_defaults.py",
    "server/tickets/service_catalog_preview.py",
    "server/tickets/statuses.py",
    "server/tickets/requester_timeline.py",
    "server/web_api/requester_handlers.py",
    "content_packs/knowledge/it-self-service-baseline.yaml",
    "content_packs/knowledge/primary-agent-requester-guides.yaml",
]

NORMAL_UI_RAW_ID_SCAN_ROOTS = (
    "webapp/src/pages/requester",
    "webapp/src/features/requester",
    "pc_agent/ui_gui",
)

NORMAL_UI_RAW_ID_ALLOWED_SUFFIXES = (
    ".py",
    ".ts",
    ".tsx",
)

NORMAL_UI_RAW_ID_ALLOWED_PATH_PARTS = (
    ".test.",
    "/assets/",
    "/__pycache__/",
)

NORMAL_UI_RAW_ID_ALLOWED_FILES = {
    "pc_agent/ui_gui/accessibility.py",
    "pc_agent/ui_gui/automation_controller.py",
    "pc_agent/ui_gui/server_api.py",
    "webapp/src/features/requester/baseline-contract.ts",
}

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
    "webapp/src/features/admin/registry/registry-requests-tab.tsx": (
        "Блокер: {claim.conflict_reason}",
    ),
}

REVIEW_FORBIDDEN_REQUESTER_VISIBLE_SNIPPETS = {
    "webapp/src/app/navigation.tsx": (
        "Новая заявка через безопасную форму",
        "Список заявок и история переписки",
    ),
    "webapp/src/features/requester/api.ts": (
        "Requester ticket preview failed",
        "Не удалось загрузить форму заявки",
        "Не удалось создать заявку",
    ),
    "webapp/src/features/requester/dynamic-form/index.tsx": (
        "requester-visible file",
    ),
    "webapp/src/pages/requester/new-request-page.tsx": (
        "Безопасный preview",
        "Проверить заявку",
        "Каталог заявок",
        "Детали заявки",
        "Не удалось проверить заявку",
    ),
    "server/tickets/service_catalog_defaults.py": (
        "Заявка на помощь",
    ),
    "server/tickets/service_catalog_preview.py": (
        "Новая заявка",
        "После отправки заявка",
        "публичного preview",
    ),
    "server/tickets/statuses.py": (
        "Заявка принята",
        "Заявка в работе",
    ),
    "server/tickets/requester_timeline.py": (
        "Заявка принята.",
        "Заявка зарегистрирована.",
        "Код доступа к заявке сформирован.",
    ),
    "server/web_api/requester_handlers.py": (
        "Новая заявка",
        "После отправки заявка",
    ),
    "content_packs/knowledge/it-self-service-baseline.yaml": (
        "заявк",
        "Заявк",
    ),
}

FORBIDDEN_NORMAL_UI_RAW_ID_TERMS = (
    "affected_person_id",
    "target_device_id",
    "binding_id",
    "claim_id",
    "pairing_id",
    "registry person",
    "account_session_id",
    "diagnostic_target_source",
    "trace_id",
    "operation_id",
)

PHASE_A_FORBIDDEN_NORMAL_UI_RAW_ID_TERMS = {
    "affected_person_id",
    "target_device_id",
    "binding_id",
    "claim_id",
    "pairing_id",
    "registry person",
    "account_session_id",
    "diagnostic_target_source",
    "trace_id",
    "operation_id",
}

PHASE_A_ROUTE_CONTRACT_COLUMNS = {
    "Allowed roles",
    "Canonical proof surface",
    "Critical API calls",
    "Expected Observer/audit events",
    "Forbidden sensitive data",
}

PHASE_A_ROUTE_CONTRACT_ROUTES = {
    "/app/register",
    "/app/login",
    "/app/requester",
    "/app/requester/profile/setup",
    "/app/requester/profile",
    "/app/requester/devices",
    "/app/device/pair",
    "/app/device/register",
    "/app/device/login",
    "/app/admin/registry",
    "/app/tickets",
    "/app/admin/observer",
}

PA11_HELP_ARTICLES = {
    "Как создать обращение за другого сотрудника",
    "Что делать, если мой ПК не включается",
    "Как запросить смену владельца устройства",
    "Как привязать устройство к аккаунту",
    "Как заполнить профиль пользователя",
}


def _normal_ui_raw_id_files() -> tuple[str, ...]:
    files: list[str] = []
    for root in NORMAL_UI_RAW_ID_SCAN_ROOTS:
        for path in sorted((ROOT / root).rglob("*")):
            if not path.is_file() or path.suffix not in NORMAL_UI_RAW_ID_ALLOWED_SUFFIXES:
                continue
            relative_path = path.relative_to(ROOT).as_posix()
            if any(part in relative_path for part in NORMAL_UI_RAW_ID_ALLOWED_PATH_PARTS):
                continue
            if relative_path in NORMAL_UI_RAW_ID_ALLOWED_FILES:
                continue
            files.append(relative_path)
    return tuple(files)


NORMAL_UI_RAW_ID_FILES = _normal_ui_raw_id_files()


def _string_literals(text: str) -> list[tuple[int, str, bool]]:
    pattern = re.compile(r"(?P<quote>['\"`])(?P<value>(?:\\.|(?!\1).)*?)(?P=quote)", re.DOTALL)
    literals: list[tuple[int, str, bool]] = []
    for match in pattern.finditer(text):
        before = text[max(0, match.start() - 64) : match.start()]
        after = text[match.end() : match.end() + 16]
        line_number = text.count("\n", 0, match.start()) + 1
        is_technical_key_lookup = bool(re.search(r"(?:\.get\(|\.pop\(|\[\s*)\s*$", before)) or bool(
            re.match(r"\s*:", after)
        )
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


def test_requester_cabinet_review_visible_terms_are_closed() -> None:
    offenders: list[str] = []
    for relative_path, snippets in REVIEW_FORBIDDEN_REQUESTER_VISIBLE_SNIPPETS.items():
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


def test_phase_a_static_raw_id_guard_scope_is_complete() -> None:
    missing_terms = sorted(PHASE_A_FORBIDDEN_NORMAL_UI_RAW_ID_TERMS - set(FORBIDDEN_NORMAL_UI_RAW_ID_TERMS))
    assert missing_terms == []
    assert any(path.startswith("webapp/src/pages/requester/") for path in NORMAL_UI_RAW_ID_FILES)
    assert any(path.startswith("webapp/src/features/requester/") for path in NORMAL_UI_RAW_ID_FILES)
    assert any(path.startswith("pc_agent/ui_gui/") for path in NORMAL_UI_RAW_ID_FILES)


def test_phase_l_guard_tracks_split_requester_runtime_files() -> None:
    required = {
        "webapp/src/pages/requester/home-page.tsx",
        "webapp/src/pages/requester/new-request-page.tsx",
        "webapp/src/pages/requester/new-request-workflow.tsx",
        "webapp/src/pages/requester/tickets-page.tsx",
        "webapp/src/pages/requester/tickets-workflow.tsx",
        "webapp/src/pages/requester/profile-page.tsx",
        "webapp/src/pages/requester/profile-workflow.ts",
        "webapp/src/pages/requester/devices-page.tsx",
        "webapp/src/pages/requester/devices-workflow.ts",
        "webapp/src/features/requester/labels.ts",
        "webapp/src/features/requester/dynamic-form/index.tsx",
        "webapp/src/features/requester/profile-runtime/index.tsx",
    }
    assert sorted(required - set(TOUCHED_TEXT_FILES)) == []


def test_phase_a_raw_id_guard_reports_user_visible_terms_with_line_numbers() -> None:
    text = "\n".join(
        [
            'const visible = "trace_id";',
            'const technical = payload.get("trace_id");',
        ]
    )
    offenders: list[str] = []
    for line_number, literal, is_technical_key_lookup in _string_literals(text):
        if is_technical_key_lookup:
            continue
        for term in FORBIDDEN_NORMAL_UI_RAW_ID_TERMS:
            if term in literal:
                offenders.append(f"sample.tsx:{line_number}: user-visible string contains {term!r}")
    assert offenders == ["sample.tsx:1: user-visible string contains 'trace_id'"]


def test_phase_a_route_contract_map_documents_required_fields() -> None:
    text = (ROOT / "docs/WEB_FIRST_REGISTRATION_UX_CONTRACT.md").read_text(encoding="utf-8")
    missing_columns = sorted(column for column in PHASE_A_ROUTE_CONTRACT_COLUMNS if column not in text)
    missing_routes = sorted(route for route in PHASE_A_ROUTE_CONTRACT_ROUTES if f"`{route}`" not in text)
    assert missing_columns == []
    assert missing_routes == []


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([str(Path(__file__).resolve())]))
