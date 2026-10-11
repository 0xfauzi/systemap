"""The icons of the page controls: the header, the zoom group and the Find palette.

Each icon is an inline SVG on a 16 unit grid. The page draws each path with a
1.5 unit stroke in the text color, with round ends and round joins, and with no
fill. The page CSS gives these values to `svg.icon`. A small circle is a closed
path with the same stroke.
"""

from __future__ import annotations

PATHS: dict[str, str] = {
    "zoom-out": "M3.5 8h9",
    "zoom-in": "M3.5 8h9M8 3.5v9",
    # Fit: small corners around the content. Full screen: large corners.
    "fit": "M2.75 5.25v-1a1.5 1.5 0 0 1 1.5-1.5h1M10.75 2.75h1a1.5 1.5 0 0 1 1.5 1.5v1"
    "M13.25 10.75v1a1.5 1.5 0 0 1-1.5 1.5h-1M5.25 13.25h-1a1.5 1.5 0 0 1-1.5-1.5v-1"
    "M5.75 6.75h4.5v2.5h-4.5z",
    "full": "M2.75 6V2.75H6M10 2.75h3.25V6M13.25 10v3.25H10M6 13.25H2.75V10",
    "full-exit": "M6 2.75V6H2.75M10 2.75V6h3.25M13.25 10H10v3.25M2.75 10H6v3.25",
    "search": "M11.25 7a4.25 4.25 0 1 1-8.5 0 4.25 4.25 0 0 1 8.5 0zM10.25 10.25l3 3",
    "sun": "M8 1.75v1.25M8 13v1.25M1.75 8H3M13 8h1.25M3.58 3.58l.88.88M11.54 11.54l.88.88"
    "M3.58 12.42l.88-.88M11.54 4.46l.88-.88M10.5 8a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z",
    "moon": "M13.25 9.75A5.5 5.5 0 1 1 6.25 2.75a4.5 4.5 0 0 0 7 7z",
    "motion": "M2.25 8h3.5M3.25 5.25h2.5M3.25 10.75h2.5"
    "M13.75 8a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0z",
    "help": "M14.25 8a6.25 6.25 0 1 1-12.5 0 6.25 6.25 0 0 1 12.5 0zM6.25 6.4a1.75 1.75 0 1 1 "
    "2.55 1.55c-.45.25-.8.6-.8 1.1v.2M8 11.25v.05",
    "panel": "M3.75 2.75h8.5a1.5 1.5 0 0 1 1.5 1.5v7.5a1.5 1.5 0 0 1-1.5 1.5h-8.5a1.5 1.5 0 0 "
    "1-1.5-1.5v-7.5a1.5 1.5 0 0 1 1.5-1.5zM10 2.75v10.5",
    "map": "M2.75 4.25l3.5-1.5 3.5 1.5 3.5-1.5v9l-3.5 1.5-3.5-1.5-3.5 1.5zM6.25 2.75v9M9.75 4.25v9",
    "route": "M11 3.25H5.5V8h5v4.75H5M14.25 3.25a1.25 1.25 0 1 1-2.5 0 1.25 1.25 0 0 1 2.5 0z"
    "M4.25 12.75a1.25 1.25 0 1 1-2.5 0 1.25 1.25 0 0 1 2.5 0z",
    "change": "M5.25 2.75v5M2.75 5.25h5M8.25 11.25h5",
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
