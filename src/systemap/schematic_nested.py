"""The marks of a nested map on its figure: neighbour cards, the frame, the ports, and the badge.

A nested map shows the inside of one parent component, the opening card. The page gives
the figure a context record (`page_context.context`). With it, the figure shows:

- A neighbour card: an actor that is an internal component of the parent map. It has the
  state label "in the parent map" and a corner notch. An actor that is also an actor of
  the parent map keeps the label "outside".
- The frame: one rectangle with the label "Inside <card>" around the internal cards. The
  actors stay outside the frame. A map with an actor inside the frame bounds has no frame.
- The ports: each point where a flow line crosses the frame. A port that has an open
  `boundary flow` or `boundary import` line is dotted and has a short text. A port that
  has no open line shows no join state, because no check confirms the boundary. The page
  never says "verified".
- The badge: the text "N inside" on a card that opens a map, at its lower-right corner.
  In the change map, a card whose map or a map below it changed has the badge text
  "changed inside" and a second outline on its back card (`changed_inside`).

The figure does not draw a relation between two maps that no check examines.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from systemap.model import Component, Model
from systemap.schematic_cards import LABEL_CHAR_W, TEXT_PX, Box, badge_box

# The space between the internal bounds and the frame line.
FRAME_PAD = 12
PARENT_LABEL = "in the parent map"
OUTSIDE_LABEL = "outside"
# The short port texts of the open boundary lines.
NO_PARENT_FLOW = "No flow in the parent map"
NO_FLOW_INSIDE = "No flow inside"
IMPORT_NO_FLOW = "Import with no flow"
# The colors of the new marks of a nested map, for the contrast test (M14): the mark, its
# theme token, its ground, and the minimum ratio. Text has 4.5:1 and a line has 3:1. The
# ground "actor" is the fill of an actor card. The parent context mark and the compact
# preview use the same tokens in the page CSS (`page_context.CSS`).
MARK_COLOURS: tuple[tuple[str, str, str, float], ...] = (
    ("frame label", "ink_2", "map", 4.5),
    ("port text", "ink_2", "map", 4.5),
    ("badge text", "ink_2", "raised", 4.5),
    ("parent context mark label", "ink_2", "surface", 4.5),
    ("frame line", "ink_3", "map", 3.0),
    ("port line", "ink_2", "map", 3.0),
    ("badge line", "ink_3", "map", 3.0),
    ("neighbour notch", "ink_2", "actor", 3.0),
    ("parent context card", "ink_3", "surface", 3.0),
    ("parent context neighbour", "ink_2", "surface", 3.0),
    ("parent context opening card", "ink_2", "surface", 3.0),
    ("preview frame and card", "ink_3", "bg", 3.0),
    ("preview stub", "ink_2", "bg", 3.0),
    ("changed inside outline", "ink_2", "card", 3.0),
)

Text = Callable[..., str]


def side(dx: float, dy: float) -> str:
    """Give the band of a direction: the axis with the larger distance wins, and a tie
    gives the left or the right band."""
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "bottom" if dy > 0 else "top"


def centre(box: Box) -> tuple[float, float]:
    x, y, w, h = box
    return x + w / 2, y + h / 2


def frame_box(model: Model) -> Box | None:
    """Give the frame of a nested map: the bounds of its internal cards, and of the regions
    and containers that hold them, with `FRAME_PAD` around them.

    The result is None for a map with no internal card or no actor, and for a map with an
    actor inside the frame."""
    inner = [c for c in model.components if c.kind != "actor" and c.positioned]
    actors = [c for c in model.components if c.kind == "actor" and c.positioned]
    if not inner or not actors:
        return None
    frame = _padded(_inner_boxes(model, inner))
    if any(_overlap(a.box, frame) for a in actors):
        return None
    return frame


def _inner_boxes(model: Model, inner: list[Component]) -> list[Box]:
    """Give the boxes of the internal cards and of the regions and containers that hold them."""
    homes = {c.home for c in inner}
    homes |= {r.container for r in model.regions if r.id in homes and r.container}
    boxes: list[Box] = [c.box for c in inner]
    boxes += [r.box for r in model.regions if r.id in homes]
    return boxes + [b.box for b in model.containers if b.id in homes]


def _padded(boxes: list[Box]) -> Box:
    """Give the bounds of the boxes with `FRAME_PAD` around them."""
    x0 = min(b[0] for b in boxes) - FRAME_PAD
    y0 = min(b[1] for b in boxes) - FRAME_PAD
    x1 = max(b[0] + b[2] for b in boxes) + FRAME_PAD
    y1 = max(b[1] + b[3] for b in boxes) + FRAME_PAD
    return (x0, y0, x1 - x0, y1 - y0)


def _overlap(a: Box, b: Box) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def actor_label(context: Mapping[str, Any] | None, cid: str) -> str:
    """Give the state label of an actor: "in the parent map" for a neighbour card."""
    found = ((context or {}).get("neighbours") or {}).get(cid) or {}
    return PARENT_LABEL if found.get("where") == "parent" else OUTSIDE_LABEL


def notch(label: str, box: Box, stroke: str) -> str:
    """Give the corner notch of a neighbour card, or nothing for a different card. The
    notch is in the upper-right corner, because the theme notch of a kind is in the
    upper-left corner. `label` is the state label of the card (`actor_label`)."""
    if label != PARENT_LABEL:
        return ""
    x, y, w, _h = box
    right = x + w - 3
    return (
        f'<path class="node__mark node__parent" d="M{right},{y + 3} h-9 l9,9 z" '
        f'fill="{stroke}" fill-opacity=".85"/>'
    )


CHANGED_INSIDE = "changed inside"


def changed_inside(c: Component, opens: Mapping[str, Mapping[str, Any]], mode: str) -> bool:
    """Tell if the change map marks the card: its map or a map below it changed
    (`page_rollup`)."""
    return mode == "change" and c.opens and bool((opens.get(c.id) or {}).get("changed"))


def inside_label(changed: bool) -> str:
    """Give the end of the card label for a card with a change inside, or nothing."""
    return f", {CHANGED_INSIDE}" if changed else ""


def back_outline(box: Box, offset: float, radius: float, stroke: str, changed: bool) -> str:
    """Give the second outline on the back card of a card with a change inside, or
    nothing for a card without a change inside."""
    if not changed:
        return ""
    x, y, w, h = box
    return (
        f'<rect class="node__inside-changed" x="{x + offset + 3}" y="{y + offset + 3}" '
        f'width="{w - 6}" height="{h - 6}" rx="{radius - 1}" fill="none" stroke="{stroke}" '
        'stroke-width="1"/>'
    )


def badge_text(c: Component, opens: Mapping[str, Mapping[str, Any]], changed: bool = False) -> str:
    """Give the badge text of a card that opens a map, or nothing without a count."""
    if changed:
        return CHANGED_INSIDE
    cards = int((opens.get(c.id) or {}).get("cards") or 0) if c.opens else 0
    return f"{cards} inside" if cards else ""


def badge(L: Text, P: Any, text: str, box: Box) -> str:
    """Give the SVG of the "N inside" badge, or nothing without text."""
    if not text:
        return ""
    left, top, width, tall = badge_box(box, text)
    return (
        f'<g class="node__inside"><rect x="{left:.1f}" y="{top:.1f}" width="{width:.1f}" '
        f'height="{tall:.0f}" rx="8" fill="{P["raised"]}" stroke="{P["ink_3"]}" '
        f'stroke-width="1"/>'
        + L(left + width / 2, top + 12, text, TEXT_PX, P["ink_2"], "500", False, "middle")
        + "</g>"
    )


def _boundary(context: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    return list((context or {}).get("boundary") or [])


def port_text(found: Mapping[str, Any], model: Model) -> str:
    """Give the short port text of one open boundary line, or nothing if the line has no
    port: a `boundary import` line for a component that is not an actor of the map."""
    if found["kind"] == "boundary flow":
        return NO_PARENT_FLOW if found["inner"] else NO_FLOW_INSIDE
    other = model.find(found["other"])
    return IMPORT_NO_FLOW if other is not None and other.kind == "actor" else ""


def _sends(found: Mapping[str, Any], card: str) -> bool:
    """Tell if the parent flow of a line goes from the opening card to the other component."""
    return bool(found["src"] == card)


def edge_lines(context: Mapping[str, Any] | None, src: str, dst: str) -> list[str]:
    """Give the open boundary lines of one nested flow between an internal component and an
    actor: the lines about the same pair in the same direction."""
    card = (context or {}).get("card", "")
    out = []
    for found in _boundary(context):
        inner, other = found["inner"], found["other"]
        if found["kind"] != "boundary flow" or not inner:
            continue
        if (src, dst) == ((inner, other) if _sends(found, card) else (other, inner)):
            out.append(found["line"])
    return out


def card_lines(context: Mapping[str, Any] | None, cid: str) -> list[str]:
    """Give the open boundary lines that name a component, for its inspector."""
    return [f["line"] for f in _boundary(context) if cid in (f["inner"], f["other"])]


def inside_flows(context: Mapping[str, Any] | None, src: str, dst: str) -> list[Any]:
    """Give the nested flows of a parent flow of a card that opens a map, with links."""
    return list(((context or {}).get("inside") or {}).get(f"{src}->{dst}") or [])


def _crossing(points: Sequence[Sequence[float]], frame: Box) -> tuple[float, float] | None:
    """Give the first point where a path crosses the frame line, or None."""
    x0, y0, w, h = frame

    def inside(p: Sequence[float]) -> bool:
        return x0 < p[0] < x0 + w and y0 < p[1] < y0 + h

    for a, b in zip(points, points[1:], strict=False):
        if inside(a) == inside(b):
            continue
        if a[1] == b[1]:
            edge = x0 if min(a[0], b[0]) <= x0 <= max(a[0], b[0]) else x0 + w
            return edge, a[1]
        edge = y0 if min(a[1], b[1]) <= y0 <= max(a[1], b[1]) else y0 + h
        return a[0], edge
    return None


def _facing(frame: Box, box: Box) -> tuple[float, float]:
    """Give the point of the frame line nearest to the centre of a card outside it."""
    x0, y0, w, h = frame
    cx, cy = centre(box)
    px, py = min(max(cx, x0), x0 + w), min(max(cy, y0), y0 + h)
    if x0 < px < x0 + w and y0 < py < y0 + h:
        return x0, py
    return px, py


def ports(
    model: Model, context: Mapping[str, Any] | None, paths: Mapping[int, Any], frame: Box
) -> list[dict[str, Any]]:
    """Give the ports of the frame: one for each flow that crosses it, and one for each
    open boundary line that has no nested flow. Each port gives its point, its flow index
    (-1 without a flow), the short text, and the open lines."""
    out: list[dict[str, Any]] = []
    for i, f in enumerate(model.flows):
        # Only a flow between an internal component and an actor goes across the boundary.
        if _is_actor(model, f.src) == _is_actor(model, f.dst):
            continue
        at = _crossing(paths.get(i) or [], frame)
        if at is None:
            continue
        lines = edge_lines(context, f.src, f.dst)
        text = NO_PARENT_FLOW if lines else ""
        out.append(
            {"at": [round(at[0], 1), round(at[1], 1)], "edge": i, "text": text, "lines": lines}
        )
    return out + _fixed_ports(model, context, frame)


def _is_actor(model: Model, cid: str) -> bool:
    found = model.find(cid)
    return found is not None and found.kind == "actor"


def _fixed_ports(
    model: Model, context: Mapping[str, Any] | None, frame: Box
) -> list[dict[str, Any]]:
    """Give one port for each open boundary line that has no nested flow. The port is at
    the point of the frame nearest to the actor, so the model alone gives its place."""
    out: list[dict[str, Any]] = []
    for found in _boundary(context):
        text = port_text(found, model)
        other = model.find(found["other"])
        if text in ("", NO_PARENT_FLOW) or other is None or not other.positioned:
            continue
        at = _facing(frame, other.box)
        out.append(
            {
                "at": [round(at[0], 1), round(at[1], 1)],
                "edge": -1,
                "text": text,
                "lines": [found["line"]],
            }
        )
    return out


def _text_box(x: float, y: float, text: str) -> Box:
    """Give the room of a start-anchored text of the figure with its baseline at y."""
    return (x - 3, y - TEXT_PX - 3, len(text) * LABEL_CHAR_W + 6, TEXT_PX + 6)


def obstacles(model: Model, context: Mapping[str, Any] | None) -> list[tuple[str, Box]]:
    """Give the room of the frame label and of the texts of the fixed ports, as obstacles
    for the flow labels. The place of a port on a flow comes from the routed path, so
    `port_collisions` examines its text after the label placement."""
    label = (context or {}).get("label") or ""
    frame = frame_box(model) if label else None
    if frame is None:
        return []
    out = [("frame label", _text_box(frame[0] + 12, frame[1] - 6, label))]
    for port in _fixed_ports(model, context, frame):
        px, py = port["at"]
        out.append((f"port text '{port['text']}'", _text_box(px + 8, py - 8, port["text"])))
    return out


def port_collisions(
    record: Mapping[str, Any], seats: Mapping[int, Box], names: Mapping[int, str]
) -> list[str]:
    """Give a label collision line for each flow label that overlaps the text of a port on
    a flow. `record` is the frame record of `frame_part`."""
    out = []
    for port in (record.get("frame") or {}).get("ports") or []:
        if port["edge"] < 0 or not port["text"]:
            continue
        px, py = port["at"]
        room = _text_box(px + 8, py - 8, port["text"])
        out += [
            f"label collision: {names[i]} overlaps port text '{port['text']}'"
            for i, box in seats.items()
            if _overlap(box, room)
        ]
    return out


def frame_svg(L: Text, P: Any, label: str, frame: Box, found: Sequence[Mapping[str, Any]]) -> str:
    """Give the SVG of the frame and its ports. An open port is dotted and has its text."""
    x, y, w, h = frame
    out = [
        f'<g class="frame" data-part="frame"><rect class="frame__line" x="{x}" y="{y}" '
        f'width="{w}" height="{h}" rx="10" fill="none" stroke="{P["ink_3"]}" '
        f'stroke-width="1.4" vector-effect="non-scaling-stroke"/>'
        + L(x + 12, y - 6, label, TEXT_PX, P["ink_2"], "600", False, "start", "", True)
    ]
    for port in found:
        px, py = port["at"]
        open_ = bool(port["text"])
        dots = ' stroke-dasharray="1.5 2"' if open_ else ""
        # The page script hides the port of a flow that the current view hides.
        out.append(
            f'<g class="frame__pt" data-edge="{port["edge"]}">'
            f'<circle class="frame__port{" frame__port--open" if open_ else ""}" '
            f'cx="{px}" cy="{py}" r="{5 if open_ else 3.5}" '
            f'fill="{P["map"]}" stroke="{P["ink_2"]}" stroke-width="1.4"{dots}/>'
        )
        if open_:
            out.append(
                L(
                    px + 8,
                    py - 8,
                    port["text"],
                    TEXT_PX,
                    P["ink_2"],
                    "500",
                    False,
                    "start",
                    "",
                    True,
                )
            )
        out.append("</g>")
    out.append("</g>")
    return "".join(out)


def card_fields(context: Mapping[str, Any] | None, cid: str) -> dict[str, Any]:
    """Give the inspector fields of one card of a nested map, or none for a map without a
    context: the neighbour record and the open boundary lines that name the card. A top
    map has no opening card, and its cards get no field."""
    if not context or not context.get("card"):
        return {}
    found = (context.get("neighbours") or {}).get(cid)
    return {"neighbour": found, "boundary": card_lines(context, cid)}


def edge_fields(context: Mapping[str, Any] | None, src: str, dst: str) -> dict[str, Any]:
    """Give the inspector fields of one flow: the open boundary lines of a nested flow, and
    the nested flows of a parent flow. A flow without them gets no field."""
    out: dict[str, Any] = {}
    lines = edge_lines(context, src, dst)
    inside = inside_flows(context, src, dst)
    if lines:
        out["boundary"] = lines
    if inside:
        out["inside"] = inside
    return out


def frame_part(
    model: Model, context: Mapping[str, Any] | None, paths: Mapping[int, Any], L: Text, P: Any
) -> tuple[str, dict[str, Any]]:
    """Give the SVG of the frame with its ports, and its record for the detail data. A map
    without a frame label or without a frame gives nothing."""
    label = (context or {}).get("label") or ""
    frame = frame_box(model) if label else None
    if frame is None:
        return "", {}
    found = ports(model, context, paths, frame)
    record = {"label": label, "box": [round(v, 1) for v in frame], "ports": found}
    return frame_svg(L, P, label, frame, found), {"frame": record}


NESTED_JS = r"""
// ---- the boundary of a nested map ------------------------------------------
function nestRows(head, rows, n){
  return rows.length ? '<section class="systemap-f__section">' + heading(head, n) + rows.join('')
    + '</section>' : '';
}
function nestLines(l){
  l = (l || []).map(function(t){ return '<p class="systemap-f__boundary">' + esc(t) + '</p>'; });
  return nestRows('Open boundary findings', l, l.length);
}
function nestFlow(f){
  var t = esc(f.art) + ': ' + esc(f.from) + ' to ' + esc(f.to);
  return PAGE && f.href ? '<a class="systemap-f__inside" href="' + esc(f.href) + '">' + t
    + '</a>' : '<p class="systemap-f__route">' + t + '</p>';
}
// A link with `child` opens a different map. In the Changes view, the page_nav script
// adds #changes to it (`data-child-map`).
function nestLink(href, text, child){
  return PAGE && href ? '<a class="systemap-f__open" href="' + esc(href) + '"'
    + (child ? ' data-child-map="' + esc(href) + '"' : '') + '>' + text + '</a>' : '';
}
function neighbourOf(d){
  var n = d.neighbour, flows = n ? n.flows || [] : [];
  return (n && n.where === 'parent' ? nestRows('In the parent map', flows.map(nestFlow).concat(
    [nestLink(n.parent_href, 'Show in the parent map'),
      nestLink(n.map_href, 'Open the map inside ' + esc(d.id), true)]), flows.length) : '')
    + nestLines(d.boundary);
}
function insideOf(e){
  var l = (e.inside || []).map(nestFlow);
  return nestLines(e.boundary) + nestRows('Flows inside', l, l.length);
}
"""
