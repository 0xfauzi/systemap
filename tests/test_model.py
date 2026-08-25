from __future__ import annotations

import dataclasses

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
    meaning_problems,
    problems,
)


def test_example_validates(example_model: tuple[Model, Meaning]) -> None:
    model, meaning = example_model
    assert problems(model, meaning) == []


def test_example_flow_endpoints_resolve(example_model: tuple[Model, Meaning]) -> None:
    model, _ = example_model
    ids = model.ids
    for f in model.flows:
        assert f.src in ids, f
        assert f.dst in ids, f
        assert f.kind in model.flow_kinds


def test_example_every_flow_has_a_relation_and_a_layer(
    example_model: tuple[Model, Meaning],
) -> None:
    model, meaning = example_model
    layer_ids = {layer.id for layer in meaning.layers}
    for f in model.flows:
        assert f.edge in meaning.relations, f
        assert meaning.layer_for(f.edge, f.kind) in layer_ids, f
    # Nothing was lost in the conversion from kstrl's tables.
    assert len(model.flows) == 60
    assert len(meaning.relations) == 60
    assert len(meaning.layers) == 7
    assert len(model.components) == 54
    assert len(model.invariants) == 15
    assert len(meaning.journeys) == 4
    assert sum(len(j.steps) for j in meaning.journeys) == 29
    assert len(meaning.verb_overrides) == 24
    assert len(meaning.layer_overrides) == 17


def test_example_journeys_resolve(example_model: tuple[Model, Meaning]) -> None:
    model, meaning = example_model
    ids = model.ids
    edges = {f.edge for f in model.flows}
    for j in meaning.journeys:
        for step in j.steps:
            assert step.edge in edges, (j.id, step.edge)
            assert set(step.acts) <= ids
            assert set(step.measures) <= ids


def test_example_positions_and_plain_words(example_model: tuple[Model, Meaning]) -> None:
    model, meaning = example_model
    assert model.layout_problems() == []
    assert set(meaning.plain) == model.ids
    assert model.component("Pipeline").x == 1264
    assert model.component("Operator").kind == "actor"


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
