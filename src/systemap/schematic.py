"""Draw the logical view as a flat figure. One generator for every picture.

A stranger needs four things from the map, and each one owns exactly one
visual channel so that no channel says two things at once:

    what exists ....... a card, inside the boundary it belongs to, carrying
                        its code name and its plain word
    what is outside ... an actor's dashed edge: a person or a system the
                        code does not contain
    how work travels .. lines between cards, each labelled with what it
                        carries and coloured by the LAYER it belongs to
    what it means ..... the focus interaction: click a card and its
                        neighbours stay lit, each edge thickens in its
                        layer's colour, each neighbour is tagged with the
                        verb that relates it, and the panel draws the
                        relationship wheel

Every card is code that exists today; the check refuses a component whose
modules or entry are not in the facts, so the drawing never has to hedge.
Every node carries `data-id` and its kind; every edge carries its artifact
as visible text and its layer as `data-layer`.

Every edge carries its evidence state (evidence.py): `observed` when an
import joins its two ends or a configured mechanism is named, `external`
when an actor is at either end, `declared` when the facts have nothing.
A declared edge is drawn dashed, here and in every figure, and the panel
says so beside its sentence.

Edges are Manhattan paths routed by route.py through the gutters between
cards: never through a card they do not connect, never through a region they
neither start nor end in. Each label sits on the longest segment of its own
path, or in the gutter beside a run too short to hold it. A container's or
a region's header text must fit its box: a sub wraps to a second line and
is refused past that. What could not be placed cleanly, label or header,
is reported in the detail JSON under `_meta.collisions`, each line worded
for the check, and
any route that had to break a rule under `_meta.notes` with the router's
reason, so a crowded layout fails loudly instead of quietly drawing text
over text.

Positions come from the model, so the same system always draws the same
figure and a moved card means the architecture moved. Meaning (layers, the
sentence per edge, the verb per spoke, the plain words) comes from the
meaning tables beside it.

No text in the figure is set below 11px.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from systemap import evidence
from systemap.model import (
    AGENT_KINDS,
    CARD_H,
    DERIVED_LAYERS,
    Container,
    Meaning,
    Model,
    Region,
    all_layers,
    build_state,
    entry_module,
    reading,
)
from systemap.route import path_d, place_labels, route_all

CARD_W = 150.0
RADIUS = 4.0
# How far the second card behind a card that opens a map is offset.
MAP_OFFSET = 3.0
# The smallest type on the figure. Edge labels, plain words and every note
# sit at this size; names sit half a point above it.
TEXT_PX = 11.0
NAME_PX = 11.5
LABEL_PX = TEXT_PX
# Width is estimated from the glyph count, so the collision pass can run
# without a renderer.
LABEL_CHAR_W = 6.1
LABEL_H = 13.0
LABEL_GAP = 2.0
# A plain word wraps to the card: 140 units of inner width at 11px sans.
PLAIN_CHARS = 26

Box = tuple[float, float, float, float]


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def wrap_all(text: str, width: int) -> list[str]:
    """Greedy word wrap with nothing dropped: a word wider than `width` stands alone."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width or not current:
            current = candidate
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


# The header text estimates the router and the check share: a mono label at
# 11px with .13em tracking, a sans sub-line at 11px.
LABEL_CHAR = 7.6
SUB_CHAR = 5.6
HEADER_LINES = 2

# ---- card text: what fits, and what is refused ---------------------------------
# A card's name is mono at 11.5px in 140 units of inner width: about 20
# characters on one line. A component, agent or tool card (56 tall, no rule
# under its head) has room for a second name line; a store or context card
# (ruled at 23) and an actor (44 tall) do not. The plain word takes the
# lines under the name, 12 units each. Nothing is cut and nothing is
# elided: what does not fit is reported, and the check refuses the map.
NAME_CHARS = 20
NAME_LINE_H = 13
TWO_LINE_NAME_KINDS = ("component", "agent", "tool")


def wrap_id(cid: str, width: int) -> list[str]:
    """A CamelCase or snake_case id over as few lines as its parts allow.

    The break points are the words of the name; a part wider than `width`
    stands alone and is then reported by the caller.
    """
    parts = re.findall(r"[A-Z]+[a-z0-9]*_*|[a-z0-9]+_*", cid)
    if "".join(parts) != cid:
        parts = [cid]
    lines: list[str] = []
    current = ""
    for part in parts:
        if current and len(current + part) > width:
            lines.append(current)
            current = part
        else:
            current += part
    if current:
        lines.append(current)
    return lines


def card_text(kind: str, cid: str, plain: str) -> tuple[list[str], list[str], list[str]]:
    """(the name lines, the plain lines, what does not fit) for one card.

    Each problem states the budget the card kind has and what the text
    measured: `actor cards fit about 26 characters on one line; this one
    has 34`. The lines returned are what the drawing prints, cut to the
    room the card has, since the check refuses the map anyway.
    """
    problems: list[str] = []
    ruled = kind in ("store", "context")
    name_lines = [cid]
    if len(cid) > NAME_CHARS and kind in TWO_LINE_NAME_KINDS:
        name_lines = wrap_id(cid, NAME_CHARS)
    if len(name_lines) > 2 or any(len(line) > NAME_CHARS for line in name_lines):
        room = "over two lines" if kind in TWO_LINE_NAME_KINDS else "on one line"
        problems.append(
            f"card {cid}: name does not fit ({kind} cards fit a name of about {NAME_CHARS} "
            f"characters {room}; this one has {len(cid)})"
        )
        name_lines = name_lines[:2]
    first = (36 if ruled else 32) + NAME_LINE_H * (len(name_lines) - 1)
    lines = max(1, int((CARD_H[kind] - 4 - first) // 12) + 1)
    plain_lines = wrap_all(plain, PLAIN_CHARS)
    if len(plain_lines) > lines or any(len(line) > PLAIN_CHARS for line in plain_lines):
        words = {1: "one line", 2: "two lines"}.get(lines, f"{lines} lines")
        under = " under a two-line name" if len(name_lines) > 1 else ""
        problems.append(
            f"card {cid}: plain word does not fit ({kind} cards fit about {PLAIN_CHARS} "
            f"characters on {words}{under}; this one has {len(plain)})"
        )
        plain_lines = plain_lines[:lines]
    return name_lines, plain_lines, problems


def _rgb(colour: str) -> tuple[int, int, int]:
    c = colour.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    """a towards b by t."""
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    r = round(ra + (rb - ra) * t)
    g = round(ga + (gb - ga) * t)
    bl = round(ba + (bb - ba) * t)
    return f"#{r:02X}{g:02X}{bl:02X}"


def _file_of(claim: str) -> str:
    """The file one claim names, and the symbol after a colon for a symbol claim."""
    module, _, name = claim.partition(":")
    path = module.replace(".", "/") + ".py"
    return f"{path}:{name}" if name else path


def lives_in(modules: list[str]) -> str:
    """One muted line for a contributor: the file, or the package when many.

    Three or fewer claims are named as files (a symbol claim as
    `file.py:name`). More than that is a package, named by its common
    directory with a count, so a component spread over a subpackage does
    not turn the panel into a listing.
    """
    if not modules:
        return ""
    if len(modules) <= 3:
        return ", ".join(_file_of(m) for m in modules)
    parts = [m.partition(":")[0].split(".") for m in modules]
    common: list[str] = []
    for column in zip(*parts, strict=False):
        if len(set(column)) == 1:
            common.append(column[0])
        else:
            break
    if len(common) == len(min(parts, key=len)):
        common = common[:-1]
    return "/".join(common) + f"/ ({len(modules)} modules)"


def legend_rows(t: dict[str, Any], mode: str) -> list[tuple[str, str, str]]:
    """(fill, stroke, label) for the legend the given mode needs."""
    if mode == "change":
        d = t["delta"]
        return [
            (mix(t["bg"], t["change"], 0.14), t["change"], "changed here"),
            (mix(t["bg"], t["reach"], 0.12), t["reach"], "reached by it"),
            (t["ghost"][0], t["ghost"][1], "untouched"),
            (d["operations"], d["operations"], "new operations"),
            (d["types"], d["types"], "new types"),
            (d["refusals"], d["refusals"], "new refusals"),
            (d["tests"], d["tests"], "new tests"),
        ]
    return [(f, s, label) for f, s, label in t["state"].values()]


def layer_rows(t: dict[str, Any], model: Model, meaning: Meaning) -> list[tuple[str, str, str]]:
    """(id, colour, label) for every layer that draws a line, in layer order.

    Structure draws no edges, so its colour would be a swatch of nothing;
    it is left out of the legend.
    """
    return [
        (layer.id, t["layers"][layer.id], layer.label)
        for layer in all_layers(model, meaning)
        if layer.id != "structure"
    ]


def kind_rows(t: dict[str, Any], model: Model) -> list[tuple[str, str]]:
    """(kind, mark) for every agent kind the model draws, in kind order."""
    present = {c.kind for c in model.components}
    marks: dict[str, str] = t.get("marks") or {}
    return [(kind, marks[kind]) for kind in AGENT_KINDS if kind in present and kind in marks]


def _svg_style(svg_id: str, t: dict[str, Any]) -> str:
    """Interaction states, scoped to one figure so two on a page cannot leak."""
    s = f"#{svg_id}"
    return (
        "<style>"
        f"{s} .node{{transition:opacity .18s ease;cursor:pointer}}"
        f"{s} .node.dim{{opacity:.16}}"
        f"{s} .node.quiet{{opacity:.42}}"
        f"{s} .node.subject .node__box{{stroke:var(--subject)}}"
        f"{s} .node.subject rect.node__mark{{stroke:var(--subject)}}"
        f"{s} .node.subject path.node__mark{{fill:var(--subject)}}"
        f"{s} .node.sel .node__box{{stroke:{t['accent']};stroke-width:2.6}}"
        f"{s} .node.meas .node__box{{stroke:{t['steel']};stroke-width:2.2}}"
        f"{s} .node.acts .node__box{{stroke:{t['accent']};stroke-width:2.4}}"
        f"{s} .node__ring{{display:none;fill:none;stroke:{t['steel']};stroke-width:1.6}}"
        f"{s} .node.meas .node__ring{{display:inline}}"
        f"{s} .node.tagged [data-layer=job]{{opacity:0}}"
        f"{s} .node:focus-visible{{outline:none}}"
        f"{s} .node:focus-visible .node__box{{stroke:{t['accent']};stroke-width:2.6}}"
        f"{s} .flow{{transition:opacity .18s ease}}"
        # A reading hides the edges it does not show; a peeked one (a spoke
        # hovered in the wheel) shows through, so a wheel is never mute.
        f"{s} .flow.off:not(.peek),{s} .flowlbl.off:not(.peek){{display:none}}"
        f"{s} .flow.dim{{opacity:.07}}"
        f"{s} .flow.hot{{opacity:1;stroke-opacity:1;stroke-width:2.6;"
        "stroke-dasharray:8 6;animation:systemapflow 1.1s linear infinite}"
        f"{s} .flow.peek{{stroke-width:3.4}}"
        f"{s} .flowlbl{{transition:opacity .15s ease;pointer-events:none}}"
        f"{s} .flowlbl.dim{{opacity:.08}}"
        f"{s} .flowlbl.hot{{opacity:1}}"
        f"{s} .vtag rect{{stroke-width:1}}"
        f"{s} .vtag text{{font-family:{t['font_ui']};font-size:{TEXT_PX}px;"
        "font-weight:500;text-anchor:middle}"
        # The figure fills its column; the drawing pans and zooms inside it
        # on the .view group, so the element itself never scrolls. touch-action
        # none hands one-finger drags and pinches to the script.
        f"{s}{{width:100%;height:auto;display:block;overflow:hidden;touch-action:none;"
        "cursor:grab}"
        f"{s}.panning{{cursor:grabbing}}"
        f"{s} .zone__h{{cursor:zoom-in;-webkit-user-select:none;user-select:none}}"
        "@keyframes systemapflow{to{stroke-dashoffset:-14}}"
        f"@media print{{{s} .view{{transform:none!important}}}}"
        "@media (prefers-reduced-motion:reduce){"
        f"{s} .flow.hot{{animation:none;stroke-dasharray:none}}"
        f"{s} .node,{s} .flow,{s} .flowlbl{{transition:none}}}}"
        "</style>"
    )


def _defs(svg_id: str, t: dict[str, Any]) -> str:
    """Arrowheads: one per layer colour, plus the change-map colours.

    Sized in user units so a thick focused edge and a hairline ghost edge
    carry the same head; the thickness is the emphasis, the head is the
    direction.
    """
    heads = dict(t["layers"])
    heads["change"] = t["change"]
    heads["reach"] = t["reach"]
    out = ["<defs>"]
    for name, colour in heads.items():
        out.append(
            f'<marker id="{svg_id}-m-{name}" viewBox="0 0 8 8" refX="7" refY="4" '
            f'markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" '
            f'orient="auto-start-reverse">'
            f'<path d="M0,0 L8,4 L0,8 z" fill="{colour}"/></marker>'
        )
    out.append("</defs>")
    return "".join(out)


@dataclass(frozen=True)
class Geometry:
    """What the router and the label pass are given, read off the model alone.

    `boxes` is every card's box; `blocks` what a route may not cross
    besides a card (every header, and a container that holds neither a
    card nor a region); `obstacles` what a label may not sit on, each
    named for the collision report (the headers, the empty containers,
    the cards with 3 clear around them); `headers` every header's box,
    for the labels rule; `collisions` the headers their box cannot hold.
    `systemap place` scores a candidate layout with this same geometry,
    so the order it picks is measured on the drawing the page makes.
    """

    boxes: dict[str, Box]
    actors: set[str]
    blocks: list[Box]
    obstacles: list[tuple[str, Box]]
    headers: list[dict[str, Any]]
    collisions: list[str]
    region_boxes: dict[str, Box]
    region_of: dict[str, str]


def container_header(box: Container) -> tuple[Box, list[str], list[str]]:
    """A container's header obstacle, the sub lines drawn, and what its box cannot hold.

    The header obstacle is the text, not the whole top edge of the box:
    the factory's spans the canvas, and a wall that wide would close the
    corridor every long edge runs along. A label wider than the box, or a
    sub that needs more than two lines, is drawn as far as it fits and
    reported, so a header never quietly runs into a card.
    """
    x, y, w, _h = box.box
    chars = max(12, int((w - 26) / SUB_CHAR))
    all_lines = wrap_all(box.sub, chars)
    sub_lines = all_lines[:HEADER_LINES]
    collisions: list[str] = []
    if len(all_lines) > HEADER_LINES or any(len(line) > chars for line in all_lines):
        collisions.append(
            f"header of container {box.id}: sub does not fit its box "
            f"({len(box.sub)} characters; {HEADER_LINES} lines of {chars} fit)"
        )
    if 13 + len(box.label) * LABEL_CHAR + 8 > w:
        collisions.append(f"header of container {box.id}: label is wider than its box")
    text_w = max([len(box.label) * LABEL_CHAR] + [len(line) * SUB_CHAR for line in sub_lines]) + 8
    header: Box = (x + 8, y + 6, min(w - 16, text_w), 30 + 12 * len(sub_lines))
    return header, sub_lines, collisions


def region_header(region: Region) -> tuple[Box, list[str]]:
    """A region's header obstacle (its number and label), and a label wider than the box."""
    x, y, w, _h = region.box
    label_w = 31 - 6 + len(region.label) * LABEL_CHAR + 8
    collisions: list[str] = []
    if 31 + len(region.label) * LABEL_CHAR + 8 > w:
        collisions.append(f"header of region {region.id}: label is wider than its box")
    return (x + 6, y + 5, max(150.0, label_w), 24), collisions


def geometry(model: Model) -> Geometry:
    """The router's and the label pass's inputs for a positioned model."""
    boxes: dict[str, Box] = {}
    for c in model.components:
        left, top, _w, tall = c.box
        boxes[c.id] = (float(left), float(top), CARD_W, float(tall))
    obstacles: list[tuple[str, Box]] = []
    blocks: list[Box] = []
    headers: list[dict[str, Any]] = []
    collisions: list[str] = []
    occupied = {c.container for c in model.components if c.container}
    occupied |= {r.container for r in model.regions if r.container}
    for box in model.containers:
        header, _sub_lines, unfit = container_header(box)
        collisions += unfit
        obstacles.append((f"{box.id} header", header))
        blocks.append(header)
        headers.append({"id": box.id, "kind": "container", "box": [round(v, 1) for v in header]})
        if box.id not in occupied:
            bx, by, bw, bh = box.box
            whole: Box = (float(bx), float(by), float(bw), float(bh))
            blocks.append(whole)
            obstacles.append((box.id, whole))
    for region in model.regions:
        header, unfit = region_header(region)
        collisions += unfit
        obstacles.append((f"{region.id} header", header))
        blocks.append(header)
        headers.append({"id": region.id, "kind": "region", "box": [round(v, 1) for v in header]})
    for cid, (x, y, w, h) in boxes.items():
        obstacles.append((cid, (x - 3, y - 3, w + 6, h + 6)))
    return Geometry(
        boxes=boxes,
        actors={c.id for c in model.components if c.kind == "actor"},
        blocks=blocks,
        obstacles=obstacles,
        headers=headers,
        collisions=collisions,
        region_boxes={
            r.id: (float(r.box[0]), float(r.box[1]), float(r.box[2]), float(r.box[3]))
            for r in model.regions
        },
        region_of={c.id: c.region or "" for c in model.components},
    )


def render(
    model: Model,
    meaning: Meaning,
    t: dict[str, Any],
    facts: dict[str, Any],
    *,
    changed: set[str] | None = None,
    changed_modules: set[str] | None = None,
    adjacent: set[str] | None = None,
    mode: str = "system",
    svg_id: str = "schematic",
    gained: dict[str, dict[str, int]] | None = None,
    hot_artifacts: set[str] | None = None,
    layer: str = "",
    observed_by: Iterable[str] = (),
    opens: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[str, str]:
    """(svg, json detail).

    `changed` marks logical components a change moved (or a plan reaches).
    `changed_modules` marks physical modules it touched. `hot_artifacts` names
    the flow labels whose owning module redefined part of its surface; the
    change detector is the one place that computes it, so this only draws
    what it is told.

    `layer` restricts the drawing to one reading: the edges the page's
    layer switch would show for it (`model.reading`, the same filter),
    painted in the reading's own hue when the reading is derived, and no
    other edge at all; every card stays. The cards the reading is about
    (`subject_of_layer`: the actors, the agents, the context cards, the
    tools) take the reading's colour as their stroke, and a card the
    reading neither is about nor reaches by an edge is dimmed, as the
    page dims it. Cards, routes and label seats are the ones the whole
    map has, so the figure is the page with edges left out, not a second
    layout. An unknown id is a ValueError; the figure module checks it
    first and names the known ids.

    `observed_by` is the repository's `[flows] observed_by` list: the
    mechanisms other than an import that make a flow observed. `opens`
    says, per card that opens a map, what the panel shows for it (its
    name, the relative path of its page, how many cards it holds, a
    preview drawing); a card with a `map` and no entry here is named
    alone, and one with a path gets the button that opens the map in
    place, which the page answers.

    The detail JSON carries one record per component (what the focus panel
    shows) plus a `_meta` key: the layers, every edge with its verbs and its
    sentence, the rules, the regions, and the edge labels the collision pass
    could not place cleanly.
    """
    changed = changed or set()
    changed_modules = changed_modules or set()
    adjacent = adjacent or set()
    gained = gained or {}
    hot_artifacts = hot_artifacts or set()
    opens = opens or {}
    change_mode = mode == "change"

    T = t
    COMPONENTS = model.components
    FLOWS = [(f.src, f.dst, f.artifact, f.kind) for f in model.flows]
    CANVAS = model.canvas
    INK, INK_3 = T["ink"], T["ink_3"]
    HALO = T["bg"]
    GHOST_FILL, GHOST_STROKE = T["ghost"]
    LAYER_COLOUR: dict[str, str] = T["layers"]
    MARKS: dict[str, str] = T.get("marks") or {}
    LAYERS = all_layers(model, meaning)
    # Which edges and which cards each reading shows, decided once here and
    # read by the page's script out of the detail JSON.
    readings = {lay.id: reading(model, meaning, lay.id) for lay in LAYERS}
    if layer and layer not in readings:
        raise ValueError(f"unknown layer id: {layer}")
    shown: set[int] | None = set(readings[layer][0]) if layer else None
    reading_hue = layer if layer in DERIVED_LAYERS else ""
    # The cards a reading is about and the cards its edges reach; the rest
    # are dimmed in a figure of that reading. Structure is about every card
    # and dims none.
    subjects: set[str] = set(readings[layer][1]) if layer else set()
    reached: set[str] = set()
    if shown is not None:
        for i in shown:
            reached.update((model.flows[i].src, model.flows[i].dst))
    marks_reading = bool(layer) and layer != "structure"

    # Text styling is deduplicated into classes: 240 text elements each
    # carrying a full font stack tripled the size of the figure for no
    # information. A lesson embeds this whole.
    text_styles: dict[tuple[float, str, str, bool, str, str, bool], str] = {}

    def L(
        px: float,
        py: float,
        text: str,
        size: float,
        colour: str,
        weight: str = "500",
        mono: bool = False,
        anchor: str = "middle",
        spacing: str = "",
        halo: bool = False,
    ) -> str:
        assert size >= TEXT_PX, f"text below {TEXT_PX}px: {text!r} at {size}"
        key = (size, colour, weight, mono, anchor, spacing, halo)
        cls = text_styles.setdefault(key, f"t{len(text_styles)}")
        return f'<text x="{px:.1f}" y="{py:.1f}" class="{cls}">{esc(text)}</text>'

    def text_css() -> str:
        rules: list[str] = []
        for (size, colour, weight, mono, anchor, spacing, halo), cls in text_styles.items():
            family = T["font_mono"] if mono else T["font_ui"]
            rule = (
                f"font-family:{family};font-size:{size}px;font-weight:{weight};"
                f"fill:{colour};text-anchor:{anchor}"
            )
            if spacing:
                rule += f";letter-spacing:{spacing}"
            if halo:
                rule += f";paint-order:stroke;stroke:{HALO};stroke-width:4;stroke-linejoin:round"
            rules.append(f"#{svg_id} .{cls}{{{rule}}}")
        return "<style>" + "".join(rules) + "</style>"

    states = {c.id: build_state(c, facts) for c in COMPONENTS}
    backed = evidence.of_model(model, meaning, facts, observed_by)

    # The geometry the router and the label pass read: the card boxes, the
    # headers and the empty containers as walls, every obstacle named for
    # the collision report, and the headers a box cannot hold. The same
    # function scores a layout for `systemap place`.
    geo = geometry(model)
    boxes = geo.boxes

    # ---- ground: boundaries, then the bands -------------------------------
    # Boxes are integers in the model and floats once routed; the drawing
    # prints each as it was given, so an integer corner stays "16", never
    # "16.0", and the SVG is stable across the two.
    x: float
    y: float
    w: float
    h: float
    floor: list[str] = []
    obstacles = geo.obstacles
    blocks = geo.blocks
    headers = geo.headers
    collisions = list(geo.collisions)
    for box in model.containers:
        x, y, w, h = box.box
        stroke, fill = T["container"][box.tone]
        if change_mode:
            stroke, fill = T["line"], T["bg"]
        _header, sub_lines, _unfit = container_header(box)
        floor.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
            + L(x + 13, y + 19, box.label, TEXT_PX, INK_3, "600", True, "start", ".13em")
            + "".join(
                L(x + 13, y + 33 + 12 * k, line, TEXT_PX, INK_3, "400", False, "start")
                for k, line in enumerate(sub_lines)
            )
        )

    zones: list[str] = []
    for i, region in enumerate(model.regions, start=1):
        x, y, w, h = region.box
        zones.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="none" '
            f'stroke="{T["region"]}" stroke-opacity=".28" stroke-width="1" '
            f'stroke-dasharray="3 4"/>'
            f'<g class="zone__h" data-zone="{esc(region.id)}">'
            f'<circle cx="{x + 17:.0f}" cy="{y + 16:.0f}" r="8.5" fill="{HALO}" '
            f'stroke="{T["region"]}" stroke-opacity=".5"/>'
            + L(x + 17, y + 20, str(i), TEXT_PX, T["region"], "600", True)
            + L(x + 31, y + 20, region.label, TEXT_PX, T["region"], "600", True, "start", ".13em")
            + "</g>"
        )

    # ---- flows ------------------------------------------------------------
    # Every flow is a Manhattan path through the gutters, routed by route.py
    # against the card boxes, the headers and the region boxes; the drawing
    # here only paints what the router returns and reports what it could
    # not do.
    actor_ids, region_of, region_boxes = geo.actors, geo.region_of, geo.region_boxes
    edges = [(src, dst) for src, dst, _art, _k in FLOWS]
    routes = route_all(edges, boxes, actor_ids, blocks, region_boxes, region_of, CANVAS)
    widths = {i: len(FLOWS[i][2]) * LABEL_CHAR_W + 6 for i in routes}
    # A collision names both labels: the one that could not be seated and
    # the one it landed on, each by its artifact and its edge.
    label_names = {
        i: f"label '{art}' ({src} -> {dst})" for i, (src, dst, art, _k) in enumerate(FLOWS)
    }
    seats = place_labels(
        routes,
        widths,
        LABEL_H,
        obstacles,
        CANVAS,
        names=label_names,
        cards=boxes,
        region_of=region_of,
    )

    flow_parts: list[str] = []
    label_parts: dict[int, str] = {}
    notes: list[str] = []
    label_boxes: list[dict[str, Any]] = []
    layers_of: dict[int, str] = {}
    paths: dict[int, list[list[float]]] = {}
    for i, (src, dst, artifact, kind) in enumerate(FLOWS):
        own = meaning.layer_for((src, dst), kind)
        layers_of[i] = own
        route = routes[i]
        paths[i] = [[round(x, 1), round(y, 1)] for x, y in route.points]
        seat = seats[i]
        lbox = seat.box
        label_boxes.append(
            {
                "from": src,
                "to": dst,
                "artifact": artifact,
                "box": [round(v, 1) for v in lbox],
                "segment": seat.segment,
            }
        )
        # An edge outside the reading is left out whole: no path, no label,
        # and nothing reported about a seat nobody sees.
        if shown is not None and i not in shown:
            continue
        if route.fallback:
            notes.append(f"{src} -> {dst}: {route.fallback}")
        art_hot = artifact in hot_artifacts
        colour, marker = LAYER_COLOUR[own], own
        if reading_hue:
            colour, marker = LAYER_COLOUR[reading_hue], reading_hue
        if art_hot:
            colour, marker = T["change"], "change"
        fid = f"{svg_id}-f{i}"
        ev = backed[(src, dst)]
        # A declared edge is dashed: the map says so and the code does not.
        dashed = ' stroke-dasharray="7 5"' if ev.state == evidence.DECLARED else ""
        flow_parts.append(
            f'<path id="{fid}" class="flow {kind}" data-edge="{i}" data-from="{esc(src)}" '
            f'data-to="{esc(dst)}" data-art="{esc(artifact)}" '
            f'data-kind="{esc(kind)}" data-layer="{own}" data-evidence="{ev.state}" '
            f'd="{path_d(route.points)}" '
            f'fill="none" stroke="{colour}" stroke-opacity="{0.95 if art_hot else 0.82}" '
            f'stroke-width="{1.8 if art_hot else 1.2}" stroke-linecap="round"{dashed} '
            f'marker-end="url(#{svg_id}-m-{marker})"/>'
        )
        if seat.cost > 0:
            # The line names what the seat touches and, from the router's
            # own seat counts, which fix applies: the gutter is full, or
            # the label is wider than any seat its path offers.
            fix = f"; {seat.fix}" if seat.fix else ""
            collisions.append(
                f"label collision: '{artifact}' ({src} -> {dst}) overlaps "
                f"{', '.join(seat.hits[:3])}{fix}"
            )
        lx, ly = lbox[0] + lbox[2] / 2, lbox[1] + LABEL_H - 3
        label_parts[i] = (
            f'<g class="flowlbl {kind}" data-edge="{i}" '
            f'data-from="{esc(src)}" data-to="{esc(dst)}" data-layer="{own}">'
            + L(lx, ly, artifact, LABEL_PX, colour, "500", False, "middle", "", True)
            + "</g>"
        )

    # ---- cards ------------------------------------------------------------
    # Cards are written in reading order, row by row and left to right,
    # so Tab moves across the map the way the eye does, and the detail
    # lists them the same way; no two overlap, so paint order is free.
    detail: dict[str, Any] = {}
    cards: list[str] = []
    for c in sorted(COMPONENTS, key=lambda c: (boxes[c.id][1], boxes[c.id][0])):
        cid = c.id
        kind = c.kind
        state = states[cid]
        fill, stroke, state_label = T["state"][state]
        if kind == "actor":
            fill, stroke = mix(T["bg"], T["line_2"], 0.35), INK_3
        moved, near = cid in changed, cid in adjacent
        tier = "moved" if moved else ("near" if near else "far")
        if change_mode and tier == "far":
            fill, stroke = GHOST_FILL, GHOST_STROKE
        if change_mode and moved:
            stroke = T["change"]
        elif change_mode and near:
            stroke = T["reach"]
        subject = marks_reading and cid in subjects
        quiet = marks_reading and not subject and cid not in reached
        if subject and layer:
            stroke = LAYER_COLOUR[layer]
        x, y, w, h = boxes[cid]
        state_class = state if kind != "actor" else "actor"
        plain = meaning.plain.get(cid, "")

        g: list[str] = [
            f'<g class="node {state_class}'
            f"{f' node--{tier}' if change_mode else ''}"
            f'{" subject" if subject else ""}{" quiet" if quiet else ""}" '
            f'data-id="{esc(cid)}" data-kind="{kind}" data-state="{state}" '
            f'data-region="{esc(c.home)}" '
            f'role="button" '
            f'tabindex="0" aria-label="{esc(cid)}, {esc(plain)}, {esc(state_label)}">'
        ]
        # The kind's mark, from the theme: an actor is dashed (outside the
        # code); an agent, a tool and a context card carry the mark the
        # theme's `marks` table gives their kind. Never a colour.
        mark = MARKS.get(kind, "")
        dashes = ' stroke-dasharray="4 3"' if kind == "actor" else ""
        if mark == "dotted":
            dashes = ' stroke-dasharray="1.5 2.5"'
        # A card that opens a map stands on a second card, offset down and
        # right: the mark that says there is a map inside, on the page and
        # in every figure. The panel names the map and links to it.
        if c.opens:
            g.append(
                f'<g class="node__map"><title>opens a map</title>'
                f'<rect x="{x + MAP_OFFSET}" y="{y + MAP_OFFSET}" width="{w}" height="{h}" '
                f'rx="{RADIUS}" fill="{fill}" stroke="{stroke}" stroke-width="1.1"{dashes}/></g>'
            )
        g.append(
            f'<rect class="node__box" x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{RADIUS}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{1.6 if change_mode and (moved or near) else 1.1}"'
            f"{dashes}/>"
            f'<rect class="node__ring" x="{x + 3}" y="{y + 3}" width="{w - 6}" '
            f'height="{h - 6}" rx="{RADIUS - 1}"/>'
        )
        if mark == "ring":
            g.append(
                f'<rect class="node__mark" x="{x + 5}" y="{y + 5}" width="{w - 10}" '
                f'height="{h - 10}" rx="{RADIUS - 2}" fill="none" stroke="{stroke}" '
                f'stroke-opacity=".7" stroke-width="1"/>'
            )
        elif mark == "notch":
            g.append(
                f'<path class="node__mark" d="M{x + 3},{y + 3} h9 l-9,9 z" fill="{stroke}" '
                f'fill-opacity=".85"/>'
            )
        # The name and the plain word, within the card's budget; what does
        # not fit is reported for the check, never cut short.
        name_lines, plain_lines, unfit = card_text(kind, cid, plain)
        collisions += unfit
        for k, line in enumerate(name_lines):
            g.append(L(x + w / 2, y + 17 + NAME_LINE_H * k, line, NAME_PX, INK, "600", True))
        # A card with a note carries a dot in its top corner, on the map and
        # in every figure; the panel shows the note itself, and the dot's
        # title does when hovered.
        if c.note:
            g.append(
                f'<g class="node__note"><title>{esc(c.note)}</title>'
                f'<circle cx="{x + w - 6}" cy="{y + 6}" r="2.5" fill="{INK_3}"/></g>'
            )
        # A store is the same card with a rule under its head: flat convention
        # for a thing that holds rows rather than does work. A context card is
        # a store too: its rows enter an agent's window.
        ruled = kind in ("store", "context")
        if ruled:
            g.append(
                f'<line x1="{x + 1}" y1="{y + 23}" x2="{x + w - 1}" y2="{y + 23}" '
                f'stroke="{stroke}" stroke-opacity=".45" stroke-width="1"/>'
            )
        # The plain word under the code name, on the lines the card has
        # left under it.
        first = y + (36 if ruled else 32) + NAME_LINE_H * (len(name_lines) - 1)
        g.append(
            '<g data-layer="job">'
            + "".join(
                L(x + w / 2, first + k * 12, line, TEXT_PX, INK_3, "400")
                for k, line in enumerate(plain_lines)
            )
            + "</g>"
        )

        delta = gained.get(cid, {}) if change_mode and moved else {}
        if delta:
            total = sum(delta.values()) or 1
            pos = 0.0
            for key in ("operations", "types", "refusals", "tests"):
                n = delta.get(key, 0)
                if not n:
                    continue
                seg = (w - 2) * n / total
                g.append(
                    f'<rect x="{x + 1 + pos:.1f}" y="{y + 1}" '
                    f'width="{seg:.1f}" height="2.5" fill="{T["delta"][key]}"/>'
                )
                pos += seg
            g.append(
                f'<circle cx="{x + 12}" cy="{y - 1}" r="10" fill="{T["change"]}"/>'
                + L(x + 12, y + 3, f"+{sum(delta.values())}", TEXT_PX, HALO, "600", True)
            )
        elif change_mode and moved:
            g.append(
                L(
                    x + w / 2,
                    y - 5,
                    "IN REACH" if not changed_modules else "CHANGED INSIDE",
                    TEXT_PX,
                    T["change"],
                    "600",
                    True,
                    "middle",
                    ".1em",
                )
            )
        g.append("</g>")
        cards.append("".join(g))

        detail[cid] = {
            "id": cid,
            "kind": kind,
            "region": c.home,
            "plain": plain,
            "does": c.does,
            "state": state if kind != "actor" else "actor",
            "state_label": state_label if kind != "actor" else "outside",
            "lives": lives_in(list(c.implemented_by)),
            # The three fields the panel prints beside the plain word: the
            # one-line signature, the entry with the module that defines
            # it, and the caveat.
            "interface": c.interface,
            "entry": c.entry,
            "entry_module": entry_module(c, facts),
            "note": c.note,
            "calls_model": c.calls_model,
            "map": (
                opens.get(cid, {"name": cid, "href": "", "cards": 0, "preview": ""})
                if c.opens
                else None
            ),
            "moved": moved,
            "rules": model.rules_of(cid),
            "edges": [
                i
                for i, (a, b, _art, _k) in enumerate(FLOWS)
                if cid in (a, b) and (shown is None or i in shown)
            ],
        }

    edges_meta = []
    for i, (src, dst, artifact, kind) in enumerate(FLOWS):
        own = layers_of[i]
        ev = backed[(src, dst)]
        edges_meta.append(
            {
                "from": src,
                "to": dst,
                "art": artifact,
                "kind": kind,
                "layer": own,
                "out": meaning.verb_for((src, dst), own, True),
                "in": meaning.verb_for((src, dst), own, False),
                "say": meaning.relations.get((src, dst), ""),
                # The evidence state and the line the panel prints for it,
                # worded here so the page and a figure say the same thing.
                "evidence": ev.state,
                "mechanism": ev.mechanism,
                "evidence_says": ev.says,
            }
        )
    edge_index = {(a, b): i for i, (a, b, _art, _k) in enumerate(FLOWS)}
    journeys_meta = [
        {
            "id": j.id,
            "label": j.label,
            "steps": [
                {
                    "acts": list(s.acts),
                    "measures": list(s.measures),
                    "edge": edge_index.get(s.edge, -1),
                    "say": s.say,
                }
                for s in j.steps
            ],
        }
        for j in meaning.journeys
    ]

    meta = {
        "_meta": {
            "layers": [
                {
                    "id": lay.id,
                    "label": lay.label,
                    "question": lay.question,
                    "sub": lay.sub,
                    "colour": LAYER_COLOUR[lay.id],
                    "derived": lay.id in DERIVED_LAYERS,
                }
                for lay in LAYERS
            ],
            "readings": {
                lid: {"edges": edges, "subjects": subjects}
                for lid, (edges, subjects) in readings.items()
            },
            "reading": layer,
            "edges": edges_meta,
            "journeys": journeys_meta,
            "regions": [
                {
                    "id": r.id,
                    "label": r.label,
                    "box": [float(v) for v in r.box],
                    "ids": [c.id for c in COMPONENTS if c.region == r.id],
                }
                for r in model.regions
            ],
            "rules": [
                {"n": inv.n, "text": inv.text, "ids": sorted(inv.governs)}
                for inv in sorted(model.invariants, key=lambda i: i.n)
            ],
            "kinds": list(model.flow_kinds),
            "states": {s: sum(1 for v in states.values() if v == s) for s in states.values()},
            "evidence": {
                state: sum(1 for ev in backed.values() if ev.state == state)
                for state in evidence.STATES
            },
            "collisions": collisions,
            "notes": notes,
            "labels": label_boxes,
            "headers": headers,
            "cards": {cid: list(box) for cid, box in boxes.items()},
            "paths": paths,
        }
    }

    pad = 26
    width, height = CANVAS
    # The drawing's title is the reading's question when it draws one
    # reading, so an image of the control flow says what it answers.
    if layer:
        lay = next(lay for lay in LAYERS if lay.id == layer)
        title = f"{lay.label}: {lay.question}" if lay.question else lay.label
        what = (
            f"{title} Every card, and only the edges of the {lay.label} reading, "
            "each labelled with what it carries."
        )
    else:
        title = "System map"
        what = (
            "System map. Fill is build state; every line is labelled with "
            "what it carries and coloured by its layer."
        )
    p: list[str] = [
        f'<svg id="{svg_id}" class="scene" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{-pad} {-pad} {width + pad * 2} {height + pad * 2}" '
        f'preserveAspectRatio="xMidYMid meet" tabindex="0" role="application" '
        f'aria-label="{esc(what)}">'
        f"<title>{esc(title)}</title>",
        _defs(svg_id, T),
        _svg_style(svg_id, T),
    ]
    # Everything drawn sits in one group the script pans and zooms with a
    # transform; the viewBox never changes, so every coordinate read back from
    # the figure (card boxes, edge paths) stays in drawing units.
    p.append('<g class="view">')
    p.extend(floor)
    p.append(f'<g data-layer="zones">{"".join(zones)}</g>')
    p.append(f'<g data-layer="flow">{"".join(flow_parts)}</g>')
    p.extend(cards)
    p.append(
        '<g data-layer="flow">' + "".join(label_parts[i] for i in sorted(label_parts)) + "</g>"
    )
    p.append('<g data-layer="tags"></g>')
    p.append("</g>")
    # Text classes are known only once everything is drawn, so their style
    # block goes in last; the renderer does not care where a style sits.
    p.append(text_css())
    p.append("</svg>")
    return "".join(p), json.dumps({**detail, **meta}, ensure_ascii=False)


def panel_css(t: dict[str, Any]) -> str:
    """Styles for the focus panel the interactive script writes into.

    Shared by the map page and a lesson figure, so a component reads the
    same in both. Class names are prefixed so a host page's own styles are
    never caught by accident.
    """
    return (
        f".systemap-panel{{font-family:{t['font_ui']};font-size:13px;line-height:1.45;"
        f"color:{t['ink_2']};background:{t['surface']};border:1px solid {t['line']};"
        "border-radius:8px;padding:.9rem 1rem 1rem;min-height:3rem}"
        f".systemap-panel:empty::before{{content:'Click a component to read it.';"
        f"color:{t['ink_3']}}}"
        f".systemap-f__plain{{font-size:19px;font-weight:600;color:{t['ink']};"
        "letter-spacing:-.01em;line-height:1.2;margin:0}"
        f".systemap-f__code{{font-family:{t['font_mono']};font-size:12px;color:{t['accent']};"
        "margin:.3rem 0 0;display:flex;flex-wrap:wrap;gap:.2rem .7rem;align-items:baseline}"
        f".systemap-f__kind{{color:{t['ink_3']};font-size:11px;letter-spacing:.06em;"
        "text-transform:uppercase}"
        f".systemap-f__does{{margin:.6rem 0 .2rem;font-size:13px;color:{t['ink_2']}}}"
        # The card's one-line signature, then the caveat, before the wheel.
        f".systemap-f__iface{{margin:.3rem 0 .2rem;font-family:{t['font_mono']};"
        f"font-size:11.5px;color:{t['ink_2']};word-break:break-word}}"
        f".systemap-f__note{{margin:.5rem 0 .2rem;padding:.4rem .6rem;font-size:12.5px;"
        f"color:{t['ink']};border-left:3px solid {t['warn']};background:{t['raised']};"
        "border-radius:0 6px 6px 0}"
        ".systemap-f__wheel{margin:.4rem 0 0}"
        ".systemap-f__wheel svg{width:100%;height:auto;display:block;margin:0 auto}"
        f".systemap-f__say{{margin:.2rem 0 .6rem;padding:.55rem .7rem;font-size:13px;"
        f"line-height:1.45;color:{t['ink']};border-left:3px solid {t['accent']};"
        f"background:{t['raised']};border-radius:0 6px 6px 0;min-height:2.6rem}}"
        f".systemap-f__say.muted{{color:{t['ink_3']};border-left-color:{t['line_2']}}}"
        # The evidence line under the sentence: what the facts say about the edge.
        f".systemap-f__evidence{{margin:-.3rem 0 .6rem;font-family:{t['font_mono']};"
        f"font-size:11px;color:{t['ink_3']};min-height:1em}}"
        f".systemap-f__evidence.declared{{color:{t['warn']}}}"
        ".systemap-f__chips{display:flex;flex-wrap:wrap;gap:.35rem;margin:.5rem 0 0}"
        f".systemap-chip{{display:inline-flex;align-items:center;gap:.35em;min-height:24px;"
        f"padding:0 .55em;border-radius:4px;font-family:{t['font_mono']};font-size:11px;"
        f"letter-spacing:.04em;background:{t['raised']};color:{t['ink_3']};"
        f"border:1px solid {t['line']}}}"
        f".systemap-chip--built{{color:{t['good']};border-color:transparent}}"
        f".systemap-chip--actor{{color:{t['ink_3']};background:none;"
        f"border:1px dashed {t['line_2']}}}"
        f".systemap-chip a{{color:{t['accent']};text-decoration:none}}"
        ".systemap-chip a:hover{text-decoration:underline}"
        f".systemap-chip--rule{{color:{t['violet']};cursor:help;min-width:24px;"
        "justify-content:center}"
        f".systemap-f__lives{{margin:.6rem 0 0;font-family:{t['font_mono']};font-size:11px;"
        f"color:{t['ink_3']}}}"
        f".systemap-f__lives b{{font-weight:400;color:{t['ink_3']}}}"
        f".systemap-f__entry{{margin:.4rem 0 0;font-family:{t['font_mono']};font-size:11px;"
        f"color:{t['ink_3']}}}"
        f".systemap-f__entry b{{font-weight:400;color:{t['ink_2']}}}"
        # The map a card opens: its name and how many cards it holds, then on
        # a page its preview and the button that opens it in place.
        f".systemap-f__opens{{margin:.4rem 0 0;font-family:{t['font_mono']};font-size:11px;"
        f"color:{t['ink_3']}}}"
        f".systemap-f__opens b{{font-weight:400;color:{t['ink_2']}}}"
        f".systemap-f__preview{{margin:.5rem 0 0;border:1px solid {t['line']};border-radius:6px;"
        f"overflow:hidden;background:{t['bg']}}}"
        ".systemap-f__preview svg{width:100%;height:auto;display:block}"
        f".systemap-f__open{{appearance:none;display:block;margin:.5rem 0 0;min-height:30px;"
        f"padding:0 .8rem;border-radius:6px;border:1px solid {t['accent']};background:none;"
        f"color:{t['accent']};font-family:{t['font_ui']};font-size:12.5px;cursor:pointer}}"
        f".systemap-f__open:hover{{background:{t['raised']}}}"
        # The wheel
        f".systemap-w__spoke{{cursor:pointer;outline:none}}"
        ".systemap-w__hit{stroke:transparent;stroke-width:26;fill:none;pointer-events:stroke}"
        ".systemap-w__line{fill:none;stroke-width:1.5;transition:stroke-width .12s ease}"
        f".systemap-w__verb{{font-family:{t['font_ui']};font-size:11px;font-weight:500;"
        f"text-anchor:middle;paint-order:stroke;stroke:{t['surface']};stroke-width:5;"
        "stroke-linejoin:round;pointer-events:none}"
        f".systemap-w__name{{font-family:{t['font_mono']};font-size:11px;font-weight:600;"
        f"fill:{t['ink']};pointer-events:none}}"
        f".systemap-w__centre rect{{fill:{t['raised']};stroke:{t['accent']};stroke-width:1.6}}"
        f".systemap-w__centre text{{font-family:{t['font_mono']};font-size:12px;font-weight:600;"
        f"fill:{t['ink']};text-anchor:middle}}"
        ".systemap-w__spoke.peek .systemap-w__line,.systemap-w__spoke:hover .systemap-w__line,"
        ".systemap-w__spoke:focus-visible .systemap-w__line{stroke-width:3.2}"
        f".systemap-w__spoke.peek .systemap-w__name,.systemap-w__spoke:hover .systemap-w__name,"
        f".systemap-w__spoke:focus-visible .systemap-w__name{{fill:{t['accent']}}}"
        f".systemap-w__empty{{font-family:{t['font_ui']};font-size:12px;fill:{t['ink_3']};"
        "text-anchor:middle}"
    )


def interactive_script(t: dict[str, Any], svg_id: str, panel_id: str, detail_json: str) -> str:
    """The one script that makes a figure operable. Plain DOM, no libraries.

    Clicking a component (or pressing Enter on it) dims everything but the
    component and its neighbours, thickens each connected edge in its
    layer's colour, tags each neighbour with the verb that relates it, and
    draws the relationship wheel in the panel. It also owns the viewport:
    wheel and pinch zoom about the pointer, drag pans, a selection or a
    journey step frames what it lights in the part of the figure on screen
    (less what the page lays over it: `view.frameFocus(cover)`), a
    double-click on a region label frames the region, and
    `svg.systemap.view` exposes fit, 100%, step, back and the last framing.
    The same script serves the map page and a lesson figure, so the
    two cannot behave differently. The page adds layer and journey controls
    on top through `svg.systemap`.

    The detail JSON is inlined; `</` is broken up so no artifact label can
    close the script early.
    """
    # The layout audit (label boxes, card boxes) is for checkers, not the
    # page; it is dropped from the inlined copy to keep a figure small.
    parsed = json.loads(detail_json)
    meta = dict(parsed.get("_meta") or {})
    meta.pop("labels", None)
    meta.pop("cards", None)
    meta.pop("paths", None)
    parsed["_meta"] = meta
    data = json.dumps(parsed, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    palette = json.dumps(
        {
            "accent": t["accent"],
            "steel": t["steel"],
            "surface": t["surface"],
            "raised": t["raised"],
            "bg": t["bg"],
            "ink": t["ink"],
        }
    )
    return (
        "<script>(function(){\n"
        f"var DETAIL = {data};\n"
        f"var PAL = {palette};\n"
        f"var svg = document.getElementById({json.dumps(svg_id)});\n"
        f"var panel = document.getElementById({json.dumps(panel_id)});\n"
        + _INTERACTIVE_JS
        + "})();</script>"
    )


_INTERACTIVE_JS = r"""
if(!svg){ return; }
var META = DETAIL._meta || {};
var LAYERS = META.layers || [];
var EDGES = META.edges || [];
var RULES = {};
(META.rules || []).forEach(function(r){ RULES[r.n] = r.text; });
var LCOL = {}, LORD = {}, LAYER_AT = {};
LAYERS.forEach(function(l, i){ LCOL[l.id] = l.colour; LORD[l.id] = i; LAYER_AT[l.id] = l; });
// Which edges and which cards each reading shows, decided in Python
// (systemap.model.reading) and carried in the detail, so the page's layer
// switch and a figure of one layer read the same table.
var READINGS = META.readings || {};
var IN_READING = {}, SUBJECT_OF = {};
Object.keys(READINGS).forEach(function(L){
  IN_READING[L] = {}; SUBJECT_OF[L] = {};
  (READINGS[L].edges || []).forEach(function(i){ IN_READING[L][i] = true; });
  (READINGS[L].subjects || []).forEach(function(id){ SUBJECT_OF[L][id] = true; });
});
var EDGE_AT = {};
EDGES.forEach(function(e, i){ EDGE_AT[e.from + '>' + e.to] = i; });
var NS = 'http://www.w3.org/2000/svg';
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function mix(a, b, t){
  function rgb(h){
    h = h.replace('#', '');
    return [0, 2, 4].map(function(i){ return parseInt(h.substr(i, 2), 16); });
  }
  var x = rgb(a), y = rgb(b);
  return '#' + x.map(function(v, i){
    var m = Math.round(v + (y[i] - v) * t);
    return ('0' + m.toString(16)).slice(-2);
  }).join('');
}
var nodes = Array.prototype.slice.call(svg.querySelectorAll('.node'));
var flows = Array.prototype.slice.call(svg.querySelectorAll('.flow'));
var labels = Array.prototype.slice.call(svg.querySelectorAll('.flowlbl'));
var nodeOf = {}, labelOf = {}, flowOf = {};
nodes.forEach(function(n){ nodeOf[n.dataset.id] = n; });
labels.forEach(function(l){ labelOf[l.dataset.edge] = l; });
flows.forEach(function(p){ flowOf[p.dataset.edge] = p; });
var tags = svg.querySelector('[data-layer="tags"]');
var state = {focus:'', layer:'all', journey:null, peek:-1};

// ---- what a focus lights ----------------------------------------------------
// The focused card, the edges of it the reading shows, and their other
// ends: one set, read from the readings table, that the dimming, the
// tags and the framing all use, so what is framed is exactly what is lit.
// A reading with no edges of its own (Structure) lights every edge of the
// card, as All does: there the click is how the edges are seen at all.
function focusEdges(f, L){
  var all = DETAIL[f] && DETAIL[f].edges || [];
  if(L === 'all' || !(READINGS[L] && READINGS[L].edges && READINGS[L].edges.length)){
    return all.slice();
  }
  return all.filter(function(i){ return edgeIn(i, L); });
}
function litSet(){
  var f = state.focus;
  if(!f || !DETAIL[f]){ return null; }
  var ids = {}, edges = focusEdges(f, state.layer);
  ids[f] = true;
  edges.forEach(function(i){ ids[EDGES[i].from] = true; ids[EDGES[i].to] = true; });
  return {id:f, ids:ids, edges:edges};
}

function setCls(el, map){
  for(var k in map){ if(map.hasOwnProperty(k)){ el.classList.toggle(k, !!map[k]); } }
}
function boxOf(n){
  var r = n.querySelector('.node__box');
  return {x:+r.getAttribute('x'), y:+r.getAttribute('y'),
    w:+r.getAttribute('width'), h:+r.getAttribute('height')};
}
function el(name, attrs, text){
  var e = document.createElementNS(NS, name);
  for(var k in attrs){ if(attrs.hasOwnProperty(k)){ e.setAttribute(k, attrs[k]); } }
  if(text !== undefined){ e.textContent = text; }
  return e;
}

// ---- the viewport ---------------------------------------------------------
// The drawing sits in <g class="view" transform="translate(tx ty) scale(k)">.
// (tx, ty, k) are in viewBox units, so a drawing point p lands at k*p + t in
// the viewBox and every box or path read from the figure stays in drawing
// units. `base` is the CSS pixels the browser gives one viewBox unit; the
// zoom the reader sees is base*k, and Fit (the whole map across the column)
// is k = 1, t = 0. Wheel and pinch zoom about the pointer, a drag pans, a
// selection or a journey step frames its neighbourhood in the part of the
// figure the reader can see (the figure's box clipped to the window, less
// whatever the page lays over it), and Escape (in the page around this
// script) returns to the view before the framing began.
var view = svg.querySelector('.view');
var VB = svg.viewBox.baseVal;
var ZMIN = 0.4, ZMAX = 2.5, ZCAP = 1.4, FRAME_PAD = 28, ANIM_MS = 320;
var cur = {k:1, tx:0, ty:0};   // what is drawn now, mid-animation included
var goal = {k:1, tx:0, ty:0};  // where the view is heading
var saved = null;              // the view before the current framing chain
var framed = false;            // the view on screen is one a frame() set
var lastFrame = null;          // {rect, area, k}: what the last framing fitted where
var anim = 0, booted = false, dragged = false;
function base(){ var m = svg.getScreenCTM(); return m && m.a ? m.a : 1; }
function reduced(){
  return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}
function isFit(v){
  v = v || goal;
  return Math.abs(v.k - 1) < 1e-3 && Math.abs(v.tx) < 0.5 && Math.abs(v.ty) < 0.5;
}
function centre(){ return {x:VB.x + VB.width / 2, y:VB.y + VB.height / 2}; }
function toVb(clientX, clientY){
  // A client point in viewBox units.
  var m = svg.getScreenCTM();
  if(!m){ return centre(); }
  var q = new DOMPoint(clientX, clientY).matrixTransform(m.inverse());
  return {x:q.x, y:q.y};
}
function clampView(v, kmin){
  // The zoom stays between ZMIN and ZMAX, except that the zoom on screen
  // and the zoom a framing asks for (kmin) are always allowed: Fit on a
  // column so narrow that Fit is under ZMIN, and a lit set too large for
  // the visible area at ZMIN, which is fitted whole rather than cropped
  // (zooming out from there is a no-op, never a jump in). A fifth of the
  // viewport always holds drawing, so the map cannot be dragged out of sight.
  var b = base(), lo = Math.min(Math.min(ZMIN, b) / b, goal.k), hi = ZMAX / b;
  if(kmin !== undefined){ lo = Math.min(lo, kmin); }
  var k = Math.min(hi, Math.max(lo, v.k));
  var mx = VB.width * 0.2, my = VB.height * 0.2;
  var tx = Math.min(VB.x + VB.width - mx - k * VB.x,
    Math.max(VB.x + mx - k * (VB.x + VB.width), v.tx));
  var ty = Math.min(VB.y + VB.height - my - k * VB.y,
    Math.max(VB.y + my - k * (VB.y + VB.height), v.ty));
  return {k:k, tx:tx, ty:ty};
}
function apply(v){
  cur = v;
  if(view){
    view.setAttribute('transform', 'translate(' + v.tx.toFixed(2) + ' ' + v.ty.toFixed(2)
      + ') scale(' + v.k.toFixed(4) + ')');
  }
  svg.dispatchEvent(new CustomEvent('systemap:view',
    {detail:{zoom:base() * v.k, fit:isFit(v)}, bubbles:true}));
}
function setView(v, instant, kmin){
  goal = clampView(v, kmin);
  if(anim){ cancelAnimationFrame(anim); anim = 0; }
  if(instant || !booted || reduced()){ apply(goal); return; }
  var from = cur, to = goal, t0 = 0;
  function tick(now){
    if(!t0){ t0 = now; }
    var u = Math.min(1, (now - t0) / ANIM_MS);
    var e = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
    apply({k:from.k + (to.k - from.k) * e, tx:from.tx + (to.tx - from.tx) * e,
      ty:from.ty + (to.ty - from.ty) * e});
    anim = u < 1 ? requestAnimationFrame(tick) : 0;
  }
  anim = requestAnimationFrame(tick);
}
function userView(v, instant){
  // The reader moved the view: it is theirs now, and there is nothing to
  // go back to until the next framing.
  framed = false; saved = null;
  setView(v, instant);
}
function zoomAt(f, cx, cy, instant){
  // Zoom by f about the viewBox point (cx, cy): the drawing point under it
  // stays under it, even when the zoom is clamped.
  var k = clampView({k:goal.k * f, tx:goal.tx, ty:goal.ty}).k, g = k / goal.k;
  userView({k:k, tx:cx - g * (cx - goal.tx), ty:cy - g * (cy - goal.ty)}, instant);
}
function visibleArea(cover){
  // The part of the figure the reader can see, in viewBox units: the
  // figure's box on screen clipped to the window, less the box the page
  // lays over one side of it (`cover`: {rect, side}, the drawer), or the
  // whole viewBox where the figure has no box yet. A figure wholly off
  // screen is framed in its own box: the page scrolls it into view.
  var whole = {x:VB.x, y:VB.y, w:VB.width, h:VB.height};
  var s = svg.getBoundingClientRect ? svg.getBoundingClientRect() : null;
  if(!s || !(s.width > 0) || !(s.height > 0)){ return whole; }
  var ww = window.innerWidth || s.right, wh = window.innerHeight || s.bottom;
  var l = Math.max(s.left, 0), t = Math.max(s.top, 0);
  var r = Math.min(s.right, ww), bt = Math.min(s.bottom, wh);
  if(r - l < 40 || bt - t < 40){ l = s.left; t = s.top; r = s.right; bt = s.bottom; }
  if(cover && cover.rect && cover.rect.width > 0){
    if(cover.side === 'left'){ l = Math.max(l, cover.rect.right + 12); }
    else { r = Math.min(r, cover.rect.left - 12); }
  }
  var p = toVb(l, t), q = toVb(r, bt);
  return {x:p.x, y:p.y, w:Math.max(40, q.x - p.x), h:Math.max(40, q.y - p.y)};
}
function frameRect(r, area, instant){
  // Fit the drawing rect r into `area` (viewBox units; the whole viewBox
  // when null) at the largest zoom that shows all of it, capped at ZCAP,
  // its centre on the area's centre. A rect larger than the area at ZMIN
  // is fitted whole, never cropped. The first framing in a chain remembers
  // the view it left.
  area = area || {x:VB.x, y:VB.y, w:VB.width, h:VB.height};
  var b = base();
  var k = Math.min(ZCAP / b, area.w / r.w, area.h / r.h);
  var cx = area.x + area.w / 2, cy = area.y + area.h / 2;
  if(!framed){ saved = goal; framed = true; }
  lastFrame = {rect:r, area:area, k:k};
  setView({k:k, tx:cx - k * (r.x + r.w / 2), ty:cy - k * (r.y + r.h / 2)}, instant, k);
}
function unionBox(ids, edgeIdx){
  // The rect around some cards and the edges between them, in drawing units.
  var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  function add(x, y, w, h){
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x + w); y1 = Math.max(y1, y + h);
  }
  ids.forEach(function(id){
    if(nodeOf[id]){ var b = boxOf(nodeOf[id]); add(b.x, b.y, b.w, b.h); } });
  (edgeIdx || []).forEach(function(i){
    var p = flowOf[i];
    if(!p || !p.getBBox){ return; }
    var bb = p.getBBox();
    if(bb.width || bb.height){ add(bb.x, bb.y, bb.width, bb.height); }
  });
  if(x0 === Infinity){ return null; }
  return {x:x0 - FRAME_PAD, y:y0 - FRAME_PAD, w:x1 - x0 + 2 * FRAME_PAD, h:y1 - y0 + 2 * FRAME_PAD};
}
function frameFocus(cover, instant){
  // What the focus lights (litSet: the card, the edges the reading shows,
  // their other ends), framed in the visible area less `cover`.
  var lit = litSet();
  if(!lit){ return; }
  var r = unionBox(Object.keys(lit.ids), lit.edges);
  if(r){ frameRect(r, visibleArea(cover), instant); }
}
function frameJourney(step, instant){
  // The step's acting and measuring components and the edge it traces,
  // framed in the visible area; the page closes its drawer for a journey.
  var ids = (step.acts || []).concat(step.measures || []), edges = [];
  if(step.edge >= 0 && EDGES[step.edge]){
    ids.push(EDGES[step.edge].from); ids.push(EDGES[step.edge].to); edges.push(step.edge);
  }
  var r = unionBox(ids, edges);
  if(r){ frameRect(r, visibleArea(null), instant); }
}
function frameRegion(id){
  var box = null;
  (META.regions || []).forEach(function(z){ if(z.id === id && z.box){ box = z.box; } });
  if(!box){ return; }
  frameRect({x:box[0] - 12, y:box[1] - 12, w:box[2] + 24, h:box[3] + 24}, visibleArea(null));
}
function back(){
  // The view before the framing chain began; nothing if the reader has
  // moved the view since.
  if(!saved){ return; }
  var v = saved;
  saved = null; framed = false;
  setView(v);
}
function fracOf(id){
  // Where the card's centre sits across the visible area (the last framing's,
  // else the viewport), 0 to 1, once the view arrives. The page docks its
  // drawer on the other side.
  var n = nodeOf[id];
  if(!n){ return 0.5; }
  var b = boxOf(n), a = lastFrame ? lastFrame.area : {x:VB.x, w:VB.width};
  return (goal.k * (b.x + b.w / 2) + goal.tx - a.x) / a.w;
}

// Wheel (and trackpad pinch, which arrives as ctrl+wheel) zooms about the
// pointer. A drag pans; under 4px of movement it is a click and the cards
// keep it. Two touches pinch.
svg.addEventListener('wheel', function(e){
  e.preventDefault();
  var d = e.deltaY;
  if(e.deltaMode === 1){ d *= 16; } else if(e.deltaMode === 2){ d *= 400; }
  var f = Math.max(0.5, Math.min(2, Math.exp(-d * (e.ctrlKey ? 0.01 : 0.0022))));
  var c = toVb(e.clientX, e.clientY);
  zoomAt(f, c.x, c.y, true);
}, {passive:false});
var ptrs = {}, drag = null, pinch = null;
function ptrList(){ return Object.keys(ptrs).map(function(k){ return ptrs[k]; }); }
function dist(a, b){ return Math.hypot(a.x - b.x, a.y - b.y); }
function startDrag(p){ drag = {x:p.x, y:p.y, tx:goal.tx, ty:goal.ty, moved:false}; }
svg.addEventListener('pointerdown', function(e){
  if(e.pointerType === 'mouse' && e.button !== 0){ return; }
  dragged = false;
  ptrs[e.pointerId] = {x:e.clientX, y:e.clientY};
  var list = ptrList();
  if(list.length === 1){ pinch = null; startDrag(list[0]); }
  else if(list.length === 2){
    drag = null;
    var m = toVb((list[0].x + list[1].x) / 2, (list[0].y + list[1].y) / 2);
    pinch = {d:dist(list[0], list[1]), k:goal.k,
      px:(m.x - goal.tx) / goal.k, py:(m.y - goal.ty) / goal.k};
  }
});
svg.addEventListener('pointermove', function(e){
  if(!ptrs[e.pointerId]){ return; }
  ptrs[e.pointerId] = {x:e.clientX, y:e.clientY};
  var list = ptrList();
  if(pinch && list.length >= 2){
    var m = toVb((list[0].x + list[1].x) / 2, (list[0].y + list[1].y) / 2);
    var k = clampView({k:pinch.k * dist(list[0], list[1]) / pinch.d, tx:0, ty:0}).k;
    dragged = true;
    userView({k:k, tx:m.x - k * pinch.px, ty:m.y - k * pinch.py}, true);
  } else if(drag){
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if(!drag.moved){
      if(Math.hypot(dx, dy) < 4){ return; }
      drag.moved = true;
      svg.classList.add('panning');
      if(svg.setPointerCapture){ try { svg.setPointerCapture(e.pointerId); } catch(_x){} }
    }
    var b = base();
    userView({k:goal.k, tx:drag.tx + dx / b, ty:drag.ty + dy / b}, true);
  }
});
function endPointer(e){
  if(!ptrs[e.pointerId]){ return; }
  delete ptrs[e.pointerId];
  if(drag && drag.moved){ dragged = true; }
  drag = null; pinch = null;
  svg.classList.remove('panning');
  var list = ptrList();
  if(list.length === 1){ startDrag(list[0]); drag.moved = true; }
}
svg.addEventListener('pointerup', endPointer);
svg.addEventListener('pointercancel', endPointer);
// A click that ends a drag is not a click: nothing under the pointer hears it.
svg.addEventListener('click', function(e){
  if(dragged){ dragged = false; e.preventDefault(); e.stopImmediatePropagation(); }
}, true);
Array.prototype.slice.call(svg.querySelectorAll('[data-zone]')).forEach(function(z){
  z.addEventListener('dblclick', function(e){ e.preventDefault(); frameRegion(z.dataset.zone); });
});

// ---- the readings ---------------------------------------------------------
// A kind layer shows the edges of its kind and hides the rest. A derived
// reading (Structure, System context, Agents) is computed from the
// endpoints, in Python, and read from the table above; on the page the
// rest are dimmed, not hidden, and the edges shown are painted in the
// reading's own hue.
function edgeIn(i, L){
  if(L === 'all'){ return true; }
  return !!(IN_READING[L] && IN_READING[L][i]);
}
function subjectOf(id, L){
  // A card the reading is about even when no edge it shows touches it.
  return !!(SUBJECT_OF[L] && SUBJECT_OF[L][id]);
}
function layerIds(L){
  var ids = {}, out = [];
  EDGES.forEach(function(e, i){ if(edgeIn(i, L)){ ids[e.from] = true; ids[e.to] = true; } });
  Object.keys(DETAIL).forEach(function(id){
    if(id !== '_meta' && (ids[id] || subjectOf(id, L))){ out.push(id); } });
  return out;
}
flows.forEach(function(p){
  p.dataset.stroke = p.getAttribute('stroke');
  p.dataset.marker = p.getAttribute('marker-end');
});
function recolour(i, colour){
  var p = flowOf[i], lbl = labelOf[i];
  if(!p){ return; }
  p.setAttribute('stroke', colour || p.dataset.stroke);
  p.setAttribute('marker-end', colour ? 'url(#' + svg.id + '-m-' + state.layer + ')'
    : p.dataset.marker);
  var t = lbl && lbl.querySelector('text');
  if(t){ t.style.fill = colour || ''; }
}

function paint(){
  var f = state.focus, j = state.journey, L = state.layer;
  var lit = litSet(), near = lit ? lit.ids : {}, hot = {};
  if(lit){ lit.edges.forEach(function(i){ hot[i] = true; }); }
  var jset = {}, traced = -1;
  if(j){
    (j.acts || []).concat(j.measures || []).forEach(function(id){ jset[id] = true; });
    traced = j.edge;
    if(traced >= 0){ jset[EDGES[traced].from] = true; jset[EDGES[traced].to] = true; }
  }
  var derived = !!(LAYER_AT[L] && LAYER_AT[L].derived) && L !== 'structure';
  var inLayer = {};
  EDGES.forEach(function(e, i){
    if(edgeIn(i, L)){ inLayer[e.from] = true; inLayer[e.to] = true; } });
  flows.forEach(function(p){
    var i = +p.dataset.edge;
    var on = edgeIn(i, L);
    var lit = !!hot[i] || i === traced;
    var vis = on || lit || derived;
    var dim = vis && !lit && (!!f || !!j || (derived && !on));
    var m = {off:!vis, hot:lit, dim:dim, peek:(i === state.peek)};
    setCls(p, m);
    if(labelOf[i]){ setCls(labelOf[i], m); }
    recolour(i, derived && on ? LCOL[L] : '');
  });
  nodes.forEach(function(n){
    var id = n.dataset.id;
    var dim = f ? !near[id] : (j ? !jset[id] : false);
    var quiet = !f && !j && L !== 'all' && !inLayer[id] && !subjectOf(id, L);
    // A card the reading is about carries the reading's colour as its
    // stroke; Structure is about every card and colours none.
    var subject = L !== 'all' && L !== 'structure' && subjectOf(id, L);
    n.style.setProperty('--subject', subject ? LCOL[L] : '');
    setCls(n, {sel:(id === f), dim:dim, quiet:quiet, subject:subject,
      acts:!!(j && (j.acts || []).indexOf(id) >= 0),
      meas:!!(j && (j.measures || []).indexOf(id) >= 0), tagged:false});
  });
  svg.classList.toggle('focused', !!f);
  drawTags();
}

function verbsFrom(cid, other, edges){
  // The verbs on the given edges between cid and other, read from cid,
  // with the layer colour of the first.
  var out = [], colour = '';
  edges.forEach(function(i){
    var e = EDGES[i];
    if(e.from === cid && e.to === other){ out.push(e.out); }
    else if(e.to === cid && e.from === other){ out.push(e['in']); }
    else { return; }
    colour = colour || LCOL[e.layer];
  });
  return {verbs:out, colour:colour || PAL.ink};
}

function drawTags(){
  if(!tags){ return; }
  while(tags.firstChild){ tags.removeChild(tags.firstChild); }
  var lit = litSet();
  if(!lit){ return; }
  var f = lit.id, seen = {};
  lit.edges.forEach(function(i){
    var e = EDGES[i];
    var other = e.from === f ? e.to : e.from;
    if(other === f || seen[other] || !nodeOf[other]){ return; }
    seen[other] = true;
    var v = verbsFrom(f, other, lit.edges);
    var text = v.verbs.join(' / ');
    var lines = text.length > 25 ? v.verbs : [text];
    var b = boxOf(nodeOf[other]);
    var th = lines.length > 1 ? 29 : 17;
    var g = el('g', {'class':'vtag', 'data-id':other});
    g.appendChild(el('rect', {x:b.x + 5, y:b.y + b.h - th - 3, width:b.w - 10, height:th, rx:3,
      fill:mix(PAL.raised, v.colour, 0.16), stroke:v.colour}));
    lines.forEach(function(line, k){
      var y = b.y + b.h - 8 - (lines.length - 1 - k) * 12;
      g.appendChild(el('text', {x:b.x + b.w / 2, y:y, fill:v.colour}, line));
    });
    tags.appendChild(g);
    nodeOf[other].classList.add('tagged');
  });
}

// ---- the relationship wheel --------------------------------------------
function wrapName(id){
  var parts = id.match(/[A-Z]+[a-z0-9]*|[a-z0-9]+/g) || [id];
  var lines = [], cur = '';
  parts.forEach(function(p){
    if(cur && (cur + p).length > 10){ lines.push(cur); cur = p; } else { cur += p; }
  });
  if(cur){ lines.push(cur); }
  return lines.slice(0, 3);
}
function wheelLayout(cid){
  // Spokes grouped by layer in LAYERS order, clockwise from the top, with a
  // half-slot of daylight between groups. Mirrored in check_layout.py.
  var d = DETAIL[cid];
  var idx = (d.edges || []).slice();
  idx.sort(function(a, b){ return (LORD[EDGES[a].layer] - LORD[EDGES[b].layer]) || (a - b); });
  var groups = 0, prev = null;
  idx.forEach(function(i){ if(EDGES[i].layer !== prev){ groups++; prev = EDGES[i].layer; } });
  var gap = groups > 1 ? 0.5 : 0;
  var step = 360 / (idx.length + gap * groups);
  var W = 400, H = 400, cx = 200, cy = 200, R = 118;
  var hw = Math.max(34, cid.length * 3.7 + 12), hh = 15;
  var spokes = [], a = -90; prev = null;
  idx.forEach(function(i){
    var e = EDGES[i];
    if(prev !== null && e.layer !== prev){ a += gap * step; }
    prev = e.layer;
    var th = a * Math.PI / 180; a += step;
    var ux = Math.cos(th), uy = Math.sin(th);
    var r0 = Math.min(hw / Math.max(Math.abs(ux), 1e-6), hh / Math.max(Math.abs(uy), 1e-6)) + 8;
    var other = e.from === cid ? e.to : e.from;
    var deg = th * 180 / Math.PI;
    spokes.push({i:i, e:e, other:other, out:(e.from === cid), ux:ux, uy:uy, r0:r0,
      deg:deg, verb:(e.from === cid ? e.out : e['in']), colour:LCOL[e.layer],
      lines:wrapName(other)});
  });
  return {W:W, H:H, cx:cx, cy:cy, R:R, hw:hw, hh:hh, spokes:spokes};
}
function wheelExtent(w){
  // The box the wheel actually occupies: the centre, plus every name label,
  // estimated at 6.6px per glyph. The viewBox is fitted to it so a component
  // with one spoke does not sit in a square of dead space.
  var x0 = w.cx - w.hw, y0 = w.cy - w.hh, x1 = w.cx + w.hw, y1 = w.cy + w.hh;
  w.spokes.forEach(function(s){
    var ex = w.cx + (w.R + 9) * s.ux, ey = w.cy + (w.R + 9) * s.uy;
    var n = s.lines.length, lw = 0;
    s.lines.forEach(function(l){ lw = Math.max(lw, l.length * 6.6); });
    var left, top;
    if(Math.abs(s.ux) < 0.35){
      left = ex - lw / 2; top = (s.uy < 0 ? ey - 4 - (n - 1) * 13 : ey + 12) - 10;
    } else {
      left = s.ux > 0 ? ex + 2 : ex - 2 - lw; top = ey + 4 - (n - 1) * 6.5 - 10;
    }
    x0 = Math.min(x0, left); y0 = Math.min(y0, top);
    x1 = Math.max(x1, left + lw); y1 = Math.max(y1, top + n * 13);
  });
  var pad = 8;
  if(!w.spokes.length){ x0 = w.cx - 100; x1 = w.cx + 100; y0 = w.cy - 44; }
  return {x:x0 - pad, y:y0 - pad, w:x1 - x0 + 2 * pad, h:y1 - y0 + 2 * pad};
}
function wheelSvg(cid){
  var w = wheelLayout(cid);
  var box = wheelExtent(w);
  var h = '<svg viewBox="' + box.x.toFixed(1) + ' ' + box.y.toFixed(1) + ' ' + box.w.toFixed(1)
        + ' ' + box.h.toFixed(1) + '" style="max-width:' + box.w.toFixed(0) + 'px" role="img" '
        + 'aria-label="relationship wheel of ' + esc(cid) + '">';
  h += '<defs>';
  LAYERS.forEach(function(l){
    h += '<marker id="wm-' + esc(l.id) + '" viewBox="0 0 8 8" refX="7" refY="4" '
       + 'markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" '
       + 'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="' + l.colour
       + '"/></marker>';
  });
  h += '</defs>';
  if(!w.spokes.length){
    h += '<text class="systemap-w__empty" x="' + w.cx + '" y="' + (w.cy - 30) + '">'
       + 'no flow touches this yet</text>';
  }
  w.spokes.forEach(function(s){
    var x0 = w.cx + s.r0 * s.ux, y0 = w.cy + s.r0 * s.uy;
    var x1 = w.cx + w.R * s.ux, y1 = w.cy + w.R * s.uy;
    var rm = (s.r0 + w.R) / 2, mx = w.cx + rm * s.ux, my = w.cy + rm * s.uy;
    var rot = s.ux < 0 ? s.deg + 180 : s.deg;
    var marker = (s.out ? ' marker-end' : ' marker-start') + '="url(#wm-' + esc(s.e.layer) + ')"';
    var ends = ' x1="' + x0.toFixed(1) + '" y1="' + y0.toFixed(1) + '" x2="' + x1.toFixed(1)
             + '" y2="' + y1.toFixed(1) + '"';
    h += '<g class="systemap-w__spoke" data-edge="' + s.i + '" data-go="' + esc(s.other)
       + '" tabindex="0" role="button" aria-label="'
       + esc(cid + ' ' + s.verb + ' ' + s.other) + '">';
    h += '<line class="systemap-w__hit"' + ends + '/>';
    // A declared edge is dashed on the wheel as it is on the map.
    var dash = s.e.evidence === 'declared' ? ' stroke-dasharray="6 4"' : '';
    h += '<line class="systemap-w__line"' + ends + ' stroke="' + s.colour + '"' + marker + dash
       + '/>';
    h += '<text class="systemap-w__verb" x="' + mx.toFixed(1) + '" y="' + (my + 4).toFixed(1)
       + '" fill="' + s.colour + '" transform="rotate(' + rot.toFixed(1) + ' ' + mx.toFixed(1)
       + ' ' + my.toFixed(1) + ')">' + esc(s.verb) + '</text>';
    var ex = w.cx + (w.R + 9) * s.ux, ey = w.cy + (w.R + 9) * s.uy;
    var n = s.lines.length, anchor, lx, first;
    if(Math.abs(s.ux) < 0.35){
      anchor = 'middle'; lx = ex;
      first = s.uy < 0 ? ey - 4 - (n - 1) * 13 : ey + 12;
    } else {
      anchor = s.ux > 0 ? 'start' : 'end'; lx = ex + (s.ux > 0 ? 2 : -2);
      first = ey + 4 - (n - 1) * 6.5;
    }
    h += '<text class="systemap-w__name" text-anchor="' + anchor + '">';
    s.lines.forEach(function(line, k){
      h += '<tspan x="' + lx.toFixed(1) + '" y="' + (first + k * 13).toFixed(1) + '">'
         + esc(line) + '</tspan>';
    });
    h += '</text></g>';
  });
  h += '<g class="systemap-w__centre"><rect x="' + (w.cx - w.hw) + '" y="' + (w.cy - w.hh)
     + '" width="' + (2 * w.hw) + '" height="' + (2 * w.hh) + '" rx="5"/>';
  h += '<text x="' + w.cx + '" y="' + (w.cy + 4) + '">' + esc(cid) + '</text></g>';
  h += '</svg>';
  return h;
}

// ---- the panel -----------------------------------------------------------
var SAY_HINT = 'Hover or tap a spoke, or a neighbour on the map, to read what the relationship is.';
function describe(d){
  var h = '<div class="systemap-f">';
  h += '<h3 class="systemap-f__plain">' + esc(d.plain || d.id) + '</h3>';
  h += '<div class="systemap-f__code">' + esc(d.id) + '<span class="systemap-f__kind">'
     + esc(d.kind) + (d.calls_model ? ', calls a model' : '')
     + (d.region ? ' in ' + esc(d.region) : '') + '</span></div>';
  h += '<p class="systemap-f__does">' + esc(d.does) + '</p>';
  // The one-line signature and the caveat, when the card has them.
  if(d.interface){ h += '<p class="systemap-f__iface">' + esc(d.interface) + '</p>'; }
  if(d.note){ h += '<p class="systemap-f__note">' + esc(d.note) + '</p>'; }
  h += '<div class="systemap-f__wheel">' + wheelSvg(d.id) + '</div>';
  var say = (d.edges && d.edges.length) ? SAY_HINT : 'Nothing flows to or from this yet.';
  h += '<p class="systemap-f__say muted" data-say>' + esc(say) + '</p>';
  // What the facts say about the peeked edge: observed, external or declared.
  h += '<p class="systemap-f__evidence" data-evidence></p>';
  h += '<div class="systemap-f__chips">';
  h += '<span class="systemap-chip systemap-chip--' + esc(d.state) + '">' + esc(d.state_label)
     + '</span>';
  (d.rules || []).forEach(function(n){
    h += '<span class="systemap-chip systemap-chip--rule" title="' + esc(RULES[n] || '')
       + '" tabindex="0">' + n + '</span>';
  });
  h += '</div>';
  if(d.lives){ h += '<p class="systemap-f__lives">lives in <b>' + esc(d.lives) + '</b></p>'; }
  // The entry the card names, with the module that defines it; a store or
  // a context card may have none, and then it is a namespace.
  if(d.kind !== 'actor'){
    var entry = d.entry
      ? esc(d.entry) + (d.entry_module ? ' (' + esc(d.entry_module) + ')' : '')
      : 'none (a namespace)';
    h += '<p class="systemap-f__entry">entry: <b>' + entry + '</b></p>';
  }
  // The map inside the card, when it opens one: its name and how many
  // cards it holds; on a page, its preview (drawn at render time, inert:
  // a picture, not a second map to click) and the button that opens it in
  // place. A figure has no page to open and names the map alone.
  if(d.map){
    h += '<p class="systemap-f__opens">opens: <b>' + esc(d.map.name)
       + (d.map.cards ? ' (' + d.map.cards + ' card' + (d.map.cards === 1 ? '' : 's') + ')' : '')
       + '</b></p>';
    if(d.map.href){
      if(d.map.preview){
        h += '<div class="systemap-f__preview" inert>' + d.map.preview + '</div>';
      }
      h += '<button type="button" class="systemap-f__open" data-open-map="' + esc(d.id)
         + '">Open the map inside</button>';
    }
  }
  h += '</div>';
  return h;
}
function peek(i, sticky){
  state.peek = i;
  var e = EDGES[i];
  if(panel){
    var say = panel.querySelector('[data-say]');
    if(say && e){
      say.textContent = e.say || (e.from + ' -> ' + e.to + ': ' + e.art);
      say.classList.remove('muted');
    }
    var ev = panel.querySelector('[data-evidence]');
    if(ev && e){
      ev.textContent = e.evidence_says || '';
      ev.classList.toggle('declared', e.evidence === 'declared');
    }
    Array.prototype.slice.call(panel.querySelectorAll('.systemap-w__spoke')).forEach(function(s){
      s.classList.toggle('peek', +s.dataset.edge === i); });
  }
  flows.forEach(function(p){ p.classList.toggle('peek', +p.dataset.edge === i); });
  if(labelOf[i]){ labelOf[i].classList.add('peek'); }
}
function unpeek(){
  if(state.peek < 0){ return; }
  state.peek = -1;
  flows.forEach(function(p){ p.classList.remove('peek'); });
  labels.forEach(function(l){ l.classList.remove('peek'); });
  if(panel){
    Array.prototype.slice.call(panel.querySelectorAll('.systemap-w__spoke.peek')).forEach(
      function(s){ s.classList.remove('peek'); });
  }
}
function edgeBetween(a, b){
  var i = EDGE_AT[a + '>' + b];
  if(i === undefined){ i = EDGE_AT[b + '>' + a]; }
  return i === undefined ? -1 : i;
}
function opensPage(cid){
  // A card that opens a map with a page to show: the page answers the event.
  var d = DETAIL[cid];
  return !!(d && d.map && d.map.href);
}
function openMap(cid){
  if(!opensPage(cid)){ return; }
  var m = DETAIL[cid].map;
  svg.dispatchEvent(new CustomEvent('systemap:open',
    {detail:{id:cid, name:m.name, href:m.href, cards:m.cards}, bubbles:true}));
}
function select(cid){
  var d = DETAIL[cid];
  if(!d){ return; }
  state.focus = cid; state.journey = null; state.peek = -1;
  paint();
  frameFocus(null, !booted);
  if(panel){
    panel.innerHTML = describe(d);
    panel.classList.add('on');
    var open = panel.querySelector('[data-open-map]');
    if(open){ open.addEventListener('click', function(){ openMap(cid); }); }
    Array.prototype.slice.call(panel.querySelectorAll('.systemap-w__spoke')).forEach(function(s){
      var i = +s.dataset.edge;
      s.addEventListener('mouseenter', function(){ peek(i); });
      s.addEventListener('focus', function(){ peek(i); });
      // A hover peeks first, so a mouse click navigates at once; on touch
      // the first tap peeks (the sentence appears) and the second navigates.
      s.addEventListener('click', function(ev){
        ev.preventDefault();
        if(state.peek === i){ select(s.dataset.go); } else { peek(i); }
      });
      s.addEventListener('keydown', function(ev){
        if(ev.key === 'Enter' || ev.key === ' '){ ev.preventDefault(); select(s.dataset.go); }
      });
    });
  }
  svg.dispatchEvent(new CustomEvent('systemap:select', {detail:{id:cid}, bubbles:true}));
}
function clearAll(){
  state.focus = ''; state.journey = null; state.peek = -1;
  paint();
  if(panel){ panel.innerHTML = ''; panel.classList.remove('on'); }
  svg.dispatchEvent(new CustomEvent('systemap:clear', {bubbles:true}));
}
nodes.forEach(function(n){
  n.addEventListener('click', function(e){ e.stopPropagation(); select(n.dataset.id); });
  // A double-click on a card that opens a map, or Enter on it a second
  // time while it is the selection, opens the map inside it.
  n.addEventListener('dblclick', function(e){
    if(opensPage(n.dataset.id)){ e.preventDefault(); openMap(n.dataset.id); }
  });
  n.addEventListener('keydown', function(e){
    if(e.key === 'Enter' && state.focus === n.dataset.id && opensPage(n.dataset.id)){
      e.preventDefault(); openMap(n.dataset.id); return;
    }
    if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); select(n.dataset.id); }
  });
  n.addEventListener('mouseenter', function(){
    if(!state.focus || n.dataset.id === state.focus){ return; }
    var i = edgeBetween(state.focus, n.dataset.id);
    if(i >= 0){ peek(i); }
  });
  n.addEventListener('mouseleave', function(){ if(state.focus){ unpeek(); } });
});
svg.addEventListener('click', function(e){ if(!e.target.closest('.node')){ clearAll(); } });
svg.systemap = {
  select: select,
  clear: clearAll,
  peek: peek,
  state: state,
  setLayer: function(id){ state.layer = id; paint(); },
  layerIds: layerIds,
  setJourney: function(step){
    // step: {acts:[], measures:[], edge:index, say:''} or null.
    state.focus = '';
    state.journey = step;
    paint();
    if(step){ frameJourney(step, !booted); }
    if(panel && step){ panel.innerHTML = ''; panel.classList.remove('on'); }
  },
  view: {
    fit: function(){ userView({k:1, tx:0, ty:0}); },
    actual: function(){ var c = centre(); zoomAt(1 / (base() * goal.k), c.x, c.y); },
    zoomBy: function(f){ var c = centre(); zoomAt(f, c.x, c.y); },
    zoom: function(){ return base() * goal.k; },
    isFit: function(){ return isFit(); },
    frameFocus: frameFocus,
    frameRegion: frameRegion,
    frame: function(){ return lastFrame; },
    visibleArea: visibleArea,
    fracOf: fracOf,
    back: back
  },
  edges: EDGES,
  layers: LAYERS,
  journeys: META.journeys || [],
  detail: DETAIL
};
svg.systemapSelect = select;
svg.systemapClear = clearAll;
function openHash(){
  var id = decodeURIComponent((location.hash || '').slice(1));
  if(id && DETAIL[id] && id !== state.focus){ select(id); }
}
window.addEventListener('hashchange', openHash);
openHash();
booted = true;
"""
