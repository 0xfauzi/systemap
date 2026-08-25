from __future__ import annotations

import dataclasses

from conftest import sample_model

from systemap.model import (
    Component,
    Container,
    Flow,
    Invariant,
    Journey,
    Layer,
    Meaning,
    Model,
    Region,
    Step,
    build_state,
    claimed,
    meaning_problems,
    module_matches,
    problems,
)


def test_sample_validates() -> None:
    model, meaning = sample_model()
    assert problems(model, meaning) == []


def test_sample_flow_endpoints_resolve() -> None:
    model, _ = sample_model()
    ids = model.ids
    for f in model.flows:
        assert f.src in ids, f
        assert f.dst in ids, f
        assert f.kind in model.flow_kinds


def test_sample_every_flow_has_a_relation_and_a_layer() -> None:
    model, meaning = sample_model()
    layer_ids = {layer.id for layer in meaning.layers}
    for f in model.flows:
        assert f.edge in meaning.relations, f
        assert meaning.layer_for(f.edge, f.kind) in layer_ids, f
    assert meaning.layer_for(("Ledger", "Parser"), "record") == "memory"
    assert meaning.verb_for(("User", "Reader"), "work", True) == "types into"
    assert meaning.verb_for(("Reader", "Parser"), "work", False) == "receives from"


def test_sample_journeys_resolve() -> None:
    model, meaning = sample_model()
    ids = model.ids
    edges = {f.edge for f in model.flows}
    for j in meaning.journeys:
        for step in j.steps:
            assert step.edge in edges, (j.id, step.edge)
            assert set(step.acts) <= ids
            assert set(step.measures) <= ids


def test_sample_positions_and_plain_words() -> None:
    model, meaning = sample_model()
    assert model.layout_problems() == []
    assert set(meaning.plain) == model.ids
    assert model.component("User").kind == "actor"
    assert model.rules_of("Writer") == [1, 2]


def small_model() -> tuple[Model, Meaning]:
    model = Model(
        canvas=(600, 300),
        containers=(Container("sys", "SYS", (16, 16, 568, 268), tone="server"),),
        regions=(Region("core", "CORE", (40, 60, 520, 200), container="sys"),),
        components=(
            Component(
                "A", "does a", region="core", x=80, y=130, implemented_by=("p.a",), entry="a"
            ),
            Component(
                "B", "does b", region="core", x=370, y=130, implemented_by=("p.b",), entry="b"
            ),
        ),
        flows=(Flow("A", "B", "thing", "work"),),
        flow_kinds=("work",),
        invariants=(Invariant(1, "rule", governs=("A",)),),
    )
    meaning = Meaning(
        plain={"A": "the a", "B": "the b"},
        layers=(Layer("work", "Work"),),
        layer_of_kind={"work": "work"},
        relations={("A", "B"): "A gives B a thing."},
        journeys=(Journey("j", "J", (Step(("A",), (), ("A", "B"), "A acts."),)),),
    )
    return model, meaning


def test_small_model_is_clean() -> None:
    model, meaning = small_model()
    assert problems(model, meaning) == []
    assert meaning.verb_for(("A", "B"), "work", True) == "to"


def test_layout_problems_find_lies() -> None:
    model, meaning = small_model()
    bad = dataclasses.replace(
        model,
        components=(
            dataclasses.replace(model.components[0], x=80, y=130),
            dataclasses.replace(model.components[1], x=80, y=130),
        ),
        flows=(Flow("A", "Nope", "thing", "work"), Flow("A", "B", "x", "unknown")),
        regions=(Region("core", "CORE", (0, 0, 520, 200), container="sys"),),
    )
    found = "\n".join(bad.layout_problems())
    assert "A overlaps B" in found
    assert "names an unknown component" in found
    assert "unknown kind unknown" in found
    assert "region core is not inside sys" in found


def test_meaning_problems_find_gaps() -> None:
    model, meaning = small_model()
    gappy = Meaning(
        plain={"A": "the a"},
        layers=meaning.layers,
        layer_of_kind={},
        relations={("B", "A"): "backwards"},
        journeys=(Journey("j", "J", (Step(("Z",), (), ("A", "Z"), "?"),)),),
        verb_overrides={("A", "Z"): ("x", "y")},
    )
    found = "\n".join(meaning_problems(model, gappy))
    assert "flow A -> B has no sentence" in found
    assert "kind work with no layer" in found
    assert "relations names a flow the model does not have: B -> A" in found
    assert "B has no plain word" in found
    assert "journey j step 1 acts names unknown component Z" in found
    assert "traces a flow the model does not have" in found
    assert "verb_overrides names an unknown flow" in found


def test_module_matches_exact_and_subtree() -> None:
    assert module_matches("p.a", "p.a")
    assert not module_matches("p.a", "p.ab")
    assert not module_matches("p.a", "p.a.b")
    assert module_matches("p.ui.*", "p.ui")
    assert module_matches("p.ui.*", "p.ui.base")
    assert module_matches("p.ui.*", "p.ui.screens.home")
    assert not module_matches("p.ui.*", "p.uix")
    assert not module_matches("p.ui.*", "p")
    comp = Component("A", "does a", implemented_by=("p.ui.*", "p.a"))
    assert claimed(comp, ["p", "p.a", "p.ui", "p.ui.base", "p.b"]) == ["p.a", "p.ui", "p.ui.base"]


def test_build_state_is_derived() -> None:
    comp = Component("A", "does a", implemented_by=("p.a", "p.b"), entry="run")
    facts = {
        "components": {
            "p.a": {"functions": [{"name": "run"}], "classes": []},
            "p.b": {"functions": [], "classes": []},
        }
    }
    assert build_state(comp, facts) == "built"
    assert build_state(comp, {"components": {"p.a": facts["components"]["p.a"]}}) == "partial"
    assert build_state(comp, {"components": {}}) == "planned"
    missing = dataclasses.replace(comp, entry="absent")
    assert build_state(missing, facts) == "partial"
    assert build_state(dataclasses.replace(missing, tracker="R1 #9"), facts) == "planned"
    assert build_state(dataclasses.replace(comp, entry=""), facts) == "partial"
    assert build_state(Component("Actor", "outside", kind="actor"), facts) == "planned"


def test_build_state_with_subtree_claim() -> None:
    facts = {
        "components": {
            "p.ui": {"functions": [], "classes": []},
            "p.ui.app": {"functions": [], "classes": [{"name": "App"}]},
            "p.other": {"functions": [{"name": "go"}], "classes": []},
        }
    }
    ui = Component("UI", "the screens", implemented_by=("p.ui.*",), entry="App")
    assert build_state(ui, facts) == "built"
    assert build_state(dataclasses.replace(ui, entry="Nope"), facts) == "partial"
    both = Component("Both", "two claims", implemented_by=("p.ui.*", "p.gone"), entry="App")
    assert build_state(both, facts) == "partial"
    assert build_state(dataclasses.replace(ui, implemented_by=("p.web.*",)), facts) == "planned"
