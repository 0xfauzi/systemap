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


INPUTS_CHANGED = "extraction inputs changed since the map was built"
TYPESCRIPT_TREE = {
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"extends":["./tsconfig.base.json","@acme/tsconfig/base.json"]}',
    "tsconfig.base.json": '{"compilerOptions":{"strict":true}}',
    PACKAGE.as_posix(): '{"compilerOptions":{"paths":{"#/*":["src/*"]}}}',
    "node_modules/typescript/package.json": '{"name":"typescript","version":"5.9.3"}',
    "src/index.ts": "export function run(): void {}\n",
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
}


def _changed(root: Path, stored: dict[str, object], name: str, text: str) -> bool:
    (root / name).write_text(text, encoding="utf-8")
    return INPUTS_CHANGED in extract.drift(extract.build(config.load(root)), stored)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "text", "changed"),
    [
        (
            "node_modules/typescript/package.json",
            '{"name":"typescript","version":"5.9.3","_where":"/home/ci/app","_resolved":"x"}',
            False,
        ),
        (
            "node_modules/typescript/package.json",
            '{\n  "name": "typescript",\n  "version": "5.4.0"\n}\n',
            False,
        ),
        ("node_modules/typescript/package.json", '{"version":"6.0.3"}', True),
        (
            PACKAGE.as_posix(),
            '// shared\n{"compilerOptions":{"paths":{"#/*":["src/*"]},"strict":true,},}\n',
            False,
        ),
        (PACKAGE.as_posix(), '{"compilerOptions":{"paths":{"#/*":["lib/*"]}}}', True),
        ("tsconfig.base.json", '/* base */ {"compilerOptions":{"strict":false}}', False),
        ("tsconfig.base.json", '{"compilerOptions":{"strict":true,"baseUrl":"src"}}', True),
        ("tsconfig.base.json", '{"compilerOptions":{"strict":true},"include":["src"]}', True),
    ],
)
def test_the_digest_has_only_the_values_that_extraction_reads(
    tmp_path: Path, name: str, text: str, changed: bool
) -> None:
    """Acceptance: npm metadata fields (`_where`, `_resolved`), a different minor version,
    comments, the text format, and a compiler option that extraction does not read
    (`strict`) give no input change. A different TypeScript major version, a `paths` or
    `baseUrl` change, and an `include` change give an input change."""
    write_tree(tmp_path, TYPESCRIPT_TREE)
    stored = extract.build(config.load(tmp_path))
    assert set(stored["provenance"]["installed"]) == {
        PACKAGE.as_posix(),
        "node_modules/typescript/package.json",
    }
    assert {"package.json", "tsconfig.json", "tsconfig.base.json"} <= set(
        stored["provenance"]["files"]
    )
    assert _changed(tmp_path, stored, name, text) is changed


PYTHON_TREE = {
    "pyproject.toml": (
        '[project]\nname = "all"\n[tool.uv.workspace]\nmembers = ["libs/*"]\n'
        '[tool.systemap]\nname = "All"\n[tool.systemap.package_roots]\n"libs/core/pkg" = "pkg"\n'
    ),
    "libs/core/pyproject.toml": '[project]\nname = "core"\n',
    "libs/core/pkg/__init__.py": "",
    "libs/core/pkg/app.py": "def run() -> None:\n    pass\n",
}


def test_the_digest_has_only_the_python_files_that_extraction_reads(tmp_path: Path) -> None:
    """Acceptance: the live watcher monitors the `pyproject.toml` of a uv workspace member,
    but extraction does not read it. A change to that file gives no input change. A change
    to the `[tool.systemap]` table of the root `pyproject.toml` gives an input change."""
    write_tree(tmp_path, PYTHON_TREE)
    cfg = config.load(tmp_path)
    folders = [package for package, _name in cfg.roots]
    watched = languages.repository("python").config_paths(tmp_path, folders)
    assert tmp_path / "libs/core/pyproject.toml" in watched
    stored = extract.build(cfg)
    assert stored["provenance"]["files"].keys() == {"pyproject.toml"}
    assert stored["provenance"]["installed"] == {}
    member = '[project]\nname = "core"\ndependencies = ["httpx"]\n'
    assert not _changed(tmp_path, stored, "libs/core/pyproject.toml", member)
    root = PYTHON_TREE["pyproject.toml"].replace('name = "All"', 'name = "Everything"')
    assert _changed(tmp_path, stored, "pyproject.toml", root)
