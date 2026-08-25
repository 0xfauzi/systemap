from __future__ import annotations

from pathlib import Path

from conftest import TINY_PACKAGE, write_tree

from systemap import config, extract


def test_extract_finds_modules_and_public_surface(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    cfg = config.load(tmp_path)
    assert cfg.package_roots == (("pkg", "pkg"),)
    facts = extract.build(cfg)

    assert facts["packages"] == ["pkg"]
    assert sorted(facts["components"]) == ["pkg", "pkg.reader", "pkg.writer"]

    reader = facts["components"]["pkg.reader"]
    assert reader["docstring"] == "Read things."
    assert [f["name"] for f in reader["functions"]] == ["read"]
    assert reader["functions"][0]["signature"] == "def read(source: str) -> Request"
    assert reader["functions"][0]["doc"] == "Read a source."
    assert [c["name"] for c in reader["classes"]] == ["Request"]
    assert reader["classes"][0]["methods"] == ["def send(self, body: str) -> None"]
    assert [e["name"] for e in reader["errors"]] == ["ReadError"]
    assert reader["constants"] == [{"name": "LIMIT", "value": "10"}]
    assert reader["file"] == "pkg/reader.py"
    assert reader["plane"] == "core"
    assert len(reader["sha"]) == 12

    writer = facts["components"]["pkg.writer"]
    assert writer["uses"] == {"pkg.reader": ["*"]}
    assert writer["imports"] == ["pkg.reader"]
    assert reader["imported_by"] == ["pkg.writer"]


def test_extract_attributes_tests_to_modules(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    facts = extract.build(config.load(tmp_path))
    reader = facts["components"]["pkg.reader"]
    assert reader["tests_total"] == 2
    assert reader["tests_primary"] == 2
    assert reader["tests"] == ["test_nested", "test_read_returns_request"]
    writer = facts["components"]["pkg.writer"]
    assert writer["tests_total"] == 1
    assert writer["tests_primary"] == 0


def test_drift_reports_changes(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    cfg = config.load(tmp_path)
    before = extract.build(cfg)
    assert extract.drift(before, before) == []
    (tmp_path / "pkg" / "reader.py").write_text("def read():\n    pass\n", encoding="utf-8")
    (tmp_path / "pkg" / "extra.py").write_text("X = 1\n", encoding="utf-8")
    after = extract.build(cfg)
    lines = extract.drift(after, before)
    assert "missing from the map: pkg.extra" in lines
    assert "code changed since the map was built: pkg.reader" in lines


def test_spec_sections_and_planes(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    write_tree(
        tmp_path,
        {
            "pkg/ui/__init__.py": "",
            "pkg/ui/screen.py": "def show() -> None:\n    pass\n",
            "docs/design.md": "# Title\n\n## One\n\ntext\n\n### One point one\n",
            "systemap.toml": 'planes = ["ui"]\nspec_path = "docs/design.md"\n',
        },
    )
    facts = extract.build(config.load(tmp_path))
    assert facts["components"]["pkg.ui.screen"]["plane"] == "ui"
    assert facts["spec_sections"] == [
        {"level": "2", "title": "One"},
        {"level": "3", "title": "One point one"},
    ]
