from pathlib import Path

from scripts import docs_inventory


def test_classify_docs_by_repo_location() -> None:
    assert docs_inventory.classify_doc(Path("docs/README.md")) == "canonical"
    assert docs_inventory.classify_doc(Path("docs/archive/OLD.md")) == "archive"
    assert docs_inventory.classify_doc(Path("docs/superpowers/plans/feature.md")) == "plan"
    assert docs_inventory.classify_doc(Path("docs/superpowers/specs/design.md")) == "spec"


def test_find_broken_links_ignores_external_and_anchor_links(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "A.md").write_text(
        "\n".join(
            [
                "# A",
                "[ok](B.md)",
                "[bad](missing.md)",
                "[anchor](#local)",
                "[web](https://example.com/docs)",
            ]
        ),
        encoding="utf-8",
    )
    (docs_dir / "B.md").write_text("# B\n", encoding="utf-8")

    broken = docs_inventory.find_broken_links(tmp_path)

    assert len(broken) == 1
    assert broken[0].source == Path("docs/A.md")
    assert broken[0].target == "missing.md"


def test_duplicate_basenames_are_reported(tmp_path: Path) -> None:
    (tmp_path / "docs" / "archive").mkdir(parents=True)
    (tmp_path / "docs" / "ROADMAP.md").write_text("# root\n", encoding="utf-8")
    (tmp_path / "docs" / "archive" / "ROADMAP.md").write_text("# archive\n", encoding="utf-8")

    docs = docs_inventory.collect_docs(tmp_path)
    duplicates = docs_inventory.find_duplicate_basenames(docs)

    assert duplicates["roadmap.md"] == [Path("docs/ROADMAP.md"), Path("docs/archive/ROADMAP.md")]


def test_build_inventory_groups_status_and_link_results(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("[missing](missing.md)\n", encoding="utf-8")

    inventory = docs_inventory.build_inventory(tmp_path)

    assert inventory.status_counts["canonical"] == 1
    assert inventory.broken_links[0].source == Path("docs/README.md")
