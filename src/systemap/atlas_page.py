"""The atlas page: all maps of a map tree on one canvas, with the look of docs/design/atlas.md.

`[render] page = "atlas"` selects this page (`config_render`). `render_pages` then uses
`pages`: the atlas page for the top map and a small page for each nested map
(`canvas_redirect`). The small page goes to the top page with the ID of its map in the URL
hash, as for the canvas page.

The page holds the page data (`atlas_data`: the canvas data object with the relation
sentence of each flow) one time, in a script element of the type application/json, and
the renderer script (`atlas_script`) without its comment lines and its indentation
(`page.compact`). The map draws on the canvas engine. The parts that do not zoom are HTML
(`atlas_header`). The page uses the embedded font (`page_font`) and loads no external
file. The page policy (`page_csp`) has the digest of each script element and style
element, and it permits no frame. The markup has no style attribute and no inline event
handler.

The page also has an empty list of the tree and a live region (`atlas_tree`). The script
writes the list from the data after the first frame. The details of a selected card and
the reading line come after the canvas (`atlas_details`), so that Tab goes from the last
item of the canvas to the details. The canvas, its help text, the details, the reading
line, the list, the live region and the headline are in one `main` element. The list of the
sequences, the step bar and the sequence diagram (`atlas_sequences`), and the list of the
state machines and the board of the States view (`atlas_states`), and the list of the
cards and the board of the Focus view (`atlas_focus`), come after the help text of the
canvas.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from systemap import (
    atlas_css,
    atlas_data,
    atlas_details,
    atlas_focus,
    atlas_header,
    atlas_sequences,
    atlas_states,
    atlas_tree,
    canvas_data,
    canvas_page,
    canvas_redirect,
    judgement_json,
    nest,
    page,
    page_csp,
    page_font,
    page_icons,
)
from systemap.atlas_script import SCRIPT
from systemap.config import Config

NAME = "atlas page"

HELP = (
    "Point at a card or a line to light its flows and read it in the line at the bottom. "
    "The wheel and a pinch zoom the camera. A drag moves the map. "
    "A click or a tap on a card selects it and opens its details. "
    "A double-click on a card with a small map goes into that map. "
    "Tab and Shift+Tab move the keyboard focus through the cards and the lines of the current map. "
    "Enter selects the focused card or keeps the focused line lit. "
    "Enter on the selected card that opens a map goes into that map. "
    "Esc closes the details, or goes out one level. "
    "The arrow keys move the map. The keys + and - zoom. F fits the current map. "
    "The list after the canvas gives the maps, the cards and the flows. "
    "Each link in the list moves the camera to its item. "
    "In the Sequences view, the left and right arrow keys go to the previous step and to the next step. "
    "In the States view, Tab and the arrow keys move the keyboard focus through the states and the transitions. "
    "Enter keeps the reading line of the focused item, and Esc removes it. "
    "In the Focus view, Tab moves the keyboard focus through the cards and the lines. "
    "The up and down arrow keys go to the card above or below. "
    "The left and right arrow keys go to the adjacent column. Home goes to the card in the middle. "
    "Enter on a card puts that card in the middle."
)

_SCRIPT = page.compact(SCRIPT)


def _has_flow(m: Mapping[str, Any], neighbours: frozenset[str] = frozenset()) -> bool:
    """True when the map data `m` has a flow between two different parts of the map. A part
    is a card that is not in `neighbours`. Then the Focus view has a card to show
    (`atlas_focus`)."""
    ids = {c.get("id") for c in m.get("cards", [])} - neighbours
    return any(
        f.get("s") != f.get("t") and f.get("s") in ids and f.get("t") in ids
        for f in m.get("flows", [])
    )


def _neighbours(maps: list[Mapping[str, Any]]) -> list[frozenset[str]]:
    """The neighbours of each map of the page data: the actors of a nested map that are cards
    of the map above (`upCard` in `atlas_lit`)."""
    above: dict[int, Mapping[str, Any]] = {}
    for m in maps:
        for c in m.get("cards", []):
            if isinstance(c.get("o"), int):
                above.setdefault(c["o"], m)
    out = []
    for i, m in enumerate(maps):
        up = {c.get("id") for c in above[i].get("cards", [])} if i in above else set()
        out.append(
            frozenset(
                c["id"] for c in m.get("cards", []) if c.get("k") == "actor" and c.get("id") in up
            )
        )
    return out


def _has_focus(maps: list[Mapping[str, Any]]) -> bool:
    """True when a map of the page data has the Focus view (`_has_flow`)."""
    return any(_has_flow(m, n) for m, n in zip(maps, _neighbours(maps), strict=True))


def pages(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    changes: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[tuple[nest.Map, str]]:
    """Give each map of the tree with its page: the atlas page for the top map, and the
    small page that goes to it for each nested map."""
    still = judgement_json.open_boundary(tree, facts, cfg)
    data = atlas_data.build(cfg, tree, facts, open_lines=still, changes=changes)
    top = build(canvas_page.tree_theme(cfg, tree), data)
    return [(m, canvas_redirect.page(m, NAME) if m.id else top) for m in tree.maps]


def build(t: dict[str, Any], data: Mapping[str, Any]) -> str:
    """Give the atlas page of the page data `data`. The theme `t` gives the schemes that
    the scheme script of the head knows (`page.head_start`)."""
    name = str(data.get("name", ""))
    body = canvas_data.text(data).replace("<", "\\u003c")
    out = (
        page.head_start(f"{name} system map", t)
        + "<style>"
        + page_font.FACE
        + atlas_css.CSS
        + page_icons.CSS
        + atlas_details.CSS
        + atlas_tree.CSS
        + atlas_sequences.CSS
        + atlas_sequences.BOARD_CSS
        + atlas_states.CSS
        + atlas_focus.CSS
        + "</style></head><body>"
        + atlas_header.header(
            name,
            any(m.get("sq") for m in data.get("maps", [])),
            any(m.get("sm") for m in data.get("maps", [])),
            _has_focus(data.get("maps", [])),
        )
        + "<main>"
        + '<canvas id="canvas" tabindex="0" role="img" aria-describedby="canvas-help" '
        + f'aria-label="System map: {page.esc(name)}"></canvas>'
        + f'<p id="canvas-help" class="sr-only">{HELP}</p>'
        + atlas_sequences.BOARD_HTML
        + atlas_sequences.HTML
        + atlas_states.HTML
        + atlas_focus.HTML
        + atlas_details.HTML
        + atlas_header.overlay()
        + atlas_tree.HTML
        + "</main>"
        + '<script type="application/json" id="atlas-data">'
        + body
        + "</script>\n<script>"
        + _SCRIPT
        + "</script></body></html>\n"
    )
    return page_csp.with_policy(out, frame=page_csp.NO_FRAME)
