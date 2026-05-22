from __future__ import annotations

from pc_agent.core.user_profile import UserProfileManager


def test_user_profile_manager_load_save_sanitize(tmp_path):
    manager = UserProfileManager(data_root=tmp_path)
    saved = manager.save(
        {
            "full_name": "  Ivan   Ivanov  ",
            "email": "ivan@example.test",
            "phone": "1" * 120,
            "relationship_type": "invalid",
            "unknown": "ignored",
        }
    )

    loaded = manager.load()

    assert saved["full_name"] == "Ivan Ivanov"
    assert loaded["email"] == "ivan@example.test"
    assert len(loaded["phone"]) == 80
    assert loaded["relationship_type"] == "primary_user"
    assert "unknown" not in loaded


def test_user_profile_manager_shared_device_maps_relationship(tmp_path):
    manager = UserProfileManager(data_root=tmp_path)

    profile = manager.sanitize({"display_name": "Shared PC", "is_shared_device": True})

    assert profile["relationship_type"] == "shared_user"
    assert manager.is_complete(profile)
