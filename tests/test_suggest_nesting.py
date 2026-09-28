"""Nesting advice for a synthetic map with known card widths."""

from __future__ import annotations

from pathlib import Path

from systemap import nest, suggest
from systemap.model import Component, Meaning, Model, Region


def _tree(model: Model, meaning: Meaning) -> nest.Tree:
    return nest.Tree((nest.Map("", Path("map/model.py"), "map/model.py", model, meaning, {}),))


def _model(cards: dict[str, int]) -> tuple[Model, Meaning, dict[str, object]]:
    """A one-region model with one card per entry, claiming that many modules."""
    components = []
    records: dict[str, object] = {}
    for k, (cid, n) in enumerate(cards.items()):
        modules = tuple(f"pkg.{cid.lower()}.m{i}" for i in range(n))
        for m in modules:
            records[m] = {
                "file": m.replace(".", "/") + ".py",
                "names": [{"name": "f", "kind": "function"}],
            }
        components.append(
            Component(
                id=cid,
                does=cid,
                implemented_by=modules,
                entry="f",
                region="r",
                x=20 + 190 * k,
                y=60,
            )
        )
    model = Model(
        canvas=(8000, 200),
        containers=(),
        regions=(Region("r", "R", (0, 0, 8000, 200)),),
        components=tuple(components),
        flows=(),
        flow_kinds=(),
    )
    return model, Meaning(plain={c.id: c.id for c in components}), {"components": records}


def test_suggest_says_when_a_map_is_past_forty_cards_and_which_cards_to_open() -> None:
    model, meaning, facts = _model({f"C{i}": (12 if i < 2 else 1) for i in range(41)})
    lines = suggest.nesting_lines(_tree(model, meaning), facts)  # type: ignore[arg-type]
    assert lines[0] == (
        "nesting: the top map holds 41 cards, past 40; one canvas stops working there. Open a "
        'map inside the cards with the most modules (map="map/<card>.py" on the card; its '
        "cards claim exactly the card's modules):"
    )
    assert lines[1:] == ["  C0: 12 modules", "  C1: 12 modules"]
    # Under forty with no wide card: nothing to open; a wide card alone is named.
    model, meaning, facts = _model({"A": 3, "B": 4})
    assert suggest.nesting_lines(_tree(model, meaning), facts) == [  # type: ignore[arg-type]
        "nesting: no map is past 40 cards and no card holds more than 10 modules; nothing to open"
    ]
    model, meaning, facts = _model({"A": 11, "B": 4})
    assert suggest.nesting_lines(_tree(model, meaning), facts) == [  # type: ignore[arg-type]
        "nesting: the top map holds 2 cards; A (11 modules) past 10 modules: split the card, "
        "or open a map inside it"
    ]
