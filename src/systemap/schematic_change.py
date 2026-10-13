"""Change map marks: card borders, tags and flows for a comparison or a plan.

A comparison marks each card by what the comparison found: changed source
(a 2 px ring and a filled CHANGED tag), only changed tests (an outlined TESTS
tag), or an import of changed source (a dashed border and an IMPORTS tag). A
plan figure marks the cards in the plan (IN REACH). The other ends of marked
flows fade to 60 percent and all other cards to 32 percent. A comparison draws
only the flows of a card with changed source that have no source review, in the
change color with their evidence dash. The other flows stay in the figure,
hidden, so that a selection can show them in the neutral flow color. The page
script animates these marks through `data-change` and the `chg-tag` groups."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, NamedTuple

from systemap import evidence
from systemap.model import Model
from systemap.schematic_cards import RADIUS, TEXT_PX
from systemap.theme import Palette

CHANGE_WORDS = {
    "changed": ("CHANGED", "changed source"),
    "tests": ("TESTS", "only tests changed"),
    "imports": ("IMPORTS", "imports changed source"),
    "plan": ("IN REACH", "in the plan"),
}
# mark: (change ring, ring width, border dash, opacity)
CHANGE_CARDS = {
    "changed": (True, "2", "", ""),
    "plan": (True, "2", "", ""),
    "tests": (True, "1.2", "", ""),
    "imports": (True, "1.2", ' stroke-dasharray="4 3"', ""),
    "end": (False, "1.1", "", ".6"),
    "none": (False, "1.1", "", ".32"),
}
TAG_H = 18.0
TAG_CHAR_W = 7.3


class ChangeMarks(NamedTuple):
    """The change map marks: a mark for each card and the marked flows."""

    cards: dict[str, str]
    lost: frozenset[int]
    comparison: bool


class Look(NamedTuple):
    """The border, attributes and accessible label of one card."""

    stroke: str
    width: str
    dashes: str
    attrs: str
    label: str


class FlowLook(NamedTuple):
    """The stroke, arrowhead and attributes of one flow, and its label color."""

    stroke: str
    width: str
    marker: str
    attrs: str
    label: str
    shown: str


def tests_only(ch: Mapping[str, Any]) -> set[str]:
    """Give the changed components with changed tests and no changed source module."""
    out = set()
    for cid, record in dict(ch.get("per_component") or ch.get("parts") or {}).items():
        surface = record.get("surface", {})
        if not record.get("modules") and (
            surface.get("tests_added") or surface.get("tests_removed")
        ):
            out.add(cid)
    return out


def change_marks(
    model: Model,
    backed: Mapping[Any, evidence.Evidence],
    mode: str,
    changed: set[str],
    adjacent: set[str],
    tests_only: set[str] | None,
    changed_modules: set[str],
) -> ChangeMarks:
    """Give the change marks. A comparison has changed modules or a test set."""
    if mode != "change":
        return ChangeMarks({}, frozenset(), False)
    comparison = tests_only is not None or bool(changed_modules)
    source = changed - (tests_only or set()) if comparison else set()
    lost = frozenset(
        i
        for i, f in enumerate(model.flows)
        if {f.src, f.dst} & source
        and backed[evidence.slot(f)].state in (evidence.STRUCTURAL, evidence.DECLARED)
    )
    ends = {end for i in lost for end in model.flows[i].edge}
    cards = {
        c.id: _card_mark(c.id, comparison, changed, tests_only, adjacent, ends)
        for c in model.components
    }
    return ChangeMarks(cards, lost, comparison)


def _card_mark(
    cid: str,
    comparison: bool,
    changed: set[str],
    tests_only: set[str] | None,
    adjacent: set[str],
    ends: set[str],
) -> str:
    if cid in changed and not comparison:
        return "plan"
    if cid in changed:
        return "tests" if cid in (tests_only or set()) else "changed"
    if cid in adjacent:
        return "imports"
    return "end" if cid in ends else "none"


def change_card(P: Palette, mark: str, stroke: str, dashes: str, label: str) -> Look:
    """Give the border of a card in the change map, or its usual border."""
    ring, width, dash, fade = CHANGE_CARDS.get(mark, (False, "1.1", "", ""))
    attrs = f' data-change="{mark}"' if mark else ""
    attrs += f' opacity="{fade}"' if fade else ""
    word = CHANGE_WORDS.get(mark, ("", label))[1]
    return Look(P["change"] if ring else stroke, width, dash or dashes, attrs, word)


def change_flow(
    P: Palette, marks: ChangeMarks, i: int, colour: str, marker: str, hot: bool
) -> FlowLook:
    """Give the stroke of a flow. A comparison hides unmarked flows until a selection.

    Every line is 1.6 px at each zoom, at full opacity, with its label in ink,
    as the design boards draw it. `shown` gives the attributes that the flow
    label also carries."""
    fixed = ' vector-effect="non-scaling-stroke"'
    if marks.comparison and i in marks.lost:
        lost = ' data-change="lost"'
        return FlowLook(P["change"], "1.6", "change", lost + fixed, P["ink"], lost)
    if marks.comparison:
        rest = ' data-change="rest" display="none"'
        return FlowLook(P["flow"], "1.6", "flow", rest + fixed, P["ink"], rest)
    if hot:
        return FlowLook(P["change"], "1.6", "change", fixed, P["ink"], "")
    return FlowLook(colour, "1.6", marker, fixed, P["ink"], "")


def _token(P: Palette, key: str, fallback: str) -> str:
    """Give a theme token, or a fallback token for a theme without it."""
    try:
        return str(P[key])
    except KeyError:
        return str(P[fallback])


def change_tag(
    P: Palette, L: Callable[..., str], mark: str, box: tuple[float, float, float, float]
) -> str:
    """Give the tag on the top right border of a marked card and its selection ring."""
    if mark not in ("changed", "plan", "tests", "imports"):
        return ""
    x, y, w, h = box
    word = CHANGE_WORDS[mark][0]
    tw = len(word) * TAG_CHAR_W + 12
    tx, ty = x + w - 6 - tw, y - TAG_H / 2
    filled = mark in ("changed", "plan")
    ground = _token(P, "map", "bg")
    fill, line, text = (
        (P["change"], "none", _token(P, "on_change", "bg"))
        if filled
        else (ground, P["change"], P["change"] if mark == "tests" else P["ink_2"])
    )
    dash = ' stroke-dasharray="3 2"' if mark == "imports" else ""
    return (
        f'<rect class="chg-halo" x="{x - 4}" y="{y - 4}" width="{w + 8}" height="{h + 8}" '
        f'rx="{RADIUS + 3}" fill="none" stroke="{P["accent"]}" stroke-width="2" display="none"/>'
        f'<g class="chg-tag" data-tag="{mark}" aria-hidden="true">'
        f'<rect x="{tx:.1f}" y="{ty:.1f}" width="{tw:.1f}" height="{TAG_H}" rx="3" '
        f'fill="{fill}" stroke="{line}" stroke-width="1"{dash}/>'
        + L(tx + tw / 2, ty + 12.6, word, TEXT_PX, text, "700", True, "middle", ".06em")
        + "</g>"
    )


def change_defs(svg_id: str, P: Palette, marks: ChangeMarks) -> str:
    """Give the arrowhead for the neutral flows of a comparison."""
    if not marks.comparison:
        return ""
    return (
        f'<defs><marker id="{svg_id}-m-flow" viewBox="0 0 8 8" refX="7" refY="4" '
        'markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" '
        f'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="{P["flow"]}"/></marker>'
        "</defs>"
    )


def change_meta(marks: ChangeMarks) -> dict[str, Any]:
    """Give the change marks for the detail JSON of a comparison."""
    if not marks.comparison:
        return {}
    return {"change": {"cards": marks.cards, "lost": sorted(marks.lost)}}
