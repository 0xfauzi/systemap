from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from conftest import TINY_PACKAGE, init_two_cards, write_tree

from systemap import config, extract, skill
from systemap.cli import main


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
    assert reader["functions"][0] == {
        "name": "read",
        "signature": "def read(source: str) -> Request",
    }
    assert [c["name"] for c in reader["classes"]] == ["Request"]
    assert "doc" not in reader["classes"][0] and "doc" not in reader["errors"][0], (
        "per-symbol docstrings are not facts the map or the change detector reads"
    )
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


# ---- 0.5: every public name, the external imports, the tests directories --------

NAMES_TREE: dict[str, str] = {
    "pkg/__init__.py": "",
    "pkg/app.py": """
        import json
        import os.path
        import anthropic.types
        from __future__ import annotations
        from google.adk import Agent
        from google.adk.tools import tool
        from pkg import core

        LIMIT = 4
        app = object()
        root_agent: object = object()
        _private = 1
        typed: int


        def serve() -> None:
            pass


        class Handler:
            pass


        class ServeError(Exception):
            pass
    """,
    "pkg/core.py": "def run() -> None:\n    pass\n",
}


def test_extract_records_every_public_name_with_its_kind_and_the_external_imports(
    tmp_path: Path,
) -> None:
    write_tree(tmp_path, NAMES_TREE)
    facts = extract.build(config.load(tmp_path))
    app = facts["components"]["pkg.app"]
    assert app["names"] == [
        {"name": "LIMIT", "kind": "constant"},
        {"name": "app", "kind": "object"},
        {"name": "root_agent", "kind": "object"},
        {"name": "serve", "kind": "function"},
        {"name": "Handler", "kind": "class"},
        {"name": "ServeError", "kind": "error"},
    ]
    # Only UPPER_CASE names are constants with a value; the rest are names.
    assert app["constants"] == [{"name": "LIMIT", "value": "4"}]
    # The standard library, __future__ and the package's own modules are not external;
    # the dotted name is kept as written.
    assert app["external"] == ["anthropic.types", "google.adk", "google.adk.tools"]
    assert facts["components"]["pkg.core"]["external"] == []
    assert extract.external_imports("import boto3, yaml\nfrom . import x\n", {"pkg"}) == [
        "boto3",
        "yaml",
    ]
    assert extract.external_imports("def broken(:\n", set()) == []


def test_entry_may_be_any_public_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A lower-case module-level object such as `app` is an entry the check accepts."""
    write_tree(tmp_path, NAMES_TREE)
    init_two_cards(tmp_path, "--no-ci")
    model = tmp_path / "map/model.py"
    model.write_text(
        model.read_text()
        .replace('implemented_by=("pkg.reader",)', 'implemented_by=("pkg.app",)')
        .replace('entry="read",', 'entry="app",')
        .replace('interface="read(source) -> Request",', 'interface="app (the server object)",')
        .replace('implemented_by=("pkg.writer",)', 'implemented_by=("pkg.core",)')
        .replace('entry="write",', 'entry="run",')
        .replace('interface="write(request) -> Result",', 'interface="run() -> None",')
    )
    assert main(["--root", str(tmp_path), "refresh"]) == 0
    assert main(["--root", str(tmp_path), "check"]) == 0
    model.write_text(model.read_text().replace('entry="app",', 'entry="_private",'))
    assert main(["--root", str(tmp_path), "check"]) == 1
    out = capsys.readouterr().out
    assert "Reader names entry _private which none of its modules defines (pkg.app)" in out
    assert "set entry to a public name one of them defines" in out


WORKSPACE_TREE: dict[str, str] = {
    "pyproject.toml": (
        '[project]\nname = "wharf"\nversion = "0"\n\n'
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    ),
    "packages/alpha/pyproject.toml": '[project]\nname = "alpha"\nversion = "0"\n',
    "packages/alpha/src/alpha/__init__.py": "",
    "packages/alpha/src/alpha/core.py": "def run() -> None:\n    pass\n",
    "packages/alpha/tests/test_core.py": "from alpha.core import run\n\n\ndef test_run():\n    run()\n",
    "packages/beta/pyproject.toml": '[project]\nname = "beta"\nversion = "0"\n',
    "packages/beta/beta/__init__.py": "",
    "packages/beta/beta/api.py": "def get() -> None:\n    pass\n",
    "packages/beta/test/test_api.py": "from beta import api\n\n\ndef test_get():\n    api.get()\n",
    "tests/test_nothing.py": "def test_nothing():\n    pass\n",
    "docs/tests/test_ignored.py": "from alpha.core import run\n\n\ndef test_doc():\n    run()\n",
    "node_modules/tests/test_ignored.py": "from alpha.core import run\n\n\ndef test_nm():\n    run()\n",
}


def test_workspace_roots_and_tests_directories_are_discovered(tmp_path: Path) -> None:
    write_tree(tmp_path, WORKSPACE_TREE)
    cfg = config.load(tmp_path)
    assert cfg.package_roots == (
        ("packages/alpha/src/alpha", "alpha"),
        ("packages/beta/beta", "beta"),
    )
    assert cfg.name == "wharf", "[project] name comes before the directory name"
    assert config.discover_tests(tmp_path) == [
        "tests",
        "packages/alpha/tests",
        "packages/beta/test",
    ]
    facts = extract.build(cfg)
    assert facts["tests_dirs"] == ["tests", "packages/alpha/tests", "packages/beta/test"]
    assert facts["components"]["alpha.core"]["tests_total"] == 1, (
        "docs/ and node_modules/ are skipped"
    )
    assert facts["components"]["beta.api"]["tests_total"] == 1
    # A configured list is read as given, in order, and recorded.
    write_tree(tmp_path, {"systemap.toml": 'tests_dir = ["packages/beta/test", "nowhere"]\n'})
    cfg = config.load(tmp_path)
    assert cfg.tests_dirs == ("packages/beta/test", "nowhere")
    facts = extract.build(cfg)
    assert facts["tests_dirs"] == ["packages/beta/test", "nowhere"]
    assert facts["components"]["alpha.core"]["tests_total"] == 0
    assert facts["components"]["beta.api"]["tests_total"] == 1
    # One directory as a string still works; anything else is refused.
    write_tree(tmp_path, {"systemap.toml": 'tests_dir = "tests"\n'})
    assert config.load(tmp_path).tests_dirs == ("tests",)
    write_tree(tmp_path, {"systemap.toml": "tests_dir = 3\n"})
    with pytest.raises(config.ConfigError, match="tests_dir must be a directory or a list"):
        config.load(tmp_path)


def test_zero_tests_is_said_in_one_line_naming_the_directories(tmp_path: Path) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    (tmp_path / "tests/test_reader.py").unlink()
    (tmp_path / "tests/test_other.py").unlink()
    facts = extract.build(config.load(tmp_path))
    assert facts["tests_dirs"] == ["tests"]
    lines = extract.summary(facts)
    assert "  tests:            none import a module; searched tests" in lines
    (tmp_path / "tests").rmdir()
    facts = extract.build(config.load(tmp_path))
    assert facts["tests_dirs"] == []
    assert (
        "  tests:            none import a module; no directory named tests or test was found"
        in extract.summary(facts)
    )
    write_tree(tmp_path, TINY_PACKAGE)
    assert (
        "  tests:            3 test functions import a module, 2 in a file named after it"
        in extract.summary(extract.build(config.load(tmp_path)))
    )


def test_no_roots_names_the_candidate_directories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(
        tmp_path,
        {
            "services/api/app/__init__.py": "",
            "services/api/app/deep/er/still/__init__.py": "",
            "lib/x/__init__.py": "",
            "map/model.py": "from systemap import Model, Meaning\n"
            "MODEL = Model((1, 1), (), (), (), (), ())\nMEANING = Meaning(plain={})\n",
        },
    )
    assert config.discover_roots(tmp_path) == []
    # Depth four: services/api/app/deep is listed if it holds an __init__.py (it does
    # not), and six deep is past the search.
    assert config.candidate_packages(tmp_path) == ["lib/x", "services/api/app"]
    assert main(["--root", str(tmp_path), "extract"]) == 2
    err = capsys.readouterr().err
    assert "no package roots found" in err
    assert "directories holding an __init__.py: lib/x, services/api/app" in err
    assert "still" not in err, "five deep is past the depth the error searches"


def test_name_defaults_to_pyproject_then_the_repository_directory(tmp_path: Path) -> None:
    main_dir = tmp_path / "main"
    write_tree(main_dir, {"pkg/__init__.py": "", "README.md": "x\n"})
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
    }

    def git(*args: str, cwd: Path = main_dir) -> None:
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)

    git("init", "-q")
    git("add", ".")
    git("commit", "-q", "-m", "one")
    assert config.load(main_dir).name == "main"
    worktree = tmp_path / "feature-branch-worktree"
    git("worktree", "add", "-q", str(worktree), "-b", "feature")
    assert config.default_name(worktree) == "main", "a worktree is named after its checkout"
    write_tree(worktree, {"pyproject.toml": '[project]\nname = "wharf"\n'})
    assert config.load(worktree).name == "wharf"
    plain = tmp_path / "plain-dir"
    write_tree(plain, {"pkg/__init__.py": ""})
    assert config.load(plain).name == "plain-dir"
    write_tree(plain, {"systemap.toml": 'name = "given"\n'})
    assert config.load(plain).name == "given"


def test_facts_fields_are_the_documented_ones(tmp_path: Path) -> None:
    """The extractor's table is what it writes, and the schema reference is the table."""
    write_tree(tmp_path, {**TINY_PACKAGE, **ENTRY_TREE})
    facts = extract.build(config.load(tmp_path))
    assert set(facts) == extract.fields_of("facts")
    for record in facts["components"].values():
        assert set(record) == extract.fields_of("module"), record["id"]
    assert facts["entry_points"], "the tree has entry points to compare"
    for point in facts["entry_points"]:
        assert set(point) == extract.fields_of("entry point")
    reference = skill.files()["references/schema.md"]
    assert reference.endswith(extract.facts_doc()), (
        "references/schema.md's facts section differs from extract.FIELDS; regenerate it"
    )


def test_facts_file_is_compact_and_one_record_per_line(tmp_path: Path) -> None:
    """The committed file stays small and diffs module by module."""
    write_tree(tmp_path, TINY_PACKAGE)
    cfg = config.load(tmp_path)
    facts = extract.build(cfg)
    extract.write_facts(cfg.facts_path, facts)
    text = cfg.facts_path.read_text()
    assert extract.read_facts(cfg.facts_path) == facts, "round-trips"
    lines = text.splitlines()
    assert lines[0] == "{" and lines[-1] == "}" and text.endswith("\n")
    assert not any(line.startswith(" ") for line in lines), "no indentation"
    records = [line for line in lines if line.startswith('"pkg')]
    assert len(records) == 3, "one module record per line"
    assert all(": " not in line.split(":", 1)[1][:2] for line in records)
    keys = [
        line.split(":", 1)[0]
        for line in lines
        if line.startswith('"') and not line.startswith('"pkg')
    ]
    assert keys == sorted(keys)
    assert '"components":{' in text
    # The compact file is smaller than the pretty one it replaces; the sizes
    # on real trees are in the changelog, this only pins the direction.
    import json

    pretty = json.dumps(facts, indent=1, ensure_ascii=False, sort_keys=True)
    assert len(text) < len(pretty)
