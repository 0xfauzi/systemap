"""The parent context of a nested page, and the compact preview of a child map.

A nested map shows the inside of one component of its parent map, the opening card.
This module gives three things to the page of a map:

- The context record for the figure (`schematic_nested`): the neighbour cards, the frame
  label, the open boundary lines, and the nested flows of each parent flow of a card that
  opens a map. A boundary line is open if no recorded answer accepts it
  (`judgement.apply_answers`). A port that has no open line shows no join state.
- The parent context mark: a small figure of the parent map at the lower left of the map
  view. Each parent card is a plain rectangle. The opening card is filled, and the
  neighbour cards are dashed. The full mark is one link to the opening card in the parent
  map. The mark has its own row below the map, so it does not cover a card or a flow at
  a zoom or a position of the map. Its height is `MARK_H` or less. A phone does not show
  it.
- The compact preview of a child map for the inspector: one rectangle for each internal
  card in a frame, and one stub at the frame for each actor with a nested flow. It
  replaces the full preview figure, so a page with many child maps stays small.

The two small figures use CSS classes only. Thus the page policy needs no digest for them.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import quote

from systemap import judgement_json, nest, nest_join
from systemap.config import Config
from systemap.model import Component, Model
from systemap.schematic_cards import Box, esc
from systemap.schematic_nested import centre, frame_box, side

# The maximum width and height of the parent context mark, and the width of the compact
# preview, in CSS pixels.
MARK_W = 168
MARK_H = 64
PREVIEW_W = 280
# The length of a stub at the frame of the compact preview, in preview units.
STUB = 14


def _q(cid: str) -> str:
    return quote(cid, safe="")


def context(
    tree: nest.Tree, m: nest.Map, facts: dict[str, Any], still: frozenset[str]
) -> dict[str, Any]:
    """Give the context record of the page of map `m` for the figure.

    Each map gets the nested flows of the parent flows of its cards that open a map. A
    nested map also gets the opening card, the frame label, the neighbour records, and
    the open boundary lines. `still` contains the open lines of the tree
    (`open_boundary`)."""
    out: dict[str, Any] = {}
    inside = inside_flows(tree, m)
    if inside:
        out["inside"] = inside
    parent = tree.parent_of(m)
    if parent is None:
        return out
    out["card"] = m.card
    out["label"] = f"Inside {m.card}"
    out["neighbours"] = neighbours(tree, m, parent)
    out["boundary"] = open_lines(tree, m, facts, still)
    return out


def _between(model: Model, a: str, b: str) -> list[dict[str, str]]:
    """Give the flows between two components, in model order."""
    return [
        {"from": f.src, "to": f.dst, "art": f.artifact}
        for f in model.flows
        if {f.src, f.dst} == {a, b} and f.src != f.dst
    ]


def neighbours(tree: nest.Tree, m: nest.Map, parent: nest.Map) -> dict[str, dict[str, Any]]:
    """Give the record of each actor of a nested map.

    `where` is "parent" for an internal component of the parent map, and "outside" for an
    actor of the parent map. The record gives the link to the component in the parent
    page, the link to its own map if it opens one, and the parent flows between the
    opening card and the component."""
    out: dict[str, dict[str, Any]] = {}
    for actor in m.model.components:
        if actor.kind != "actor":
            continue
        found = parent.model.find(actor.id)
        inner = found is not None and found.kind != "actor"
        opened = f"{parent.id}/{actor.id}" if parent.id else actor.id
        out[actor.id] = {
            "where": "parent" if inner else "outside",
            "card": m.card,
            "parent_href": f"../index.html#{_q(actor.id)}",
            "map_href": f"../{_q(actor.id)}/index.html" if tree.has(opened) else "",
            "flows": _between(parent.model, m.card, actor.id),
        }
    return out


def open_boundary(cfg: Config, tree: nest.Tree, facts: dict[str, Any]) -> frozenset[str]:
    """Give the open judgement lines of the tree, with the rules of `systemap judgement`
    (`judgement_json.answered`). A tree with no nested map has no boundary line, so it
    gets no set. A render calls this one time for all pages of the tree."""
    if not tree.nested:
        return frozenset()
    return frozenset(judgement_json.answered(tree, facts, cfg)[2].open)


def open_lines(
    tree: nest.Tree, m: nest.Map, facts: dict[str, Any], still: frozenset[str]
) -> list[dict[str, Any]]:
    """Give the boundary lines of a nested map that are in the open lines `still`."""
    found = nest_join.map_findings(tree, m, facts)
    return [
        {
            "line": f.line,
            "kind": f.kind,
            "inner": f.inner,
            "other": f.other,
            "src": f.parent_flow[0],
            "dst": f.parent_flow[1],
        }
        for f in found
        if f.line in still
    ]


def inside_flows(tree: nest.Tree, m: nest.Map) -> dict[str, list[dict[str, str]]]:
    """Give the nested flows of each parent flow of a card that opens a map.

    The key is "SRC->DST" of the parent flow. A nested flow agrees with the parent flow
    if it connects an internal component and the actor at the other end, in the same
    direction. Each record has a link to the internal component in the nested page."""
    out: dict[str, list[dict[str, str]]] = {}
    # Two parent flows in the same direction between the same cards share one key.
    edges = list(dict.fromkeys(f.edge for f in m.model.flows if f.src != f.dst))
    for child in tree.children(m):
        card = child.card
        for src, dst in edges:
            if card not in (src, dst):
                continue
            out_going = src == card
            found = nest_join.nested_flows(child.model, dst if out_going else src, out_going)
            # A flow between two cards that open a map has nested flows in both maps.
            out.setdefault(f"{src}->{dst}", []).extend(
                _inside_row(card, g.src if out_going else g.dst, g.src, g.dst, g.artifact)
                for g in found
            )
    return {key: rows for key, rows in out.items() if rows}


def _inside_row(card: str, inner: str, src: str, dst: str, art: str) -> dict[str, str]:
    href = f"{_q(card)}/index.html#{_q(inner)}"
    return {"from": src, "to": dst, "art": art, "inner": inner, "href": href}


# ---- the two small figures -------------------------------------------------------------


def _scale(canvas: tuple[int, int], width: int, height: int = 0) -> float:
    """Give the scale that makes the canvas `width` wide, or less to keep it in `height`."""
    k = width / max(canvas[0], 1)
    return min(k, height / max(canvas[1], 1)) if height else k


def _rect(box: Box, k: float, cls: str) -> str:
    x, y, w, h = box
    return (
        f'<rect class="{cls}" x="{x * k:.1f}" y="{y * k:.1f}" width="{max(w * k, 2):.1f}" '
        f'height="{max(h * k, 2):.1f}" rx="1.5"/>'
    )


def _drawn(model: Model) -> Iterable[Component]:
    return (c for c in model.components if c.positioned)


def mark(tree: nest.Tree, m: nest.Map) -> str:
    """Give the parent context mark of a nested page, or nothing for the top page.

    The mark shows the parent map: the opening card filled, the neighbour cards dashed,
    and the other cards as outlines. The full mark is one link to the opening card in the
    parent page."""
    parent = tree.parent_of(m)
    if parent is None:
        return ""
    near = {c.id for c in m.model.components if c.kind == "actor"}
    k = _scale(parent.model.canvas, MARK_W, MARK_H)
    rects = []
    for c in _drawn(parent.model):
        role = "ctx__open" if c.id == m.card else "ctx__near" if c.id in near else "ctx__card"
        rects.append(_rect(c.box, k, role))
    w, h = parent.model.canvas
    name = f"The parent map {parent.id}" if parent.id else "The top map"
    label = f"{name}: {m.card} is the filled card. Go to {m.card} in the parent map."
    return (
        f'<a class="ctx" href="../index.html#{_q(m.card)}" aria-label="{esc(label)}">'
        f'<svg class="ctx__svg" viewBox="0 0 {w * k:.1f} {h * k:.1f}" width="{w * k:.0f}" '
        f'height="{h * k:.0f}" aria-hidden="true" focusable="false">{"".join(rects)}</svg>'
        f'<span class="ctx__k">Parent map</span></a>'
    )


def preview(child: nest.Map, svg_id: str) -> str:
    """Give the compact preview of a child map for the inspector.

    The preview has one rectangle for each internal card, the frame, and one stub at the
    frame for each actor that has a nested flow. A stub faces the actor."""
    model = child.model
    k = _scale(model.canvas, PREVIEW_W)
    frame = frame_box(model)
    parts = [_rect(c.box, k, "mini__card") for c in _drawn(model) if c.kind != "actor"]
    if frame is not None:
        parts.insert(0, _rect(frame, k, "mini__frame"))
        parts += [_stub(frame, actor.box, k) for actor in _connected(model)]
    w, h = model.canvas
    count = child.inside
    label = f"The nested map has {count} component{'' if count == 1 else 's'}."
    return (
        f'<svg id="{esc(svg_id)}" class="mini" viewBox="0 0 {w * k:.1f} {h * k:.1f}" role="img" '
        f'aria-label="{esc(label)}">{"".join(parts)}</svg>'
    )


def _connected(model: Model) -> list[Component]:
    """Give the actors with a nested flow to or from an internal component."""
    ends = {e for f in model.flows for e in (f.src, f.dst)}
    return [c for c in _drawn(model) if c.kind == "actor" and c.id in ends]


def _stub(frame: Box, box: Box, k: float) -> str:
    """Give a short line from the frame toward an actor."""
    fx, fy, fw, fh = frame
    cx, cy = centre(box)
    where = side(cx - (fx + fw / 2), cy - (fy + fh / 2))
    px, py = min(max(cx, fx), fx + fw), min(max(cy, fy), fy + fh)
    dx, dy = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}[where]
    if where in ("left", "right"):
        px = fx if where == "left" else fx + fw
    else:
        py = fy if where == "top" else fy + fh
    x1, y1 = px * k, py * k
    return (
        f'<line class="mini__stub" x1="{x1:.1f}" y1="{y1:.1f}" '
        f'x2="{x1 + dx * STUB:.1f}" y2="{y1 + dy * STUB:.1f}"/>'
    )


# The mark and the legend after it are the foot rows of the map section, below the map.
# Thus the map cannot go below the mark, and a legend on two lines does not cover the mark.
# The status of a copied link goes to the right end of the row of the mark. The Changes
# view has its own figure in the full section, so it does not show the mark.
CSS = r"""
.ctx{align-self:flex-start;display:flex;align-items:flex-end;gap:10px;margin:8px 24px 6px;
  padding:8px;border:1px solid var(--line-2);border-radius:8px;background:var(--surface);
  color:var(--ink-2);text-decoration:none}
@media (min-width:641px){body:not([data-phone]):not([data-mode="change"]) .ctx~.map-legend{
  position:static;align-self:flex-start;margin:0 24px 10px}
.ctx~#linkstatus{left:auto;right:24px}}
.ctx:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.ctx__svg{display:block}
.ctx__k{font:600 11px/1.2 var(--fs);letter-spacing:.08em;text-transform:uppercase}
.ctx__card{fill:none;stroke:var(--ink-3);stroke-width:1}
.ctx__near{fill:none;stroke:var(--ink-2);stroke-width:1;stroke-dasharray:2 1.5}
.ctx__open{fill:var(--ink-2);stroke:var(--ink-2);stroke-width:1}
@media (max-width:640px){.ctx{display:none}}
body[data-phone] .ctx,body[data-mode="change"] .ctx{display:none}
.mini{display:block;width:100%;height:auto}
.mini__frame{fill:none;stroke:var(--ink-3);stroke-width:1}
.mini__card{fill:var(--card);stroke:var(--ink-3);stroke-width:1}
.mini__stub{stroke:var(--ink-2);stroke-width:1.5}
"""
