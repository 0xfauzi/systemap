"""The HTML parts of the atlas page that do not zoom: the header, the headline and the controls.

The atlas page (`atlas_page`) puts these parts over its canvas. The renderer writes their
words with DOM functions (`atlas_view`): the tabs of the layers, the path, the name and
the question of the layer, the counts, the key and the readout of the zoom. The HTML here
has the empty elements and the fixed words only. It has no style attribute and no inline
event handler (docs/design/atlas.md, "Requirements of the product page").

- The header: the name of the project, the views and the tabs of the layers. The views
  have only Map in this stage. A view shows only when the map has data for it.
- The headline (`atlas-ask`): type on the ground, beside the map or above it.
- The zoom control: zoom out, the readout of the scale, zoom in, and Fit.
- The key of the kinds of lines, and a note with the inputs of the map.
"""

from __future__ import annotations

from systemap.page import esc

_MARK = (
    '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">'
    '<path d="M13 4.5H7.2a2.2 2.2 0 0 0 0 4.4h3.6a2.2 2.2 0 0 1 0 4.4H5" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="square"/>'
    '<rect class="mark" x="13.5" y="2" width="3" height="3"/></svg>'
)

_FIT = (
    '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">'
    '<path d="M1.5 5V1.5H5M9 1.5h3.5V5M12.5 9v3.5H9M5 12.5H1.5V9" fill="none" '
    'stroke="currentColor" stroke-width="1.4"/></svg>'
)

NOTE = (
    "Drag to move the map. Use the wheel or two fingers to zoom. "
    "Double-click a card with a small map in it to go into that map. Esc goes out."
)


def header(name: str) -> str:
    """Give the header of the page for the project `name`."""
    return (
        '<header class="bar" id="atlas-head">'
        f'<p class="brand">{_MARK}<span>{esc(name)}</span></p>'
        '<div class="views" role="group" aria-label="Views">'
        '<button type="button" data-mode="map" aria-pressed="true">Map</button></div>'
        '<nav class="tabs" id="atlas-tabs" role="tablist" aria-label="Layers"></nav>'
        "</header>"
    )


def overlay() -> str:
    """Give the headline, the zoom control, the key and the note."""
    return (
        '<div class="ask" id="atlas-ask"><div class="ask__k" id="atlas-ask-k"></div>'
        '<h1 class="ask__q" id="atlas-ask-q"></h1><div class="ask__n" id="atlas-ask-n"></div></div>'
        '<div class="zoom" role="group" aria-label="Zoom">'
        '<button type="button" id="atlas-zo" aria-label="Zoom out" title="Zoom out">−</button>'
        '<span id="atlas-zv">100%</span>'
        '<button type="button" id="atlas-zi" aria-label="Zoom in" title="Zoom in">+</button>'
        '<button type="button" id="atlas-zf" aria-label="Fit the map" title="Fit the map (F)">'
        f"{_FIT}</button></div>"
        '<div class="key" id="atlas-key" role="group" aria-label="Kinds of lines"></div>'
        f'<p class="note" id="atlas-note">{NOTE}</p>'
    )
