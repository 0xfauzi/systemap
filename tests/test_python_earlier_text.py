"""The 2.0.0 form of the evidence has the `ast.unparse` text (issue 143).

From facts format 14, the signatures, the methods, and the `constants` previews come
from the source lines. systemap 2.0.0 and 3.0.0 got them from `ast.unparse`. Acceptance
values:

1. `python_earlier_text.record` gives the `ast.unparse` text of a function signature, an
   async function signature, a method, the method of an error class, a function in an
   `if True:` block, and three constant previews. A preview has a maximum of 80
   characters. The other values of the record do not change.
2. An answer from 2.0.0 that agrees with the source becomes current after one
   `systemap extract`, also when its module has such a value. Without `python_earlier_text`,
   the 2.0.0 form of its evidence is different. Thus the test needs `python_earlier_text`.
3. A record without a Python source file stays the same.
4. A module with too many syntax levels gives its record without a change. `extract`
   with an answer that is not current and such a module exits 0.
5. An error class and a class that is not an error, with the same name, each keep the
   methods of their own class.

A probe on this repository at 80e418b gave the evidence: with `python_earlier_text`, the 2.0.0
form gave the 6 digests that 80e418b recorded in `systemap.toml`. Without it, it gave 3
(`bench/jev/earlier_text_probe.py`, `bench/jev/README.md`).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from test_answer_identity import append, project, structural_lines

from systemap import answer_write, config, extract, judgement, nest, python_earlier_text
from systemap.cli import main

__all__ = ["project"]

ADDED = (
    "\n\nLIMIT = 200_000\n"
    'TITLE: str = "Reader"\n'
    '\n\ndef shape(size:int=1, *, name = "x") -> str:\n    return name\n'
    "\n\nclass Shape:\n    def scale(self, factor:float=2.0) -> None:\n        pass\n"
    "\n\nclass ReadError(Exception):\n    def code(self, n:int=1) -> int:\n        return n\n"
    "\n\nasync def fetch(size:int=1) -> None:\n    pass\n"
    f'\n\nLONG = "{"a" * 100}"\n'
    "\n\nif True:\n    def inside(k:int=3) -> int:\n        return k\n"
)
# The `ast.unparse` text of ADDED, as systemap 2.0.0 and 3.0.0 recorded it.
UNPARSED = {
    "LIMIT": "200000",
    "TITLE": "'Reader'",
    "shape": "def shape(size: int=1, *, name='x') -> str",
    "Shape": ["def scale(self, factor: float=2.0) -> None"],
    "ReadError": ["def code(self, n: int=1) -> int"],
    "fetch": "async def fetch(size: int=1) -> None",
    "LONG": ("'" + "a" * 100)[:80],
    "inside": "def inside(k: int=3) -> int",
}


def _records(root: Path) -> dict[str, Any]:
    cfg = config.load(root)
    return extract.build(cfg)


def _two_zero(record: dict[str, Any]) -> dict[str, Any]:
    """Give the record with the values of UNPARSED, without `python_earlier_text`."""
    out = copy.deepcopy(record)
    for item in out["functions"]:
        item["signature"] = UNPARSED.get(item["name"], item["signature"])
    for item in out["classes"] + out["errors"]:
        item["methods"] = UNPARSED.get(item["name"], item["methods"])
    for item in out["constants"]:
        item["value"] = UNPARSED.get(item["name"], item["value"])
    return out


@pytest.mark.parametrize("project", ["python"], indirect=True)
def test_the_record_has_the_unparse_text(project: Path) -> None:
    """Acceptance 1."""
    append(project, "pkg/reader.py", ADDED)
    record = _records(project)["components"]["pkg.reader"]
    assert record != _two_zero(record)
    assert python_earlier_text.record(project, record) == _two_zero(record)


@pytest.mark.parametrize("project", ["python"], indirect=True)
def test_an_answer_from_2_0_0_with_changed_text_becomes_current(project: Path) -> None:
    """Acceptance 2."""
    append(project, "pkg/reader.py", ADDED)
    assert main(["--root", str(project), "extract"]) == 0
    line = structural_lines(project)[0]
    cfg = config.load(project)
    tree = nest.load(cfg)
    facts = extract.build(cfg)
    before = copy.deepcopy(facts)
    before["components"]["pkg.reader"] = _two_zero(facts["components"]["pkg.reader"])
    old = judgement.evidence_for_tree(tree, before, project, [line], earlier=True)[line]
    without = judgement.evidence_for_tree(tree, facts, project, [line], earlier=True)[line]
    assert old != without
    answer_write.add(project, cfg.source, [{"item": line, "reason": "A test.", "evidence": old}])
    assert main(["--root", str(project), "extract"]) == 0
    now = judgement.evidence_for_tree(tree, facts, project, [line])[line]
    assert config.load(project).judgement_answered[-1].evidence == now


def test_a_record_without_python_source_stays_the_same(tmp_path: Path) -> None:
    """Acceptance 3."""
    (tmp_path / "service.ts").write_text("export const LIMIT = 200_000;\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def f(:\n", encoding="utf-8")
    for name in ("service.ts", "broken.py", "missing.py"):
        record = {"file": name, "constants": [{"name": "LIMIT", "value": "200_000"}]}
        assert python_earlier_text.record(tmp_path, record) == record


# A module with too many syntax levels for `ast.parse` on each supported Python version.
# Python 3.13 and later parse 3000 terms, so the text has 200000 terms, as in
# tests/test_depth_limits.py.
DEEP = "X = " + "+".join(["1"] * 200000) + "\n"


def test_a_module_that_is_too_deep_stays_the_same(tmp_path: Path) -> None:
    """Acceptance 4: the record."""
    (tmp_path / "deep.py").write_text(DEEP, encoding="utf-8")
    record = {"file": "deep.py", "constants": [{"name": "X", "value": "?"}]}
    assert python_earlier_text.record(tmp_path, record) == record


@pytest.mark.parametrize("project", ["python"], indirect=True)
def test_extract_with_a_pending_answer_and_a_module_that_is_too_deep(project: Path) -> None:
    """Acceptance 4: `extract`."""
    line = structural_lines(project)[0]
    cfg = config.load(project)
    answer = {"item": line, "reason": "A test.", "evidence": "0" * 64}
    answer_write.add(project, cfg.source, [answer])
    (project / "pkg" / "deep.py").write_text(DEEP, encoding="utf-8")
    assert main(["--root", str(project), "extract"]) == 0


# An error class and a class that is not an error, with the same name.
SAME_NAME = (
    "\n\nclass Thing(Exception):\n    def a(self, x:int=1): ...\n"
    "\n\nclass Thing:\n    def b(self, y:int=2): ...\n"
)


@pytest.mark.parametrize("project", ["python"], indirect=True)
def test_an_error_and_a_class_with_the_same_name_keep_their_methods(project: Path) -> None:
    """Acceptance 5."""
    append(project, "pkg/reader.py", SAME_NAME)
    record = _records(project)["components"]["pkg.reader"]
    out = python_earlier_text.record(project, record)
    errors = [item["methods"] for item in out["errors"] if item["name"] == "Thing"]
    classes = [item["methods"] for item in out["classes"] if item["name"] == "Thing"]
    assert errors == [["def a(self, x: int=1)"]]
    assert classes == [["def b(self, y: int=2)"]]
