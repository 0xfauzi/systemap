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


ENTRY_TREE: dict[str, str] = {
    "pyproject.toml": '[project]\nname = "pkg"\nversion = "0"\n\n[project.scripts]\npkg = "pkg.cli:main"\nother = "elsewhere.run:main"\n',
    "pkg/__init__.py": "def open_thing(path: str) -> str:\n    return path\n\n\ndef _hidden() -> None:\n    pass\n",
    "pkg/__main__.py": "from pkg.cli import main\n\nraise SystemExit(main())\n",
    "pkg/cli.py": """
        import argparse


        def main(argv: list[str] | None = None) -> int:
            parser = argparse.ArgumentParser()
            sub = parser.add_subparsers()
            sub.add_parser("init", help="start")
            s = sub.add_parser("check")
            s.set_defaults(x=1)
            name = "dynamic"
            sub.add_parser(name)
            return 0
    """,
    "pkg/worker.py": "def main() -> None:\n    pass\n",
}


def test_extract_records_entry_points(tmp_path: Path) -> None:
    write_tree(tmp_path, ENTRY_TREE)
    facts = extract.build(config.load(tmp_path))
    assert facts["entry_points"] == [
        {"kind": "console_script", "name": "pkg", "module": "pkg.cli", "target": "main"},
        {"kind": "public_function", "name": "open_thing", "module": "pkg", "target": ""},
        {"kind": "main_module", "name": "python -m pkg", "module": "pkg.__main__", "target": ""},
        {"kind": "main_function", "name": "main", "module": "pkg.cli", "target": "main"},
        {"kind": "subcommand", "name": "init", "module": "pkg.cli", "target": "pkg"},
        {"kind": "subcommand", "name": "check", "module": "pkg.cli", "target": "pkg"},
        {"kind": "main_function", "name": "main", "module": "pkg.worker", "target": "main"},
    ]
    # A script pointing outside the package is not this package's entry
    # point; a subcommand built from a variable is not detected.
    labels = [extract.entry_label(e) for e in facts["entry_points"]]
    assert labels == [
        "pkg (console script)",
        "open_thing() in pkg",
        "python -m pkg",
        "main() in pkg.cli",
        "pkg init (subcommand)",
        "pkg check (subcommand)",
        "main() in pkg.worker",
    ]
    assert (
        extract.entry_label({"kind": "subcommand", "name": "go", "module": "p.m", "target": ""})
        == "go (subcommand in p.m)"
    )


def test_drift_sees_an_entry_point_change(tmp_path: Path) -> None:
    write_tree(tmp_path, ENTRY_TREE)
    cfg = config.load(tmp_path)
    before = extract.build(cfg)
    assert extract.drift(before, before) == []
    # A new console script is a change to the tree no module hash covers.
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + 'pkg-worker = "pkg.worker:main"\n')
    after = extract.build(cfg)
    assert extract.drift(after, before) == [
        "entry point not in the map: pkg-worker (console script)"
    ]
    assert extract.drift(before, after) == [
        "entry point in the map but gone from the tree: pkg-worker (console script)"
    ]
    # Old facts with no entry points at all read as empty, not as an error.
    legacy = {k: v for k, v in before.items() if k != "entry_points"}
    assert all("entry point not in the map" in line for line in extract.drift(before, legacy))


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
