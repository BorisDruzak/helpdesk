import scripts.verify_workspace as verify


def test_verify_workspace_tracks_harness_text_files() -> None:
    assert ".mdc" in verify.TEXT_SUFFIXES
    assert ".ps1" in verify.TEXT_SUFFIXES
    assert ".cursor" not in verify.SKIP_DIRS
