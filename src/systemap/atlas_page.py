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
writes the list from the data after the first frame. The canvas, its help text, the list,
the live region and the headline are in one `main` element.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from systemap import (
    atlas_css,
    atlas_data,
    atlas_header,
    atlas_tree,
    canvas_data,
    canvas_page,
    canvas_redirect,
    judgement_json,
    nest,
    page,
    page_csp,
    page_font,
)
from systemap.atlas_script import SCRIPT
from systemap.config import Config

NAME = "atlas page"

HELP = (
    "The wheel and a pinch zoom the camera. A drag moves the map. "
    "A double-click or a tap on a card with a small map goes into that map. "
    "Tab and Shift+Tab move the keyboard focus through the cards of the current map. "
    "Enter on a card that opens a map goes into that map. Esc goes out one level. "
    "The arrow keys move the map. The keys + and - zoom. F fits the current map. "
    "The list after the canvas gives the maps, the cards and the flows. "
    "Each link in the list moves the camera to its item."
)

_SCRIPT = page.compact(SCRIPT)


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
        + atlas_tree.CSS
        + "</style></head><body>"
        + atlas_header.header(name)
        + "<main>"
        + '<canvas id="canvas" tabindex="0" role="img" aria-describedby="canvas-help" '
        + f'aria-label="System map: {page.esc(name)}"></canvas>'
        + f'<p id="canvas-help" class="sr-only">{HELP}</p>'
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
