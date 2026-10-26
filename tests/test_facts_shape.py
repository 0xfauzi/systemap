"""Stored facts with an incorrect shape, and the namespace set of a Python extraction.

A committed facts file can contain values that extraction does not write. Before the
shape check, each case below stopped judgement, check, render, facts, or refresh with a
traceback. The namespace tests count the work of one Python extraction.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import TINY_PACKAGE, init_two_cards, write_tree

from systemap import config, extraction, facts_file, facts_shape, python_imports
from systemap.cli import main


def run(*argv: str) -> int:
    return main(list(argv))


# ---- the namespace set -------------------------------------------------------------


def _earlier_namespaces(known: set[str]) -> set[str]:
    """The set comprehension that python_unresolved used before, for each module."""
    return {
        ".".join(name.split(".")[:end]) for name in known for end in range(1, len(name.split(".")))
    }


def test_namespace_packages_are_the_prefixes_of_each_module() -> None:
    known = {"a", "a.b", "a.b.c", "x.y.z.w", ".lead", "two..dots", "end."}
    assert python_imports.namespace_packages(known) == _earlier_namespaces(known)
    assert python_imports.namespace_packages({"a.b.c"}) == {"a", "a.b"}


def test_one_extraction_calculates_the_namespace_set_one_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before the fix, python_unresolved calculated the set for each module. Thus the
    time grew with the square of the module count: 4161 modules took 16.6 s in it."""
    files = {"pyproject.toml": '[project]\nname = "wide"\n', "pkg/__init__.py": ""}
    for group in range(3):
        files[f"pkg/g{group}/__init__.py"] = ""
        for index in range(10):
            text = f"from pkg.g{group} import m{(index + 1) % 10}\nfrom .absent import x\n"
            files[f"pkg/g{group}/m{index}.py"] = text
    write_tree(tmp_path, files)
    calls: list[int] = []
    original = python_imports.namespace_packages

    def counted(known: Any) -> frozenset[str]:
        calls.append(len(known))
        return original(known)

    monkeypatch.setattr(python_imports, "namespace_packages", counted)
    facts = extraction.build(config.load(tmp_path))
    assert len(facts["components"]) == 34
    assert calls == [34]
    record = facts["components"]["pkg.g0.m0"]
    assert record["completeness"]["unresolved_imports"] == [".absent"]


def test_the_namespace_cache_calculates_again_for_a_different_module_set() -> None:
    cache = python_imports.NamespaceCache()
    first = {"a.b"}
    assert cache.of(first) == {"a"}
    assert cache.of(first) is cache.of(first)
    assert cache.of({"c.d"}) == {"c"}


# ---- the shape of the stored facts -------------------------------------------------


@pytest.fixture(scope="module")
def good(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("good")
    write_tree(root, TINY_PACKAGE)
    write_tree(root, {"pkg/__main__.py": "from pkg.reader import read\nread('x')\n"})
    facts = extraction.build(config.load(root))
    # The records that some readers index, so that each case has a record to change.
    facts["entry_point_issues"] = [
        {"cause": "target", "kind": "package_bin", "name": "t", "reason": "r", "target": "x"}
    ]
    facts["components"]["pkg.reader"]["unknown"] = [{"cause": "syntax", "line": 1, "reason": "r"}]
    return facts


def _set(*keys: str | int, value: Any) -> Callable[[dict[str, Any]], None]:
    def change(data: dict[str, Any]) -> None:
        target: Any = data
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value

    return change


def _drop(*keys: str | int) -> Callable[[dict[str, Any]], None]:
    def change(data: dict[str, Any]) -> None:
        target: Any = data
        for key in keys[:-1]:
            target = target[key]
        del target[keys[-1]]

    return change


READER = ("components", "pkg.reader")
# Each case, and the problem text. The g1ts-8 and g1full-6 cases come first.
CASES: dict[str, tuple[Callable[[dict[str, Any]], None], str]] = {
    "components list": (
        _set("components", value=[]),
        'the value at ["components"] must be an object',
    ),
    "names integer": (
        _set(*READER, "names", value=5),
        'the value at ["components"]["pkg.reader"]["names"] must be a list',
    ),
    "unknown without reason": (
        _drop(*READER, "unknown", 0, "reason"),
        'the value at ["components"]["pkg.reader"]["unknown"][0] has no "reason" key',
    ),
    "entry issue without kind": (
        _drop("entry_point_issues", 0, "kind"),
        'the value at ["entry_point_issues"][0] has no "kind" key',
    ),
    "absolute file": (
        _set(*READER, "file", value="/etc/reader.py"),
        'the value at ["components"]["pkg.reader"]["file"] must be a relative path',
    ),
    "windows drive file": (
        _set(*READER, "file", value="C:/reader.py"),
        'the value at ["components"]["pkg.reader"]["file"] must be a relative path',
    ),
    "no components": (_drop("components"), 'the file has no "components" key'),
    "record text": (
        _set(*READER, value="x"),
        'the value at ["components"]["pkg.reader"] must be an object',
    ),
    "entry points text": (
        _set("entry_points", value="x"),
        'the value at ["entry_points"] must be a list',
    ),
    "uses list": (
        _set(*READER, "uses", value=["pkg"]),
        'the value at ["components"]["pkg.reader"]["uses"] must be an object',
    ),
    "boolean count": (
        _set(*READER, "tests_total", value=True),
        'the value at ["components"]["pkg.reader"]["tests_total"] must be an integer',
    ),
    "deep value": (
        _set(*READER, "api", value=json.loads("[" * 40 + "]" * 40)),
        "the JSON value has more than 32 levels",
    ),
}


def test_the_facts_that_extraction_writes_have_the_correct_shape(good: dict[str, Any]) -> None:
    assert facts_shape.problem(good) is None
    # A key that extraction does not write is permitted.
    assert facts_shape.problem({**good, "later_field": [1, {"a": None}]}) is None


@pytest.mark.parametrize("case", sorted(CASES))
def test_each_incorrect_shape_gives_its_problem(good: dict[str, Any], case: str) -> None:
    change, text = CASES[case]
    data = copy.deepcopy(good)
    change(data)
    assert facts_shape.problem(data) == text


def test_read_facts_gives_an_error_for_an_incorrect_shape(
    tmp_path: Path, good: dict[str, Any]
) -> None:
    path = tmp_path / "docs/map/map.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({**good, "components": []}), encoding="utf-8")
    with pytest.raises(facts_shape.FactsError, match=r"docs/map/map.json does not have"):
        facts_file.read_facts(path, tmp_path)
    # Before the fix, the JSON parser stopped with a RecursionError.
    path.write_text('{"x":' + "[" * 100000 + "]" * 100000 + "}", encoding="utf-8")
    with pytest.raises(facts_shape.FactsError, match="has more than 32 levels"):
        facts_file.read_facts(path, tmp_path)
    # An empty object, a JSON list, and text that is not JSON stay "no facts".
    for text in ("{}", "[]", "{"):
        path.write_text(text, encoding="utf-8")
        assert facts_file.read_facts(path, tmp_path) == {}
    path.write_text(facts_file.dumps(good), encoding="utf-8")
    assert facts_file.read_facts(path, tmp_path) == good


def test_commands_give_the_error_and_refresh_writes_a_new_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_tree(tmp_path, TINY_PACKAGE)
    init_two_cards(tmp_path, "--no-ci")
    root = ("--root", str(tmp_path))
    assert run(*root, "extract") == 0
    path = tmp_path / "docs/map/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"]["pkg.reader"]["file"] = "/etc/reader.py"
    path.write_text(json.dumps(data), encoding="utf-8")
    capsys.readouterr()
    for command in ("judgement", "check", "render", "facts", "rules"):
        assert run(*root, command) == 1, command
        err = capsys.readouterr().err
        assert "does not have the shape that extraction writes" in err, command
        assert "Use systemap refresh or systemap extract" in err, command
    assert run(*root, "extract", "--check") == 1
    capsys.readouterr()
    # Refresh and extract must replace a file that read_facts refuses.
    run(*root, "refresh")
    assert facts_shape.problem(json.loads(path.read_text(encoding="utf-8"))) is None
    path.write_text(json.dumps({**data, "components": []}), encoding="utf-8")
    assert run(*root, "extract") == 0
    assert facts_shape.problem(json.loads(path.read_text(encoding="utf-8"))) is None
