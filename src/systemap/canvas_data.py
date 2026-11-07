"""The canvas data: one JSON object for all maps of a map tree.

The canvas page (docs/design/nested-canvas.md) draws all maps of a tree on one canvas
from this object. This module adds no facts. It uses the model, the stored facts, the
evidence states, the assurance claims, the router, and the boundary findings
(`nest_join`). The page code uses the same functions for the same values.

`build` gives the object, and `text` gives its JSON text. The object is deterministic:
the maps are in tree order, the cards are in reading order (top to bottom, then left to
right), the flows are in model order, and `text` sorts the keys. A number is rounded to
one decimal, as the SVG path of the page is. A number without a fraction is an integer.

The keys of the object:

- `v`: the format version. `name`: the project name. `rev`: the commit of the facts.
- `unknown`: the lines of the facts that the extractor could not read. The page gives
  them as "Unknown source information".
- `judged`: true if `build` received the open lines of the judgement. Then each port
  gives only its open lines. If it is false, each port gives all of its lines, and the
  page must not tell that a line is open.
- `maps`: one object for each map, in tree order.

The keys of a map:

- `id`: the map ID, "" for the top map. `up`: the ID of the parent map. `card`: the ID
  of the card in the parent map that opens this map. The top map has no `up` and `card`.
- `size`: the canvas width and height.
- `boxes`: the containers. Each has `id`, `n` (the label), `b` (the box: x, y, width,
  height), `t` (the tone), and `u` (the subtitle, if any).
- `regions`: the regions in model order. The region number is the index plus 1. Each has
  `id`, `n`, `b`, and `c` (the container, if any).
- `layers`: the layers in page order. Each has `id`, `n`, `q` (the question), `e` (the
  indexes of the flows that the layer shows), and `dv` (1 for a derived layer).
- `cards`: each card has `id`, `b`, `k` (the kind), `r` (the region or the container),
  `p` (the card text), and `d` (the `does` text). It can also have `m` (the
  `implemented_by` claims), `s` (the source state), `as` (the assurance level and the
  freshness), `l` (the layers that have the card as a subject, except `structure`,
  which has all cards), `u` (the claims that cover no module), and `o` (the ID of the
  map that the card opens).
- `flows`: each flow has `s` (the source), `t` (the destination), `a` (the artifact),
  `k` (the kind), `l` (the layer), `ev` (the evidence state), `p` (the route points),
  and `lb` (the label box). It can also have `id` (the flow id) and `as`. The route
  points and the label box come from `route.routed`, in the coordinates of this map.
- `ports`: only in a nested map. A port is the end of a boundary flow at the actor
  card. Each port has `x` (the actor, or for a `boundary import` line, the parent
  component that has no actor in the map), `d` ("in" or "out" of the map), and `pf` (the
  indexes of the parent flows between the opening card and the actor, in the same
  direction). A port of a nested flow also has `i` (the internal component), `f` (the
  flow index) and `at` (the end point of the route). It can also have `fp`: two points,
  from the middle of a side of the actor card to the frame of the map, in a straight
  line that crosses no other card. The page draws
  the boundary flow from the portal to the frame, then along `fp` to the actor card, and
  then along the route of the nested flow. A port without `fp` has no side for this line.
  `n` gives the `boundary flow` and `boundary import` lines of the port. A line that has
  no nested flow gives a port without `f`.
- `ch`: the revision comparison of the map (`page_data.comparison`), if `build`
  received changes for the map. Such a map also has the change keys `cm`, `cl`, `cr`
  and `ci` (`canvas_changes`): the change marks of the cards, the lost flows, and the
  roll-up of the map changes.
- `sq`: the sequences of the map (`canvas_sequences`), only in a map that has sequences.

An example from the fixture of tests/test_nest_join.py, after `place`: the card Gateway
and its flow to Auth in the top map, and a port of the map inside Gateway.

    {"as": ["unknown", "missing"], "b": [147, 200, 150, 56], "d": "Takes the requests.",
     "id": "Gateway", "k": "component", "m": ["pkg.gateway.*"], "o": "Gateway",
     "p": "the gateway", "r": "work", "s": "built"}
    {"a": "token", "as": ["unknown", "missing"], "ev": "structural", "k": "data",
     "l": "data", "lb": [307.8, 167.4, 36.5, 13], "p": [[297, 212], [326, 212],
     [326, 152], [337, 152]], "s": "Gateway", "t": "Auth"}
    {"at": [186, 136], "d": "out", "f": 0, "fp": [[36, 136], [0, 136]], "i": "Routes",
     "pf": [0], "x": "Auth"}
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from typing import Any

from systemap import (
    assurance,
    canvas_changes,
    canvas_sequences,
    evidence,
    nest,
    nest_join,
    page_data,
    source_facts,
)
from systemap.config import Config
from systemap.model import (
    DERIVED_LAYERS,
    Component,
    Meaning,
    Model,
    all_layers,
    build_state,
    claimed,
    reading,
)
from systemap.schematic import Box, Placed, Point, Route, crosses, flow_routes, geometry

VERSION = 1


def _num(value: float) -> float | int:
    """Round a coordinate to one decimal. Give an integer for a value without a fraction."""
    rounded = round(float(value), 1)
    return int(rounded) if rounded.is_integer() else rounded


def _box(box: Collection[float]) -> list[float | int]:
    return [_num(v) for v in box]


def _level(claim: assurance.Claim | None) -> dict[str, list[str]]:
    return {"as": [claim.level, claim.freshness]} if claim is not None else {}


def _some(**fields: Any) -> dict[str, Any]:
    """Give the fields that have a value. An empty list or text is not a value."""
    return {key: value for key, value in fields.items() if value not in ("", [], None)}


def _layers(m: nest.Map) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Give the layers of the map, and the subject layers of each card."""
    out: list[dict[str, Any]] = []
    subject_of: dict[str, list[str]] = {}
    for layer in all_layers(m.model, m.meaning):
        edges, subjects = reading(m.model, m.meaning, layer.id)
        out.append(
            {"id": layer.id, "n": layer.label, "q": layer.question, "e": edges}
            | ({"dv": 1} if layer.id in DERIVED_LAYERS else {})
        )
        if layer.id != "structure":
            for cid in subjects:
                subject_of.setdefault(cid, []).append(layer.id)
    return out, subject_of


def _card(
    c: Component,
    m: nest.Map,
    box: Collection[float],
    facts: dict[str, Any],
    found: Mapping[str, assurance.Claim],
    owned: list[str],
    extra: dict[str, Any],
) -> dict[str, Any]:
    modules = facts.get("components", {})
    state = "" if c.kind == "actor" else build_state(c, facts)
    unresolved = page_data.unresolved_claims(c, modules, owned)
    return {
        "id": c.id,
        "b": _box(box),
        "k": c.kind,
        "r": c.home,
        "p": m.meaning.plain.get(c.id, ""),
        "d": c.does,
        **_some(m=list(c.implemented_by), s=state, u=unresolved),
        **_level(found.get(c.id)),
        **extra,
    }


def _flows(
    model: Model,
    meaning: Meaning,
    routes: Mapping[int, Route],
    seats: Mapping[int, Placed],
    backed: evidence.ByFlow,
    found: Mapping[str, assurance.Claim],
) -> list[dict[str, Any]]:
    return [
        {
            "s": f.src,
            "t": f.dst,
            "a": f.artifact,
            "k": f.kind,
            "l": meaning.layer_for(f, f.kind),
            "ev": backed.of(f).state,
            "p": [_box(point) for point in routes[i].points],
            "lb": _box(seats[i].box),
            **_some(id=f.id),
            **_level(found.get(f.key)),
        }
        for i, f in enumerate(model.flows)
    ]


def _parent_flows(parent: Model, card: str, other: str, way: str) -> list[int]:
    """Give the indexes of the parent flows between `card` and `other`, from the card
    for the direction "out" and to the card for "in"."""
    edge = (card, other) if way == "out" else (other, card)
    return [i for i, f in enumerate(parent.flows) if f.edge == edge]


def _frame_path(
    actor: str, boxes: Mapping[str, Box], size: Point, used: str
) -> list[list[float | int]]:
    """Give the shortest straight line from a side of the actor card to the frame of the
    map that crosses no other card. The line does not start on the side `used` of the route.

    Give an empty list when each side has a card between the actor card and the frame."""
    x, y, w, h = boxes[actor]
    cx, cy = x + w / 2, y + h / 2
    sides: dict[str, tuple[Point, Point]] = {
        "left": ((x, cy), (0.0, cy)),
        "right": ((x + w, cy), (size[0], cy)),
        "top": ((cx, y), (cx, 0.0)),
        "bottom": ((cx, y + h), (cx, size[1])),
    }
    clear = [
        (abs(b[0] - a[0]) + abs(b[1] - a[1]), a, b)
        for side, (a, b) in sides.items()
        if side != used
        and not any(crosses(a, b, box) for cid, box in boxes.items() if cid != actor)
    ]
    if not clear:
        return []
    _length, a, b = min(clear, key=lambda one: one[0])
    return [_box(a), _box(b)]


def _flow_ports(
    m: nest.Map,
    parent: Model,
    routes: Mapping[int, Route],
    lines: dict[tuple[str, str, str], list[str]],
    boxes: Mapping[str, Box],
) -> list[dict[str, Any]]:
    """Give one port for each nested flow between an internal component and an actor.

    A line goes to the first port of its component, actor, and direction only."""
    out = []
    size = (float(m.model.canvas[0]), float(m.model.canvas[1]))
    for i, f in enumerate(m.model.flows):
        if nest_join.crossing(m.model, m.card, f.src, f.dst):
            inner, other, way = f.src, f.dst, "out"
        elif nest_join.crossing(m.model, m.card, f.dst, f.src):
            inner, other, way = f.dst, f.src, "in"
        else:
            continue
        route = routes[i]
        end, side = (
            (route.points[-1], route.dst_side)
            if way == "out"
            else (route.points[0], route.src_side)
        )
        out.append(
            {
                "x": other,
                "i": inner,
                "d": way,
                "f": i,
                "pf": _parent_flows(parent, m.card, other, way),
                "at": _box(end),
                **_some(
                    fp=_frame_path(other, boxes, size, side),
                    n=lines.pop((inner, other, way), []),
                ),
            }
        )
    return out


def _ports(
    tree: nest.Tree,
    m: nest.Map,
    facts: dict[str, Any],
    routes: Mapping[int, Route],
    boxes: Mapping[str, Box],
    open_lines: Collection[str] | None,
) -> list[dict[str, Any]]:
    """Give the ports of a nested map with the boundary lines of each port.

    A `boundary flow` line about a nested flow goes to the port of that flow. Each other
    line gives a port without a flow, one port for each actor, component, and direction.
    """
    parent = tree.get(m.parent or "")
    at_flow: dict[tuple[str, str, str], list[str]] = {}
    alone: dict[tuple[str, str, str], list[str]] = {}
    for one in nest_join.map_findings(tree, m, facts):
        if open_lines is not None and one.line not in open_lines:
            continue
        way = "out" if one.parent_flow[0] == m.card else "in"
        key = (one.inner, one.other, way)
        held = at_flow if one.kind == nest_join.FLOW_KIND and one.inner else alone
        held.setdefault(key, []).append(one.line)
    out = _flow_ports(m, parent.model, routes, at_flow, boxes)
    for (inner, other, way), lines in sorted(alone.items()):
        pf = _parent_flows(parent.model, m.card, other, way)
        out.append({"x": other, "d": way, "pf": pf, "n": sorted(lines), **_some(i=inner)})
    return out


def _map(
    cfg: Config,
    tree: nest.Tree,
    m: nest.Map,
    facts: dict[str, Any],
    open_lines: Collection[str] | None,
    change: Mapping[str, Any],
    found: canvas_changes.Rollups,
) -> dict[str, Any]:
    model = m.model
    geo = geometry(model)
    routes, seats = flow_routes(model, geo)
    claims = assurance.of_model(model, m.meaning, facts, m.id)
    modules = facts.get("components", {})
    owned = {c: claimed(c, modules) for c in model.components}
    layers, subject_of = _layers(m)
    opens = {child.card: child.id for child in tree.children(m)}
    cards_found = assurance.by_type(claims, assurance.COMPONENT)
    order = sorted(model.components, key=lambda c: (geo.boxes[c.id][1], geo.boxes[c.id][0], c.id))
    backed = evidence.of_model(model, m.meaning, facts, cfg.observed_by, owned)
    out: dict[str, Any] = {
        "id": m.id,
        **({} if m.parent is None else {"up": m.parent, "card": m.card}),
        "size": list(model.canvas),
        "boxes": [
            {"id": b.id, "n": b.label, "b": _box(b.box), "t": b.tone, **_some(u=b.sub)}
            for b in model.containers
        ],
        "regions": [
            {"id": r.id, "n": r.label, "b": _box(r.box), **_some(c=r.container)}
            for r in model.regions
        ],
        "layers": layers,
        "cards": [
            _card(
                c,
                m,
                geo.boxes[c.id],
                facts,
                cards_found,
                owned[c],
                _some(l=subject_of.get(c.id, []), o=opens.get(c.id, "")),
            )
            for c in order
        ],
        "flows": _flows(
            model,
            m.meaning,
            routes,
            seats,
            backed,
            assurance.by_type(claims, assurance.FLOW),
        ),
    }
    if m.parent is not None and tree.has(m.parent):
        out["ports"] = _ports(tree, m, facts, routes, geo.boxes, open_lines)
    comparison = page_data.comparison(dict(change))
    if comparison:
        out["ch"] = comparison
        out |= canvas_changes.keys(tree, m, backed, change, found)
    out.update(canvas_sequences.of_map(m, facts))
    return out


def build(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    open_lines: Collection[str] | None = None,
    changes: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Give the canvas data of all maps of the tree (see the module docstring).

    `open_lines` gives the open lines of the judgement (`judgement_json.evaluate`). Without
    it, the ports give all of their boundary lines. `changes` gives the change data of each
    map by map ID (`change.for_page`). A map without change data has no `ch`."""
    changes = changes or {}
    chosen = None if open_lines is None else frozenset(open_lines)
    found = canvas_changes.rollups(tree, changes)
    return {
        "v": VERSION,
        "name": cfg.name,
        "rev": facts.get("built_at_commit", ""),
        "unknown": source_facts.unknown_fact_lines(facts),
        "judged": chosen is not None,
        "maps": [
            _map(cfg, tree, m, facts, chosen, changes.get(m.id, {}), found) for m in tree.maps
        ],
    }


def text(data: Mapping[str, Any]) -> str:
    """Give the JSON text of the canvas data: sorted keys and no spaces."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
