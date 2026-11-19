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

After the third review of stage 8 (2026-11-19), written before the run: the test left out
each text and mark that the page draws at a reduced alpha, because a ratio used only the
token on its ground. Acceptance values:

3. Each text and mark that the page draws at a reduced alpha in a state at rest has a row in
   `FAINT` or in `FAINT_BELOW`, and the ratio of the row includes that alpha. The states at
   rest are: a later step of a sequence, a busy layer, a light on the map (the other cards
   and lines go back), a quiet card, the rows of the Sequences diagram after the current
   row, a step button that is not available, the thin lines and the lines that go back in
   the Focus view, the transitions and states that go back in the States view, and a cell of
   the History view with few lines. A fade while the camera moves or while the view changes
   is not a state at rest, and has no row.
4. The alpha of a row comes from the code of the page (`_number`), thus a change of the
   alpha changes the ratio. A row with `under` is a faded part with its own ground, for
   example the text of a card that goes back: the ground is the card at that alpha on the
   map. The test uses the lower ratio of the two orders of painting (the canvas paints the
   ground and the text one after the other, and SVG paints a group at one opacity).
5. Each row of `FAINT` has a ratio of its floor or more in the two schemes. Each row of
   `FAINT_BELOW` is below its floor in a scheme, and has an `ALSO` partner in `MARKS` or
   `FAINT`, as the rows of `BELOW_FLOOR` have. These are decisions for the maintainer: the
   specification says that later steps are faint and that the other cards and lines go
   back, and the design study gives the faint quiet cards and views.

Result of the first run, 2026-11-19: the dot and the arrowhead of a busy layer were 2.92 in
the light scheme, below 3.0, at the alpha 0.75. The specification says that they stay in a
busy layer. Thus the lowest alpha of the dot and the arrowhead is now 0.8 (3.20 light, 3.84
dark, `atlas_lines.py`). The other faint rows that are below their floor are in
`FAINT_BELOW`.
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
    # The partners at full alpha of the faint rows below.
    (
        "dot and arrowhead of an earlier step",
        "ink-2",
        "map",
        MARK,
        "g.fillStyle = st === 'was' ? C['--ink-2'] : C['--ink-3'];",
    ),
    (
        "label of the current row of the Sequences diagram",
        "ink",
        "map",
        TEXT,
        ".sedge.lit text{fill:var(--ink)}",
    ),
    (
        "number of an earlier row of the Sequences diagram",
        "ink-2",
        "map",
        TEXT,
        ".sedge .qbead text{font:600 10.5px/1 var(--fm);fill:var(--ink-2)",
    ),
    (
        "ring of the number of a row of the Sequences diagram",
        "ink-3",
        "map",
        MARK,
        ".qbead circle{fill:var(--map);stroke:var(--ink-3)",
    ),
    (
        "line of an earlier row of the Sequences diagram",
        "ink-2",
        "map",
        MARK,
        ".sedge.done path.wire{stroke:var(--ink-2)",
    ),
    (
        "arrowhead of an earlier row of the Sequences diagram",
        "ink-2",
        "map",
        MARK,
        ".sedge.done polygon{fill:var(--ink-2)}",
    ),
    (
        "label of a step button",
        "ink-2",
        "surface",
        TEXT,
        "border:1px solid var(--line-2);color:var(--ink-2);font-weight:500",
    ),
    (
        "arrowhead of a line of the Focus view",
        "ink-3",
        "map",
        MARK,
        ".fedge polygon{fill:var(--ink-3)",
    ),
    (
        "label of a transition",
        "ink-2",
        "map",
        TEXT,
        ".tedge text{font:500 12px/1 var(--fs);fill:var(--ink-2)",
    ),
    ("arrowhead of a transition", "ink-3", "map", MARK, ".tedge polygon{fill:var(--ink-3)"),
    (
        "name of a state",
        "ink",
        "card",
        TEXT,
        ".snode .nm{font:600 15px/1 var(--fs);letter-spacing:-.01em;fill:var(--ink)",
    ),
    (
        "symbol of a state",
        "ink-3",
        "card",
        TEXT,
        ".snode .sy{font:400 10.5px/1 var(--fm);fill:var(--ink-3)",
    ),
    (
        "outline of a state",
        "ink-3",
        "map",
        MARK,
        ".snode rect{fill:var(--card);stroke:var(--ink-3)",
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


def _number(pattern: str) -> float:
    """Give the number that the pattern finds in the code of the page."""
    found = re.search(pattern, CODE)
    assert found, pattern
    return float(found.group(1))


# The alphas of the faint states, from the code of the page.
LATER = _number(r"LATER_A = ([\d.]+)")
REST = _number(r"list\.length / 56, ([\d.]+), 1\)")
ENDS = _number(r"list\.length / 160, ([\d.]+), 1\)")
BACK_LINE = 1 - _number(r"!lit\.flows\[i\] \? 1 - ([\d.]+) \* DIM")
BACK_CARD = 1 - _number(r"!lit\.cards\[c\.id\] \? 1 - ([\d.]+) \* DIM")
QUIET_NAME = 1 - _number(r"t \* \(1 - ([\d.]+) \* qv\), qv > 0\.5")
QUIET_KIND = 1 - _number(r"t \* \(1 - ([\d.]+) \* qv\), 0\.09")
QUIET_LINE = 1 - _number(r"C\['--line-2'\], alpha \* t \* \(1 - ([\d.]+) \* qv\)")
SEQ_LATER = _number(r"\.stepping \.sedge:not\(\.lit\):not\(\.done\)\{opacity:([\d.]+)\}")
OFF = _number(r"\.stepper button:disabled\{opacity:([\d.]+)")
THIN = _number(r"\.fedge\.thin path\.wire\{stroke-opacity:([\d.]+)")
FOCUS_BACK = _number(r"\.ffocus \.fedge:not\(\.lit\)\{opacity:([\d.]+)\}")
STATE_BACK = _number(r"\.sfocus \.snode:not\(\.lit\)\{opacity:([\d.]+)\}")
# A cell of the History view has the alpha sqrt(lines / largest lines). The example is a
# cell of one line where the largest cell has ten lines.
CELL = (1 / 10) ** 0.5

# Faint rows: (what, token, ground, floor, code, alpha, under). With `under`, the ground is
# also faded: it is the ground at the alpha on `under`.
Faint = tuple[str, str, str, float, str, float, str]
LATER_ENDS = "g.globalAlpha = alpha * L.ends * (st === 'later' ? LATER_A : 1)"
LATER_LINE = "g.globalAlpha = rest * backLine(lit, e.f.i) * (st === 'later' ? LATER_A : 1)"
CARD_BACK = "alpha *= backCard(lit, c);"
MARK_BACK = "var al = alpha * backCard(lit, c)"
SEQ_BACK = ".stepping .sedge:not(.lit):not(.done){opacity:"
FOCUS_FADE = ".ffocus .fedge:not(.lit){opacity:"
STATE_FADE = ".sfocus .tedge:not(.lit),.sfocus .snode:not(.lit){opacity:"

FAINT: tuple[Faint, ...] = (
    (
        "dot and arrowhead in a busy layer",
        "ink-3",
        "map",
        MARK,
        "out.ends = clamp(1.25 - list.length / 160",
        ENDS,
        "",
    ),
)

FAINT_BELOW: tuple[Faint, ...] = (
    # A later step of a sequence on the map.
    ("label of a later step", "ink-2", "map", TEXT, "C['--ink-2'], la, 500", LATER, ""),
    ("dot and arrowhead of a later step", "ink-3", "map", MARK, LATER_ENDS, ENDS * LATER, ""),
    ("wire of a later step", "wire", "map", MARK, LATER_LINE, REST * LATER, ""),
    # A busy layer.
    ("wire of a line in a busy layer", "wire", "map", MARK, "out.rest = clamp(1.25", REST, ""),
    # A light on the map: the other cards and lines go back.
    ("name of a card that goes back", "ink", "card", TEXT, CARD_BACK, BACK_CARD, "map"),
    ("name of an actor that goes back", "ink", "map", TEXT, CARD_BACK, BACK_CARD, ""),
    ("kind tag of a card that goes back", "ink-3", "card", TEXT, CARD_BACK, BACK_CARD, "map"),
    ("short name of a card that goes back", "ink-3", "card", TEXT, CARD_BACK, BACK_CARD, "map"),
    (
        "name of a quiet card that goes back",
        "ink-3",
        "map",
        TEXT,
        CARD_BACK,
        BACK_CARD * QUIET_NAME,
        "",
    ),
    (
        "kind tag of a quiet card that goes back",
        "ink-3",
        "map",
        TEXT,
        CARD_BACK,
        BACK_CARD * QUIET_KIND,
        "",
    ),
    ("outline of a card that goes back", "line-2", "map", MARK, CARD_BACK, BACK_CARD, ""),
    (
        "wire of a line that goes back",
        "wire",
        "map",
        MARK,
        "g.globalAlpha = rest * backLine(lit, e.f.i)",
        REST * BACK_LINE,
        "",
    ),
    (
        "dot and arrowhead of a line that goes back",
        "ink-3",
        "map",
        MARK,
        "g.globalAlpha = alpha * L.ends * (back ? 1 - 0.78 * DIM : 1);",
        ENDS * BACK_LINE,
        "",
    ),
    ("ring of a change on a card that goes back", "change", "map", MARK, MARK_BACK, BACK_CARD, ""),
    ("tag of a change on a card that goes back", "change", "map", TEXT, MARK_BACK, BACK_CARD, ""),
    (
        "ring of an open boundary line on a card that goes back",
        "ink-2",
        "map",
        MARK,
        MARK_BACK,
        BACK_CARD,
        "",
    ),
    (
        "tag of an open boundary line on a card that goes back",
        "ink-2",
        "map",
        TEXT,
        MARK_BACK,
        BACK_CARD,
        "",
    ),
    (
        "lost flow of a change that goes back",
        "change",
        "map",
        MARK,
        "ctx.globalAlpha = alpha * backLine(lit, e.f.i); ctx.strokeStyle = C['--change']",
        BACK_LINE,
        "",
    ),
    # A quiet card: it has no flow in the layer, and no fill.
    ("name of a quiet card", "ink-3", "map", TEXT, "t * (1 - 0.4 * qv), qv > 0.5", QUIET_NAME, ""),
    ("kind tag of a quiet card", "ink-3", "map", TEXT, "t * (1 - 0.5 * qv), 0.09", QUIET_KIND, ""),
    (
        "outline of a quiet card",
        "line-2",
        "map",
        MARK,
        "C['--line-2'], alpha * t * (1 - 0.3 * qv)",
        QUIET_LINE,
        "",
    ),
    # The rows of the Sequences diagram after the current row.
    (
        "label of a later row of the Sequences diagram",
        "ink-2",
        "map",
        TEXT,
        SEQ_BACK,
        SEQ_LATER,
        "",
    ),
    (
        "number of a later row of the Sequences diagram",
        "ink-2",
        "map",
        TEXT,
        SEQ_BACK,
        SEQ_LATER,
        "",
    ),
    (
        "ring of the number of a later row of the Sequences diagram",
        "ink-3",
        "map",
        MARK,
        SEQ_BACK,
        SEQ_LATER,
        "",
    ),
    (
        "arrowhead of a later row of the Sequences diagram",
        "ink-3",
        "map",
        MARK,
        SEQ_BACK,
        SEQ_LATER,
        "",
    ),
    ("line of a later row of the Sequences diagram", "wire", "map", MARK, SEQ_BACK, SEQ_LATER, ""),
    # A step button that is not available. WCAG 1.4.3 does not apply to a control that is
    # not available, but the page draws it, thus it has a row.
    (
        "label of a step button that is not available",
        "ink-2",
        "surface",
        TEXT,
        ".stepper button:disabled{opacity:",
        OFF,
        "",
    ),
    (
        "label of the next step button that is not available",
        "surface",
        "ink",
        TEXT,
        ".stepper button:disabled{opacity:",
        OFF,
        "surface",
    ),
    # The Focus view.
    (
        "thin line of the Focus view",
        "wire",
        "map",
        MARK,
        ".fedge.thin path.wire{stroke-opacity:",
        THIN,
        "",
    ),
    ("line of the Focus view that goes back", "wire", "map", MARK, FOCUS_FADE, FOCUS_BACK, ""),
    (
        "thin line of the Focus view that goes back",
        "wire",
        "map",
        MARK,
        FOCUS_FADE,
        THIN * FOCUS_BACK,
        "",
    ),
    (
        "arrowhead of a line of the Focus view that goes back",
        "ink-3",
        "map",
        MARK,
        FOCUS_FADE,
        FOCUS_BACK,
        "",
    ),
    # The States view: the transitions and the states that go back.
    ("label of a transition that goes back", "ink-2", "map", TEXT, STATE_FADE, STATE_BACK, ""),
    ("wire of a transition that goes back", "wire", "map", MARK, STATE_FADE, STATE_BACK, ""),
    ("arrowhead of a transition that goes back", "ink-3", "map", MARK, STATE_FADE, STATE_BACK, ""),
    ("name of a state that goes back", "ink", "card", TEXT, STATE_FADE, STATE_BACK, "map"),
    ("symbol of a state that goes back", "ink-3", "card", TEXT, STATE_FADE, STATE_BACK, "map"),
    ("outline of a state that goes back", "ink-3", "map", MARK, STATE_FADE, STATE_BACK, ""),
    # The History view.
    (
        "cell of few lines in the History view",
        "ink",
        "map",
        MARK,
        "Math.sqrt(x[1] / max)",
        CELL,
        "",
    ),
)

# For each faint row below its floor, a row of `MARKS` or `FAINT` for the same item. A later
# step, a card or a line that goes back, and a quiet card show at full alpha when the reader
# goes to that step, takes the light away, or points at the card.
ALSO_FAINT = {
    "label of a later step": "lit label",
    "dot and arrowhead of a later step": "dot and arrowhead of an earlier step",
    "wire of a later step": "line of an earlier step",
    "wire of a line in a busy layer": "dot and arrowhead in a busy layer",
    "name of a card that goes back": "card name",
    "name of an actor that goes back": "actor name",
    "kind tag of a card that goes back": "kind tag of a card",
    "short name of a card that goes back": "short name of a card",
    "name of a quiet card that goes back": "card name",
    "kind tag of a quiet card that goes back": "kind tag of a card",
    "outline of a card that goes back": "card name",
    "wire of a line that goes back": "dot and arrowhead at rest",
    "dot and arrowhead of a line that goes back": "dot and arrowhead at rest",
    "ring of a change on a card that goes back": "ring of a change",
    "tag of a change on a card that goes back": "tag of a change",
    "ring of an open boundary line on a card that goes back": "ring of an open boundary line",
    "tag of an open boundary line on a card that goes back": "tag of an open boundary line",
    "lost flow of a change that goes back": "lost flow of a change",
    "name of a quiet card": "card name",
    "kind tag of a quiet card": "kind tag of a card",
    "outline of a quiet card": "card name",
    "label of a later row of the Sequences diagram": "label of the current row of the Sequences diagram",
    "number of a later row of the Sequences diagram": "number of an earlier row of the Sequences diagram",
    "ring of the number of a later row of the Sequences diagram": (
        "ring of the number of a row of the Sequences diagram"
    ),
    "arrowhead of a later row of the Sequences diagram": (
        "arrowhead of an earlier row of the Sequences diagram"
    ),
    "line of a later row of the Sequences diagram": "line of an earlier row of the Sequences diagram",
    "label of a step button that is not available": "label of a step button",
    "label of the next step button that is not available": "text of the next step button",
    "thin line of the Focus view": "arrowhead of a line of the Focus view",
    "line of the Focus view that goes back": "arrowhead of a line of the Focus view",
    "thin line of the Focus view that goes back": "arrowhead of a line of the Focus view",
    "arrowhead of a line of the Focus view that goes back": "arrowhead of a line of the Focus view",
    "label of a transition that goes back": "label of a transition",
    "wire of a transition that goes back": "arrowhead of a transition",
    "arrowhead of a transition that goes back": "arrowhead of a transition",
    "name of a state that goes back": "name of a state",
    "symbol of a state that goes back": "symbol of a state",
    "outline of a state that goes back": "outline of a state",
    "cell of few lines in the History view": "reading line",
}


def _tokens(text: str) -> dict[str, str]:
    return dict(re.findall(r"--([\w-]+):(#[0-9A-Fa-f]{6}|rgba\([^)]*\))", text))


def _rgb(table: dict[str, str], token: str, ground: str) -> list[float]:
    """Give the color of the token. A token with an alpha (rgba) is first put on the ground."""
    color = table[token]
    if color.startswith("rgba("):
        *rgb, alpha = (float(v) for v in color[5:-1].split(","))
        under = _rgb(table, ground, ground)
        return [alpha * c + (1 - alpha) * g for c, g in zip(rgb, under, strict=True)]
    return [float(int(color[i : i + 2], 16)) for i in (1, 3, 5)]


def _over(top: list[float], below: list[float], alpha: float) -> list[float]:
    return [alpha * c + (1 - alpha) * g for c, g in zip(top, below, strict=True)]


def _hex(rgb: list[float]) -> str:
    return "#" + "".join(f"{round(v):02X}" for v in rgb)


def _ratio(
    table: dict[str, str], token: str, ground: str, alpha: float = 1.0, under: str = ""
) -> float:
    """Give the contrast of the token at the alpha on the ground, as the screen shows it.
    With `under`, the ground is also at the alpha, on `under`. Then the ratio is the lower
    of the two orders of painting: one after the other (the canvas), and as one group at
    the alpha (SVG)."""
    top = _rgb(table, token, ground)
    if not under:
        below = _rgb(table, ground, ground)
        return contrast(_hex(_over(top, below, alpha)), _hex(below))
    base = _rgb(table, under, under)
    below = _over(_rgb(table, ground, under), base, alpha)
    each = contrast(_hex(_over(top, below, alpha)), _hex(below))
    group = contrast(_hex(_over(top, base, alpha)), _hex(below))
    return min(each, group)


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


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("row", FAINT, ids=[row[0] for row in FAINT])
def test_each_faint_text_and_mark_with_its_alpha_clears_its_floor(scheme: str, row: Faint) -> None:
    """Acceptance 3, 4 and 5."""
    what, token, ground, floor, code, alpha, under = row
    ratio = _ratio(SCHEMES[scheme], token, ground, alpha, under)
    assert ratio >= floor, (what, scheme, round(ratio, 2))
    assert code in CODE, (what, code)


def test_each_faint_mark_below_its_floor_is_a_decision_with_a_readable_partner() -> None:
    """Acceptance 3, 4 and 5."""
    names = {row[0] for row in MARKS} | {row[0] for row in FAINT}
    for what, token, ground, floor, code, alpha, under in FAINT_BELOW:
        assert 0 < alpha < 1, what
        ratios = [_ratio(t, token, ground, alpha, under) for t in SCHEMES.values()]
        assert min(ratios) < floor, (what, [round(r, 2) for r in ratios])
        assert code in CODE, (what, code)
        assert ALSO_FAINT[what] in names, what
    assert set(ALSO_FAINT) == {row[0] for row in FAINT_BELOW}
