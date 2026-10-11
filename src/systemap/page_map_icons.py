"""The icons of the map controls: zoom out, zoom in and fit.

Each icon is an inline SVG on a 16 unit grid. The page draws each path with a
1.5 unit stroke in the text color, with round ends and round joins, and with no
fill. The page CSS gives these values to `svg.icon`. The icons use the rules of
the header icons, so the two sets can become one set.
"""

from __future__ import annotations

PATHS: dict[str, str] = {
    "zoom-out": "M3.5 8h9",
    "zoom-in": "M3.5 8h9M8 3.5v9",
    "fit": "M2.75 6V2.75H6M10 2.75h3.25V6M13.25 10v3.25H10M6 13.25H2.75V10",
    # The arrow of the sequence chooser button.
    "down": "M4.5 6.25 8 9.75l3.5-3.5",
}

CSS = (
    "svg.icon{width:16px;height:16px;flex:none;fill:none;stroke:currentColor;stroke-width:1.5;"
    "stroke-linecap:round;stroke-linejoin:round}"
)


def icon(name: str) -> str:
    """Give the inline SVG of one icon. A screen reader does not read it."""
    return (
        '<svg class="icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
        f'<path d="{PATHS[name]}"/></svg>'
    )
