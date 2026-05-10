from __future__ import annotations

from dataclasses import dataclass

import config


@dataclass(frozen=True, slots=True)
class RemoteAssistModePolicy:
    mode: str
    permission: str
    enabled_config: str | None = None
    consent_required: bool = True
    control_channel: bool = False
    file_channel: bool = False
    clipboard: bool = False
    elevated: bool = False


MODE_POLICIES: dict[str, RemoteAssistModePolicy] = {
    "view_only": RemoteAssistModePolicy(
        mode="view_only",
        permission="remote_assist.request",
    ),
    "interactive_control": RemoteAssistModePolicy(
        mode="interactive_control",
        permission="remote_assist.control",
        enabled_config="REMOTE_ASSIST_INTERACTIVE_CONTROL_ENABLED",
        control_channel=True,
    ),
    "file_transfer": RemoteAssistModePolicy(
        mode="file_transfer",
        permission="remote_assist.file_transfer",
        enabled_config="REMOTE_ASSIST_FILE_TRANSFER_ENABLED",
        file_channel=True,
    ),
    "elevated_admin": RemoteAssistModePolicy(
        mode="elevated_admin",
        permission="remote_assist.elevated",
        enabled_config="REMOTE_ASSIST_ELEVATED_ADMIN_ENABLED",
        control_channel=True,
        elevated=True,
    ),
}


REMOTE_ASSIST_CLIPBOARD_PERMISSION = "remote_assist.clipboard"
REMOTE_ASSIST_UNATTENDED_PERMISSION = "remote_assist.unattended"


def normalize_remote_assist_mode(mode: str | None) -> str:
    return str(mode or "view_only").strip().lower() or "view_only"


def get_remote_assist_mode_policy(mode: str | None) -> RemoteAssistModePolicy | None:
    return MODE_POLICIES.get(normalize_remote_assist_mode(mode))


def get_remote_assist_mode_permission(mode: str | None) -> str:
    policy = get_remote_assist_mode_policy(mode)
    return policy.permission if policy else "remote_assist.request"


def is_remote_assist_mode_enabled(mode: str | None) -> bool:
    normalized = normalize_remote_assist_mode(mode)
    policy = MODE_POLICIES.get(normalized)
    if policy is None:
        return False
    if normalized not in config.REMOTE_ASSIST_ALLOWED_MODES:
        return False
    if policy.enabled_config and not bool(getattr(config, policy.enabled_config, False)):
        return False
    return True


def get_remote_assist_feature_flags() -> dict[str, bool]:
    return {
        "interactive_control": bool(config.REMOTE_ASSIST_INTERACTIVE_CONTROL_ENABLED),
        "file_transfer": bool(config.REMOTE_ASSIST_FILE_TRANSFER_ENABLED),
        "clipboard": bool(config.REMOTE_ASSIST_CLIPBOARD_ENABLED),
        "elevated_admin": bool(config.REMOTE_ASSIST_ELEVATED_ADMIN_ENABLED),
        "managed_unattended": bool(config.REMOTE_ASSIST_MANAGED_UNATTENDED_ENABLED),
        "allow_unattended": bool(config.REMOTE_ASSIST_ALLOW_UNATTENDED),
    }
