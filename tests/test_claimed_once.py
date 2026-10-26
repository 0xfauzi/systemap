"""A render calculates the claimed modules of each component a fixed number of times.

Finding scale-6: `model.claimed` was calculated again 232 times in one render of this
repository (21 components), 0.20 s of a 2.0 s render. The flow evidence calculated the
module owners two times, and the assurance claims calculated the claimed modules again
for the import rules, for each source review state and for the flow evidence. Now each
of these users calculates them one time for each component and gives them to the others.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from conftest import Sample

from systemap import (
    assurance,
    card_review,
    evidence,
    import_rules,
    model,
    page_data,
    route,
)
from systemap.schematic import render as render_schematic

USERS = (model, evidence, assurance, card_review, import_rules, page_data)


@pytest.fixture(autouse=True)
def empty_caches() -> Iterator[None]:
    route.clear_routed()
    assurance.clear_claims()
    evidence.clear_evidence()
    yield
    route.clear_routed()
    assurance.clear_claims()
    evidence.clear_evidence()


def count_claimed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    original = model.claimed

    def counted(component: Any, modules: Any) -> list[str]:
        calls.append(component.id)
        return original(component, modules)

    for user in USERS:
        # raising=False: on the earlier source, some users do not import `claimed`.
        # Then the test fails on the number of calls, not on the patch.
        monkeypatch.setattr(user, "claimed", counted, raising=False)
    return calls


def test_the_schematic_calculates_the_claims_of_a_component_three_times(
    sample: Sample, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = count_claimed(monkeypatch)
    render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    cards = [c.id for c in sample.model.components]
    # One time each for the flow evidence, the assurance claims and the entry modules.
    # Before the change: 2 for the flow evidence, and for the assurance claims 1 for the
    # import rules and 1 for each source review state of a component or an invariant.
    assert sorted(calls) == sorted(cards * 3)


def test_the_page_sources_calculate_the_claims_of_a_component_one_time(
    sample: Sample, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = count_claimed(monkeypatch)
    page_data.sources(sample.model, sample.facts)
    # Before the change: 2, one for the modules and one for the claims without a module.
    assert sorted(calls) == sorted(c.id for c in sample.model.components)


def test_the_given_claims_give_the_same_results(sample: Sample) -> None:
    records = sample.facts["components"]
    owned = {c: model.claimed(c, records) for c in sample.model.components}
    assert evidence.owners(sample.model, sample.facts, owned) == evidence.owners(
        sample.model, sample.facts
    )
    assert import_rules.evaluate(sample.model, sample.facts, owned) == import_rules.evaluate(
        sample.model, sample.facts
    )
    for card in sample.model.components:
        found = card_review.state(card, sample.model, sample.meaning, sample.facts, owned[card])
        assert found == card_review.state(card, sample.model, sample.meaning, sample.facts)
