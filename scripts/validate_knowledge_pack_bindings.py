from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"
for path in (str(REPO_ROOT), str(SERVER_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from tickets.service_catalog_defaults import (  # noqa: E402
    DEFAULT_SERVICE_CATALOG_OFFERINGS,
    DEFAULT_SERVICE_CATALOG_SERVICES,
    FALLBACK_FULL_CODE,
    FALLBACK_SERVICE_CODE,
    FALLBACK_TEMPLATE_KEY,
)


PACK_DIR = REPO_ROOT / "content_packs" / "knowledge"
OBSOLETE_TEMPLATE_KEYS = {"password_reset", "laptop_issue", "printer_issue", "other_unknown", "vpn_issue"}
OBSOLETE_SERVICE_CODES = {"communications"}
OBSOLETE_OFFERING_CODES = {
    "communications.mail_issue",
    "access.password_reset",
    "workplace.laptop_issue",
}


@dataclass(frozen=True)
class CatalogOffering:
    service_code: str
    offering_code: str
    request_template_key: str


@dataclass(frozen=True)
class CatalogBaseline:
    services: set[str]
    offerings: dict[str, CatalogOffering]
    templates: set[str]


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    source: str
    slug: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "source": self.source,
            "slug": self.slug,
            "path": self.path,
            "message": self.message,
        }


def build_catalog_baseline() -> CatalogBaseline:
    services = {str(item["code"]) for item in DEFAULT_SERVICE_CATALOG_SERVICES}
    offerings: dict[str, CatalogOffering] = {}
    templates: set[str] = set()
    for item in DEFAULT_SERVICE_CATALOG_OFFERINGS:
        service_code = str(item["service_code"])
        full_code = f"{service_code}.{item['code']}"
        template_key = str(item["request_template_key"])
        offerings[full_code] = CatalogOffering(
            service_code=service_code,
            offering_code=full_code,
            request_template_key=template_key,
        )
        templates.add(template_key)
    return CatalogBaseline(services=services, offerings=offerings, templates=templates)


def _issue(
    issues: list[ValidationIssue],
    *,
    severity: str,
    code: str,
    source: str,
    slug: str,
    path: str,
    message: str,
) -> None:
    issues.append(ValidationIssue(severity, code, source, slug, path, message))


def validate_pack_file(path: str | Path, *, baseline: CatalogBaseline | None = None, strict: bool = False) -> list[ValidationIssue]:
    source = str(path)
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return validate_pack_payload(payload, baseline=baseline or build_catalog_baseline(), source=source, strict=strict)


def validate_pack_payload(
    payload: Any,
    *,
    baseline: CatalogBaseline | None = None,
    source: str,
    strict: bool = False,
) -> list[ValidationIssue]:
    baseline = baseline or build_catalog_baseline()
    issues: list[ValidationIssue] = []
    if not isinstance(payload, dict):
        return [
            ValidationIssue(
                "error",
                "invalid_pack",
                source,
                "",
                "",
                "content pack must be a YAML object",
            )
        ]
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    for item_index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or item.get("title") or f"item[{item_index}]")
        bindings = item.get("bindings") if isinstance(item.get("bindings"), list) else []
        for binding_index, binding in enumerate(bindings):
            if not isinstance(binding, dict):
                continue
            path = f"items[{item_index}].bindings[{binding_index}]"
            service_code = str(binding.get("service_code") or "").strip()
            offering_code = str(binding.get("offering_code") or "").strip()
            template_key = str(binding.get("request_template_key") or "").strip()
            if service_code in OBSOLETE_SERVICE_CODES:
                _issue(
                    issues,
                    severity="error",
                    code="obsolete_service_code",
                    source=source,
                    slug=slug,
                    path=f"{path}.service_code",
                    message=f"{service_code} is obsolete; use current Service Catalog defaults",
                )
            if offering_code in OBSOLETE_OFFERING_CODES:
                _issue(
                    issues,
                    severity="error",
                    code="obsolete_offering_code",
                    source=source,
                    slug=slug,
                    path=f"{path}.offering_code",
                    message=f"{offering_code} is obsolete; use current Service Catalog defaults",
                )
            if template_key in OBSOLETE_TEMPLATE_KEYS and template_key not in baseline.templates:
                _issue(
                    issues,
                    severity="error",
                    code="obsolete_template_key",
                    source=source,
                    slug=slug,
                    path=f"{path}.request_template_key",
                    message=f"{template_key} is obsolete; use the offering request_template_key",
                )
            if service_code and service_code not in baseline.services:
                _issue(
                    issues,
                    severity="error",
                    code="unknown_service_code",
                    source=source,
                    slug=slug,
                    path=f"{path}.service_code",
                    message=f"Unknown service_code {service_code}",
                )
            if offering_code:
                offering = baseline.offerings.get(offering_code)
                if offering is None:
                    _issue(
                        issues,
                        severity="error",
                        code="unknown_offering_code",
                        source=source,
                        slug=slug,
                        path=f"{path}.offering_code",
                        message=f"Unknown offering_code {offering_code}",
                    )
                else:
                    if service_code and offering.service_code != service_code:
                        _issue(
                            issues,
                            severity="error",
                            code="service_offering_mismatch",
                            source=source,
                            slug=slug,
                            path=path,
                            message=f"{offering_code} belongs to {offering.service_code}, not {service_code}",
                        )
                    if template_key and offering.request_template_key != template_key:
                        _issue(
                            issues,
                            severity="error",
                            code="template_mismatch",
                            source=source,
                            slug=slug,
                            path=f"{path}.request_template_key",
                            message=f"{offering_code} uses request_template_key={offering.request_template_key}, not {template_key}",
                        )
            if template_key and template_key not in baseline.templates:
                _issue(
                    issues,
                    severity="error" if strict else "warning",
                    code="unknown_request_template_key",
                    source=source,
                    slug=slug,
                    path=f"{path}.request_template_key",
                    message=f"Unknown request_template_key {template_key}",
                )
            if service_code == FALLBACK_SERVICE_CODE and offering_code and offering_code != FALLBACK_FULL_CODE:
                _issue(
                    issues,
                    severity="error",
                    code="fallback_mismatch",
                    source=source,
                    slug=slug,
                    path=path,
                    message=f"Fallback service must bind to {FALLBACK_FULL_CODE}/{FALLBACK_TEMPLATE_KEY}",
                )
    return issues


def _pack_paths(pack_code: str | None) -> list[Path]:
    if pack_code:
        return [path for path in (PACK_DIR / f"{pack_code}.yaml", PACK_DIR / f"{pack_code}.yml") if path.exists()]
    return sorted(PACK_DIR.glob("*.yaml"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Knowledge content-pack bindings against Service Catalog defaults.")
    parser.add_argument("--pack", help="Validate one pack code.")
    parser.add_argument("--strict", action="store_true", help="Treat unknown template warnings as errors.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    args = parser.parse_args()

    baseline = build_catalog_baseline()
    issues: list[ValidationIssue] = []
    paths = _pack_paths(args.pack)
    for path in paths:
        issues.extend(validate_pack_file(path, baseline=baseline, strict=args.strict))
    errors = [issue for issue in issues if issue.severity == "error"]
    payload = {
        "status": "error" if errors else "ok",
        "checked": [str(path) for path in paths],
        "errors": len(errors),
        "warnings": len([issue for issue in issues if issue.severity == "warning"]),
        "issues": [issue.as_dict() for issue in issues],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not issues:
            print("OK: all Knowledge content-pack bindings match Service Catalog defaults.")
        else:
            for issue in issues:
                print(f"{issue.severity.upper()}: {issue.source} {issue.slug} {issue.path}: {issue.message}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
