"""The description command gives measurements of the map geometry.

The page generator supplies positions, paths, and labels. The report gives component
counts, route scores, label capacity, layers, sequences, and evidence states. A coding
agent can read these measurements without a browser.
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
    """This function counts right-angle bends in a route. A straight path has no bends."""
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
    """This function gets the label span along a row gutter or column gutter."""
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
    """This function gives the maximum occupied seats and capacity of each gutter.

    A horizontal path assigns its label to a row gutter. A vertical path assigns its
    label to a column gutter.
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
    """This function calculates the routing score from reported collisions, fallback
    routes, bends, and path lengths.
    """
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
    """This function gives sequences and entry point coverage."""
    if not meaning.journeys:
        return [
            (
                "sequences: No sequence is available. Use systemap journeys, or write a "
                "sequence for each entry point."
            )
        ]
    states = evidence_of(model, meaning, facts, observed_by)
    out = ["sequences: These steps give the system operations."]
    for j in meaning.journeys:
        out += _walk_lines(j, states)
    return out + _ways_in_lines(model, meaning, facts)


def _walk_lines(j: Journey, states: dict[Edge, Any]) -> list[str]:
    """This function gives a sequence start, step count, and steps without import evidence."""
    where = f", from {j.starts}" if j.starts else ""
    note = (
        " (an agent wrote the sequence. no maintainer source review is available)"
        if j.drafted
        else ""
    )
    out = [f"  {j.id}: {_plural(len(j.steps), 'step')}{where}{note}"]
    thin = [f"{a} -> {b}" for a, b in (s.edge for s in j.steps) if _unbacked(states, (a, b))]
    if thin:
        out.append(
            f"    no import evidence: {', '.join(thin)}. No import gives evidence for "
            f"{_word(len(thin))}"
        )
    return out


def _ways_in_lines(model: Model, meaning: Meaning, facts: dict[str, Any]) -> list[str]:
    """This function gives entry point coverage and entry points without sequences."""
    ways = len(facts.get("entry_points", []))
    if not ways:
        return ["  entry points: The facts contain none. No sequence is necessary."]
    left = journeys_mod.uncovered(meaning, facts, owners(model, facts))
    out = [f"  entry points: {ways - len(left)} of {ways} have sequence coverage"]
    if left:
        named = ", ".join(entry_label(p) for p in left[:5])
        more = f", and {len(left) - 5} more" if len(left) > 5 else ""
        out.append(f"    without a sequence: {named}{more}. Use systemap journeys.")
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
    """This function gives the geometry from drawing metadata.

    The placed argument identifies temporary component positions missing from the model.
    The report identifies these positions separately from stored positions.
    """
    cards: dict[str, list[float]] = meta["cards"]
    paths: dict[str, list[list[float]]] = meta["paths"]
    labels: list[dict[str, Any]] = meta["labels"]
    w, h = model.canvas
    layers = all_layers(model, meaning)
    out = [
        (
            f"canvas {w} x {h}: {_plural(len(model.components), 'component')}, "
            f"{_plural(len(model.flows), 'edge')}, "
            f"{_plural(len(model.regions), 'region')}, {_plural(len(layers), 'layer')}"
        )
    ]
    placed_ids = list(placed)
    pinned = sum(1 for c in model.components if c.pinned and c.id not in placed_ids)
    written = len(model.components) - pinned - len(placed_ids)
    line = f"positions: {pinned} pinned, {written} placed"
    if placed_ids:
        line += (
            f", {len(placed_ids)} positions for this report are missing from the model "
            f"({', '.join(placed_ids)}). Use systemap place."
        )
    out.append(line)

    out.append("regions: The component counts follow.")
    for r in model.regions:
        ids = [c.id for c in model.components if c.region == r.id]
        held = f" ({', '.join(ids)})" if ids else ""
        out.append(f"  {r.id}: {_plural(len(ids), 'component')}{held}")
    outside = [c.id for c in model.components if not c.region]
    if outside:
        out.append(
            f"  in a container only: {_plural(len(outside), 'component')} ({', '.join(outside)})"
        )

    order = ", ".join(grid_order(model)) if model.regions else "none"
    cost = drawn_score(meta, len(model.flows)).text()
    if searched is None:
        how = "as written"
    elif searched[0]:
        how = (
            f"{searched[0]} orders examined, {searched[1]} routed for this report. Use "
            f"systemap place."
        )
    else:
        how = "listed order for this report. Use systemap place."
    out.append(f"region order: {order}. {cost}. {how}")

    rows, cols = gutters({cid: (b[0], b[1], b[2], b[3]) for cid, b in cards.items()}, (w, h))
    out.append("edges: Bend counts, lengths, and label positions follow in score order.")
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
            where = f". label {g.name}" if g is not None else ". label on its path"
        out.append(
            f"  {f.src} -> {f.dst} ('{f.artifact}'): {_plural(bends(path), 'bend')}, "
            f"{length(path):.0f} long{where}"
        )

    out.append("gutters: The maximum occupied seat counts and seat capacities follow.")
    out += gutter_lines(labels, paths, rows, True)
    out += gutter_lines(labels, paths, cols, False)

    counts: dict[str, int] = meta.get("evidence", {})
    out.append(
        "evidence: "
        + ", ".join(f"{counts.get(state, 0)} {state}" for state in STATES)
        + " (import evidence, a shared module, an external actor, or no fact evidence)"
    )

    out.append("layers: The component and edge counts follow.")
    for lay in layers:
        edges, subjects = reading(model, meaning, lay.id)
        lit = set(subjects)
        for i in edges:
            lit.update(model.flows[i].edge)
        out.append(f"  {lay.id}: {_plural(len(lit), 'component')}, {_plural(len(edges), 'edge')}")

    collisions = list(meta.get("collisions", []))
    notes = list(meta.get("notes", []))
    if collisions or notes:
        out.append(
            f"check errors: {_plural(len(collisions), 'label collision')}, "
            f"{_plural(len(notes), 'route')} with rule errors. Use systemap check."
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
    """This function renders the map once with the page generator and gives its
    measurements.
    """
    _svg, detail = render_schematic(model, meaning, t, facts, observed_by=observed_by)
    meta = json.loads(detail)["_meta"]
    out = lines(model, meaning, meta, placed, searched)
    walks = journey_lines(model, meaning, facts, observed_by)
    # What the check refuses stays the last line: it is the one that names a fix.
    if out and out[-1].startswith("check errors"):
        return out[:-1] + walks + out[-1:]
    return out + walks
