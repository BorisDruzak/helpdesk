#!/usr/bin/env python3
"""Report whether the new /app/* cutover is operationally ready."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_WORKSPACE = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-full-switch", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    server_root = workspace / "server"
    if str(server_root) not in sys.path:
        sys.path.insert(0, str(server_root))

    from config import (  # noqa: PLC0415
        WEBAPP_CUTOVER_ADMIN_ENABLED,
        WEBAPP_CUTOVER_LOGIN_ENABLED,
        WEBAPP_CUTOVER_SUPPORT_ENABLED,
    )
    from static_pages.cutover import build_webapp_cutover_state  # noqa: PLC0415
    from static_pages.webapp_assets import WEBAPP_DIST_DIR  # noqa: PLC0415

    state = build_webapp_cutover_state(
        dist_dir=WEBAPP_DIST_DIR,
        login_enabled=WEBAPP_CUTOVER_LOGIN_ENABLED,
        support_enabled=WEBAPP_CUTOVER_SUPPORT_ENABLED,
        admin_enabled=WEBAPP_CUTOVER_ADMIN_ENABLED,
    )
    report = {
        "workspace": str(workspace),
        "dist_dir": str(WEBAPP_DIST_DIR),
        "bundle_ready": state.bundle_ready,
        "bundle_reason": state.bundle_reason,
        "requested": {
            "login": state.login.requested,
            "support": state.support.requested,
            "admin": state.admin.requested,
        },
        "active": {
            "login": state.login.active,
            "support": state.support.active,
            "admin": state.admin.active,
        },
        "reasons": {
            "login": state.login.reason,
            "support": state.support.reason,
            "admin": state.admin.reason,
        },
        "full_switch_ready": state.full_switch_ready,
        "recommended_checks": [
            "python scripts/bootstrap_web_toolchain.py",
            "pnpm --dir webapp run build",
            "pnpm --dir webapp run check:remote:webapp -- --base-url http://192.168.100.17:8666",
        ],
    }

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Проверка operational cutover для нового webapp")
        print(f"- bundle: {'ready' if state.bundle_ready else 'missing'} ({WEBAPP_DIST_DIR})")
        print(
            f"- requested: login={state.login.requested} support={state.support.requested} admin={state.admin.requested}"
        )
        print(
            f"- active: login={state.login.active} support={state.support.active} admin={state.admin.active}"
        )
        print(
            f"- reasons: login={state.login.reason} support={state.support.reason} admin={state.admin.reason}"
        )
        print(f"- full switch ready: {state.full_switch_ready}")
        print("- recommended checks:")
        for command in report["recommended_checks"]:
            print(f"  - {command}")

    if args.strict:
        target_ready = state.full_switch_ready if args.require_full_switch else state.bundle_ready
        if not target_ready:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
