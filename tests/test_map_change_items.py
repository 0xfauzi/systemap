"""The map comparison of the Changes view gives each changed field of a flow and a sequence.

Codex results change-2 and change-18:

- A flow with an explicit `id` keeps its identifier when its endpoints change. Acceptance
  value: the comparison gives one changed flow with the field `endpoints`, and its new
  endpoints. Before the repair, the comparison gave no flow.
- A sequence with a changed `covers` value is a changed sequence. Acceptance value: the
  comparison gives one changed sequence with the field `coverage`. A different order of
  the same identities is not a change. Before the repair, the comparison gave no sequence.
"""

from __future__ import annotations

from systemap import delta_model
from systemap.delta_model import Item
from systemap.model import Component, Flow, Journey, Meaning, Model, Step


def model(*flows: Flow) -> Model:
    return Model(
        canvas=(0, 0),
        containers=(),
        regions=(),
        components=tuple(Component(c, "Does.") for c in ("A", "B", "C")),
        flows=flows,
        flow_kinds=(),
    )


def sequence(*covers: str) -> Journey:
    step = Step(("A",), (), ("A", "B"), "A sends the request.", flow="send")
    return Journey("send", "Send a request", (step,), covers=covers)


def test_a_flow_with_an_id_and_new_endpoints_is_a_changed_flow() -> None:
    before = model(Flow("A", "B", "request", "data", id="send"))
    after = model(Flow("A", "C", "request", "data", id="send"))
    meaning = Meaning(plain={})
    found = delta_model.compare((before, meaning), (after, meaning))
    assert found.flows == (Item("changed", "request", ("endpoints",), ("A", "C"), 0),)
    assert found.count == 1


def test_a_flow_with_the_same_endpoints_has_no_endpoint_change() -> None:
    flows = model(Flow("A", "B", "request", "data", id="send"))
    meaning = Meaning(plain={})
    assert delta_model.compare((flows, meaning), (flows, meaning)).count == 0


def test_a_sequence_with_changed_coverage_is_a_changed_sequence() -> None:
    flows = model(Flow("A", "B", "request", "data", id="send"))
    before = Meaning(plain={}, journeys=(sequence('["route","pkg.a","","GET /a"]'),))
    after = Meaning(plain={}, journeys=(sequence('["route","pkg.a","","GET /b"]'),))
    found = delta_model.compare((flows, before), (flows, after))
    assert found.sequences == (Item("changed", "Send a request", ("coverage",), go=0),)


def test_the_order_of_the_covered_identities_is_not_a_change() -> None:
    flows = model(Flow("A", "B", "request", "data", id="send"))
    one, two = '["route","pkg.a","","GET /a"]', '["route","pkg.a","","GET /b"]'
    before = Meaning(plain={}, journeys=(sequence(one, two),))
    after = Meaning(plain={}, journeys=(sequence(two, one),))
    assert delta_model.compare((flows, before), (flows, after)).count == 0
