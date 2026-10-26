"""The caches of the routes, the label positions and the claims (scale-2).

One command renders the same map several times: for the page, for each figure, for the
check and for the stale check. Before this change, each render calculated route_all,
place_labels, assurance.of_model and evidence.of_model again. On this repository, `systemap check` took
13.1 s and a refresh that wrote all outputs took 32.4 s (Router.route was called 400 and
1120 times).

Acceptance:
- Three renders of the same model call route_all, place_labels, the claims and the flow
  evidence one time. Two equal renders give the same SVG and detail JSON. The old code
  called each of them three times.
- If pickle cannot copy an input, such as a MappingProxyType field of a Meaning, the
  claims, the flow evidence and the render are the same as for a dict. The first cache
  code stopped with a TypeError for this input.
- A change to one input of the router or of the label placement gives a new result.
- A changed model or changed facts give new claims and new flow evidence.
- A caller that changes a result does not change the cached result.
"""

from __future__ import annotations

import copy
import pickle
import types
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from conftest import Sample

from systemap import assurance, evidence, route
from systemap.schematic import render as render_schematic


@pytest.fixture(autouse=True)
def empty_caches() -> Iterator[None]:
    route.clear_routed()
    assurance.clear_claims()
    evidence.clear_evidence()
    yield
    route.clear_routed()
    assurance.clear_claims()
    evidence.clear_evidence()


def _counted(monkeypatch: pytest.MonkeyPatch, module: Any, name: str) -> list[int]:
    calls: list[int] = []
    original = getattr(module, name)

    def counted(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, counted)
    return calls


def test_two_renders_route_and_seat_one_time(
    sample: Sample, monkeypatch: pytest.MonkeyPatch
) -> None:
    routes = _counted(monkeypatch, route, "route_all")
    seats = _counted(monkeypatch, route, "place_labels")
    claims = _counted(monkeypatch, assurance, "_Context")
    flows = _counted(monkeypatch, evidence, "_of_model")
    first = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    second = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    figure = render_schematic(
        sample.model, sample.meaning, sample.theme, sample.facts, svg_id="fig", layer="data"
    )
    assert first == second
    assert figure != first
    # The old code called each function one time for each render: three times.
    assert (len(routes), len(seats), len(claims), len(flows)) == (1, 1, 1, 1)


def test_a_cached_render_is_the_same_as_a_new_render(sample: Sample) -> None:
    cached = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    cached = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    route.clear_routed()
    assurance.clear_claims()
    evidence.clear_evidence()
    assert render_schematic(sample.model, sample.meaning, sample.theme, sample.facts) == cached


CARDS = {"A": (20.0, 100.0, 150.0, 56.0), "B": (800.0, 100.0, 150.0, 56.0)}
ROUTE_ARGS: dict[str, Any] = {
    "edges": [("A", "B")],
    "cards": CARDS,
    "actors": set(),
    "blocks": [],
    "regions": {},
    "region_of": {},
    "canvas": (1000.0, 300.0),
    "widths": {0: 40.0},
    "lh": 14.0,
    "obstacles": [("A", CARDS["A"]), ("B", CARDS["B"])],
    "names": {0: "label 'x'"},
}
CHANGES: dict[str, Any] = {
    "edges": [("B", "A")],
    "cards": {"A": (20.0, 180.0, 150.0, 56.0), "B": CARDS["B"]},
    "actors": {"A"},
    "blocks": [(400.0, 0.0, 60.0, 200.0)],
    "regions": {"R": (0.0, 80.0, 190.0, 100.0)},
    "region_of": {"A": "R"},
    "canvas": (1000.0, 400.0),
    "widths": {0: 300.0},
    "lh": 30.0,
    "obstacles": [("A", CARDS["A"]), ("B", CARDS["B"]), ("wall", (300.0, 100.0, 400.0, 60.0))],
    # A collision message uses the names.
    "names": {0: "label 'y'"},
}


def _uncached(args: dict[str, Any]) -> tuple[Any, Any]:
    routes = route.route_all(
        args["edges"],
        args["cards"],
        args["actors"],
        args["blocks"],
        args["regions"],
        args["region_of"],
        args["canvas"],
    )
    seats = route.place_labels(
        routes,
        args["widths"],
        args["lh"],
        args["obstacles"],
        args["canvas"],
        names=args["names"],
        cards=args["cards"],
        region_of=args["region_of"],
    )
    return routes, seats


@pytest.mark.parametrize("name", sorted(CHANGES))
def test_a_changed_input_gives_a_new_result(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _counted(monkeypatch, route, "route_all")
    first = route.routed(**ROUTE_ARGS)
    changed = {**ROUTE_ARGS, name: CHANGES[name]}
    second = route.routed(**changed)
    assert len(calls) == 2, "the changed input did not get a new calculation"
    assert route.routed(**ROUTE_ARGS) == first
    assert len(calls) == 2
    assert second == _uncached(changed)


def test_an_equal_number_of_a_different_type_gives_a_new_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The SVG writes an integer and a float in different forms. Thus they are different
    # inputs, and 0.0 and -0.0 are different inputs.
    calls = _counted(monkeypatch, route, "route_all")
    route.routed(**ROUTE_ARGS)
    route.routed(**{**ROUTE_ARGS, "canvas": (1000, 300)})
    route.routed(**{**ROUTE_ARGS, "blocks": [(0.0, 0.0, 1.0, 1.0)]})
    route.routed(**{**ROUTE_ARGS, "blocks": [(-0.0, 0.0, 1.0, 1.0)]})
    assert len(calls) == 4


def test_a_caller_cannot_change_a_cached_result() -> None:
    routes, seats = route.routed(**ROUTE_ARGS)
    expected = copy.deepcopy((routes, seats))
    routes[0].points.clear()
    seats[0].hits.append("changed")
    assert route.routed(**ROUTE_ARGS) == expected


def test_the_route_cache_keeps_a_limited_number_of_entries() -> None:
    for k in range(route.ROUTED_KEEP + 5):
        route.routed(**{**ROUTE_ARGS, "widths": {0: 40.0 + k}})
    assert len(route._routed) == route.ROUTED_KEEP


def test_changed_facts_or_a_changed_model_give_new_claims(
    sample: Sample, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _counted(monkeypatch, assurance, "_Context")
    before = assurance.of_model(sample.model, sample.meaning, sample.facts)
    facts = copy.deepcopy(sample.facts)
    facts["components"].pop(next(iter(facts["components"])))
    model = replace(sample.model, flows=sample.model.flows[:-1])
    changed = [
        assurance.of_model(sample.model, sample.meaning, facts),
        assurance.of_model(model, sample.meaning, sample.facts),
        assurance.of_model(sample.model, sample.meaning, sample.facts, "other"),
    ]
    assert len(calls) == 4
    assert changed[1] != before
    assurance.clear_claims()
    assert changed == [
        assurance.of_model(sample.model, sample.meaning, facts),
        assurance.of_model(model, sample.meaning, sample.facts),
        assurance.of_model(sample.model, sample.meaning, sample.facts, "other"),
    ]
    assert assurance.of_model(sample.model, sample.meaning, sample.facts) == before


def test_changed_inputs_give_new_flow_evidence(
    sample: Sample, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _counted(monkeypatch, evidence, "_of_model")
    before = evidence.of_model(sample.model, sample.meaning, sample.facts)
    facts = copy.deepcopy(sample.facts)
    facts["components"].pop(next(iter(facts["components"])))
    model = replace(sample.model, flows=sample.model.flows[:-1])
    args: list[tuple[Any, ...]] = [
        (sample.model, sample.meaning, facts),
        (model, sample.meaning, sample.facts),
        (sample.model, sample.meaning, sample.facts, ("facts file",)),
    ]
    changed = [evidence.of_model(*each) for each in args]
    assert len(calls) == 4
    # A caller that changes its copy does not change the cached evidence.
    expected = dict(before)
    before.clear()
    again = evidence.of_model(sample.model, sample.meaning, sample.facts)
    assert len(calls) == 4
    assert again == expected and again.pairs == before.pairs
    evidence.clear_evidence()
    assert changed == [evidence.of_model(*each) for each in args]
    assert evidence.of_model(sample.model, sample.meaning, sample.facts) == expected


class _Unpicklable(dict[str, str]):
    """A Mapping that pickle cannot copy, as a class in a model file that is not in
    sys.modules after it runs."""

    def __reduce__(self) -> Any:
        raise pickle.PicklingError("no pickle")


@pytest.mark.parametrize("kind", ["proxy", "class"])
def test_a_meaning_that_pickle_cannot_copy_is_not_kept(
    sample: Sample, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = dict(sample.meaning.plain)
    other = types.MappingProxyType(plain) if kind == "proxy" else _Unpicklable(plain)
    meaning = replace(sample.meaning, plain=other)
    claims = assurance.of_model(sample.model, sample.meaning, sample.facts)
    flows = evidence.of_model(sample.model, sample.meaning, sample.facts)
    svg = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    # The first cache code stopped here with "TypeError: cannot pickle 'mappingproxy'".
    assert assurance.of_model(sample.model, meaning, sample.facts) == claims
    calls = _counted(monkeypatch, evidence, "_of_model")
    assert evidence.of_model(sample.model, meaning, sample.facts) == flows
    assert len(calls) == 1, "the result for an input without a key must not come from the cache"
    assert render_schematic(sample.model, meaning, sample.theme, sample.facts) == svg
    assert len(assurance._claims) == len(evidence._evidence) == 1
