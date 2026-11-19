"""The contrast of each text color and mark color of the atlas page, in the two schemes.

The map of the atlas page draws on a `<canvas>` element, and axe-core cannot measure the
contrast of its pixels. Thus this test examines the theme tokens of the atlas page
(`atlas_css.LIGHT` and `atlas_css.DARK`) that the renderer and the styles give to each text
and mark, on the ground under it. The ratio comes from the tokens, not from the rendered
pixels. axe-core measures the HTML parts in tests/test_atlas_parity_browser.py.

Acceptance values, written on 2026-11-19 before the first run:

1. Each row of `MARKS` (what, token, ground, floor, the code that gives the token) has a
   ratio of the floor or more in the light and the dark scheme: 4.5 for a text and 3.0 for
   a mark (a line, a ring, a dot, an arrowhead or the focus ring). The code of the row is in
   the script or in the styles of the atlas page.
2. `BELOW_FLOOR` gives each mark that the page draws below its floor. Each one is a decision
   for the maintainer: the design study gives these quiet marks at rest, and the specification
   says that the lines at rest are thin and neutral. The test asserts that each one is below
   its floor in a scheme, thus a change of the token removes it from the list. Each one has a
   text or a mark with a ratio of its floor or more for the same item (`ALSO`).

After the review of stage 8 (2026-11-19), with no change to a value: the review found marks
with no row, for example the focus rings of the views in --brand. The rings now use --focus,
and the test has a row for each of them. The halo of the selected card, the dot of a new module
and the bars of the History view are below their floor, thus they are in `BELOW_FLOOR`.
"""

from __future__ import annotations

import re

import pytest
from test_theme import contrast

from systemap import (
    atlas_css,
    atlas_details,
    atlas_find,
    atlas_focus,
    atlas_history,
    atlas_script,
    atlas_sequences,
    atlas_states,
    atlas_tools,
    atlas_tree,
)

TEXT, MARK = 4.5, 3.0

CODE = atlas_script.SCRIPT + "".join(
    (
        atlas_css.CSS,
        atlas_details.CSS,
        atlas_tree.CSS,
        atlas_sequences.CSS,
        atlas_sequences.BOARD_CSS,
        atlas_states.CSS,
        atlas_focus.CSS,
        atlas_history.CSS,
        atlas_tools.CSS,
        atlas_find.CSS,
    )
)

# (what, token, ground, floor, the code of the page that gives the token).
MARKS: tuple[tuple[str, str, str, float, str], ...] = (
    # Texts on the canvas.
    ("card name", "ink", "card", TEXT, "qv > 0.5 ? C['--ink-3'] : C['--ink']"),
    ("actor name", "ink", "map", TEXT, "qv > 0.5 ? C['--ink-3'] : C['--ink']"),
    ("quiet card name", "ink-3", "card", TEXT, "qv > 0.5 ? C['--ink-3'] : C['--ink']"),
    ("short name of a card", "ink-3", "card", TEXT, "C['--ink-3'], t * far"),
    ("kind tag of a card", "ink-3", "card", TEXT, "caps(c.k, x + w - 9 * u - thumb - kw"),
    ("name of a container", "ink-3", "surface", TEXT, "caps(b.n, x + 20 * a, y + 30 * a"),
    ("name of a region", "ink-3", "surface", TEXT, "caps(r.n, x + 31 * a"),
    ("label of a container of actors", "ink-3", "map", TEXT, "caps(b.n, ox + a * b._at[0]"),
    ("label at rest", "ink-2", "map", TEXT, "text(s.e.s, x, y, fs, C['--ink-2']"),
    ("lit label", "ink", "map", TEXT, "text(s.e.s, x, y, fs, C['--ink'], alpha * DIM"),
    ("tag of an open boundary line", "ink-2", "map", TEXT, "k.port ? C['--ink-2'] : C['--change']"),
    ("tag of a change", "change", "map", TEXT, "k.port ? C['--ink-2'] : C['--change']"),
    # Marks on the canvas.
    ("dot and arrowhead at rest", "ink-3", "map", MARK, "g.fillStyle = C['--ink-3'];"),
    ("outline of an actor", "ink-3", "map", MARK, "actor && !qv ? C['--ink-3']"),
    ("outline of a lit card", "ink", "card", MARK, "ink ? C['--ink']"),
    ("line of an earlier step", "ink-2", "map", MARK, "st === 'was' ? C['--ink-2'] : C['--wire']"),
    ("lit line of a data flow", "data", "map", MARK, "data: '--data'"),
    ("lit line of a control flow", "control", "map", MARK, "control: '--control'"),
    ("lit line of a review flow", "judge", "map", MARK, "judge: '--judge'"),
    ("lit line of a context flow", "context", "map", MARK, "context: '--context'"),
    ("lit line of a tool flow", "tool", "map", MARK, "tool: '--tool'"),
    ("ring of an open boundary line", "ink-2", "map", MARK, "PORT_RING = {c: '--ink-2'"),
    ("ring of a change", "change", "map", MARK, "changed: {c: '--change', w: 2"),
    ("lost flow of a change", "change", "map", MARK, "ctx.strokeStyle = C['--change']"),
    ("focus ring", "focus", "map", MARK, ":focus-visible{outline:2px solid var(--focus)"),
    (
        "focus ring in the header",
        "focus",
        "surface",
        MARK,
        ":focus-visible{outline:2px solid var(--focus)",
    ),
    ("focus ring of the canvas", "focus", "map", MARK, "inset 0 0 0 2px var(--focus)"),
    (
        "focus ring of a card on the canvas",
        "ink",
        "map",
        MARK,
        "ctx.strokeStyle = C['--ink']; ctx.lineWidth = RING_W;",
    ),
    (
        "focus ring of a line on the canvas",
        "focus",
        "map",
        MARK,
        "ctx.strokeStyle = C['--focus']; ctx.lineWidth = 2;",
    ),
    (
        "outline of the selected card",
        "ink",
        "card",
        MARK,
        "ctx.strokeStyle = C['--ink']; ctx.lineWidth = 1.5;",
    ),
    (
        "focus ring of a link of the map tree",
        "focus",
        "map",
        MARK,
        "outline:2px solid var(--focus);outline-offset:2px;text-decoration:none",
    ),
    # Marks of the parts that do not zoom. A ring on the edge of a card has the card as its
    # ground, because the card is the lightest ground in the light scheme and in the dark scheme.
    (
        "focus ring of a row of the Sequences diagram",
        "focus",
        "map",
        MARK,
        ".board .qrow:focus-visible rect{fill:var(--tint);stroke:var(--focus)",
    ),
    (
        "focus ring of a state",
        "focus",
        "card",
        MARK,
        ".snode:focus-visible rect{stroke:var(--focus)",
    ),
    ("focused transition", "focus", "map", MARK, ".tedge.kf path.wire{stroke:var(--focus)"),
    (
        "arrowhead of a focused transition",
        "focus",
        "map",
        MARK,
        ".tedge.kf polygon{fill:var(--focus)}",
    ),
    (
        "focus ring of a card of the Focus view",
        "focus",
        "card",
        MARK,
        ".fcard:focus-visible rect{stroke:var(--focus)",
    ),
    (
        "focused line of the Focus view",
        "focus",
        "map",
        MARK,
        ".fedge.kf path.wire{stroke:var(--focus)",
    ),
    (
        "outline of a lit cell of the History view",
        "focus",
        "map",
        MARK,
        ".hcell:hover rect,.hcell.lit rect{stroke:var(--focus)",
    ),
    (
        "focus ring of a cell of the History view",
        "focus",
        "map",
        MARK,
        ".hcell:focus-visible rect{stroke:var(--focus)",
    ),
    (
        "focus ring of a row of the History view",
        "focus",
        "map",
        MARK,
        ".hrow:focus-visible rect{stroke:var(--focus)",
    ),
    ("cell of the History view", "ink", "map", MARK, ".hcell rect{fill:var(--ink)"),
    # Texts of the HTML parts.
    ("question of the headline", "ink", "map", TEXT, "body{background:var(--map);color:var(--ink)"),
    (
        "path and layer of the headline",
        "ink-3",
        "map",
        TEXT,
        "text-transform:uppercase;color:var(--ink-3)",
    ),
    ("counts of the headline", "ink-3", "map", TEXT, "margin-top:8px;color:var(--ink-3)"),
    ("tab of a layer", "ink-3", "surface", TEXT, "padding:0 11px;color:var(--ink-3)"),
    ("view button", "ink-3", "map", TEXT, "border-radius:7px;color:var(--ink-3)"),
    ("note and key", "ink-3", "map", TEXT, "font-size:11.5px;color:var(--ink-3)"),
    ("reading line", "ink-2", "surface", TEXT, ".say span{color:var(--ink-2)"),
    ("tool of the header", "ink-3", "surface", TEXT, "border-radius:8px;color:var(--ink-3)"),
    ("Find button", "ink-3", "map", TEXT, "background:var(--map);color:var(--ink-3)"),
    ("tool of the phone menu", "ink-2", "surface", TEXT, "padding:0 10px;color:var(--ink-2)"),
    (
        "text of a Find row",
        "ink-3",
        "surface",
        TEXT,
        ".pal__s{font:12px/16px var(--fs);color:var(--ink-3)",
    ),
    (
        "name of a Find row",
        "ink",
        "surface",
        TEXT,
        ".pal__t{font:13px/18px var(--fs);color:var(--ink)",
    ),
    (
        "text of the button that opens a map",
        "surface",
        "ink",
        TEXT,
        "background:var(--ink);color:var(--surface);font:600 12.5px/1 var(--fs)",
    ),
    (
        "text of the next step button",
        "surface",
        "ink",
        TEXT,
        ".stepper button.go{background:var(--ink);color:var(--surface)",
    ),
    (
        "keyboard sheet",
        "ink-2",
        "surface",
        TEXT,
        ".keys__note{margin:0;font:13px/19px var(--fs);color:var(--ink-2)",
    ),
)

# Marks below their floor: (what, token, ground, floor, code).
BELOW_FLOOR: tuple[tuple[str, str, str, float, str], ...] = (
    ("wire of a line at rest", "wire", "map", MARK, ": C['--wire']"),
    ("outline of a card", "line-2", "map", MARK, "C['--line-2'], alpha * t * (1 - 0.3 * qv)"),
    ("ring of the number of a region", "line-2", "surface", MARK, "rings.rect(C['--line-2']"),
    ("border of a container", "line", "map", MARK, "lines.rect(C['--line'], alpha"),
    (
        "mark of the brand in the header",
        "brand",
        "surface",
        MARK,
        ".brand .mark{fill:var(--brand)}",
    ),
    (
        "halo of the selected card",
        "halo",
        "map",
        MARK,
        "ctx.strokeStyle = C['--halo']; ctx.lineWidth = 5;",
    ),
    ("dot of a new module in the History view", "brand", "map", MARK, ".hborn{fill:var(--brand)"),
    (
        "bar of a column total in the History view",
        "line-2",
        "map",
        MARK,
        ".hbar{fill:var(--line-2)}",
    ),
)

# For each row below its floor, a row of `MARKS` that gives the same item to the reader.
ALSO = {
    "wire of a line at rest": "dot and arrowhead at rest",
    "outline of a card": "card name",
    "ring of the number of a region": "name of a region",
    "border of a container": "name of a container",
    "mark of the brand in the header": "question of the headline",
    "halo of the selected card": "outline of the selected card",
    "dot of a new module in the History view": "reading line",
    "bar of a column total in the History view": "reading line",
}


def _tokens(text: str) -> dict[str, str]:
    return dict(re.findall(r"--([\w-]+):(#[0-9A-Fa-f]{6}|rgba\([^)]*\))", text))


def _ratio(table: dict[str, str], token: str, ground: str) -> float:
    """Give the contrast of the token on the ground. A token with an alpha (rgba) is
    first put on the ground, as the screen shows it."""
    color = table[token]
    if color.startswith("rgba("):
        *rgb, alpha = (float(v) for v in color[5:-1].split(","))
        under = [int(table[ground][i : i + 2], 16) for i in (1, 3, 5)]
        mixed = [round(alpha * c + (1 - alpha) * g) for c, g in zip(rgb, under, strict=True)]
        color = "#" + "".join(f"{v:02X}" for v in mixed)
    return contrast(color, table[ground])


SCHEMES = {"light": _tokens(atlas_css.LIGHT), "dark": _tokens(atlas_css.DARK)}


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("row", MARKS, ids=[row[0] for row in MARKS])
def test_each_text_and_mark_clears_its_contrast_floor(
    scheme: str, row: tuple[str, str, str, float, str]
) -> None:
    """Acceptance 1."""
    what, token, ground, floor, code = row
    table = SCHEMES[scheme]
    ratio = _ratio(table, token, ground)
    assert ratio >= floor, (what, scheme, round(ratio, 2))
    assert code in CODE, (what, code)


def test_each_mark_below_its_floor_is_a_decision_with_a_readable_partner() -> None:
    """Acceptance 2."""
    names = {row[0] for row in MARKS}
    for what, token, ground, floor, code in BELOW_FLOOR:
        ratios = [_ratio(t, token, ground) for t in SCHEMES.values()]
        assert min(ratios) < floor, what
        assert code in CODE, (what, code)
        assert ALSO[what] in names, what
