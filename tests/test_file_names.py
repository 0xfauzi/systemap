"""A file name that is not valid UTF-8 (audit finding rest-1).

Before the repair, such a name went through the walks into the facts. The facts write
then stopped `extract`, `refresh`, `live` and the CI delta with an uncaught
UnicodeEncodeError. Each acceptance value is in the docstring of its test.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree

from systemap import config, extract, facts_file, file_names, source_text, unknown_causes
from systemap.cli import main
from systemap.config import ConfigError

PY_TREE = {
    "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
    "pkg/__init__.py": "",
    "pkg/ok_é.py": "def ok() -> None: ...\n",
}
TS_TREE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "web"\n',
    "package.json": '{"name":"web"}',
    "tsconfig.json": '{"compilerOptions":{}}',
    "src/index.ts": "export function run(): void {}\n",
}
BAD = os.fsdecode(b"bad\xff\xfe")
REASON = f"source could not be read: {file_names.REASON}"


def _bad_file(path: Path, text: str = "VALUE = 1\n") -> Path:
    """Write a file with a name that is not valid UTF-8. Skip the test if the file system
    refuses the name, as some file systems do."""
    if sys.platform in {"win32", "darwin"}:
        pytest.skip("the file system does not keep a name that is not valid UTF-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(text, encoding="utf-8")
    except (OSError, UnicodeError):
        pytest.skip("the file system does not keep a name that is not valid UTF-8")
    return path


def _facts(root: Path) -> dict[str, Any]:
    return extract.build(config.load(root))


def _written(root: Path, facts: dict[str, Any]) -> dict[str, Any]:
    """Write the facts as `systemap extract` does, and read them again."""
    path = root / "docs" / "map" / "map.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    facts_file.write_facts(path, facts, root)
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def test_a_python_file_name_that_is_not_utf8_is_a_record_with_a_cause(tmp_path: Path) -> None:
    """Acceptance: the module record of `pkg/bad\\xff\\xfe.py` has the shown name, `parsed`
    false, the cause `encoding` and the reason of the name. The facts write does not stop.
    A valid UTF-8 name (`ok_é.py`) keeps its module. Before the repair, the facts write
    gave UnicodeEncodeError."""
    write_tree(tmp_path, PY_TREE)
    _bad_file(tmp_path / "pkg" / f"{BAD}.py")
    components = _written(tmp_path, _facts(tmp_path))["components"]
    record = components["pkg.bad\\xff\\xfe"]
    assert record["file"] == "pkg/bad\\xff\\xfe.py"
    assert record["package"] == "pkg"
    assert record["completeness"]["parsed"] is False
    assert record["completeness"]["cause"] == unknown_causes.ENCODING
    assert record["parse_error"]["reason"] == REASON
    assert "pkg.ok_é" in components
    assert components["pkg.ok_é"]["completeness"]["parsed"] is True


def test_a_python_file_in_a_folder_name_that_is_not_utf8_is_a_record(tmp_path: Path) -> None:
    """Acceptance: a file in a folder with a name that is not valid UTF-8 gives a record
    with the cause `encoding`. The facts write does not stop."""
    write_tree(tmp_path, PY_TREE)
    _bad_file(tmp_path / "pkg" / BAD / "inner.py")
    components = _written(tmp_path, _facts(tmp_path))["components"]
    assert components["pkg.bad\\xff\\xfe.inner"]["file"] == "pkg/bad\\xff\\xfe/inner.py"
    assert components["pkg.bad\\xff\\xfe.inner"]["completeness"]["cause"] == "encoding"


def test_a_python_test_file_name_that_is_not_utf8_is_a_test_file_issue(tmp_path: Path) -> None:
    """Acceptance: a test file with a name that is not valid UTF-8 gives a
    `test_file_issues` record with the shown name and the cause `encoding`. No test module
    record is made, and the facts write does not stop."""
    write_tree(tmp_path, {**PY_TREE, "tests/test_ok.py": "import pkg\n\ndef test_x(): ...\n"})
    _bad_file(tmp_path / "tests" / f"test_{BAD}.py", "import pkg\n")
    facts = _written(tmp_path, _facts(tmp_path))
    issues = facts["test_file_issues"]
    assert [issue["file"] for issue in issues] == ["tests/test_bad\\xff\\xfe.py"]
    assert issues[0]["problem"]["cause"] == unknown_causes.ENCODING
    assert issues[0]["problem"]["reason"] == REASON


def test_a_typescript_file_name_that_is_not_utf8_is_a_record_with_a_cause(tmp_path: Path) -> None:
    """Acceptance: the TypeScript version. `src/b\\xff.ts` gives the module `web.b\\xff`
    with `parsed` false and the cause `encoding`. A test file with such a name gives a
    `test_file_issues` record. The facts write does not stop."""
    write_tree(tmp_path, TS_TREE)
    _bad_file(tmp_path / "src" / os.fsdecode(b"b\xff.ts"), "export const B = 1;\n")
    _bad_file(tmp_path / "test" / os.fsdecode(b"t\xff.test.ts"), "import '../src/index';\n")
    facts = _written(tmp_path, _facts(tmp_path))
    record = facts["components"]["web.b\\xff"]
    assert record["file"] == "src/b\\xff.ts"
    assert record["completeness"]["parsed"] is False
    assert record["completeness"]["cause"] == unknown_causes.ENCODING
    assert record["completeness"]["reason"] == REASON
    assert facts["components"]["web.index"]["completeness"]["parsed"] is True
    issues = [issue for issue in facts["test_file_issues"] if "\\xff" in issue["file"]]
    assert [issue["file"] for issue in issues] == ["test/t\\xff.test.ts"]
    assert issues[0]["problem"]["cause"] == unknown_causes.ENCODING


def test_extract_exits_normally_with_a_file_name_that_is_not_utf8(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance: `systemap extract` exits 0 and writes facts with the record. Before the
    repair, the command stopped with a traceback of UnicodeEncodeError."""
    write_tree(tmp_path, {"pkg/__init__.py": "", "pkg/reader.py": "def read() -> None: ...\n"})
    write_tree(tmp_path, {"pkg/writer.py": "def write() -> None: ...\n"})
    init_two_cards(tmp_path, "--no-ci")
    _bad_file(tmp_path / "pkg" / f"{BAD}.py")
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "extract"]) == 0
    stored = facts_file.read_facts(tmp_path / "docs" / "map" / "map.json", tmp_path)
    assert stored["components"]["pkg.bad\\xff\\xfe"]["completeness"]["cause"] == "encoding"


def test_the_source_read_refuses_a_name_that_is_not_utf8(tmp_path: Path) -> None:
    """Acceptance: `source_text.read` gives NameNotText, a UnicodeError, for a path that is
    not valid UTF-8, and `read_problems` gives the reason and the cause `encoding`."""
    path = _bad_file(tmp_path / f"{BAD}.py")
    with pytest.raises(file_names.NameNotText):
        source_text.read(tmp_path, path)
    assert source_text.read_problems(path, tmp_path) == ("", [(REASON, "encoding")])


def test_the_directory_walks_do_not_give_a_name_that_is_not_utf8(tmp_path: Path) -> None:
    """Acceptance: `config.walk` and `config.discover_tests` do not give a folder with a
    name that is not valid UTF-8, or a folder below it."""
    _bad_file(tmp_path / BAD / "tests" / "test_a.py")
    _bad_file(tmp_path / "ok" / "tests" / "test_a.py")
    found = [path.relative_to(tmp_path).as_posix() for path in config.walk(tmp_path, bool)]
    assert found == ["ok", "ok/tests"]
    assert config.discover_tests(tmp_path, lambda folder: False) == ["ok/tests"]


def test_the_facts_write_gives_a_config_error_for_text_that_is_not_utf8(tmp_path: Path) -> None:
    """Acceptance: the last guard. A facts value that is not valid UTF-8 gives a
    ConfigError that names the cause, and no facts file."""
    path = tmp_path / "docs" / "map" / "map.json"
    path.parent.mkdir(parents=True)
    with pytest.raises(ConfigError, match="not valid UTF-8"):
        facts_file.write_facts(path, {"version": 1, "name": BAD}, tmp_path)
    assert not path.exists()


def test_the_shown_name_keeps_a_valid_name() -> None:
    """Acceptance: `file_names.shown` does not change a valid name, and shows each byte
    that is not UTF-8 as `\\xNN`."""
    assert file_names.shown("ok_é.py") == "ok_é.py"
    assert file_names.shown(f"{BAD}.py") == "bad\\xff\\xfe.py"
    assert file_names.shown("\ud800") == "\\ud800"
    assert file_names.valid("ok_é.py")
    assert not file_names.valid(BAD)


def test_a_shown_name_that_is_also_a_real_name_gives_a_config_error(tmp_path: Path) -> None:
    """Acceptance: if the shown name of a file is the name of a different module, the
    extraction gives a ConfigError that names the two files. It does not join them."""
    write_tree(tmp_path, {**PY_TREE, "pkg/bad\\xff\\xfe.py": "VALUE = 2\n"})
    _bad_file(tmp_path / "pkg" / f"{BAD}.py")
    with pytest.raises(ConfigError, match="is shared by pkg/bad"):
        _facts(tmp_path)
