"""The canvas page: all maps of a map tree on one canvas (docs/design/nested-canvas.md).

With `[render] canvas = true` (`config_render`), `render_pages` uses `pages`: the canvas
page for the top map and a small page for each nested map. The small page goes to the top
page with the ID of its map in the URL hash, for example `../index.html#Gateway`. Thus a
link to a nested page still opens that map.

The canvas page holds the canvas data (`canvas_data`) one time, in a script element of
the type application/json, and the renderer script (`page_canvas`). The page CSP
(`page_csp`) has the digest of each script element and style element. The page uses
the theme tokens of the map page. Thus the light and the dark schemes both apply.

The page also has an empty list of the tree and a live region (`page_canvas_tree`). The
script writes the list from the canvas data after the first frame. The canvas, its help
text, the list and the live region are in one `main` element. Thus all text of the page is
in a landmark.

In front of `main`, the page has one `header` element over the top of the canvas
(`canvas_header`): the views, the layers and the Find button. The view parts of the
renderer (docs/design/nested-canvas.md, step 4) add their parts to the page in `SLOTS`.
"""

from __future__ import annotations

import html as html_text
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from systemap import (
    canvas_data,
    canvas_header,
    nest,
    page,
    page_canvas_changes,
    page_canvas_find,
    page_canvas_sequences,
    page_csp,
    page_font,
)
from systemap import theme as theme_mod
from systemap.config import Config
from systemap.model import all_layers
from systemap.page_canvas import CSS, SCRIPT
from systemap.page_canvas_tree import HTML as TREE_HTML


def pages(
    cfg: Config,
    tree: nest.Tree,
    facts: dict[str, Any],
    changes: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[tuple[nest.Map, str]]:
    """Give each map of the tree with its page: the canvas page for the top map, and the
    small page that goes to it for each nested map.

    `changes` gives the change data of each map by map ID (`change.for_page`)."""
    top = build(tree_theme(cfg, tree), canvas_data.build(cfg, tree, facts, changes=changes))
    return [(m, redirect(m) if m.id else top) for m in tree.maps]


def tree_theme(cfg: Config, tree: nest.Tree) -> dict[str, Any]:
    """Give the theme of the canvas page: one color for each layer of each map of the tree.

    The layers of the top map come first. Thus they have the colors of the top page."""
    layers = {layer.id: layer for m in tree.maps for layer in all_layers(m.model, m.meaning)}
    return nest.theme_of(cfg, layers.values())


# The parts that the view parts add to the page, each a text: `css` goes after the CSS of
# the page, `head` into the header before the Find button, `main` into `main` after the list
# of the tree, and `after` after `main` (for example a dialog). Each view part adds its text
# in one line for each slot.
SLOTS: dict[str, tuple[str, ...]] = {
    "css": (page_canvas_changes.CSS, page_canvas_sequences.CSS, page_canvas_find.CSS),
    "head": (page_canvas_sequences.HTML,),
    "main": (),
    "after": (page_canvas_find.HTML,),
}


def _slot(name: str) -> str:
    return "".join(SLOTS[name])


def build(t: dict[str, Any], data: Mapping[str, Any]) -> str:
    """Give the canvas page of the canvas data `data`, with the colors of the theme `t`."""
    name = str(data.get("name", ""))
    body = canvas_data.text(data).replace("<", "\\u003c")
    out = (
        page.head_start(f"{name} system map", t)
        + "<style>"
        + page_font.FACE
        + theme_mod.root_css(t)
        + CSS
        + canvas_header.CSS
        + _slot("css")
        + "</style></head><body>"
        + canvas_header.html_of(data, _slot("head"))
        + "<main>"
        + '<canvas id="canvas" tabindex="0" role="img" aria-describedby="canvas-help" '
        + f'aria-label="System map: {page.esc(name)}"></canvas>'
        + '<p id="canvas-help" class="sr-only">'
        + "The wheel and a pinch zoom the camera. A drag moves the map. "
        "A double-click on a card goes into the card. "
        "Tab and Shift+Tab move the keyboard focus through the cards of the current map. "
        "Enter on a card that opens a map goes into that map. "
        "Enter on a different card selects it. Esc goes out one level. "
        "On a touch screen, a tap on a card selects the card. "
        "A second tap on a card that opens a map goes into that map. "
        "The arrow keys move the map. The keys + and - zoom. "
        "F fits the current map. The list after the canvas gives the maps, the cards "
        "and the flows. Each link in the list moves the camera to its item.</p>"
        + page_canvas_changes.empty_html(data)
        + TREE_HTML
        + _slot("main")
        + "</main>"
        + _slot("after")
        + '<script type="application/json" id="canvas-data">'
        + body
        + "</script>\n<script>"
        + SCRIPT
        + "</script></body></html>\n"
    )
    return page_csp.with_policy(out)


def target(m: nest.Map) -> str:
    """Give the URL of the top page with the hash of the map, relative to the page of `m`."""
    if not m.id:
        return "index.html"
    return "../" * (m.id.count("/") + 1) + "index.html#" + quote(m.id, safe="/")


def redirect(m: nest.Map) -> str:
    """Give the small page of a nested map. It goes to the top page with the map ID."""
    url = html_text.escape(target(m), quote=True)
    shown = html_text.escape(m.id)
    return page_csp.with_policy(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={url}">'
        f"<title>{shown}</title></head><body>"
        f'<p>The map {shown} is on the <a href="{url}">canvas page</a>.</p>'
        "</body></html>\n"
    )
