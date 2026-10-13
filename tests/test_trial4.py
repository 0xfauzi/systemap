"""Repairs of the fourth trial results (trial4-3 and trial4-5).

Each acceptance value is in the docstring of its test.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import write_tree
from test_trial_check import mapped_project

from systemap import config, extract, file_write, unknown_causes
from systemap import language as languages
from systemap.cli import main

# ---- trial4-5: a written file has the mode of a usual write -----------------------------


@pytest.fixture
def umask_022() -> Iterator[None]:
    old = os.umask(0o022)
    yield
    os.umask(old)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
@pytest.mark.usefixtures("umask_022")
def test_a_new_file_has_the_mode_of_a_usual_write(tmp_path: Path) -> None:
    """Acceptance: with umask 022, write_atomic gives a new file the mode 0644 (before:
    0600 from mkstemp)."""
    path = tmp_path / "docs" / "map" / "index.html"
    file_write.write_atomic(tmp_path, path, "<p>map</p>\n")
    assert _mode(path) == 0o644
    assert path.read_text(encoding="utf-8") == "<p>map</p>\n"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
@pytest.mark.usefixtures("umask_022")
def test_an_existing_file_keeps_its_mode(tmp_path: Path) -> None:
    """Acceptance: with umask 022, write_atomic keeps the mode 0640 of a file that is present,
    and no temporary file stays in the folder."""
    path = tmp_path / "map.json"
    path.write_text("{}\n", encoding="utf-8")
    path.chmod(0o640)
    file_write.write_atomic(tmp_path, path, '{"a": 1}\n')
    assert _mode(path) == 0o640
    assert path.read_text(encoding="utf-8") == '{"a": 1}\n'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["map.json"]


# ---- trial4-3: the extraction inputs include each configuration file that is read ------

TSCONFIG = (
    '{"extends":"@acme/tsconfig/base.json",'
    '"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}'
)
PACKAGE = Path("node_modules/@acme/tsconfig/base.json")


def run(root: Path, *argv: str) -> int:
    return main(["--root", str(root), *argv])


def test_an_installed_configuration_package_is_an_extraction_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: a tsconfig file extends a package in node_modules, and the package does
    not change the module facts. (1) Before the install, `check` gives the fix line of the
    cause `package`. (2) After the install, `extract --check` exits 1 (before: 0). (3) The
    command of the fix line (`refresh`) removes the config_issues record (before: it kept
    the record). (4) After a change of the inherited `paths`, `extract --check` exits 1
    (before: 0). (5) A clone without the package agrees with the facts."""
    root = mapped_project(tmp_path, "typescript")
    (root / "tsconfig.json").write_text(TSCONFIG, encoding="utf-8")
    facts = root / "docs" / "map" / "map.json"
    assert run(root, "refresh") == 0
    assert run(root, "check") == 0
    fix = unknown_causes.FIX[unknown_causes.PACKAGE]
    assert f"  fix: {fix}" in capsys.readouterr().out
    assert "systemap refresh" in fix
    assert json.loads(facts.read_text(encoding="utf-8"))["config_issues"] != []

    write_tree(root, {PACKAGE.as_posix(): '{"compilerOptions":{"strict":true}}'})
    capsys.readouterr()
    assert run(root, "extract", "--check") == 1
    assert "extraction inputs changed since the map was built" in capsys.readouterr().out
    assert run(root, "refresh") == 0
    assert json.loads(facts.read_text(encoding="utf-8"))["config_issues"] == []
    assert run(root, "extract", "--check") == 0
    assert run(root, "check") == 0
    assert fix not in capsys.readouterr().out

    paths = {"compilerOptions": {"strict": True, "paths": {"#/*": ["src/*"]}}}
    write_tree(root, {PACKAGE.as_posix(): json.dumps(paths)})
    assert run(root, "extract", "--check") == 1
    assert run(root, "refresh") == 0
    assert run(root, "extract", "--check") == 0

    (root / PACKAGE).unlink()
    assert run(root, "extract", "--check") == 0


TREES = {
    "python": {
        "pyproject.toml": '[project]\nname = "all"\n',
        "libs/core/pyproject.toml": '[project]\nname = "core"\n',
        "libs/core/pkg/__init__.py": "",
        "libs/core/pkg/app.py": "def run() -> None:\n    pass\n",
        "systemap.toml": '[package_roots]\n"libs/core/pkg" = "pkg"\n',
    },
    "typescript": {
        "package.json": '{"name":"web"}',
        "tsconfig.json": '{"extends":"./tsconfig.base.json"}',
        "tsconfig.base.json": '{"compilerOptions":{"strict":true}}',
        "src/index.ts": "export function run(): void {}\n",
        "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    },
}
NEW_INPUT = {"python": "libs/core/pyproject.toml", "typescript": "tsconfig.base.json"}


@pytest.mark.parametrize("language", sorted(TREES))
def test_the_digest_has_each_configuration_file_of_the_adapter(
    tmp_path: Path, language: str
) -> None:
    """Acceptance: in 2 of 2 languages, the provenance digest has one entry for each
    configuration file that `config_paths` of the adapter gives and that is present. A change
    to a file that only `config_paths` gives (before: not in the digest) is an extraction
    input change."""
    write_tree(tmp_path, TREES[language])
    cfg = config.load(tmp_path)
    stored = extract.build(cfg)
    adapter = languages.repository(language)
    folders = [package for package, _name in cfg.roots]
    expected = {
        path.relative_to(tmp_path).as_posix()
        for path in adapter.config_paths(tmp_path, folders)
        if path.is_file()
    }
    assert set(stored["provenance"]["files"]) == expected
    assert NEW_INPUT[language] in expected
    target = tmp_path / NEW_INPUT[language]
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    changed = extract.build(config.load(tmp_path))
    assert "extraction inputs changed since the map was built" in extract.drift(changed, stored)
