"""Card text budgets and legends shared by the scene and its checks."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

from systemap.model import AGENT_KINDS, CARD_H, Container, Meaning, Model, Region, all_layers
from systemap.theme import Palette

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


def legend_rows(
    t: dict[str, Any], mode: str, variables: bool = False
) -> list[tuple[str, str, str]]:
    """(fill, stroke, label) for the legend the given mode needs.

    `variables` writes each colour as `var(--token)`, for the page; a
    figure takes the literals.
    """
    P = Palette(t, variables)
    if mode == "change":
        ghost_fill, ghost_stroke = P.ghost()
        rows = [
            (P.changed_fill(), P["change"], "changed here"),
            (P.reach_fill(), P["reach"], "reached by it"),
            (ghost_fill, ghost_stroke, "untouched"),
        ]
        for key, label in (
            ("operations", "new operations"),
            ("types", "new types"),
            ("refusals", "new refusals"),
            ("tests", "new tests"),
        ):
            rows.append((P.delta(key), P.delta(key), label))
        return rows
    return [P.state(name) for name in t["state"]]


def layer_rows(
    t: dict[str, Any], model: Model, meaning: Meaning, variables: bool = False
) -> list[tuple[str, str, str]]:
    """(id, colour, label) for every layer that draws a line, in layer order.

    Structure draws no edges, so its colour would be a swatch of nothing;
    it is left out of the legend.
    """
    P = Palette(t, variables)
    return [
        (layer.id, P.layer(layer.id), layer.label)
        for layer in all_layers(model, meaning)
        if layer.id != "structure"
    ]


def kind_rows(t: dict[str, Any], model: Model) -> list[tuple[str, str]]:
    """(kind, mark) for every agent kind the model draws, in kind order."""
    present = {c.kind for c in model.components}
    marks: dict[str, str] = t.get("marks") or {}
    return [(kind, marks[kind]) for kind in AGENT_KINDS if kind in present and kind in marks]


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
