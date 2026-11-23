"""N5: the neighbours of a nested map at the sides of its frame, with the side moves.

docs/design/atlas.md, rule "Neighbours of a nested map". N4 failed acceptance 1 on the
nested map Page: the sides layout had one label collision, and the column layout had none.
The rule now has one more step (`place_order._clear_sides`): when a sides layout has a
label collision or a refused route, the placer tries each actor at each other side with
free room, and keeps the move with the fewest collisions and refused routes, then the
smallest map, while a move removes a collision or a refused route. This script measures
the rule with that step.

Inputs:

- the four inputs of N4, with no change: `page` (map/page.py) and one map of each level of
  the generated M11 tree (`m11 P0`, `m11 P0/Q0`, `m11 P0/Q0/Deep`);
- three inputs that no earlier measurement used: the stubs that `systemap parts --stub`
  makes for the cards Check, Config and Model of the map of this repository
  (`parts_stub.build`). A stub has no flow, thus it measures only the sides of actors
  with no flow, the size of the map and the layout problems.

Acceptance values, written on 2026-11-19 before the first run of this script. They are the
six values of N4, with no change (bench/jev/neighbour_sides_n4.py). Value 4 and value 5
apply to the inputs that they name. On the stubs, value 5 is 80 percent or more. The rule
is used in the commands (`place.SIDES_IN_COMMANDS = True`, for the atlas page only) only
if all of them hold. If one fails, the commands keep the column layout.

1. On each input, `refused` and `collisions` of `sides` are not more than those of
   `column`.
2. The total `bends` of `sides` over all inputs is not more than that of `column`.
3. The total `length` of `sides` over all inputs is not more than that of `column`.
4. On each input with an actor that has a flow, `reach` of `sides` is not more than that
   of `column`, and the total `reach` of `sides` over these inputs is less than that of
   `column`.
5. On `page`, `shown` of `sides` is 90 percent or more of that of `column`. On each other
   input, it is 80 percent or more.
6. No `sides` layout has a layout problem (`Model.layout_problems`).

This is not a blind test on `page`. The step was written after N4 failed on `page`, to
remove that collision. Before this text, a calculation in the same session gave the sides
layout of `page` with the step: 0 collisions, 0 refused routes, 101 bends, length 18,472,
canvas 928 x 980, and the actor Judgement at the bottom side. The values of the M11 maps
were known from N4 (no collision, thus the step does not change them). The values of the
three stubs were not calculated before this text.

Run from the repository root:
    uv run python bench/jev/neighbour_sides_n5.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import neighbour_sides as ns  # noqa: E402  (a neighbour script in bench/jev)
import neighbour_sides_n4 as n4  # noqa: E402  (a neighbour script in bench/jev)

from systemap import config, facts_file, nest, parts_stub  # noqa: E402
from systemap.model import Model  # noqa: E402

STUBS = ("Check", "Config", "Model")


def stubs() -> dict[str, Model]:
    """Give the stub of a nested map for each card of STUBS, with no positions."""
    cfg = config.load(ROOT)
    tree = nest.load(cfg)
    facts = facts_file.read_facts(cfg.facts_path, cfg.root)
    top = tree.top
    out: dict[str, Model] = {}
    for cid in STUBS:
        card = top.model.find(cid)
        assert card is not None
        model, _meaning = parts_stub.build(tree, top, card, facts, False)
        out[f"stub {cid}"] = model
    return out


def main() -> int:
    models = {**n4.inputs(), **stubs()}
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for name, model in models.items():
        results[name] = {"column": ns.measure(model, False), "sides": ns.measure(model, True)}
    print(
        "| input | layout | canvas | area | zoom | shown | collisions | refused | bends | "
        "length | reach |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for name, r in results.items():
        for layout in ("column", "sides"):
            print(ns._row(name, layout, r[layout]))
    for name, r in results.items():
        for layout in ("column", "sides"):
            if r[layout]["problems"]:
                print(f"{name} {layout}: {r[layout]['problems']}")
    print()
    found = n4.verdicts(results)
    for text, ok in found:
        print(f"{text}: {'PASS' if ok else 'FAIL'}")
    print(f"Result: {'PASS' if all(ok for _t, ok in found) else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
