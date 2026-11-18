"""The `[render]` table of the configuration: the settings of the page output.

`render` and `refresh` write the canvas page (docs/design/nested-canvas.md) at the top
page, and a small page that goes to it at the page of each nested map. This is the
default, and `canvas = true` gives the same output.

`canvas = false` makes the commands write the linked pages, one page for each map, with
no change from the earlier releases. This setting is for one release only. The linked
pages get no new function. `render`, `refresh` and `live` then give the notice line
`NOTICE` (`render_pages.notice`), and the exit code does not change.

`page` selects the page (docs/design/atlas.md): "atlas" (`atlas_page`), "canvas" or
"linked". The default is "canvas". `page = "linked"` is the same as `canvas = false`. A
table with the two keys must give the same page with each key. Thus `canvas = false` with
`page = "atlas"` is a configuration error.

A ValueError gives the configuration error. The configuration reader changes it to a
ConfigError.
"""

from __future__ import annotations

from typing import Any

KEYS = frozenset({"canvas", "page"})
PAGES = ("atlas", "canvas", "linked")

NOTICE = (
    "notice: [render] canvas = false writes the linked pages. The next release removes "
    "the linked pages. Remove the setting to write the canvas page."
)


def canvas(raw: dict[str, Any], where: str) -> bool:
    """Read `[render] canvas`. Give true if the table or the key is not there."""
    table = raw.get("render", {})
    if not isinstance(table, dict):
        raise ValueError(f"{where}: render must be a table")
    bad = sorted(set(table) - KEYS)
    if bad:
        raise ValueError(f"{where}: render has an unknown key: {', '.join(bad)}")
    value = table.get("canvas", True)
    if not isinstance(value, bool):
        raise ValueError(f"{where}: render.canvas must be true or false")
    return value


def page(raw: dict[str, Any], where: str) -> str:
    """Read `[render] page`: "atlas", "canvas" or "linked".

    Without the key, `canvas = false` gives "linked", and else the page is "canvas"."""
    shown = canvas(raw, where)
    table = raw.get("render", {})
    value = table.get("page")
    if value is None:
        return "canvas" if shown else "linked"
    if value not in PAGES:
        names = ", ".join(f'"{name}"' for name in PAGES)
        raise ValueError(f"{where}: render.page must be one of {names}, not {value!r}")
    if "canvas" in table and shown != (value != "linked"):
        raise ValueError(
            f"{where}: render.canvas = {str(shown).lower()} does not agree with "
            f'render.page = "{value}". Remove render.canvas.'
        )
    return str(value)
