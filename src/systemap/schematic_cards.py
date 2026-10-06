"""Card text limits, diagram legends and layout geometry."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from math import ceil
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
# Recorded diagnostic lines keep this value.
PLAIN_CHARS = 26
PLAIN_WIDTH = CARD_W - 20
# ArialMT and Liberation Sans 2.1.5 give these character widths for ASCII 32 through 126.
# Each value uses 2048 font units.
# The CSS requires font-kerning:none and font-variant-ligatures:none.
PLAIN_ADVANCES = (
    569,
    569,
    727,
    1139,
    1139,
    1821,
    1366,
    391,
    682,
    682,
    797,
    1196,
    569,
    682,
    569,
    569,
    1139,
    1139,
    1139,
    1139,
    1139,
    1139,
    1139,
    1139,
    1139,
    1139,
    569,
    569,
    1196,
    1196,
    1196,
    1139,
    2079,
    1366,
    1366,
    1479,
    1479,
    1366,
    1251,
    1593,
    1479,
    569,
    1024,
    1366,
    1139,
    1706,
    1479,
    1593,
    1366,
    1593,
    1479,
    1366,
    1251,
    1479,
    1366,
    1933,
    1366,
    1366,
    1251,
    569,
    569,
    569,
    961,
    1139,
    682,
    1139,
    1139,
    1024,
    1139,
    1139,
    569,
    1139,
    1139,
    455,
    455,
    1024,
    455,
    1706,
    1139,
    1139,
    1139,
    1139,
    682,
    1024,
    569,
    1139,
    1024,
    1479,
    1024,
    1024,
    1024,
    684,
    532,
    684,
    1196,
)
# These values include the maximum extension to the right of each character.
PLAIN_OVERHANG = {"A": 3, "_": 23, "f": 71, "k": 3, "r": 28, "w": 5}
PLAIN_LEFT_OVERHANG = {"A": 3, "_": 31, "j": 94, "w": 3}

Box = tuple[float, float, float, float]


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def wrap_all(text: str, width: int) -> list[str]:
    """Put words on lines up to `width` characters. Keep a longer word on a separate line."""
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


def plain_inset(text: str) -> float:
    """Give the measured origin correction, rounded upward to the SVG coordinate precision."""
    return ceil(PLAIN_LEFT_OVERHANG.get(text[:1], 0) * TEXT_PX / 2048 * 10) / 10


def plain_width(text: str) -> float:
    """Give the measured description width, or infinity for a character with no measurement."""
    advance = 0
    for char in text:
        code = ord(char) - 32
        if not 0 <= code < len(PLAIN_ADVANCES):
            return float("inf")
        advance += PLAIN_ADVANCES[code]
    return (advance + PLAIN_OVERHANG.get(text[-1:], 0)) * TEXT_PX / 2048 + plain_inset(text)


def wrap_plain(text: str, width: float) -> list[str]:
    """Put complete words on lines that do not exceed the measured description width."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if plain_width(candidate) <= width or not current:
            current = candidate
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def _fitted_plain_lines(lines: list[str]) -> list[str]:
    """Keep only description lines that do not exceed the card width."""
    return [line for line in lines if plain_width(line) <= PLAIN_WIDTH]


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
    """Separate CamelCase or snake_case identifiers at word boundaries.

    Keep a name section longer than `width` on a separate line. The caller
    gives a finding for this condition."""
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


def _card_description(
    kind: str, cid: str, plain: str, name_line_count: int
) -> tuple[list[str], list[str]]:
    """Give description lines and diagnostics for measured widths or missing measurements."""
    problems = [
        f"card {cid}: description width is not measured for character {char!r}"
        for char in dict.fromkeys(plain)
        if not (32 <= ord(char) < 32 + len(PLAIN_ADVANCES) or char in "\t\n\r")
    ]
    if problems:
        return [], problems
    ruled = kind in ("store", "context")
    first = (36 if ruled else 32) + NAME_LINE_H * (name_line_count - 1)
    lines = max(1, int((CARD_H[kind] - 4 - first) // 12) + 1)
    plain_lines = wrap_plain(plain, PLAIN_WIDTH)
    if len(plain_lines) > lines or any(plain_width(line) > PLAIN_WIDTH for line in plain_lines):
        words = {1: "one line", 2: "two lines"}.get(lines, f"{lines} lines")
        under = " under a two-line name" if name_line_count > 1 else ""
        problems.append(
            f"card {cid}: plain word does not fit ({kind} cards fit about {PLAIN_CHARS} "
            f"characters on {words}{under}; this one has {len(plain)})"
        )
        plain_lines = _fitted_plain_lines(plain_lines[:lines])
    return plain_lines, problems


def card_text(kind: str, cid: str, plain: str) -> tuple[list[str], list[str], list[str]]:
    """Give the name lines, plain text lines and diagnostics for one card.

    Description lines use measured font widths. Recorded diagnostic lines keep their identifiers.
    The diagram uses only the lines that fit. The map check rejects dimension errors."""
    problems: list[str] = []
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
    plain_lines, description_problems = _card_description(kind, cid, plain, len(name_lines))
    problems.extend(description_problems)
    return name_lines, plain_lines, problems


def _file_of(claim: str) -> str:
    """Give the file for a module claim. Add the symbol name after a colon for a symbol claim."""
    module, _, name = claim.partition(":")
    path = module.replace(".", "/") + ".py"
    return f"{path}:{name}" if name else path


def lives_in(modules: list[str]) -> str:
    """Give source paths or a common package path for a component.

    For three or fewer claims, give the files and symbol names. For more
    claims, give the common directory and module count."""
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
    """Give legend fill, stroke and label values for the specified mode.

    With `variables`, colors use CSS tokens. Figures use literal colors."""
    P = Palette(t, variables)
    if mode == "change":
        ghost_fill, ghost_stroke = P.ghost()
        rows = [
            (P.changed_fill(), P["change"], "changed source"),
            (P.reach_fill(), P["reach"], "import connection"),
            (ghost_fill, ghost_stroke, "unchanged source"),
        ]
        for key, label in (
            ("operations", "new operations"),
            ("types", "new types"),
            ("refusals", "new exceptions"),
            ("tests", "new tests"),
        ):
            rows.append((P.delta(key), P.delta(key), label))
        return rows
    return [P.state(name) for name in t["state"]]


def layer_rows(
    t: dict[str, Any], model: Model, meaning: Meaning, variables: bool = False
) -> list[tuple[str, str, str]]:
    """Give each layer identifier, color and label in layer order.

    The Structure layer has no flow lines and has no legend entry."""
    P = Palette(t, variables)
    return [
        (layer.id, P.layer(layer.id), layer.label)
        for layer in all_layers(model, meaning)
        if layer.id != "structure"
    ]


def kind_rows(t: dict[str, Any], model: Model) -> list[tuple[str, str]]:
    """Give each agent card kind and its mark, in kind order."""
    present = {c.kind for c in model.components}
    marks: dict[str, str] = t.get("marks") or {}
    return [(kind, marks[kind]) for kind in AGENT_KINDS if kind in present and kind in marks]


@dataclass(frozen=True)
class Geometry:
    """Model geometry for the router and label placement.

    `boxes` contains card bounds. `blocks` contains headers and containers
    with no cards or regions. Flow paths cannot cross these blocks.
    `obstacles` contains named headers, empty containers and cards with
    3 SVG user units of clearance. Labels cannot have an overlap with these obstacles.

    `headers` contains header bounds. `collisions` contains header size
    errors. `systemap place` uses this same geometry to measure layouts."""

    boxes: dict[str, Box]
    actors: set[str]
    blocks: list[Box]
    obstacles: list[tuple[str, Box]]
    headers: list[dict[str, Any]]
    collisions: list[str]
    region_boxes: dict[str, Box]
    region_of: dict[str, str]


def container_header(box: Container) -> tuple[Box, list[str], list[str]]:
    """Give the container header bounds, subtitle lines and size errors.

    The obstacle contains the header text, not the full container width.
    This leaves space for flow paths. A subtitle can have two lines.
    Text that exceeds its bounds gives a size error."""
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
    """Give region header bounds and errors for labels that exceed those bounds."""
    x, y, w, _h = region.box
    label_w = 31 - 6 + len(region.label) * LABEL_CHAR + 8
    collisions: list[str] = []
    if 31 + len(region.label) * LABEL_CHAR + 8 > w:
        collisions.append(f"header of region {region.id}: label is wider than its box")
    return (x + 6, y + 5, max(150.0, label_w), 24), collisions


def geometry(model: Model) -> Geometry:
    """Give model geometry for flow routing and label placement."""
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
