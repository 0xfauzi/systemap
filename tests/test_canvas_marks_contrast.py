"""The contrast of the texts and the lines of the canvas page, in the two schemes.

Step 8 of docs/design/nested-parts.md had a table of the marks of a nested map
(`schematic_nested.MARK_COLOURS` on origin/claude/nested-step-8). The canvas page draws on
a `<canvas>` element, and axe-core cannot measure the contrast of its pixels. Thus this
test examines the theme tokens that the renderer gives to each text and line, on the
ground under it. The ratio comes from the tokens, not from the rendered pixels.

Acceptance values, written before the first run on 2026-11-08:

1. Each row of `CANVAS_MARKS` (what, token, ground, floor) has a ratio of the floor or
   more in the light and the dark scheme: 4.5 for a text and 3.0 for a line. A row names
   the renderer code that uses the token, and that code has the token.
2. The back card of a card that opens a map is in --line-2 (1.36 on the map in the light
   scheme and 1.50 in the dark scheme). Its outline is in --card-line, and that outline is
   a row of the table.
3. `BELOW_FLOOR` gives each line that the renderer draws below its floor and that is not
   in the table. Each one is a decision for the maintainer. The test asserts that each one
   is below its floor in a scheme, thus a fix removes it from the list.
"""

from __future__ import annotations

import pytest
from test_theme import contrast

from systemap import (
    page_canvas,
    page_canvas_changes,
    page_canvas_draw,
    page_canvas_ports,
    page_canvas_sequences,
    page_canvas_text,
    page_canvas_touch,
)
from systemap import theme as theme_mod
from systemap.model import Layer

TEXT, LINE = 4.5, 3.0
# The script text of each part, by the name that a row gives.
PARTS = {
    "draw": page_canvas_draw.DRAW,
    "text": page_canvas_text.TEXT,
    "touch": page_canvas_touch.TOUCH_PART,
    "changes": page_canvas_changes.PART,
    "sequences": page_canvas_sequences.SEQ_PART,
    "ports": page_canvas_ports.PORTS,
}

# (what, token, ground, floor, part, the code of the part that gives the token).
CANVAS_MARKS: tuple[tuple[str, str, str, float, str, str], ...] = (
    # Texts on a card.
    ("card name", "ink", "card", TEXT, "text", "C['--ink'], alpha, 600"),
    ("card text", "ink_2", "card", TEXT, "text", "lh, C['--ink-2'], alpha"),
    ("does text and fact row", "ink_3", "card", TEXT, "text", "small, C['--ink-3'], alpha * fact"),
    ("list item", "ink_2", "card", TEXT, "text", "fs, C['--ink-2'], 400, mono"),
    (
        "count of cards in an open map",
        "ink_3",
        "map",
        TEXT,
        "text",
        "small, C['--ink-3'], alpha * extra.alpha",
    ),
    # Texts on the map.
    ("box name", "ink_3", "map", TEXT, "draw", "b.b[1] + 19), C['--ink-3']"),
    ("region name", "ink_2", "map", TEXT, "draw", "b.b[1] + 20), C['--ink-2']"),
    ("flow label", "ink_2", "map", TEXT, "draw", "fs, C['--ink-2'], alpha * flowShown(f)"),
    # Texts on a plate.
    ("portal name", "ink", "raised", TEXT, "draw", "12, C['--ink'], t.show"),
    ("portal map", "ink_3", "raised", TEXT, "draw", "10.5, C['--ink-3'], t.show"),
    ("path part", "ink", "raised", TEXT, "draw", "last ? C['--raised'] : C['--ink']"),
    (
        "last path part",
        "raised",
        "ink",
        TEXT,
        "draw",
        "C['--ink']; ctx.beginPath(); rr(ctx, x, y + 2",
    ),
    ("path level and help line", "ink_3", "raised", TEXT, "draw", "HELP_FS, C['--ink-3'], 1"),
    ("selection plate facts", "ink_3", "raised", TEXT, "touch", "11, C['--ink-3'], e.a"),
    # The tags of the views.
    ("tag CHANGED", "on_change", "change", TEXT, "changes", "c: '--change', t: '--on-change'"),
    ("tag TESTS", "change", "map", TEXT, "changes", "c: '--map', t: '--change'"),
    ("tag IMPORTS", "ink_2", "map", TEXT, "changes", "c: '--map', t: '--ink-2'"),
    ("note changed inside", "ink_2", "raised", TEXT, "changes", "c: '--raised', t: '--ink-2'"),
    ("tag START and MEASURES", "map", "ink_2", TEXT, "sequences", "c: '--ink-2'}"),
    ("tag ACTS", "map", "accent", TEXT, "sequences", "c: '--accent'}"),
    ("tag of an open port", "ink_2", "raised", TEXT, "ports", "c: '--raised', t: '--ink-2'"),
    # Lines.
    ("card border", "card_line", "map", LINE, "draw", "LINE.rect(k.line"),
    (
        "outline of the back card",
        "card_line",
        "map",
        LINE,
        "draw",
        "BACK_LINE.rect(C['--card-line']",
    ),
    ("frame of an open card", "ink_3", "map", LINE, "draw", "o > 0.5 ? C['--ink-3'] : k.line"),
    (
        "portal outline",
        "ink_3",
        "map",
        LINE,
        "draw",
        "C['--raised']; ctx.strokeStyle = C['--ink-3']",
    ),
    ("flow line and boundary flow", "flow", "map", LINE, "draw", "flowColor(f, null)"),
    ("ring of a change", "change", "map", LINE, "changes", "c: '--change', w: 2"),
    ("ring of an open port", "ink_2", "map", LINE, "ports", "PORT_RING = {c: '--ink-2'"),
    ("ring of the selection", "accent", "map", LINE, "touch", "C['--accent']; ctx.lineWidth = 2.5"),
)

# Lines below their floor that are not in the table. Each one needs a decision of the
# maintainer. The linked page uses the same tokens for these lines.
BELOW_FLOOR: tuple[tuple[str, str, str, float, str, str], ...] = (
    # The border of a container, for the tones host, client and server (`--box-*-line`).
    ("container border", "line_2", "map", LINE, "draw", "C['--box-' + b.t + '-line']"),
)


def _schemes() -> dict[str, dict[str, str]]:
    t = theme_mod.resolve({}, [Layer("data", "Data flow")])
    return dict(t["schemes"])


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("row", CANVAS_MARKS, ids=[row[0] for row in CANVAS_MARKS])
def test_each_mark_of_the_canvas_clears_its_contrast_floor(
    scheme: str, row: tuple[str, str, str, float, str, str]
) -> None:
    """Acceptance 1."""
    what, token, ground, floor, part, code = row
    table = _schemes()[scheme]
    ratio = contrast(table[token], table[ground])
    assert ratio >= floor, (what, scheme, round(ratio, 2))
    assert code in PARTS[part] or code in page_canvas.SCRIPT, (what, part, code)


def test_the_back_card_has_an_outline_that_clears_the_line_floor() -> None:
    """Acceptance 2."""
    for scheme, table in _schemes().items():
        assert contrast(table["line_2"], table["map"]) < LINE, scheme
        assert contrast(table["card_line"], table["map"]) >= LINE, scheme
    assert "BACK.rect(C['--line-2']" in page_canvas_draw.DRAW
    assert "BACK_LINE.rect(C['--card-line']" in page_canvas_draw.DRAW
    assert "g.strokeStyle = C['--card-line']; g.lineWidth = 1;" in page_canvas_draw.DRAW


def test_each_line_below_its_floor_is_a_recorded_decision() -> None:
    """Acceptance 3."""
    tables = _schemes()
    for what, token, ground, floor, part, code in BELOW_FLOOR:
        ratios = [contrast(t[token], t[ground]) for t in tables.values()]
        assert min(ratios) < floor, what
        assert code in PARTS[part], what
    for name, table in tables.items():
        for tone, (stroke, _fill) in table["container"].items():
            if contrast(stroke, table["map"]) < LINE:
                assert stroke == table["line_2"], (name, tone)
