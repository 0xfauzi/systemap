"""What a look at the picture would tell an agent that cannot look.

The agent that draws the map often cannot open the page: it runs headless,
and a figure is bytes it cannot see. What a person takes from one look
(this region is crowded, that edge snakes across the whole map, the
gutter under the second row is full, the Control reading lights almost
nothing) is read here out of the same geometry the drawing has, and
printed as numbers:

    positions ... how many cards are pinned (marked `pinned=True`, a
                  position a person chose), how many `systemap place`
                  placed and wrote, and how many it placed for this look
                  only, not yet written
    regions ..... how many cards each holds, and which
    order ....... the regions as they follow each other on the grid, and
                  what the drawing costs under that order: label
                  collisions and refused routes when there are any, the
                  bends and the length of every route together; and, when
                  `place` chose the order for this look, how many orders
                  it tried and routed
    edges ....... bends and length, worst first, and where each label sits
    evidence .... how many edges are observed, external and declared
    gutters ..... the bands between card rows and columns: how many label
                  seats each has and how many are used at its fullest
    readings .... how many cards and edges each layer lights
    journeys .... each walk: its steps, where it starts, whether the code
                  backs every step, and whether an agent wrote it and
                  nobody has read it yet; then how many ways into the
                  system a journey walks from

Nothing here is a rule; `systemap check` refuses, this describes. A
crowded gutter is a thing to look at, not a failure, until a label cannot
be seated, and then the check says so with the fix.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from systemap import journeys as journeys_mod
from systemap.evidence import DECLARED, STATES, owners
from systemap.evidence import of_model as evidence_of
from systemap.extract import entry_label
from systemap.model import Edge, Journey, Meaning, Model, all_layers, reading
from systemap.place import Score, grid_order
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


def drawn_score(meta: dict[str, Any], flows: int) -> Score:
    """The drawing's score, read back from its `_meta`: the label collisions
    it reports, the routes that had to break a rule, every path's bends and length."""
    paths: dict[str, list[list[float]]] = meta["paths"]
    return Score(
        collisions=sum(1 for line in meta.get("collisions", []) if line.startswith("label ")),
        refused=len(meta.get("notes", [])),
        bends=sum(bends(paths.get(str(i), [])) for i in range(flows)),
        length=int(round(sum(length(paths.get(str(i), [])) for i in range(flows)))),
    )


def journey_lines(
    model: Model, meaning: Meaning, facts: dict[str, Any], observed_by: Iterable[str] = ()
) -> list[str]:
    """Each walk through the system, and how many ways in have one.

    A journey is what a reader follows to understand the system, so what
    matters about it here is where it starts, how far it goes, and whether
    the code backs every step it claims. A step over a flow no import backs
    is a step the reader is asked to take on trust.
    """
    if not meaning.journeys:
        return ["journeys: none written; run: systemap journeys, or write one per way in"]
    states = evidence_of(model, meaning, facts, observed_by)
    out = ["journeys: the walks a reader can take through the system"]
    for j in meaning.journeys:
        out += _walk_lines(j, states)
    return out + _ways_in_lines(model, meaning, facts)


def _walk_lines(j: Journey, states: dict[Edge, Any]) -> list[str]:
    """One walk: how far it goes, where from, and the steps nothing backs."""
    where = f", from {j.starts}" if j.starts else ""
    note = " (an agent wrote it; nobody has read it yet)" if j.drafted else ""
    out = [f"  {j.id}: {_plural(len(j.steps), 'step')}{where}{note}"]
    thin = [f"{a} -> {b}" for a, b in (s.edge for s in j.steps) if _unbacked(states, (a, b))]
    if thin:
        out.append(f"    on trust: {', '.join(thin)}; no import backs {_word(len(thin))}")
    return out


def _ways_in_lines(model: Model, meaning: Meaning, facts: dict[str, Any]) -> list[str]:
    """How many ways into the system a journey walks from, and which do not.

    The cards are passed so that a walk written for a whole crowd, which
    names its card rather than one of its hundred routes, counts here as it
    counts in `systemap judgement`.
    """
    ways = len(facts.get("entry_points", []))
    if not ways:
        return ["  ways in: none in the facts, so no walk can be asked for"]
    left = journeys_mod.uncovered(meaning, facts, owners(model, facts))
    out = [f"  ways in: {ways - len(left)} of {ways} walked from"]
    if left:
        named = ", ".join(entry_label(p) for p in left[:5])
        more = f", and {len(left) - 5} more" if len(left) > 5 else ""
        out.append(f"    with no walk: {named}{more}; run: systemap journeys")
    return out


def _unbacked(states: dict[Edge, Any], edge: Edge) -> bool:
    found = states.get(edge)
    return found is not None and found.state == DECLARED


def _word(n: int) -> str:
    return "it" if n == 1 else "them"


def lines(
    model: Model,
    meaning: Meaning,
    meta: dict[str, Any],
    placed: Iterable[str] = (),
    searched: tuple[int, int] | None = None,
) -> list[str]:
    """The description, from the drawing's own `_meta` (cards, paths, labels).

    `placed` names the cards `systemap place` positioned for this look
    because the model has none for them; the rest have a written
    position, and the ones marked `pinned` are counted as pinned.
    `searched` is (orders tried, orders routed) when `place` laid the
    whole map out for this look and chose the region order; None when
    the order is the one written.
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
    pinned = sum(1 for c in model.components if c.pinned and c.id not in placed_ids)
    written = len(model.components) - pinned - len(placed_ids)
    line = f"positions: {pinned} pinned, {written} placed"
    if placed_ids:
        line += (
            f", {len(placed_ids)} placed for this look and not yet written "
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

    order = ", ".join(grid_order(model)) if model.regions else "none"
    cost = drawn_score(meta, len(model.flows)).text()
    if searched is None:
        how = "as written"
    elif searched[0]:
        how = (
            f"{searched[0]} orders tried, {searched[1]} routed, for this look; run: systemap place"
        )
    else:
        how = "as listed, for this look; run: systemap place"
    out.append(f"region order: {order}; {cost}; {how}")

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
        + " (an import or a shared module joins the ends, an actor is at one end, or nothing "
        "in the facts does)"
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
    searched: tuple[int, int] | None = None,
) -> list[str]:
    """Draw once, the way the page does, and describe what was drawn."""
    _svg, detail = render_schematic(model, meaning, t, facts, observed_by=observed_by)
    meta = json.loads(detail)["_meta"]
    out = lines(model, meaning, meta, placed, searched)
    walks = journey_lines(model, meaning, facts, observed_by)
    # What the check refuses stays the last line: it is the one that names a fix.
    if out and out[-1].startswith("and what the check refuses"):
        return out[:-1] + walks + out[-1:]
    return out + walks
