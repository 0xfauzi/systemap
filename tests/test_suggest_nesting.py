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
        'nesting: the top map has 41 components, more than 40. A nested map can reduce the component count. Open a map in a component with many modules (set map="map/<card>.py". Use the same module set in the nested map):'
    )
    assert lines[1:] == ["  C0: 12 modules", "  C1: 12 modules"]
    # Under forty with no wide card: nothing to open; a wide card alone is named.
    model, meaning, facts = _model({"A": 3, "B": 4})
    assert suggest.nesting_lines(_tree(model, meaning), facts) == [  # type: ignore[arg-type]
        "nesting: no map has more than 40 components and no component has more than 10 modules. No nested map is necessary."
    ]
    model, meaning, facts = _model({"A": 11, "B": 4})
    assert suggest.nesting_lines(_tree(model, meaning), facts) == [  # type: ignore[arg-type]
        "nesting: the top map has 2 components: A (11 modules) more than 10 modules: Divide the component, or open a map inside it."
    ]
