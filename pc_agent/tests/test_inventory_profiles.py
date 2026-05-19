from __future__ import annotations

from pc_agent.modules.impl.inventory_profiles import (
    KEY_APP_PROFILES,
    detect_key_apps,
    parse_version_from_output,
)


def test_key_app_profiles_include_operational_apps():
    profile_ids = {profile.app_id for profile in KEY_APP_PROFILES}

    assert {"libreoffice", "r7_office", "yandex_browser", "chromium_or_chrome", "kaspersky", "vipnet"} <= profile_ids


def test_parse_version_from_output_extracts_first_semver():
    assert parse_version_from_output("LibreOffice 7.6.4.1 40(Build:1)") == "7.6.4.1"
    assert parse_version_from_output("no version here") == ""


def test_detect_key_apps_uses_safe_profile_paths(monkeypatch, tmp_path):
    executable = tmp_path / "libreoffice"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    warnings: list[str] = []

    monkeypatch.setattr(
        "pc_agent.modules.impl.inventory_profiles.KEY_APP_PROFILES",
        [
            KEY_APP_PROFILES[0].__class__(
                app_id="libreoffice",
                name="LibreOffice",
                linux_paths=(str(executable),),
                linux_commands=(),
                windows_paths=(),
                windows_commands=(),
                windows_registry=(),
            )
        ],
    )

    result = detect_key_apps(warnings, os_name="linux")

    assert result["profile_version"] == "1.0"
    assert result["key_apps"][0]["id"] == "libreoffice"
    assert result["key_apps"][0]["present"] is True
    assert result["key_apps"][0]["source"] == "path"
    assert warnings == []
