"""The import crossing rules of `judgement`: the run-time filter and the refused answers.

Acceptance values:

1. A family answer (`kind`, `crossing`, `crossing_into`, `crossing_from`) for a
   `crossing import`, `module use`, or `declared flow` line is a refused answer with the
   cause `family`. The report does not apply it, and it is not stale.
2. A family answer for a different kind, for example `kind = "unknown surface"`, is
   accepted as before.
3. An answer with two or more items is refused (cause `items`) when one item is a line
   of these kinds. An answer with one item for a `crossing import` line is accepted.
4. The report gives one `refused answer:` row for each refused answer after the
   `policy answer:` rows, and `judgement --strict` exits 1 while an answer is refused.
5. A component pair whose imports all operate only for type checks gives no
   `crossing import` line. A pair with a type import and a load import keeps its line,
   and the evidence digest of the line does not change.
6. With `--verbose`, the rows give each import only in a function body, each import by
   a string value, and a row when the adapter does not find imports for type checks.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from conftest import init_two_cards, write_tree

from systemap import judgement, judgement_json, nest, refused_answers
from systemap.cli import main
from systemap.config import Answer
from systemap.model import Component, Meaning, Model, Region

CROSSING = "crossing import: P imports Q and no flow connects them"
DECLARED = "declared flow: P -> Q (rows) has no import evidence and no mechanism"
SURFACE = "unknown surface: p.a has a record that the adapter cannot read"


def test_family_answers_of_the_three_kinds_are_refused() -> None:
    """Acceptance 1 and 2."""
    lines = [CROSSING, "Sub: " + CROSSING, DECLARED, SURFACE]
    for kind in refused_answers.NO_FAMILY_KINDS:
        answer = Answer((), "a family", kind=kind, policy=True)
        assert refused_answers.form(answer) == ("family", kind)
        result = judgement.apply_answers(lines, [answer], {})
        assert result.open == lines and result.stale == [] and result.policies == []
    for form in ({"crossing": ("P", "Q")}, {"crossing_into": "Q"}, {"crossing_from": "P"}):
        answer = Answer((), "a family", policy=True, **form)  # type: ignore[arg-type]
        assert refused_answers.form(answer) == ("family", "crossing import")
    surface = Answer((), "the parser cannot read it", kind="unknown surface", policy=True)
    assert refused_answers.form(surface) is None
    result = judgement.apply_answers(lines, [surface], {})
    assert result.open == lines[:3] and len(result.policies) == 1
    found = refused_answers.texts([Answer((), "a family", kind="crossing import")], lines)
    assert found == [
        {
            "answer": 'kind = "crossing import"',
            "items": [],
            "cause": "family",
            "text": 'kind = "crossing import" selects 2 lines. A family answer cannot close a '
            "crossing import line. Remove the answer. Then give one exact answer for each line. "
            "Give the module use answers first.",
            "lines": 2,
        }
    ]


def test_an_answer_for_a_crossing_import_line_must_have_one_item() -> None:
    """Acceptance 3."""
    lines = [CROSSING, SURFACE, DECLARED]
    evidence = {line: "e" for line in lines}
    two = Answer(
        (CROSSING, SURFACE),
        "two lines",
        evidence=judgement.answer_digest([CROSSING, SURFACE], evidence),
    )
    assert refused_answers.form(two) == ("items", "crossing import")
    result = judgement.apply_answers(lines, [two], evidence)
    assert result.open == lines and result.stale == [] and result.pending == []
    assert refused_answers.texts([two], lines)[0]["text"] == (
        f"items = {[CROSSING, SURFACE]} has 2 items. An answer for a crossing import line "
        "must have one item. Give one exact answer for each line."
    )
    prefixed = Answer(("Sub: " + DECLARED, SURFACE), "two lines")
    assert refused_answers.form(prefixed) == ("items", "declared flow")
    assert refused_answers.form(Answer((SURFACE, SURFACE + " too"), "two")) is None
    one = Answer((CROSSING,), "one line", evidence=judgement.answer_digest([CROSSING], evidence))
    assert refused_answers.form(one) is None
    assert judgement.apply_answers(lines, [one], evidence).open == [SURFACE, DECLARED]


def test_the_report_rows_and_the_strict_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Acceptance 4."""
    shown = judgement.Answered(
        [SURFACE], 0, [], policies=["a policy row"], refused=["the refused text"]
    )
    assert judgement.report(shown, teach=False)[-2:] == [
        "  policy answer: a policy row",
        "  refused answer: the refused text",
    ]
    assert judgement_json.Judged([], {}, judgement.Answered([], 0, [], refused=["x"])).blocking
    assert not judgement_json.Judged([], {}, judgement.Answered([], 0, [])).blocking
    write_tree(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/reader.py": "def read(source: str) -> str:\n    return source\n",
            "pkg/writer.py": "from pkg.reader import read\n\n\ndef write(r: str) -> str:\n"
            "    return read(r)\n",
        },
    )
    init_two_cards(tmp_path, "--no-ci")
    assert main(["--root", str(tmp_path), "extract"]) == 0
    toml = tmp_path / "systemap.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8")
        + "\n[judgement]\nanswered = [\n"
        + '    { kind = "single module", policy = true, reason = "two real parts" },\n'
        + '    { kind = "thin layer", policy = true, reason = "nothing drives anything" },\n'
        + '    { kind = "flow review", policy = true, reason = "the flow is reviewed" },\n'
        + '    { kind = "declared flow", policy = true, reason = "a family" },\n]\n',
        encoding="utf-8",
    )
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "judgement", "--strict"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("judgement: No possible map error to examine")
    assert '  refused answer: kind = "declared flow" selects 0 lines.' in out
    assert main(["--root", str(tmp_path), "judgement", "--strict", "--json"]) == 1
    capsys.readouterr()


def crossing_model() -> tuple[nest.Tree, dict[str, Any]]:
    model = Model(
        canvas=(400, 200),
        containers=(),
        regions=(Region("all", "ALL", (16, 16, 368, 168)),),
        components=(
            Component("P", "does p", implemented_by=("p.a",), entry="a", region="all"),
            Component("Q", "does q", implemented_by=("q.x", "q.y"), entry="x", region="all"),
        ),
        flows=(),
        flow_kinds=(),
    )
    meaning = Meaning(plain={"P": "p", "Q": "q"}, relations={})
    top = nest.Map(id="", path=Path("map/model.py"), rel="", model=model, meaning=meaning, theme={})
    facts = {
        "import_details": ["call", "dynamic", "type"],
        "components": {
            "p.a": {
                "functions": [{"name": "a"}],
                "classes": [],
                "uses": {"q.x": ["X"], "q.y": ["Y"]},
            },
            "q.x": {"functions": [], "classes": [{"name": "X"}], "uses": {}},
            "q.y": {"functions": [], "classes": [{"name": "Y"}], "uses": {}},
        },
    }
    return nest.Tree((top,)), facts


def test_imports_only_for_type_checks_give_no_crossing_import_line(tmp_path: Path) -> None:
    """Acceptance 5."""
    tree, facts = crossing_model()
    model = tree.top.model
    lines = judgement.crossing_imports_without_flow(model, facts)
    assert lines == [CROSSING]
    before = judgement.evidence_for_tree(tree, facts, tmp_path, lines)[CROSSING]
    # One import for type checks and one at load: the line and its digest stay.
    mixed = copy.deepcopy(facts)
    mixed["components"]["p.a"]["import_forms"] = {"q.y": ["load", "type"], "q.x": ["type"]}
    assert judgement.crossing_imports_without_flow(model, mixed) == [CROSSING]
    assert judgement.evidence_for_tree(tree, mixed, tmp_path, lines)[CROSSING] == before
    assert judgement.crossing_imports(model, mixed)[("P", "Q")] == [("p.a", "q.x"), ("p.a", "q.y")]
    # Each import only for type checks: no line. The full list is still available.
    typed = copy.deepcopy(facts)
    typed["components"]["p.a"]["import_forms"] = {"q.x": ["type"], "q.y": ["type"]}
    assert judgement.crossing_imports_without_flow(model, typed) == []
    owner = {"p.a": "P", "q.x": "Q", "q.y": "Q"}
    assert judgement.crossing_pairs(typed["components"], owner) == {}
    assert judgement.crossing_pairs(typed["components"], owner, runtime_only=False) == {
        ("P", "Q"): [("p.a", "q.x"), ("p.a", "q.y")]
    }


def test_the_rows_give_the_import_forms_and_the_imports_by_a_string_value() -> None:
    """Acceptance 6."""
    tree, facts = crossing_model()
    model = tree.top.model
    assert judgement.crossing_detail(model, facts) == {
        CROSSING: ["p.a imports q.x", "p.a imports q.y"]
    }
    record = facts["components"]["p.a"]
    record["import_forms"] = {"q.x": ["call"], "q.y": ["call", "load"]}
    record["dynamic_imports"] = [
        {"call": "import_module", "text": "q.x", "target": "q.x", "line": 4},
        {"call": "__import__", "text": "", "target": "", "line": 9},
    ]
    facts["import_details"] = ["call", "dynamic"]
    assert judgement.crossing_detail(model, facts, "Sub: ")["Sub: " + CROSSING] == [
        "p.a imports q.x",
        "p.a imports q.y",
        "p.a imports q.x only in a function body.",
        "p.a imports a module by a string value at line 4: import_module(q.x).",
        "p.a imports a module by a string value at line 9: __import__(a value).",
        "The language adapter does not find imports for type checks. Thus each import "
        "counts as an import at run time.",
    ]
