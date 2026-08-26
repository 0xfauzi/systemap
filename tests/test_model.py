from __future__ import annotations

import dataclasses

import pytest
from conftest import sample_model

from systemap.model import (
    BUILT,
    STANDARD_KINDS,
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
    all_layers,
    build_state,
    claimed,
    defines_entry,
    flow_layers,
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
        assert f.kind in STANDARD_KINDS or f.kind in model.flow_kinds


def test_sample_every_flow_has_a_relation_and_a_layer() -> None:
    model, meaning = sample_model()
    layer_ids = {layer.id for layer in all_layers(model, meaning)}
    for f in model.flows:
        assert f.edge in meaning.relations, f
        assert meaning.layer_for(f.edge, f.kind) in layer_ids, f
    assert meaning.layer_for(("User", "Reader"), "data") == "data"
    assert meaning.layer_for(("Reader", "Parser"), "control") == "control"
    assert meaning.layer_for(("Ledger", "Parser"), "record") == "memory"
    assert meaning.verb_for(("User", "Reader"), "data", True) == "types into"
    assert meaning.verb_for(("Parser", "Writer"), "data", False) == "receives from"
    # A standard layer the model gives no verbs has its own.
    assert meaning.verb_for(("Reader", "Parser"), "control", True) == "drives"
    assert meaning.verb_for(("Reader", "Parser"), "control", False) == "is driven by"


def test_layers_are_standard_then_the_models_own() -> None:
    model, meaning = sample_model()
    assert [layer.id for layer in all_layers(model, meaning)] == [
        "structure",
        "system",
        "data",
        "control",
        "record",
        "memory",
    ]
    assert all_layers(model, meaning)[0].label == "Structure"
    assert all_layers(model, meaning)[1].label == "System context"
    assert [layer.id for layer in flow_layers(model, meaning)] == [
        "data",
        "control",
        "record",
        "memory",
    ]
    # A model with no custom kind needs no layers, no layer_of_kind, no verbs.
    bare = Meaning(plain=meaning.plain, relations=meaning.relations)
    assert bare.layer_for(("A", "B"), "data") == "data"
    assert bare.verb_for(("A", "B"), "tools", True) == "invokes"
    with pytest.raises(KeyError):
        bare.layer_for(("A", "B"), "record")


def test_a_custom_layer_may_not_take_a_standard_id() -> None:
    model, meaning = sample_model()
    clash = dataclasses.replace(
        meaning, layers=(*meaning.layers, Layer("data", "Data"), Layer("all", "All"))
    )
    found = "\n".join(meaning_problems(model, clash))
    assert "layer data is a standard layer; it is derived, not declared" in found
    assert "layer all is a standard layer" in found


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
    assert (
        "has kind unknown, which is neither standard (data, control, context, tool) "
        "nor declared in flow_kinds"
    ) in found
    assert "region core is not inside sys" in found


def test_one_flow_per_ordered_pair() -> None:
    model, meaning = small_model()
    doubled = dataclasses.replace(
        model, flows=(*model.flows, Flow("A", "B", "another thing", "work"))
    )
    assert doubled.layout_problems() == [
        "flow A -> B appears twice ('thing' and 'another thing'); one flow per ordered "
        "pair: pick the artifact that matters, or draw one each way when something "
        "travels back"
    ]
    # The other direction is its own pair.
    both_ways = dataclasses.replace(model, flows=(*model.flows, Flow("B", "A", "reply", "work")))
    assert both_ways.layout_problems() == []


def test_two_invariants_with_one_number_are_refused_with_both_quoted() -> None:
    model, _meaning = small_model()
    doubled = dataclasses.replace(
        model,
        invariants=(
            Invariant(1, "The writer never reads the input.", governs=("A",)),
            Invariant(2, "Every record is written once.", governs=("B",)),
            Invariant(1, "Nothing is fetched at run time.", governs=("A",)),
        ),
    )
    assert doubled.layout_problems() == [
        "invariant 1 is numbered twice: 'The writer never reads the input.' and 'Nothing is "
        "fetched at run time.'; give each rule its own number"
    ]
    assert model.layout_problems() == []


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


def test_defines_entry_looks_the_name_up_in_the_claimed_modules() -> None:
    facts = {
        "components": {
            "p.ui": {"functions": [], "classes": []},
            "p.ui.app": {"functions": [], "classes": [{"name": "App"}]},
            "p.other": {"functions": [{"name": "go"}], "classes": []},
        }
    }
    ui = Component("UI", "the screens", implemented_by=("p.ui.*",), entry="App")
    assert defines_entry(ui, facts)
    assert not defines_entry(dataclasses.replace(ui, entry="Nope"), facts)
    # A name another component's module defines does not count.
    assert not defines_entry(dataclasses.replace(ui, entry="go"), facts)
    assert not defines_entry(dataclasses.replace(ui, entry=""), facts)
    assert not defines_entry(dataclasses.replace(ui, implemented_by=("p.web.*",)), facts)


def test_build_state_has_one_value() -> None:
    # The map draws what exists today; the check refuses everything else, so
    # nothing is derived, and the field that declared a plan is gone.
    comp = Component("A", "does a", implemented_by=("p.a",), entry="run")
    assert build_state(comp, {"components": {}}) == BUILT == "built"
    assert "tracker" not in {f.name for f in dataclasses.fields(Component)}
