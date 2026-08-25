"""Check the map geometry and the meaning tables mechanically.

The map is hand-placed (positions) and hand-authored (relations), so two
kinds of quiet lie are possible: a card drawn where the model does not claim
it, or a sentence that names a flow the model no longer has. Both fail here
instead of shipping.

What is checked, in order:

    placement ..... every card inside its band, no two cards overlapping,
                    every flow naming known components (the model)
    routes ........ every edge an orthogonal path that passes through no
                    card it does not connect and crosses no region box it
                    neither starts nor ends in (both counted, each offender
                    listed with the router's reason)
    labels ........ every edge label seated without touching a card, a
                    header or another label (the schematic's collision pass,
                    re-verified from the boxes it reports)
    type size ..... nothing in the figure set below 11px
    meaning ....... every flow has a layer and a sentence, every component a
                    plain word, every journey step a real edge and real ids,
                    every verb override a real edge
    wheel ......... for every component, the relationship wheel's name labels
                    stay inside the drawing and off each other and the centre

The CLI prints one line per problem and exits 1 when any is found.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from systemap.model import Meaning, Model
from systemap.model import problems as model_problems
from systemap.schematic import TEXT_PX
from systemap.schematic import render as render_schematic

Box = tuple[float, float, float, float]


def _overlap(a: Box, b: Box) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _box(values: list[float]) -> Box:
    return float(values[0]), float(values[1]), float(values[2]), float(values[3])


def check_labels(meta: dict[str, Any]) -> list[str]:
    out = [f"label collision: {line}" for line in meta.get("collisions", [])]
    labels: list[dict[str, Any]] = meta.get("labels", [])
    cards: dict[str, list[float]] = meta.get("cards", {})
    for k, lab in enumerate(labels):
        lb = _box(lab["box"])
        for cid, cb in cards.items():
            if _overlap(lb, _box(cb)):
                out.append(f"label '{lab['artifact']}' touches card {cid}")
        for other in labels[k + 1 :]:
            if _overlap(lb, _box(other["box"])):
                out.append(f"label '{lab['artifact']}' touches label '{other['artifact']}'")
    return out


def _seg_hits(a: list[float], b: list[float], box: Box) -> bool:
    """Does the axis-aligned segment a-b cross the interior of box?"""
    bx, by, bw, bh = box
    (x0, y0), (x1, y1) = a, b
    if abs(y0 - y1) < 1e-6:
        if not (by < y0 < by + bh):
            return False
        return min(x0, x1) < bx + bw and max(x0, x1) > bx
    if not (bx < x0 < bx + bw):
        return False
    return min(y0, y1) < by + bh and max(y0, y1) > by


def check_routes(meta: dict[str, Any], model: Model) -> tuple[list[str], int, int]:
    """(problems, edges through a foreign card, edges across a foreign region).

    A segment is judged against the exact card box (the router keeps a
    margin, so a touch here is a real pass-through) and against every
    region box other than the two the edge belongs to. An edge is counted
    once per offence, and listed with the router's own reason when it had
    to fall back.
    """
    out: list[str] = []
    paths: dict[Any, list[list[float]]] = meta.get("paths", {})
    cards: dict[str, list[float]] = meta.get("cards", {})
    notes: list[str] = meta.get("notes", [])
    region_of = {c.id: c.region or "" for c in model.components}
    regions = {r.id: _box(list(r.box)) for r in model.regions}
    through = 0
    across = 0
    for i, f in enumerate(model.flows):
        src, dst, art = f.src, f.dst, f.artifact
        pts = paths.get(str(i)) or paths.get(i)
        if not pts:
            out.append(f"route: {src} -> {dst} ('{art}') has no path")
            continue
        segs = list(zip(pts, pts[1:], strict=False))
        hit_cards = sorted(
            cid
            for cid, box in cards.items()
            if cid not in (src, dst) and any(_seg_hits(a, b, _box(box)) for a, b in segs)
        )
        hit_regions = sorted(
            rid
            for rid, box in regions.items()
            if rid not in (region_of[src], region_of[dst])
            and any(_seg_hits(a, b, box) for a, b in segs)
        )
        why = next((n for n in notes if n.startswith(f"{src} -> {dst}:")), "")
        reason = f" ({why.split(': ', 1)[1]})" if why else ""
        if hit_cards:
            through += 1
            out.append(f"route: {src} -> {dst} passes through {', '.join(hit_cards)}{reason}")
        if hit_regions:
            across += 1
            out.append(f"route: {src} -> {dst} crosses region {', '.join(hit_regions)}{reason}")
    return out, through, across


def check_type_size(svg: str) -> list[str]:
    small = sorted(
        {float(m) for m in re.findall(r"font-size:\s*([0-9.]+)px", svg) if float(m) < TEXT_PX}
    )
    return [f"text set at {s}px, below {TEXT_PX}px" for s in small]


# ---- the wheel, mirrored from schematic._INTERACTIVE_JS ----------------------
# The page lays the wheel out in the browser; this is the same arithmetic in
# Python so the label geometry can be checked without one. Keep the two in
# step: a change to one is a change to both.

W, H, CX, CY, R = 400.0, 400.0, 200.0, 200.0, 118.0
MONO_CHAR_W = 6.6
NAME_LINE_H = 13.0


def wrap_name(cid: str) -> list[str]:
    parts = re.findall(r"[A-Z]+[a-z0-9]*|[a-z0-9]+", cid) or [cid]
    lines: list[str] = []
    cur = ""
    for p in parts:
        if cur and len(cur + p) > 10:
            lines.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        lines.append(cur)
    return lines[:3]


def wheel_boxes(
    cid: str, edges: list[dict[str, str]], meaning: Meaning
) -> tuple[Box, list[tuple[str, Box]]]:
    order = {layer.id: i for i, layer in enumerate(meaning.layers)}
    idx = sorted(
        (i for i, e in enumerate(edges) if cid in (e["from"], e["to"])),
        key=lambda i: (order[edges[i]["layer"]], i),
    )
    groups = 0
    prev: str | None = None
    for i in idx:
        if edges[i]["layer"] != prev:
            groups += 1
            prev = edges[i]["layer"]
    gap = 0.5 if groups > 1 else 0.0
    step = 360.0 / (len(idx) + gap * groups) if idx else 360.0
    hw, hh = max(34.0, len(cid) * 3.7 + 12), 15.0
    centre: Box = (CX - hw, CY - hh, 2 * hw, 2 * hh)
    boxes: list[tuple[str, Box]] = []
    a = -90.0
    prev = None
    for i in idx:
        e = edges[i]
        if prev is not None and e["layer"] != prev:
            a += gap * step
        prev = e["layer"]
        th = math.radians(a)
        a += step
        ux, uy = math.cos(th), math.sin(th)
        other = e["to"] if e["from"] == cid else e["from"]
        lines = wrap_name(other)
        n = len(lines)
        lw = max(len(line) for line in lines) * MONO_CHAR_W
        ex, ey = CX + (R + 9) * ux, CY + (R + 9) * uy
        if abs(ux) < 0.35:
            first = ey - 4 - (n - 1) * NAME_LINE_H if uy < 0 else ey + 12
            left = ex - lw / 2
        else:
            first = ey + 4 - (n - 1) * 6.5
            left = ex + 2 if ux > 0 else ex - 2 - lw
        top = first - 10
        boxes.append((other, (left, top, lw, (n - 1) * NAME_LINE_H + NAME_LINE_H)))
    return centre, boxes


def check_wheels(edges: list[dict[str, str]], model: Model, meaning: Meaning) -> list[str]:
    out: list[str] = []
    for c in model.components:
        cid = c.id
        centre, boxes = wheel_boxes(cid, edges, meaning)
        for k, (name, box) in enumerate(boxes):
            x, y, w, h = box
            if x < 0 or y < 0 or x + w > W or y + h > H:
                out.append(f"wheel of {cid}: label {name} leaves the drawing")
            if _overlap(box, centre):
                out.append(f"wheel of {cid}: label {name} touches the centre")
            for other, ob in boxes[k + 1 :]:
                if _overlap(box, ob):
                    out.append(f"wheel of {cid}: labels {name} and {other} touch")
    return out


def run(
    model: Model, meaning: Meaning, t: dict[str, Any], facts: dict[str, Any], issue_url: str = ""
) -> tuple[list[str], list[str], tuple[int, int]]:
    """(problems, notes, (edges through a foreign card, edges across a foreign region)).

    Placement and meaning are checked first; the drawing is only attempted
    once those are clean, since a model that contradicts itself cannot be
    drawn honestly.
    """
    problems = model_problems(model, meaning)
    through = across = 0
    notes: list[str] = []
    if not problems:
        svg, detail = render_schematic(model, meaning, t, facts, issue_url=issue_url)
        meta = json.loads(detail)["_meta"]
        route_problems, through, across = check_routes(meta, model)
        problems += route_problems
        problems += check_labels(meta)
        problems += check_type_size(svg)
        problems += check_wheels(meta["edges"], model, meaning)
        notes = [n for n in meta.get("notes", []) if "shorter segment" in n]
    return problems, notes, (through, across)


def report(
    model: Model, problems: list[str], notes: list[str], counts: tuple[int, int]
) -> list[str]:
    """The lines the CLI prints for one check run."""
    through, across = counts
    out = [
        f"map routes: {through} edge{'s' if through != 1 else ''} through a card "
        f"they do not connect, {across} across a region they neither start nor end in"
    ]
    out += [f"  note: {line}" for line in notes]
    if problems:
        out.append(f"map layout: {len(problems)} problem{'s' if len(problems) != 1 else ''}")
        out += [f"  {line}" for line in problems]
        return out
    n = len(model.components)
    out.append(
        f"map layout: clean ({n} cards, {len(model.flows)} orthogonal labelled "
        f"edges, {n} wheels, nothing below {TEXT_PX:g}px)"
    )
    return out
