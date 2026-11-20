"""T0 C1: the lines between the actor column and the system frame in the System context layer.

This script measures the layer "system" (System context) of the top map at the fit of
1440 x 900, on the self map and on the workspace fixture (tests/fixture_workspace.py with
the positions of the placer). The band is the space between the right edge of the actor
column (the largest right edge of an actor card) and the left edge of the system frame (the
container that holds the most cards that are not actors). The driver is
bench/jev/t0_context.js. In CSS px at the fit, it gives:

- (a) each pair of parallel segments of two different lines in the band, with an overlap of
  more than 0.5 map units: the distance, the smallest distance, and the count of pairs
  under 4, 6, 8 and 10 px. "across" pairs are segments at a right angle to the band (the
  vertical parts), "along" pairs are segments that go through the band.
- (b) each label at rest with a box in the band: the distance of its centre to its own
  line, the distance of its centre to the nearest other line, and the distance of its box
  to the nearest other line. The count of labels nearer to a different line than to their
  own.
- (c) the count of crossings of two lines in the band.
- the count of lines with a part in the band, the count of the vertical tracks (different x
  values of vertical parts), and the count of actors.

Then the script measures the same values for scratch changes of the page (the script text
and the page data in the temporary page only, no change of the product code):

The workspace fixture has one actor at the left of its frame and two actors below it. Thus
the script also measures the band between the bottom edge of the frame and the actors below
it, on the axis y (`below`).

- `gap+D`: the band at the left of the frame is D map units wider. The page data of the top map stretches each x in
  the band to the new width, and moves each x at the right of the band D units to the
  right (cards, boxes, regions, the points of the routes). This is the effect of a larger
  gap between the actor column and the frame with the same routes.
- `lane=N`: the lanes of a shared line are N map units apart (`LANE`, now 4.5).
- `least=N`: lanes spaced by a minimum. Parallel parts whose axis values are less than N map
  units apart (a chain in the order of `lanesOf`) and whose ranges overlap are one group, and
  the group gets lanes N map units apart around its mean axis value. Today only parts on
  the same axis value are a group.
- `clear=G`: a label at rest takes a place on its line only when no other line is within G
  map units of its box, and the places are each 1/80 of a part (`SEAT_T`, now 1/20).
- combinations of these changes.

For each change, the cost: the zoom at the fit, the width of the map in map units and of
its frame on the screen, and the count of the labels at rest in each layer tab of the top
map.

This is a baseline measurement for the targets of stages 3 and 4 of the open faults. It has
no acceptance value.

Run from the repository root (Node and the Playwright package must be installed):
    uv run python bench/jev/t0_context.py
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import t0_common as common  # noqa: E402

DRIVER = HERE / "t0_context.js"
LANE = ("var LANE = 4.5,", "var T0MIN = {m}, LANE = {v},")
GROUP = (
    "while (j < segs.length && segs[j].c === segs[k].c && segs[j].lo < hi - 2) {",
    "while (j < segs.length && segs[j].c - segs[j - 1].c < T0MIN && segs[j].lo < hi - 2) {",
)
SPREAD = (
    "group.sort(function (a, b) { return a.n - b.n; });group.forEach(function (s, n) "
    "{var d = (n - (group.length - 1) / 2) * LANE;",
    "var base = group.reduce(function (t, s) { return t + s.c; }, 0) / group.length, "
    "gap = Math.max(LANE, T0MIN);group.sort(function (a, b) { return a.c - b.c || a.n - b.n; });"
    "group.forEach(function (s, n) {var d = base + (n - (group.length - 1) / 2) * gap - s.c;",
)
SEAT = (
    "for (var n = 1; n < 20; n++) if (out.indexOf(n / 20) < 0) more.push(n / 20);",
    "for (var n = 1; n < 80; n++) if (out.indexOf(n / 80) < 0) more.push(n / 80);",
)
CLEAR = (
    "if (!crossed(box, list, e) && !ownCrossed(box, q, i)) best",
    "if (!crossed([box[0] - {v}, box[1] - {v}, box[2] + {v}, box[3] + {v}], list, e)"
    " && !ownCrossed(box, q, i)) best",
)


def _band(top: dict[str, Any]) -> tuple[float, float]:
    def held(b: list[float]) -> int:
        return sum(
            1
            for c in top["cards"]
            if c["k"] != "actor"
            and c["b"][0] >= b[0]
            and c["b"][0] + c["b"][2] <= b[0] + b[2]
            and c["b"][1] >= b[1]
            and c["b"][1] + c["b"][3] <= b[1] + b[3]
        )

    frame = max(top["boxes"], key=lambda b: held(b["b"]))["b"]
    left = [c for c in top["cards"] if c["k"] == "actor" and c["b"][0] + c["b"][2] <= frame[0]]
    return max(c["b"][0] + c["b"][2] for c in left), frame[0]


def _fx(x: float, lo: float, hi: float, d: float) -> float:
    """The new x of the change `gap+d`: the band from lo to hi is d units wider."""
    if x <= lo:
        return x
    if x >= hi:
        return x + d
    return lo + (x - lo) * (hi - lo + d) / (hi - lo)


def _box(b: list[float], lo: float, hi: float, d: float) -> None:
    x0, x1 = _fx(b[0], lo, hi, d), _fx(b[0] + b[2], lo, hi, d)
    b[0], b[2] = x0, x1 - x0


def stretch(d: float) -> Callable[[dict[str, Any]], None]:
    """Give the data change `gap+d` for the top map."""

    def shape(data: dict[str, Any]) -> None:
        top = data["maps"][0]
        lo, hi = _band(top)
        for item in top["cards"] + top["boxes"] + top["regions"]:
            _box(item["b"], lo, hi, d)
        for f in top["flows"]:
            for p in f["p"]:
                p[0] = _fx(p[0], lo, hi, d)
            if "lb" in f:
                _box(f["lb"], lo, hi, d)
        top["size"][0] += d

    return shape


def _edits(
    lane: float | None, least: float | None, clear: float | None
) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    if lane is not None or least is not None:
        out.append((LANE[0], LANE[1].format(v=lane or 4.5, m=least or 0)))
    if least is not None:
        out += [GROUP, SPREAD]
    if clear is not None:
        out += [SEAT, (CLEAR[0], CLEAR[1].format(v=clear))]
    return tuple(out)


# name: (gap, lane, least, clear)
CHANGES: dict[str, tuple[float, float | None, float | None, float | None]] = {
    "today": (0, None, None, None),
    "gap+60": (60, None, None, None),
    "gap+120": (120, None, None, None),
    "lane=9": (0, 9, None, None),
    "least=9": (0, None, 9, None),
    "least=12": (0, None, 12, None),
    "clear=4": (0, None, None, 4),
    "clear=8": (0, None, None, 8),
    "gap+120 least=12": (120, None, 12, None),
    "gap+120 least=12 clear=4": (120, None, 12, 4),
}


def _counts(d: list[float]) -> str:
    return ", ".join(f"<{t}: {sum(1 for v in d if v < t)}" for t in (4, 6, 8, 10))


def report(name: str, out: dict[str, Any], base: dict[str, Any] | None) -> None:
    """Print the values of one page."""
    fit = out["fit"]["k"]
    labels = sum(out["perTab"].values())
    print(f"\n### {name}")
    print(
        f"fit zoom {fit:.3f}, map {out['size'][0]:.0f} x {out['size'][1]:.0f} units, "
        f"frame {out['frame'][2]:.0f} px of {out['width']} px, "
        f"labels at rest in all tabs {labels} ({out['perTab']})"
    )
    if base is not None:
        lost = {
            t: base["perTab"][t] - out["perTab"].get(t, 0)
            for t in base["perTab"]
            if base["perTab"][t] != out["perTab"].get(t, 0)
        }
        print(f"labels lost against today (negative: more labels): {lost or 'none'}")
    for key in ("system", "below"):
        band(key, out[key])


def band(key: str, s: dict[str, Any] | None) -> None:
    """Print the values of one band."""
    if s is None or s.get("axis", -1) < 0:
        print(f"no band ({key}): {s}")
        return
    print(f"band of the actors {'at the left of' if key == 'system' else 'below'} the frame:")
    print(
        f"system layer: {s['n']} lines, busy {s['dense']}, scale {s['a']:.3f}; actors "
        f"{s['actors']} of {s['actorsAll']}; frame {s['frame']['id']}; band {s['band'][0]:.1f} to "
        f"{s['band'][1]:.1f} units ({(s['band'][1] - s['band'][0]):.1f} units, "
        f"{(s['band'][1] - s['band'][0]) * s['a']:.0f} px) on axis {'xy'[s['axis']]}"
    )
    print(
        f"(c) lines in the band {s['lines']}, vertical tracks {s['tracks']}, vertical parts "
        f"{s['vertical']}, horizontal parts {s['horizontal']}, crossings {s['crossings']}"
    )
    d = s["pairs"]
    print(
        f"(a) parallel pairs {len(d)} ({s['pairKinds']}), smallest "
        f"{(min(d) if d else float('nan')):.2f} px, {_counts(d)}"
    )
    for kind in ("across", "along"):
        print(f"    {kind}: {_counts([p['d'] for p in s['near'] if p['kind'] == kind])}")
    print(
        "    the closest pairs: "
        + "; ".join(f"{p['kind']} flows {p['f']} {p['d']:.2f} px" for p in s["near"][:6])
    )
    lab = s["labels"]
    nearer = sum(1 for x in lab if x["other"] < x["own"])
    tight = sum(1 for x in lab if x["otherBox"] < 4)
    print(
        f"(b) labels at rest in the band {len(lab)} of {s['labelsAll']} in the layer; nearer to "
        f"a different line than to their own: {nearer}; box less than 4 px from a different "
        f"line: {tight}"
    )
    for x in lab:
        print(
            f"    flow {x['f']} '{x['s']}': own {x['own']:.1f} px, nearest other (flow "
            f"{x['near']}) {x['other']:.1f} px from the centre, {x['otherBox']:.1f} px from "
            f"the box (label height {x['h']:.1f} px)"
        )


def main() -> int:
    inputs = {"self": common.self_data(), "workspace": common.workspace_data()}
    with tempfile.TemporaryDirectory() as tmp:
        for page, (theme, data) in inputs.items():
            print(f"\n## {page}")
            base = None
            for name, (gap, lane, least, clear) in CHANGES.items():
                html = common.write(
                    Path(tmp) / f"{page}.html",
                    theme,
                    data,
                    _edits(lane, least, clear),
                    stretch(gap) if gap else None,
                )
                out = common.drive(DRIVER, str(html))
                report(name, out, base)
                if base is None:
                    base = out
                    if out["system"] is None:
                        print("the map has no System context layer: no change is measured")
                        break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
