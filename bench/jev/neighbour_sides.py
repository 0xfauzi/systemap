"""N1: the neighbours of a nested map at the four sides of its frame, against one column.

Stage 7 of the atlas page (docs/design/atlas.md) adds a placer rule for a nested map: its
actors go to the four sides of its frame, each near the mean centre of the parts that it
has flows with (`systemap.place_sides`). Before the rule is kept, this script compares
it with the present layout, where the actors are in one column at the left of the frame.

For each input, the script makes two fresh layouts with `place.compute(model,
all_cards=True)`: `column` with nested=False and `sides` with nested=True. Both search
the region order in the same way. For each layout it gives:

- `canvas`: the width and the height of the map, and `area` in thousands of square units.
- `zoom`: the smaller of 1440 / width and 790 / height, for a comparison only. 790 is
  900 less the approximate height of the header and the rows above the map.
- `collisions`, `refused`, `bends`, `length`: the values of `place.score`.
- `reach`: the mean distance from the centre of each actor to the mean centre of the
  parts that it has flows with. An actor with no such flow does not count.

Inputs: the nested maps of the test fixtures (Gateway and Style of tests/test_nested.py,
Gateway of tests/test_nest_join.py, the nested maps of tests/three_levels.py with 2 parts
and 2 sub parts), and the draft nested map Page (docs/design/atlas/tools/page_model.py.txt).

Acceptance values, written before the first run on 2026-11-19. The rule is kept only if
all of them hold:

1. On each input, `refused` and `collisions` of `sides` are not more than those of
   `column`.
2. The total `bends` of `sides` over all inputs is not more than that of `column`.
3. The total `length` of `sides` over all inputs is not more than that of `column`.
4. On each input with an actor, `reach` of `sides` is less than that of `column`.
5. On the draft map Page, `zoom` of `sides` is 90 percent or more of that of `column`.
   On each other input, it is 80 percent or more.

The fixtures are small. The draft map Page is the only input of the size of a real
nested map. A result on these inputs does not show the effect on all nested maps.

N2: the form of the study, added on 2026-11-19 after a review of N1. The `sides` layout
of N1 is the form BOX of `place_sides`: the actor container is a box with the room for its
label above the actors, CONTAINER_PAD inside its edge, and 48 units from the frame to an
actor. The study (docs/design/atlas/tools/sides.py.txt) has no actor box: the frame and
the actors start 28 units from the edge of the map, and an actor is 70 units from the
frame. N1 thus did not measure the form of the study. With `--form study`, the `sides`
layout is the form STUDY of `place_sides`: no room for a label, 28 units from the edge of
the map to the cards, and 70 units from the frame to an actor. The choice of the sides,
the move on a full side and the spread along a side are the rules of `place_sides`, not
the slightly different rules of the study script.

Acceptance values of N2, written before the first run of N2: the five values of N1, with
no change, so that N2 and N1 have the same test. Known before the run: acceptance 4 can
not pass on an input where the column is already at the nearest side of the parts,
because an actor at that side with a gap of 44 or more has a reach that is equal to or
more than the reach of the column. The review of N1 found this. N2 does not change
acceptance 4 for this reason. A different acceptance 4 is a decision for the maintainer.

N3: the form BOX with SIDE_GAP 44, with acceptance 4 and 5 corrected, added on 2026-11-20
after a second review. The review found two errors in the acceptance values of N1 and N2:

- `zoom` has no upper limit, but the page limits the fit to a screen scale of 1.6
  (`fitK` in src/systemap/atlas_input.py). On each small fixture the zoom of the column
  is more than 1.6, thus the reader sees 1.6 and not the value of the metric.
- Acceptance 4 asks for a reach that is strictly less on each input. Where the column is
  already at the nearest side of the parts, an actor at that side has the same reach or
  more, and the value can not pass. Run 5 of N1 showed equal reach (234 = 234).

SIDE_GAP is now 44, the gap of the column layout, so that the form BOX is the form of run 5
of N1. `shown` is the smaller of `zoom` and 1.6: the zoom that the page shows.

Acceptance values of N3, written before the run of N3 with `--acceptance n3`. They are not
a blind test: the values of N1, N2 and run 5 were known, and a scratch calculation in the
same session gave the values of these forms before this text. The maintainer can refuse
them. The rule is kept in the commands only if all of them hold:

1. to 3. The values 1, 2 and 3 of N1, with no change.
4. On each input with an actor, `reach` of `sides` is not more than that of `column`, and
   the total `reach` of `sides` over these inputs is less than that of `column`.
5. On the draft map Page, `shown` of `sides` is 90 percent or more of that of `column`.
   On each other input, it is 80 percent or more.

Run from the repository root:
    uv run python bench/jev/neighbour_sides.py               (N1, the form BOX)
    uv run python bench/jev/neighbour_sides.py --form study  (N2, the form STUDY)
    uv run python bench/jev/neighbour_sides.py --acceptance n3  (N3, the form BOX)

N1 ran with SIDE_GAP 48. To run N1 again with its own form, set SIDE_GAP to 48.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from systemap import place  # noqa: E402
from systemap.model import CARD_H, CARD_W, Model  # noqa: E402

# The largest screen scale of the fit of a map on the page (`fitK` in atlas_input.py).
FIT_LIMIT = 1.6


def _model(source: str) -> Model:
    space: dict[str, Any] = {}
    exec(compile(source, "<fixture>", "exec"), space)  # noqa: S102
    model = space["MODEL"]
    assert isinstance(model, Model)
    return model


def inputs() -> dict[str, Model]:
    """Give the nested maps of the fixtures and the draft map Page, by name."""
    import test_nest_join  # noqa: PLC0415
    import test_nested  # noqa: PLC0415
    import three_levels  # noqa: PLC0415

    out = {
        "nested Gateway": _model(test_nested.GATEWAY),
        "nested Style": _model(test_nested.STYLE),
        "join Gateway": _model(test_nest_join.NESTED),
    }
    for rel, text in sorted(three_levels.files(2, 2).items()):
        if rel.startswith("map/") and rel != "map/model.py" and rel.endswith(".py"):
            out[f"levels {rel[4:-3]}"] = _model(text)
    page = runpy.run_path(str(ROOT / "docs/design/atlas/tools/page_model.py.txt"))["MODEL"]
    out["draft Page"] = page
    return out


def _reach(model: Model) -> float | None:
    """The mean distance from each actor to the mean centre of its parts."""
    centre = {
        c.id: (c.box[0] + CARD_W / 2, c.box[1] + CARD_H[c.kind] / 2) for c in model.components
    }
    actors = {c.id for c in model.components if c.kind == "actor"}
    out: list[float] = []
    for a in sorted(actors):
        near = [
            centre[f.dst if f.src == a else f.src]
            for f in model.flows
            if a in (f.src, f.dst)
            and f.src != f.dst
            and (f.dst if f.src == a else f.src) not in actors
        ]
        if not near:
            continue
        mx = sum(p[0] for p in near) / len(near)
        my = sum(p[1] for p in near) / len(near)
        out.append(abs(centre[a][0] - mx) + abs(centre[a][1] - my))
    return sum(out) / len(out) if out else None


def measure(model: Model, nested: bool | str) -> dict[str, Any]:
    """Give the values of one fresh layout."""
    placement = place.compute(model, all_cards=True, nested=nested)
    laid = place.apply(model, placement)
    assert placement.score is not None
    problems = laid.layout_problems()
    w, h = laid.canvas
    return {
        "canvas": (w, h),
        "area": round(w * h / 1000),
        "zoom": round(min(1440 / w, 790 / h), 3),
        "shown": round(min(1440 / w, 790 / h, FIT_LIMIT), 3),
        "collisions": placement.score.collisions,
        "refused": placement.score.refused,
        "bends": placement.score.bends,
        "length": placement.score.length,
        "reach": _reach(laid),
        "problems": problems,
    }


def _row(name: str, form: str, v: dict[str, Any]) -> str:
    reach = "-" if v["reach"] is None else f"{v['reach']:.0f}"
    w, h = v["canvas"]
    return (
        f"| {name} | {form} | {w} x {h} | {v['area']} | {v['zoom']} | {v['shown']} | "
        f"{v['collisions']} | "
        f"{v['refused']} | {v['bends']} | {v['length']} | {reach} |"
    )


def _verdicts(results: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    col = {n: r["column"] for n, r in results.items()}
    sid = {n: r["sides"] for n, r in results.items()}
    one = all(
        sid[n]["refused"] <= col[n]["refused"] and sid[n]["collisions"] <= col[n]["collisions"]
        for n in results
    )
    bends = (sum(v["bends"] for v in sid.values()), sum(v["bends"] for v in col.values()))
    length = (sum(v["length"] for v in sid.values()), sum(v["length"] for v in col.values()))
    four = all(col[n]["reach"] is None or sid[n]["reach"] < col[n]["reach"] for n in results)
    five = all(
        sid[n]["zoom"] >= (0.9 if n == "draft Page" else 0.8) * col[n]["zoom"] for n in results
    )
    clean = all(not r["sides"]["problems"] for r in results.values())
    return [
        f"1. refused and collisions not more on each input: {'PASS' if one else 'FAIL'}",
        f"2. total bends {bends[0]} against {bends[1]}: {'PASS' if bends[0] <= bends[1] else 'FAIL'}",
        f"3. total length {length[0]} against {length[1]}: "
        f"{'PASS' if length[0] <= length[1] else 'FAIL'}",
        f"4. reach less on each input with an actor: {'PASS' if four else 'FAIL'}",
        f"5. zoom 90 percent (Page) or 80 percent (others) or more: {'PASS' if five else 'FAIL'}",
        f"layout problems of the sides layouts: {'none' if clean else 'SOME'}",
    ]


def _n3(results: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    """The values 4 and 5 of N3: the reach not more, and the zoom that the page shows."""
    col = {n: r["column"] for n, r in results.items()}
    sid = {n: r["sides"] for n, r in results.items()}
    with_actor = [n for n in results if col[n]["reach"] is not None]
    each = all(sid[n]["reach"] <= col[n]["reach"] for n in with_actor)
    total = (sum(sid[n]["reach"] for n in with_actor), sum(col[n]["reach"] for n in with_actor))
    four = each and total[0] < total[1]
    ratio = {n: sid[n]["shown"] / col[n]["shown"] for n in results}
    five = all(ratio[n] >= (0.9 if n == "draft Page" else 0.8) for n in results)
    worst = min(ratio, key=lambda n: ratio[n])
    return [
        f"4. (N3) reach not more on each input, total {total[0]:.0f} against {total[1]:.0f}: "
        f"{'PASS' if four else 'FAIL'}",
        f"5. (N3) shown zoom 90 percent (Page) or 80 percent (others) or more, smallest "
        f"{ratio[worst]:.3f} ({worst}), Page {ratio['draft Page']:.3f}: "
        f"{'PASS' if five else 'FAIL'}",
    ]


def _args(argv: list[str]) -> tuple[str, str] | None:
    opts = dict(zip(argv[::2], argv[1::2], strict=False))
    if len(argv) % 2 or set(opts) - {"--form", "--acceptance"}:
        return None
    form, acceptance = opts.get("--form", "box"), opts.get("--acceptance", "n1")
    if form not in ("box", "study") or acceptance not in ("n1", "n3"):
        return None
    return form, acceptance


def main(argv: list[str]) -> int:
    parsed = _args(argv)
    if parsed is None:
        print(
            "Usage: neighbour_sides.py [--form box|study] [--acceptance n1|n3]",
            file=sys.stderr,
        )
        return 2
    form, acceptance = parsed
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for name, model in inputs().items():
        results[name] = {"column": measure(model, False), "sides": measure(model, form)}
    print(
        "| input | layout | canvas | area | zoom | shown | collisions | refused | bends | "
        "length | reach |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for name, r in results.items():
        for layout in ("column", "sides"):
            print(_row(name, layout, r[layout]))
    for name, r in results.items():
        for layout in ("column", "sides"):
            if r[layout]["problems"]:
                print(f"{name} {layout}: {r[layout]['problems']}")
    print()
    lines = _verdicts(results)
    if acceptance == "n3":
        lines = [*lines[:3], *_n3(results), lines[5]]
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
