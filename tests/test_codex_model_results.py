"""Regression tests for the Codex results model-4 to model-14 (model-12 excluded).

Each test shows the failure on `origin/main` at d4b1514 before the repair.

Acceptance values:

1. model-4: An interface that starts with a Unicode public name, or names a Unicode
   method, gives no finding. An interface with an unknown Unicode method gives a finding.
   This holds for a Python fixture and a TypeScript fixture.
2. model-5: A change to the target of an entry point changes the evidence digest of
   its `entry point` line.
3. model-6: A change to a layer description in an imported model file changes the
   evidence digest of a line that names nothing.
4. model-7: A flow with an actor endpoint keeps the external state and keeps its
   source records and the unresolved records. `systemap review` refuses the flow.
5. model-8: A module `unknown surface` line occurs once, in the map that owns the
   module. A repository line occurs once, in the top map. An exact answer to the
   earlier top-map line still applies to the moved line.
6. model-9: Two regions with the same id, two containers with the same id, and a region
   and a container with the same id each give a placement finding.
7. model-10: An empty or whitespace-only relation sentence gives a meaning finding.
8. model-11: Two components that open the same nested model file give a configuration
   error before the loader reads the file a second time.
9. model-13: A sequence that names a component only in `starts` is a claim of that
   component.
10. model-14: The flow explanation does not say that the question has no instance-call
    evidence, because the context contains instance calls.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_nested import CONFIG, MODELS, TREE, edit, nested

from systemap import (
    audit_code,
    card_review,
    check,
    config,
    decision_kinds,
    evidence,
    explain,
    extract,
    facts_file,
    judgement,
    judgement_json,
    nest,
    review,
)
from systemap.config import Answer, ConfigError
from systemap.model import (
    Component,
    Container,
    Flow,
    Journey,
    Meaning,
    Model,
    Region,
    Step,
    meaning_problems,
)

__all__ = ["nested"]


# ---- model-4: Unicode identifiers in an interface ---------------------------------

PYTHON_SOURCE = {
    "systemap.toml": '[package_roots]\n"pkg" = "pkg"\n',
    "pkg/__init__.py": "",
    "pkg/reader.py": (
        "def 読み取る(source: str) -> str:\n    return source\n\n\n"
        "def लिखो(text: str) -> str:\n    return text\n\n\n"
        "class Ledger:\n"
        "    def 読む(self) -> int:\n        return 1\n\n"
        "    def लिखो(self) -> int:\n        return 2\n"
    ),
}
TYPESCRIPT_SOURCE = {
    "systemap.toml": 'language = "typescript"\n[package_roots]\n"src" = "pkg"\n',
    "tsconfig.json": "{}",
    "src/reader.ts": (
        "export function 読み取る(source: string): string { return source; }\n"
        "export function लिखो(text: string): string { return text; }\n"
        "export class Ledger {\n"
        "  読む(): number { return 1; }\n"
        "  लिखो(): number { return 2; }\n"
        "}\n"
    ),
}


@pytest.mark.parametrize("files", [PYTHON_SOURCE, TYPESCRIPT_SOURCE], ids=["python", "typescript"])
def test_model_4_unicode_interface_names(tmp_path: Path, files: dict[str, str]) -> None:
    write_tree(tmp_path, files)
    facts = extract.build(config.load(tmp_path))
    components = facts["components"]
    assert "pkg.reader" in components

    def problem(interface: str) -> str:
        card = Component(
            id="Reader", does="Reads.", interface=interface, implemented_by=("pkg.reader",)
        )
        return check.interface_problem(card, components)

    assert problem("読み取る(source) -> text") == ""
    assert problem("लिखो(text) -> text") == ""
    assert problem("Ledger.読む() -> number") == ""
    assert problem("Ledger.लिखो() -> number") == ""
    assert "Ledger.書く" in problem("Ledger.書く() -> number")
    assert "starts with 書く" in problem("書く(source)")


def test_model_4_identifier_ends_at_a_token_boundary() -> None:
    assert check.interface_head("  読み取る(source)") == ("読み取る", "")
    assert check.interface_head("Ledger.लिखो()") == ("Ledger", "लिखो")
    assert check.interface_head("$el.on$(x)") == ("$el", "on$")
    assert check.interface_head("2fast()") is None
    assert check.interface_head("(x)") is None


# ---- model-5: the entry point target is evidence ----------------------------------


def _entry_facts(target: str) -> dict[str, Any]:
    record = {
        "file": "pkg/cli.py",
        "names": [{"name": "start", "kind": "function"}, {"name": "stop", "kind": "function"}],
    }
    point = {
        "kind": "console_script",
        "module": "pkg.cli",
        "target": target,
        "name": "tool",
        "label": "tool (console script)",
    }
    return {"components": {"pkg.cli": record}, "entry_points": [point]}


def _one_map(tmp_path: Path, model: Model, meaning: Meaning) -> nest.Tree:
    path = tmp_path / "map" / "model.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("MODEL = None\n", encoding="utf-8")
    return nest.Tree((nest.Map("", path, "map/model.py", model, meaning, {}, None, ""),))


def test_model_5_entry_point_target_changes_the_evidence(tmp_path: Path) -> None:
    write_tree(tmp_path, {"pkg/cli.py": "def start():\n    pass\n\n\ndef stop():\n    pass\n"})
    card = Component(id="Cli", does="Starts.", implemented_by=("pkg.cli",), entry="start")
    model = Model((0, 0), (), (), (card,), (), ())
    tree = _one_map(tmp_path, model, Meaning(plain={"Cli": "the command"}))
    line = "entry point tool (console script) has no sequence (component Cli)"
    before = _entry_facts("start")
    assert line in judgement.run_tree(tree, before)
    after = _entry_facts("stop")
    assert line in judgement.run_tree(tree, after)
    old = judgement.evidence_for_tree(tree, before, tmp_path, [line])[line]
    new = judgement.evidence_for_tree(tree, after, tmp_path, [line])[line]
    assert old != new


# ---- model-6: imported model files are evidence -----------------------------------


def test_model_6_imported_model_file_changes_the_full_evidence(nested: Path) -> None:
    write_tree(
        nested,
        {
            "map/extra.py": (
                "from systemap import Layer\n\n"
                'LAYERS = (Layer(id="extra", label="EXTRA", question="Q?", sub="first"),)\n'
            )
        },
    )
    edit(nested, "map/model.py", "from systemap import", "import extra\nfrom systemap import")
    edit(
        nested,
        "map/model.py",
        "MEANING = Meaning(\n",
        "MEANING = Meaning(\n    layers=extra.LAYERS,\n",
    )
    cfg = config.load(nested)
    facts = facts_file.read_facts(cfg.facts_path)
    assert facts is not None
    line = "thin layer: extra shows 0 components"
    assert line in judgement.run_tree(nest.load(cfg), facts)
    old = judgement.evidence_for_tree(nest.load(cfg), facts, nested, [line])[line]
    edit(nested, "map/extra.py", 'sub="first"', 'sub="second"')
    assert line in judgement.run_tree(nest.load(cfg), facts)
    new = judgement.evidence_for_tree(nest.load(cfg), facts, nested, [line])[line]
    assert old != new


# ---- model-7: an external flow keeps its review values ----------------------------

OBSOLETE = "pkg.reader:read@" + "0" * 64


def _actor_flow() -> tuple[Model, Meaning, Flow, dict[str, Any]]:
    flow = Flow("User", "Reader", "input", "data", source_refs=(OBSOLETE,))
    meaning = Meaning(plain={}, relations={("User", "Reader"): "The user gives the input."})
    flow = dataclasses.replace(flow, review_digest=evidence.flow_claim_digest(flow, meaning))
    model = Model(
        (0, 0),
        (),
        (),
        (
            Component(id="User", does="Types.", kind="actor"),
            Component(id="Reader", does="Reads.", implemented_by=("pkg.reader",), entry="read"),
        ),
        (flow,),
        (),
    )
    record = {
        "file": "pkg/reader.py",
        "source_sha256": "1" * 64,
        "names": [{"name": "read", "kind": "function"}],
        "completeness": {"parsed": True},
    }
    return model, meaning, flow, {"components": {"pkg.reader": record}}


def test_model_7_external_flow_keeps_unresolved_records(tmp_path: Path) -> None:
    model, meaning, flow, facts = _actor_flow()
    found = evidence.of_model(model, meaning, facts).of(flow)
    assert found.state == evidence.EXTERNAL
    assert found.source_refs == (OBSOLETE,)
    assert found.unresolved_refs == (OBSOLETE,)
    tree = _one_map(tmp_path, model, meaning)
    target = review.Target(flow=flow.key, found=flow)
    with pytest.raises(review.ReviewError, match="do not agree with the current source"):
        review._digest(tree.top, model, meaning, facts, target)
    # The judgement gives no new line for the external flow.
    assert judgement.flow_review(model, meaning, facts) == []


# ---- model-8: one unknown-surface line in the map that owns the module ------------


def _unknown_facts(root: Path) -> dict[str, Any]:
    facts = facts_file.read_facts(config.load(root).facts_path)
    assert facts is not None
    facts["components"]["pkg.gateway.app"]["unknown"] = [{"line": 3, "reason": "a dynamic import"}]
    facts["entry_point_issues"] = [
        {"kind": "console_script", "name": "tool", "target": "pkg.x:y", "reason": "no module"}
    ]
    return facts


MODULE_LINE = "unknown surface: module pkg.gateway.app (pkg/gateway/app.py:3): a dynamic import"
REPOSITORY_LINE = "unknown surface: console_script tool -> pkg.x:y: no module"


def test_model_8_unknown_surface_lines_occur_once(nested: Path) -> None:
    facts = _unknown_facts(nested)
    lines = judgement.run_tree(nest.load(config.load(nested)), facts)
    unknown = [line for line in lines if "unknown surface" in line]
    assert unknown == [REPOSITORY_LINE, "Gateway: " + MODULE_LINE]


def test_model_8_earlier_top_line_answer_moves_with_the_line(nested: Path) -> None:
    facts = _unknown_facts(nested)
    cfg = config.load(nested)
    tree = nest.load(cfg)
    lines = judgement.run_tree(tree, facts)
    # The digest that the earlier top-map line had is the digest of the moved line.
    digest = judgement.evidence_for_tree(tree, facts, nested, [MODULE_LINE])[MODULE_LINE]
    moved = judgement.evidence_for_tree(tree, facts, nested, lines)["Gateway: " + MODULE_LINE]
    assert digest == moved
    earlier = Answer(items=(MODULE_LINE,), reason="The import is examined.", evidence=digest)
    cfg = dataclasses.replace(cfg, judgement_answered=(earlier,))
    judged = judgement_json.evaluate(tree, facts, cfg)
    assert "Gateway: " + MODULE_LINE not in judged.result.open
    assert judged.result.stale == []
    assert judged.result.pending == []


# ---- model-9: duplicate region and container ids ----------------------------------


def _boxes(regions: tuple[Region, ...], containers: tuple[Container, ...]) -> list[str]:
    return Model((0, 0), containers, regions, (), (), ()).layout_problems()


def test_model_9_duplicate_boundary_ids() -> None:
    box = (0, 0, 100, 100)
    outer = Container("c", "C", box)
    two_regions = _boxes((Region("r", "R1", box, "c"), Region("r", "R2", box, "c")), (outer,))
    assert any("region r is the id of two regions" in p for p in two_regions)
    two_containers = _boxes((), (outer, Container("c", "D", box)))
    assert any("container c is the id of two containers" in p for p in two_containers)
    shared = _boxes((Region("c", "R", box, "c"),), (outer,))
    assert any("region c has the id of a container" in p for p in shared)
    assert _boxes((Region("r", "R", box, "c"),), (outer,)) == []


# ---- model-10: an empty relation sentence -----------------------------------------


@pytest.mark.parametrize("sentence", ["", "   "])
def test_model_10_empty_relation_sentence(sentence: str) -> None:
    model = Model(
        (0, 0),
        (),
        (),
        (Component(id="A", does="A."), Component(id="B", does="B.")),
        (Flow("A", "B", "data", "data"),),
        (),
    )
    meaning = Meaning(plain={"A": "a", "B": "b"}, relations={("A", "B"): sentence})
    assert "flow A -> B has no sentence in relations" in meaning_problems(model, meaning)


# ---- model-11: one nested model file for one opening component --------------------


def test_model_11_a_model_file_opened_twice_is_refused(tmp_path: Path) -> None:
    second = MODELS["map/model.py"].replace('map="style.py"', 'map="gateway.py"')
    write_tree(tmp_path, {**TREE, "systemap.toml": CONFIG, **MODELS, "map/model.py": second})
    with pytest.raises(
        ConfigError, match="Style opens map/gateway.py, but the map Gateway uses this file"
    ):
        nest.load(config.load(tmp_path))


# ---- model-13: a sequence that starts at a component ------------------------------


def test_model_13_sequence_start_is_a_component_claim() -> None:
    model = Model(
        (0, 0),
        (),
        (),
        (
            Component(id="Gateway", does="Takes."),
            Component(id="A", does="A."),
            Component(id="B", does="B."),
        ),
        (Flow("A", "B", "data", "data"),),
        (),
    )
    step = Step(("A",), (), ("A", "B"), "A gives data to B.")
    first = Meaning(plain={}, journeys=(Journey("j", "J", (step,), starts="Gateway"),))
    second = Meaning(plain={}, journeys=(Journey("j", "J changed", (step,), starts="Gateway"),))
    gateway = model.components[0]
    assert card_review.claims(gateway, model, first) != card_review.claims(gateway, model, second)


# ---- model-14: the flow explanation agrees with the call-site context --------------


def test_model_14_flow_explanation_agrees_with_the_context() -> None:
    assert "property of a local name" in (audit_code.__doc__ or "")
    lesson = explain.AUDIT[decision_kinds.FLOW]
    assert "no instance-call evidence" not in lesson.do
    assert "instance call" not in lesson.do
