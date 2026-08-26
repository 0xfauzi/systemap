"""What a look at the picture would tell an agent that cannot look.

The agent that draws the map often cannot open the page: it runs headless,
and a figure is bytes it cannot see. What a person takes from one look
(this region is crowded, that edge snakes across the whole map, the
gutter under the second row is full, the Control reading lights almost
nothing) is read here out of the same geometry the drawing has, and
printed as numbers:

    positions ... how many cards are pinned (x and y in the model) and how
                  many `systemap place` placed for this look, not yet
                  written
    regions ..... how many cards each holds, and which
    edges ....... bends and length, worst first, and where each label sits
    evidence .... how many edges are observed, external and declared
    gutters ..... the bands between card rows and columns: how many label
                  seats each has and how many are used at its fullest
    readings .... how many cards and edges each layer lights

Nothing here is a rule; `systemap check` refuses, this describes. A
crowded gutter is a thing to look at, not a failure, until a label cannot
be seated, and then the check says so with the fix.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from systemap.evidence import STATES
from systemap.model import Meaning, Model, all_layers, reading
from systemap.route import Gutter, gutters, locate, seats
from systemap.schematic import LABEL_H
from systemap.schematic import render as render_schematic

Box = tuple[float, float, float, float]


def bends(points: list[list[float]]) -> int:
    """The right-angle turns on a routed path: a straight run has none."""
    return max(0, len(points) - 2)


def length(points: list[list[float]]) -> float:
    return sum(
        abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:], strict=False)
    )


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _centre(box: list[float], horizontal: bool) -> float:
    return box[1] + box[3] / 2 if horizontal else box[0] + box[2] / 2


def _extent(box: list[float], horizontal: bool) -> tuple[float, float]:
    """The label's span along the gutter: x for a row gutter, y for a column."""
    return (box[0], box[0] + box[2]) if horizontal else (box[1], box[1] + box[3])


def _seat_orientation(path: list[list[float]], segment: int) -> bool:
    if not 0 <= segment < len(path) - 1:
        return True
    return abs(path[segment + 1][1] - path[segment][1]) < 1e-6


def gutter_lines(
    labels: list[dict[str, Any]],
    paths: dict[str, list[list[float]]],
    bands: list[Gutter],
    horizontal: bool,
) -> list[str]:
    """One line per gutter: seats used at its fullest of the seats it has.

    A label sits in the row gutter its centre falls in (for a label on a
    horizontal run) or the column gutter (on a vertical run); `horizontal`
    says which kind `bands` are. The seats a gutter has is how many labels
    stack across it; the seats used is the deepest stack of labels whose
    spans overlap along it.
    """
    out: list[str] = []
    for g in bands:
        inside = [
            lab
            for i, lab in enumerate(labels)
            if _seat_orientation(paths.get(str(i), []), int(lab["segment"])) == horizontal
            and g.holds(_centre(lab["box"], horizontal))
        ]
        peak = 0
        for lab in inside:
            lo, hi = _extent(lab["box"], horizontal)
            depth = sum(
                1
                for other in inside
                if (o := _extent(other["box"], horizontal)) and o[0] < hi and lo < o[1]
            )
            peak = max(peak, depth)
        available = seats(g.size, LABEL_H)
        out.append(
            f"  {g.name} ({g.size:.0f} units): {peak} of {available} seats used, "
            f"{_plural(len(inside), 'label')}"
        )
    return out


def lines(
    model: Model, meaning: Meaning, meta: dict[str, Any], placed: Iterable[str] = ()
) -> list[str]:
    """The description, from the drawing's own `_meta` (cards, paths, labels).

    `placed` names the cards `systemap place` positioned for this look
    because the model has none for them; the rest are pinned.
    """
    cards: dict[str, list[float]] = meta["cards"]
    paths: dict[str, list[list[float]]] = meta["paths"]
    labels: list[dict[str, Any]] = meta["labels"]
    w, h = model.canvas
    layers = all_layers(model, meaning)
    out = [
        f"canvas {w} x {h}: {_plural(len(model.components), 'card')}, "
        f"{_plural(len(model.flows), 'edge')}, {_plural(len(model.regions), 'region')}, "
        f"{_plural(len(layers), 'reading')}"
    ]
    placed_ids = list(placed)
    pinned = len(model.components) - len(placed_ids)
    line = f"positions: {pinned} pinned"
    if placed_ids:
        line += (
            f", {len(placed_ids)} placed by systemap place and not yet written "
            f"({', '.join(placed_ids)}); run: systemap place"
        )
    out.append(line)

    out.append("regions: the cards each holds")
    for r in model.regions:
        ids = [c.id for c in model.components if c.region == r.id]
        held = f" ({', '.join(ids)})" if ids else ""
        out.append(f"  {r.id}: {_plural(len(ids), 'card')}{held}")
    outside = [c.id for c in model.components if not c.region]
    if outside:
        out.append(f"  in a container only: {_plural(len(outside), 'card')} ({', '.join(outside)})")

    rows, cols = gutters({cid: (b[0], b[1], b[2], b[3]) for cid, b in cards.items()}, (w, h))
    out.append("edges, worst first: bends, length, where the label sits")
    ranked = sorted(
        range(len(model.flows)),
        key=lambda i: (-bends(paths.get(str(i), [])), -length(paths.get(str(i), []))),
    )
    for i in ranked:
        f = model.flows[i]
        path = paths.get(str(i), [])
        lab = labels[i] if i < len(labels) else None
        where = ""
        if lab is not None:
            box = lab["box"]
            g = locate(
                (box[0], box[1], box[2], box[3]),
                _seat_orientation(path, int(lab["segment"])),
                rows,
                cols,
            )
            where = f"; label {g.name}" if g is not None else "; label on its run"
        out.append(
            f"  {f.src} -> {f.dst} ('{f.artifact}'): {_plural(bends(path), 'bend')}, "
            f"{length(path):.0f} long{where}"
        )

    out.append("gutters: seats used at the fullest point of the seats each has")
    out += gutter_lines(labels, paths, rows, True)
    out += gutter_lines(labels, paths, cols, False)

    counts: dict[str, int] = meta.get("evidence", {})
    out.append(
        "evidence: "
        + ", ".join(f"{counts.get(state, 0)} {state}" for state in STATES)
        + " (an import joins the ends, an actor is at one end, or nothing in the facts does)"
    )

    out.append("readings: the cards and edges each lights")
    for lay in layers:
        edges, subjects = reading(model, meaning, lay.id)
        lit = set(subjects)
        for i in edges:
            lit.update(model.flows[i].edge)
        out.append(f"  {lay.id}: {_plural(len(lit), 'card')}, {_plural(len(edges), 'edge')}")

    collisions = list(meta.get("collisions", []))
    notes = list(meta.get("notes", []))
    if collisions or notes:
        out.append(
            f"and what the check refuses: {_plural(len(collisions), 'label collision')}, "
            f"{_plural(len(notes), 'route')} that had to break a rule; run: systemap check"
        )
    return out


def run(
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    observed_by: Iterable[str] = (),
    placed: Iterable[str] = (),
) -> list[str]:
    """Draw once, the way the page does, and describe what was drawn."""
    _svg, detail = render_schematic(model, meaning, t, facts, observed_by=observed_by)
    meta = json.loads(detail)["_meta"]
    return lines(model, meaning, meta, placed)
