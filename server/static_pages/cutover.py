from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


CUTOVER_REASON_ACTIVE = "active"
CUTOVER_REASON_FLAG_DISABLED = "flag_disabled"
CUTOVER_REASON_BUNDLE_MISSING = "bundle_missing"
CUTOVER_REASON_LOGIN_REQUIRED = "login_cutover_required"


@dataclass(frozen=True)
class WebappCutoverRouteState:
    requested: bool
    active: bool
    target_path: str
    reason: str


@dataclass(frozen=True)
class WebappCutoverState:
    bundle_ready: bool
    bundle_reason: str | None
    login: WebappCutoverRouteState
    support: WebappCutoverRouteState
    admin: WebappCutoverRouteState
    help: WebappCutoverRouteState
    ticket: WebappCutoverRouteState

    @property
    def full_switch_ready(self) -> bool:
        return self.login.active and self.support.active and self.admin.active


def has_built_webapp_bundle(dist_dir: Path) -> bool:
    index_path = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"
    if not index_path.is_file() or not assets_dir.is_dir():
        return False
    return any(path.is_file() for path in assets_dir.rglob("*"))


def build_webapp_cutover_state(
    *,
    dist_dir: Path,
    login_enabled: bool,
    support_enabled: bool,
    admin_enabled: bool,
    help_enabled: bool = False,
    ticket_enabled: bool = False,
) -> WebappCutoverState:
    bundle_ready = has_built_webapp_bundle(dist_dir)
    bundle_reason = None if bundle_ready else CUTOVER_REASON_BUNDLE_MISSING

    login = _build_route_state(
        requested=login_enabled,
        target_path="/app/login",
        bundle_ready=bundle_ready,
    )
    support = _build_route_state(
        requested=support_enabled,
        target_path="/app/support",
        bundle_ready=bundle_ready,
        login_enabled=login_enabled,
    )
    admin = _build_route_state(
        requested=admin_enabled,
        target_path="/app/admin",
        bundle_ready=bundle_ready,
        login_enabled=login_enabled,
    )
    help = _build_route_state(
        requested=help_enabled,
        target_path="/app/help",
        bundle_ready=bundle_ready,
    )
    ticket = _build_route_state(
        requested=ticket_enabled,
        target_path="/app/ticket",
        bundle_ready=bundle_ready,
    )
    return WebappCutoverState(
        bundle_ready=bundle_ready,
        bundle_reason=bundle_reason,
        login=login,
        support=support,
        admin=admin,
        help=help,
        ticket=ticket,
    )


def _build_route_state(
    *,
    requested: bool,
    target_path: str,
    bundle_ready: bool,
    login_enabled: bool | None = None,
) -> WebappCutoverRouteState:
    if not requested:
        return WebappCutoverRouteState(
            requested=False,
            active=False,
            target_path=target_path,
            reason=CUTOVER_REASON_FLAG_DISABLED,
        )
    if not bundle_ready:
        return WebappCutoverRouteState(
            requested=True,
            active=False,
            target_path=target_path,
            reason=CUTOVER_REASON_BUNDLE_MISSING,
        )
    if login_enabled is False:
        return WebappCutoverRouteState(
            requested=True,
            active=False,
            target_path=target_path,
            reason=CUTOVER_REASON_LOGIN_REQUIRED,
        )
    return WebappCutoverRouteState(
        requested=True,
        active=True,
        target_path=target_path,
        reason=CUTOVER_REASON_ACTIVE,
    )
