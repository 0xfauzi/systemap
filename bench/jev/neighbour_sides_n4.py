"""N4: the neighbours of a nested map at the sides of its frame, on nested maps that N1 to N3 did not use.

docs/design/atlas.md, rule "Neighbours of a nested map": to use the rule, write the
acceptance values first and measure on nested maps that N1 to N3 did not use. This script
does that. It uses the functions of bench/jev/neighbour_sides.py (`measure`, `_row`) with
no change: two fresh layouts of each input with `place.compute(model, all_cards=True)`,
`column` (nested=False) and `sides` (nested=True, the form BOX of `place_sides.KEPT` with
SIDE_GAP 44).

Inputs. N1 to N3 used the nested maps of the small test fixtures and the draft map Page
(docs/design/atlas/tools/page_model.py.txt). N4 uses none of them:

- `page`: the nested map Page of this repository (map/page.py), as stage 10 committed it
  (7295d1f). It has 11 parts and 10 neighbours, and it is not the draft.
- `m11 P0`, `m11 P0/Q0`, `m11 P0/Q0/Deep`: one nested map of each level of the generated
  M11 tree (`files` of bench/jev/canvas_data_size.py). Each other map of a level has the
  same form as the map of that level here.

Acceptance values, written on 2026-11-19 before the first run of this script. They are
the values of N3, with no change, and one more value. The values of N3 correct two errors
of N1 (the fit of the page has the upper limit 1.6, and an equal reach can not be less).
N3 itself was not a test, because its values were written after the results of N1 and N2.
Here the values come first, on inputs with no earlier result. The rule is used in the
commands (`place.SIDES_IN_COMMANDS = True`, for the atlas page only) only if all of these
hold. If one fails, the commands keep the column layout.

1. On each input, `refused` and `collisions` of `sides` are not more than those of
   `column`.
2. The total `bends` of `sides` over all inputs is not more than that of `column`.
3. The total `length` of `sides` over all inputs is not more than that of `column`.
4. On each input with an actor, `reach` of `sides` is not more than that of `column`, and
   the total `reach` of `sides` over these inputs is less than that of `column`.
5. On `page`, `shown` of `sides` is 90 percent or more of that of `column`. On each other
   input, it is 80 percent or more.
6. No `sides` layout has a layout problem (`Model.layout_problems`).

Known before the run: the results of N1 to N3 on the draft map Page, which has a form
near the form of map/page.py. The values of map/page.py and of the M11 maps were not
calculated before this text.

Run from the repository root:
    uv run python bench/jev/neighbour_sides_n4.py
"""

from __future__ import annotations

import runpy
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import canvas_data_size  # noqa: E402  (a neighbour script in bench/jev)
import neighbour_sides as ns  # noqa: E402  (a neighbour script in bench/jev)

from systemap.model import Model  # noqa: E402

M11 = {"m11 P0": "map/p0.py", "m11 P0/Q0": "map/p0_q0.py", "m11 P0/Q0/Deep": "map/p0_q0_deep.py"}


def _load(path: Path) -> Model:
    model = runpy.run_path(str(path))["MODEL"]
    assert isinstance(model, Model)
    return model


def inputs() -> dict[str, Model]:
    """Give the nested map Page of this repository and one M11 map of each level."""
    out = {"page": _load(ROOT / "map/page.py")}
    files = canvas_data_size.files()
    with tempfile.TemporaryDirectory() as tmp:
        for name, rel in M11.items():
            path = Path(tmp) / rel.replace("/", "_")
            path.write_text(files[rel], encoding="utf-8")
            out[name] = _load(path)
    return out


def verdicts(results: dict[str, dict[str, dict[str, Any]]]) -> list[tuple[str, bool]]:
    """Give the six acceptance values of N4, each with its result."""
    col = {n: r["column"] for n, r in results.items()}
    sid = {n: r["sides"] for n, r in results.items()}
    one = all(
        sid[n]["refused"] <= col[n]["refused"] and sid[n]["collisions"] <= col[n]["collisions"]
        for n in results
    )
    bends = (sum(v["bends"] for v in sid.values()), sum(v["bends"] for v in col.values()))
    length = (sum(v["length"] for v in sid.values()), sum(v["length"] for v in col.values()))
    with_actor = [n for n in results if col[n]["reach"] is not None]
    reach = (sum(sid[n]["reach"] for n in with_actor), sum(col[n]["reach"] for n in with_actor))
    four = all(sid[n]["reach"] <= col[n]["reach"] for n in with_actor) and reach[0] < reach[1]
    ratio = {n: sid[n]["shown"] / col[n]["shown"] for n in results}
    five = all(ratio[n] >= (0.9 if n == "page" else 0.8) for n in results)
    worst = min(ratio, key=lambda n: ratio[n])
    six = all(not sid[n]["problems"] for n in results)
    return [
        ("1. refused and collisions not more on each input", one),
        (f"2. total bends {bends[0]} against {bends[1]}", bends[0] <= bends[1]),
        (f"3. total length {length[0]} against {length[1]}", length[0] <= length[1]),
        (f"4. reach not more on each input, total {reach[0]:.0f} against {reach[1]:.0f}", four),
        (
            f"5. shown zoom 90 percent (page) or 80 percent (others) or more, smallest "
            f"{ratio[worst]:.3f} ({worst}), page {ratio['page']:.3f}",
            five,
        ),
        ("6. no layout problem in a sides layout", six),
    ]


def main() -> int:
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for name, model in inputs().items():
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
    found = verdicts(results)
    for text, ok in found:
        print(f"{text}: {'PASS' if ok else 'FAIL'}")
    print(f"Result: {'PASS' if all(ok for _t, ok in found) else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
