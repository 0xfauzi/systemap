"""The header of the canvas page: the views, the layers and the Find button.

The canvas page (`canvas_page`) puts one `header` element in front of its `main` element.
The header is over the top of the canvas. Its height is constant for a screen: 48 px, and
56 px on a touch screen, where each control is 44 x 44 px or more. The renderer keeps a top
band of that height free for the fit, the path and the top row of the portals (`HEAD_H` in
`page_canvas_view`).

The header holds these controls, from left to right:

- The name of the project, as the heading of the page.
- The views Map, Sequences and Changes, with the words of the linked page (`page._views`).
  Each view is a button with `aria-pressed`. They are views of the same canvas, not
  navigation (docs/design/nested-canvas.md, "Views"). The script hides the button of a
  view that no part of the renderer registers (`VIEWS` in `page_canvas_view`).
- The layer control: one button for each layer of the union of the layers of all maps,
  then All. The layers of the top map come first, in the order of `page.tab_layers`: System
  context first when actors have flows. Then the other layers come in tree order. The
  buttons are a toolbar: Tab goes to the pressed button, and the arrow keys move between
  the buttons. When the buttons do not fit in the header, the script shows a select in
  their place, as the linked page does on a phone.
- The Find button (`find-open`). It is hidden until the search part of the renderer wires
  its dialog and removes the `hidden` attribute.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from systemap.page import esc
from systemap.page_icons import icon

ALL_TITLE = "All flows of all layers"


def layers(data: Mapping[str, Any]) -> list[dict[str, str]]:
    """Give the union of the layers of all maps of the canvas data: `id`, `n` and `q`.

    The layers of the top map come first, in the order of the canvas data: the tab order of
    the linked page (`page.tab_layers`). Each other layer comes after them, in tree order. A
    layer that two maps have keeps the name and the question of the first map. The Find
    dialog lists the layers in the same order (`LAYER_OF`)."""
    out: dict[str, dict[str, str]] = {}
    for m in data.get("maps") or []:
        for lay in m.get("layers") or []:
            out.setdefault(lay["id"], {"id": lay["id"], "n": lay["n"], "q": lay.get("q", "")})
    return list(out.values())


def _views() -> str:
    return (
        '<nav class="cbar__views" aria-label="Views">'
        '<button type="button" data-view="map" aria-pressed="true">Map</button>'
        '<button type="button" data-view="sequences" aria-pressed="false">Sequences</button>'
        '<button type="button" data-view="changes" aria-pressed="false">Changes</button>'
        "</nav>"
    )


def _layers(found: list[dict[str, str]]) -> str:
    buttons = "".join(
        f'<button type="button" data-layer="{esc(lay["id"])}" aria-pressed="false" '
        f'tabindex="-1" title="{esc(lay["q"])}">{esc(lay["n"])}</button>'
        for lay in found
    )
    options = "".join(f'<option value="{esc(lay["id"])}">{esc(lay["n"])}</option>' for lay in found)
    return (
        '<div class="cbar__layers" role="toolbar" aria-label="Layer">'
        f"{buttons}"
        '<button type="button" data-layer="all" aria-pressed="true" tabindex="0" '
        f'title="{ALL_TITLE}">All</button></div>'
        '<div class="cbar__pick"><label for="canvas-layer">Layer</label>'
        f'<select id="canvas-layer">{options}<option value="all" selected>All</option>'
        "</select></div>"
    )


def _find() -> str:
    return (
        '<button type="button" class="cbar__find" id="find-open" aria-haspopup="dialog" '
        'aria-expanded="false" aria-keyshortcuts="Control+K Meta+K /" title="Find" hidden>'
        f'{icon("search")}<span class="cbar__find-label">Find</span>'
        '<kbd data-mod-key aria-hidden="true">Ctrl K</kbd></button>'
    )


def html_of(data: Mapping[str, Any], tools: str = "") -> str:
    """Give the header element of the canvas page of the canvas data `data`.

    `tools` is HTML of the view parts. It goes after the layer control."""
    name = esc(data.get("name", "") or "map")
    return (
        '<header class="cbar" id="canvas-head">'
        f'<h1 class="cbar__name">{name}</h1>'
        + _views()
        + _layers(layers(data))
        + tools
        + '<span class="cbar__space"></span>'
        + _find()
        + "</header>"
    )


# The header is over the canvas, so it has an opaque background. A link of the list of the
# tree with the keyboard focus is over the bars of the views (z-index 5). Thus the bar of a
# view, also with two rows on a phone, does not cover it. `data-fit` is set by the
# script: 1 when the layer buttons do not fit (the select shows), 2 when the name and the
# label of Find also do not fit (they go, and a screen reader still reads the name and the
# label of the select). `cview` is the fade of the bar of a view (the toolbar of the
# Sequences view, the bar of the Changes view and the text for a page without a revision
# comparison): 160 ms, and none with reduced motion. During the fade out, the bar has no
# visibility, so it has no keyboard focus and no screen reader reads it.
CSS = """
.cbar{position:fixed;left:0;right:0;top:0;z-index:4;box-sizing:border-box;height:48px;
display:flex;align-items:center;gap:12px;padding:0 16px;overflow:hidden;
border-bottom:1px solid var(--line);background:var(--surface);color:var(--ink);
font:13px/1 var(--fs)}
.cbar button,.cbar select{box-sizing:border-box;height:32px;min-width:32px;margin:0;
border:1px solid transparent;border-radius:6px;background:none;color:var(--ink-2);
font:inherit;cursor:pointer}
.cbar button:hover{color:var(--ink);background:var(--raised)}
.cbar button[aria-pressed="true"]{border-color:var(--line-2);background:var(--raised);
color:var(--ink);font-weight:500}
.cbar button:focus-visible,.cbar select:focus-visible{outline:2px solid var(--ink);
outline-offset:1px}
.cbar__name{flex:none;max-width:240px;margin:0;overflow:hidden;font:600 15px/1 var(--fs);
letter-spacing:-.02em;white-space:nowrap;text-overflow:ellipsis}
.cbar__views,.cbar__layers{display:flex;flex:none;gap:2px}
.cbar__views button{padding:0 12px}
.cbar__layers button{padding:0 9px;white-space:nowrap}
.cbar__layers{padding-left:12px;border-left:1px solid var(--line)}
.cbar__pick{display:none;flex:1 1 auto;align-items:center;gap:8px;min-width:0}
.cbar__pick label{color:var(--ink-3)}
.cbar__pick select{flex:1 1 auto;min-width:0;max-width:240px;padding:0 6px;
border-color:var(--line-2);background:var(--map);color:var(--ink)}
.cbar__space{flex:1 1 0;min-width:0}
.cbar .cbar__find{display:flex;flex:none;align-items:center;gap:8px;padding:0 8px;
border-color:var(--line-2);background:var(--map);color:var(--ink-2)}
.cbar__find[hidden]{display:none}
.cbar__find kbd{font:11px/16px var(--fm);color:var(--ink-3);border:1px solid var(--line-2);
border-radius:4px;padding:0 5px}
.cbar .icon{width:16px;height:16px;fill:currentColor}
.cbar[data-fit] .cbar__layers{display:none}
.cbar[data-fit] .cbar__pick{display:flex}
.cbar[data-fit="2"]{gap:6px;padding:0 8px}
.cbar[data-fit="2"] .cbar__name{position:absolute;width:1px;height:1px;overflow:hidden;
clip-path:inset(50%)}
.cbar[data-fit="2"] .cbar__views button{padding:0 8px}
.cbar[data-fit="2"] .cbar__pick label{position:absolute;width:1px;height:1px;
overflow:hidden;clip-path:inset(50%)}
.cbar[data-fit="2"] .cbar__find-label,
.cbar[data-fit="2"] .cbar__find kbd,.cbar[data-fit="2"] .cbar__space{display:none}
.cbar[data-fit="2"] .cbar__find{justify-content:center;padding:0}
.cbar[data-fit="2"] .cbar__pick select{max-width:none}
@media (pointer:coarse){.cbar{height:56px}
.cbar button,.cbar select{height:44px;min-width:44px}
.cbar .cbar__pick select{min-width:88px}}
.cview{visibility:hidden;opacity:0;transition:opacity .16s ease-out,visibility 0s linear .16s}
.cview.on{visibility:visible;opacity:1;transition:opacity .16s ease-out}
@media (prefers-reduced-motion:reduce){.cview,.cview.on{transition:none}}
:root[data-reduce-motion="true"] .cview{transition:none}
.tree a:focus{top:104px;z-index:5}
@media (pointer:coarse){.tree a:focus{top:120px}}
"""
