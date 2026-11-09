"""The 2.0.0 form of the evidence has the `ast.unparse` text (issue 143).

From facts format 14, the signatures, the methods, and the `constants` previews come
from the source lines. systemap 2.0.0 and 3.0.0 got them from `ast.unparse`. Acceptance
values:

1. `python_earlier_text.record` gives the `ast.unparse` text of a function signature, a method,
   and two constant previews. The other values of the record do not change.
2. An answer from 2.0.0 that agrees with the source becomes current after one
   `systemap extract`, also when its module has such a value. Without `python_earlier_text`,
   the 2.0.0 form of its evidence is different. Thus the test needs `python_earlier_text`.
3. A record without a Python source file stays the same.

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
)
# The `ast.unparse` text of ADDED, as systemap 2.0.0 and 3.0.0 recorded it.
UNPARSED = {
    "LIMIT": "200000",
    "TITLE": "'Reader'",
    "shape": "def shape(size: int=1, *, name='x') -> str",
    "Shape": ["def scale(self, factor: float=2.0) -> None"],
}


def _records(root: Path) -> dict[str, Any]:
    cfg = config.load(root)
    return extract.build(cfg)


def _two_zero(record: dict[str, Any]) -> dict[str, Any]:
    """Give the record with the values of UNPARSED, without `python_earlier_text`."""
    out = copy.deepcopy(record)
    for item in out["functions"]:
        item["signature"] = UNPARSED.get(item["name"], item["signature"])
    for item in out["classes"]:
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
